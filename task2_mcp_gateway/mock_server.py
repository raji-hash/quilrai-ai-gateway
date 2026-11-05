
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="Mock Downstream MCP Server")


@app.post("/mcp")
async def handle_mcp_request(request: Request):
    payload = await request.json()

    method = payload.get("method")
    request_id = payload.get("id")

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": [
                    {
                        "name": "get_customer_record",
                        "description": "Retrieve a customer record",
                    },
                    {
                        "name": "trigger_refund",
                        "description": "Create a refund request",
                    },
                    {
                        "name": "admin_reset_key",
                        "description": "Reset an API key",
                    },
                ]
            },
        }

    if method == "tools/call":
        params = payload.get("params", {})
        tool_name = params.get("name")

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "message": f"Mock server executed tool: {tool_name}"
            },
        }

    return JSONResponse(
        status_code=400,
        content={
            "jsonrpc": "2.0",
            "id": request_id,
            "error": {
                "code": -32601,
                "message": "Method not found",
            },
        },
    )
