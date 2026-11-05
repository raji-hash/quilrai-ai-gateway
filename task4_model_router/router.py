
import asyncio
import sqlite3
import time
from pathlib import Path

import httpx
from fastapi import FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


app = FastAPI(title="Quilr LLM Router")

DB_PATH = Path(__file__).with_name("usage.db")
TOKEN_LIMIT = 50_000
WINDOW_SECONDS = 60
PRIMARY_TIMEOUT = 3.0

TENANTS = {
    "tenant-a-key": "tenant-a",
    "tenant-b-key": "tenant-b",
}


# --------------------------------
# SQLite database
# --------------------------------

def get_connection():
    connection = sqlite3.connect(
        DB_PATH,
        timeout=10,
    )
    connection.execute("PRAGMA busy_timeout = 10000")
    return connection


def initialize_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                tokens INTEGER NOT NULL,
                timestamp REAL NOT NULL
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_tenant_timestamp
            ON token_usage (tenant_id, timestamp)
        """)

        connection.commit()


def record_usage(tenant_id: str, tokens: int):
    """Persist token usage in SQLite."""

    with get_connection() as connection:
        connection.execute(
            """
            INSERT INTO token_usage (tenant_id, tokens, timestamp)
            VALUES (?, ?, ?)
            """,
            (tenant_id, tokens, time.time()),
        )
        connection.commit()


def get_recent_usage(tenant_id: str) -> int:
    """Return token usage within the last 60 seconds."""

    cutoff = time.time() - WINDOW_SECONDS

    with get_connection() as connection:
        result = connection.execute(
            """
            SELECT COALESCE(SUM(tokens), 0)
            FROM token_usage
            WHERE tenant_id = ? AND timestamp > ?
            """,
            (tenant_id, cutoff),
        ).fetchone()

    return result[0]


initialize_database()


# --------------------------------
# SQLite-backed sliding window
# --------------------------------

class SlidingWindowRateLimiter:

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    def allow(self, tenant_id: str, tokens: int) -> bool:
        """
        Atomically check and reserve token capacity.

        BEGIN IMMEDIATE prevents concurrent requests from
        exceeding the tenant's token limit.
        """

        if tokens <= 0 or tokens > TOKEN_LIMIT:
            return False

        now = time.time()
        cutoff = now - WINDOW_SECONDS

        connection = sqlite3.connect(
            self.db_path,
            timeout=10,
        )

        try:
            connection.execute("PRAGMA busy_timeout = 10000")
            connection.execute("BEGIN IMMEDIATE")

            # Remove expired usage records.
            connection.execute(
                """
                DELETE FROM token_usage
                WHERE timestamp <= ?
                """,
                (cutoff,),
            )

            result = connection.execute(
                """
                SELECT COALESCE(SUM(tokens), 0)
                FROM token_usage
                WHERE tenant_id = ?
                AND timestamp > ?
                """,
                (tenant_id, cutoff),
            ).fetchone()

            current_usage = result[0]

            if current_usage + tokens > TOKEN_LIMIT:
                connection.rollback()
                return False

            # Reserve capacity before sending the model request.
            connection.execute(
                """
                INSERT INTO token_usage
                (tenant_id, tokens, timestamp)
                VALUES (?, ?, ?)
                """,
                (tenant_id, tokens, now),
            )

            connection.commit()
            return True

        except Exception:
            connection.rollback()
            raise

        finally:
            connection.close()


rate_limiter = SlidingWindowRateLimiter()


# --------------------------------
# Request model
# --------------------------------

class LLMRequest(BaseModel):
    prompt: str = Field(min_length=1)
    max_tokens: int = Field(gt=0, le=50_000)


# --------------------------------
# Simulated LLM providers
# --------------------------------

async def primary_model(prompt: str):
    """Simulated primary LLM provider."""

    await asyncio.sleep(0.1)

    return {
        "model": "primary",
        "response": f"Primary model response to: {prompt}",
    }


async def fallback_model(prompt: str):
    """Simulated fallback LLM provider."""

    await asyncio.sleep(0.1)

    return {
        "model": "fallback",
        "response": f"Fallback model response to: {prompt}",
    }


# --------------------------------
# Model routing and failover
# --------------------------------

async def route_request(prompt: str):

    try:
        return await asyncio.wait_for(
            primary_model(prompt),
            timeout=PRIMARY_TIMEOUT,
        )

    except (asyncio.TimeoutError, httpx.TimeoutException):
        return await fallback_model(prompt)

    except httpx.HTTPStatusError as error:

        if error.response.status_code == 429:
            return await fallback_model(prompt)

        raise


# --------------------------------
# API endpoints
# --------------------------------

@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/v1/chat/completions")
async def chat_completion(
    request: LLMRequest,
    authorization: str = Header(default=""),
):

    parts = authorization.split()

    if len(parts) != 2 or parts[0].lower() != "bearer":
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized"},
        )

    tenant_id = TENANTS.get(parts[1])

    if tenant_id is None:
        return JSONResponse(
            status_code=401,
            content={"error": "unauthorized"},
        )

    # Atomically check and reserve the tenant's token budget.
    try:
        allowed = rate_limiter.allow(
            tenant_id,
            request.max_tokens,
        )

    except sqlite3.Error:
        return JSONResponse(
            status_code=503,
            content={"error": "usage_service_unavailable"},
        )

    if not allowed:
        return JSONResponse(
            status_code=429,
            content={"error": "rate_limit_exceeded"},
        )

    try:
        result = await route_request(request.prompt)

        return {
            "tenant": tenant_id,
            "result": result,
        }

    except Exception:
        return JSONResponse(
            status_code=502,
            content={"error": "model_provider_unavailable"},
        )

