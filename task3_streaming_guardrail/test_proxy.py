
from task3_streaming_guardrail.proxy import (
    PIIRedactionBuffer,
    redact_pii,
)


def test_complete_pii():
    message = (
        "Email user@example.com "
        "SSN 123-45-6789 "
        "Card 4111111111111111"
    )

    result = redact_pii(message)

    assert "user@example.com" not in result
    assert "123-45-6789" not in result
    assert "4111111111111111" not in result

    print("PASS: Complete PII detection")


def test_split_pii():
    guard = PIIRedactionBuffer()

    chunks = [
        "Email user@gmai",
        "l.com SSN 123-",
        "45-6789 Card 411111",
        "111111111111",
    ]

    result = ""

    for chunk in chunks:
        result += guard.process_chunk(chunk)

    result += guard.flush()

    assert "user@gmail.com" not in result
    assert "123-45-6789" not in result
    assert "4111111111111111" not in result

    assert "[REDACTED_EMAIL]" in result
    assert "[REDACTED_SSN]" in result
    assert "[REDACTED_CC]" in result

    print("PASS: Cross-chunk PII detection")


def test_buffer_limit():
    guard = PIIRedactionBuffer(max_buffer_size=32)

    result = guard.process_chunk("A" * 100)

    assert len(guard.buffer) <= 32
    assert "[REDACTED_OVERSIZED_TOKEN]" in result

    print("PASS: Buffer size limit")


def test_normal_text():
    guard = PIIRedactionBuffer()

    result = guard.process_chunk("Hello world ")
    result += guard.flush()

    assert result == "Hello world "

    print("PASS: Normal text preserved")


if __name__ == "__main__":
    test_complete_pii()
    test_split_pii()
    test_buffer_limit()
    test_normal_text()

    print("\nAll guardrail tests passed!")
