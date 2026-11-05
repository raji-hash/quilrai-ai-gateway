
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import httpx

app = FastAPI(title="MCP Security Gateway")

DOWNSTREAM_URL = "http://127.0.0.1:8001/mcp"

# Demo tokens for the assessment
TOKENS = {
    "admin-token": "admin",
    "viewer-token": "viewer",
}


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "MCP Security Gateway",
    }


@app.post("/mcp")
async def handle_mcp_request(request: Request):
    payload = await request.json()
    request_id = payload.get("id")

    # Extract and validate the Bearer token
    authorization = request.headers.get("Authorization", "")
    parts = authorization.split()

    if len(parts) != 2 or parts[0].lower() != "bearer":
        return JSONResponse(
            status_code=401,
            content={
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32001,
                    "message": "Unauthorized: missing or invalid token",
                },
            },
        )

    token = parts[1]
    role = TOKENS.get(token)

    if role is None:
        return JSONResponse(
            status_code=401,
            content={
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32001,
                    "message": "Unauthorized: invalid token",
                },
            },
        )

    method = payload.get("method")

    # Check permissions for tool execution
    if method == "tools/call":
        params = payload.get("params", {})
        tool_name = params.get("name", "")

        if tool_name.startswith("admin_") and role != "admin":
            return JSONResponse(
                status_code=200,
                content={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32001,
                        "message": "Forbidden: admin role required",
                    },
                },
            )

    # Forward authorized requests to the downstream MCP server
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            DOWNSTREAM_URL,
            json=payload,
        )

    return JSONResponse(
        status_code=response.status_code,
        content=response.json(),
    )

