
import re

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel


app = FastAPI(title="LLM Streaming PII Guardrail")

MAX_BUFFER_SIZE = 256

PII_PATTERNS = {
    "EMAIL": re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    ),
    "SSN": re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)"),
    "CC": re.compile(
        r"(?<!\d)(?:\d[ -]?){12,18}\d(?!\d)"
    ),
}


def redact_pii(text: str) -> str:
    text = PII_PATTERNS["EMAIL"].sub("[REDACTED_EMAIL]", text)
    text = PII_PATTERNS["SSN"].sub("[REDACTED_SSN]", text)
    text = PII_PATTERNS["CC"].sub("[REDACTED_CC]", text)
    return text


class PIIRedactionBuffer:
    """
    Incremental PII redaction with a hard buffer limit.

    Keeps the final token until a delimiter arrives so PII
    split across chunks can be detected.

    If a token exceeds the buffer limit, it is discarded
    conservatively rather than being sent to the client.
    """

    def __init__(self, max_buffer_size: int = MAX_BUFFER_SIZE):
        if max_buffer_size < 32:
            raise ValueError("max_buffer_size must be at least 32")

        self.buffer = ""
        self.max_buffer_size = max_buffer_size
        self.discarding_oversized_token = False

    def process_chunk(self, chunk: str) -> str:
        output = []

        for char in chunk:
            if self.discarding_oversized_token:
                if char.isspace():
                    self.discarding_oversized_token = False
                else:
                    continue

            self.buffer += char

            # A whitespace boundary means the preceding token
            # is complete and can be inspected safely.
            if char.isspace():
                output.append(redact_pii(self.buffer))
                self.buffer = ""

            # Fail closed if a single token becomes too large.
            if len(self.buffer) > self.max_buffer_size:
                self.buffer = ""
                output.append("[REDACTED_OVERSIZED_TOKEN]")
                self.discarding_oversized_token = True

        return "".join(output)

    def flush(self) -> str:
        """Process the final buffered token when the stream ends."""
        if self.discarding_oversized_token:
            self.discarding_oversized_token = False
            self.buffer = ""
            return ""

        remaining = redact_pii(self.buffer)
        self.buffer = ""
        return remaining


class StreamRequest(BaseModel):
    text: str


async def mock_llm_stream(text: str):
    """Simulate an LLM generating small chunks."""
    chunk_size = 12

    for index in range(0, len(text), chunk_size):
        yield text[index:index + chunk_size]


async def protected_stream(text: str):
    """Send only sanitized text to the client."""
    guardrail = PIIRedactionBuffer()

    async for chunk in mock_llm_stream(text):
        safe_chunk = guardrail.process_chunk(chunk)

        if safe_chunk:
            yield safe_chunk

    remaining = guardrail.flush()

    if remaining:
        yield remaining


@app.post("/stream")
async def stream_response(request: StreamRequest):
    return StreamingResponse(
        protected_stream(request.text),
        media_type="text/plain",
    )


@app.get("/health")
async def health():
    return {"status": "healthy"}
