
import asyncio
import sqlite3
import tempfile
from pathlib import Path

import httpx

import task4_model_router.router as router


def create_test_database(path):
    connection = sqlite3.connect(path)
    try:
        connection.execute("""
            CREATE TABLE token_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tenant_id TEXT NOT NULL,
                tokens INTEGER NOT NULL,
                timestamp REAL NOT NULL
            )
        """)
        connection.commit()
    finally:
        connection.close()


def test_rate_limiter():
    with tempfile.TemporaryDirectory() as directory:
        db_path = Path(directory) / "test_usage.db"
        create_test_database(db_path)

        limiter = router.SlidingWindowRateLimiter(db_path)

        assert limiter.allow("tenant-a", 30000)
        assert not limiter.allow("tenant-a", 25000)
        assert limiter.allow("tenant-b", 40000)

    print("PASS: SQLite-backed per-tenant rate limiting")


def test_persistent_usage():
    with tempfile.TemporaryDirectory() as directory:
        db_path = Path(directory) / "test_usage.db"
        create_test_database(db_path)

        limiter = router.SlidingWindowRateLimiter(db_path)
        assert limiter.allow("tenant-a", 15000)

        new_limiter = router.SlidingWindowRateLimiter(db_path)
        assert not new_limiter.allow("tenant-a", 40000)

    print("PASS: Usage persists across limiter instances")


def test_concurrent_requests():
    with tempfile.TemporaryDirectory() as directory:
        db_path = Path(directory) / "test_usage.db"
        create_test_database(db_path)

        limiter = router.SlidingWindowRateLimiter(db_path)

        async def run_requests():
            return await asyncio.gather(
                asyncio.to_thread(limiter.allow, "tenant-a", 30000),
                asyncio.to_thread(limiter.allow, "tenant-a", 30000),
            )

        results = asyncio.run(run_requests())

        assert results.count(True) == 1
        assert results.count(False) == 1

    print("PASS: Concurrent requests respect token limit")


def test_primary_model():
    result = asyncio.run(router.route_request("Hello"))
    assert result["model"] == "primary"

    print("PASS: Primary model routing")


def test_timeout_failover():
    async def slow_primary(prompt):
        await asyncio.sleep(4)

    async def mock_fallback(prompt):
        return {
            "model": "fallback",
            "response": "Fallback response",
        }

    original_primary = router.primary_model
    original_fallback = router.fallback_model

    try:
        router.primary_model = slow_primary
        router.fallback_model = mock_fallback

        result = asyncio.run(router.route_request("Hello"))
        assert result["model"] == "fallback"

    finally:
        router.primary_model = original_primary
        router.fallback_model = original_fallback

    print("PASS: Timeout failover")


def test_429_failover():
    async def rate_limited_primary(prompt):
        request = httpx.Request(
            "POST", "https://primary.example.com"
        )
        response = httpx.Response(429, request=request)

        raise httpx.HTTPStatusError(
            "Rate limit exceeded",
            request=request,
            response=response,
        )

    async def mock_fallback(prompt):
        return {
            "model": "fallback",
            "response": "Fallback response",
        }

    original_primary = router.primary_model
    original_fallback = router.fallback_model

    try:
        router.primary_model = rate_limited_primary
        router.fallback_model = mock_fallback

        result = asyncio.run(router.route_request("Hello"))
        assert result["model"] == "fallback"

    finally:
        router.primary_model = original_primary
        router.fallback_model = original_fallback

    print("PASS: HTTP 429 failover")


if __name__ == "__main__":
    test_rate_limiter()
    test_persistent_usage()
    test_concurrent_requests()
    test_primary_model()
    test_timeout_failover()
    test_429_failover()

    print("\nAll router tests passed!")
