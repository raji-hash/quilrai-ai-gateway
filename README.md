
# Quilr AI Gateway

This project brings together four small components that demonstrate some of the important building blocks behind AI applications. I built each component to explore how MCP tools can be exposed securely, how sensitive information can be protected during streaming, and how LLM requests can be routed reliably.

The project is divided into four tasks.

## What I Built

### 1. Custom MCP Server

I created an MCP server with two tools:

- **get_customer_record** – Looks up a customer using their customer ID.
- **trigger_refund** – Creates a refund request with the supplied customer ID, amount, and reason.

I used Pydantic to validate incoming inputs and added checks to reject invalid customer IDs, negative refund amounts, and missing or invalid reasons. I also configured logging to use stderr so that the MCP communication over stdout stays clean.

### 2. MCP Security Gateway

For this part, I built an HTTP gateway that sits between clients and a downstream MCP server.

It uses Bearer tokens to identify whether a request comes from an admin or a viewer. Both roles can discover available tools, but only admins can execute tools whose names start with `admin_`.

The gateway forwards requests to the downstream server and returns a JSON-RPC error (`-32001`) when a user tries to access something they aren't authorized to use.

For local testing, I used two demo tokens:

- Admin: `admin-token`
- Viewer: `viewer-token`

### 3. Streaming PII Guardrail

I built a streaming proxy that checks text as it comes in and looks for sensitive information before passing it along.

It currently detects and redacts:

- Email addresses
- Social Security numbers (SSNs)
- Credit card numbers

One challenge here was handling sensitive information that arrives across multiple chunks instead of all at once. I added a buffering mechanism to handle those cases and a size limit to prevent the buffer from growing indefinitely.

The LLM stream is simulated for this implementation.

### 4. LLM Router

The final component is an LLM router that manages requests for different tenants.

It tracks token usage in SQLite and enforces a limit of 50,000 tokens per tenant within a one-minute window. Requests are sent to a primary model first, with a fallback when the primary provider returns a 429 rate-limit response or takes longer than three seconds.

I also added tests for token limits, concurrent requests, usage persistence, and both failover scenarios.

The model providers are simulated for local testing.

## Tech Stack

- Python 3.11+
- FastAPI
- Pydantic
- MCP Python SDK
- HTTPX
- SQLite
- Uvicorn

## Project Structure

```text
quilrai-ai-gateway/
├── task1_mcp_server/
│   └── server.py
├── task2_mcp_gateway/
│   ├── mock_server.py
│   └── gateway.py
├── task3_streaming_guardrail/
│   ├── proxy.py
│   └── test_proxy.py
├── task4_model_router/
│   ├── router.py
│   └── test_router.py
├── tests/
│   └── test_mcp_server.py
├── requirements.txt
├── README.md
└── .gitignore
```

## Getting Started

### 1. Clone the project

```bash
git clone <your-repository-url>
cd quilrai-ai-gateway
```

### 2. Set up a virtual environment

For Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install the dependencies

```bash
pip install -r requirements.txt
```

## Running the Applications

Run each component from the project root in a separate terminal, with the virtual environment activated.

**Task 1 – MCP Server**

```bash
python -m task1_mcp_server.server
```

This server uses stdio transport to communicate with MCP clients.

**Task 2 – MCP Gateway**

Start the downstream mock server:

```bash
python -m uvicorn task2_mcp_gateway.mock_server:app --host 127.0.0.1 --port 8001
```

In another terminal, start the gateway:

```bash
python -m uvicorn task2_mcp_gateway.gateway:app --host 127.0.0.1 --port 8000
```

**Task 3 – Streaming PII Guardrail**

```bash
python -m uvicorn task3_streaming_guardrail.proxy:app --host 127.0.0.1 --port 8002
```

**Task 4 – LLM Router**

```bash
python -m uvicorn task4_model_router.router:app --host 127.0.0.1 --port 8003
```

## Running the Tests

From the project root, run:

```bash
python -m tests.test_mcp_server
python -m task3_streaming_guardrail.test_proxy
python -m task4_model_router.test_router
```

To check that all Python files compile:

```bash
python -m compileall -q task1_mcp_server task2_mcp_gateway task3_streaming_guardrail task4_model_router tests
```

## A Few Notes

- The downstream MCP server and LLM providers are simulated, so the project can be tested locally without connecting to external services.
- The admin and viewer tokens are demo credentials, not intended for production use.
- The SQLite database is created locally when the router runs and is excluded from Git.
