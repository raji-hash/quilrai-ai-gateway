
import logging
import re

from mcp.server.fastmcp import FastMCP
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Send diagnostic logs to stderr, never stdout.
logging.basicConfig(level=logging.INFO, stream=__import__("sys").stderr)

mcp = FastMCP("quilrai-customer-server")

class CustomerInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    customer_id: str = Field(
        description="Customer ID in the format CUST-12345"
    )

    @field_validator("customer_id")
    @classmethod
    def validate_customer_id(cls, value: str) -> str:
        if not re.fullmatch(r"CUST-\d{5}", value):
            raise ValueError(
                "customer_id must match the format CUST-XXXXX "
                "where X is a digit"
            )
        return value

class RefundInput(CustomerInput):
    amount: float = Field(gt=0, description="Refund amount; must be positive")
    reason: str = Field(min_length=10, description="Reason for the refund")

    @field_validator("amount", mode="before")
    @classmethod
    def reject_boolean_amount(cls, value):
        if isinstance(value, bool):
            raise ValueError("amount must be a number, not a boolean")
        return value

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reason cannot be blank")
        return value

CUSTOMERS = {
    "CUST-12345": {
        "customer_id": "CUST-12345",
        "name": "Alex Morgan",
        "status": "active",
    },
    "CUST-67890": {
        "customer_id": "CUST-67890",
        "name": "Taylor Smith",
        "status": "active",
    },
}

REFUND_REQUESTS = []

@mcp.tool()
def get_customer_record(
    customer_id: Annotated[
        str,
        Field(pattern=r"^CUST-\d{5}$")
    ],
) -> dict:
    """Retrieve a customer record using an ID such as CUST-12345."""
    validated = CustomerInput(customer_id=customer_id)
    record = CUSTOMERS.get(validated.customer_id)

    if record is None:
        raise ValueError("Customer not found")

    return record

@mcp.tool()
def trigger_refund(
    customer_id: Annotated[str, Field(pattern=r"^CUST-\d{5}$")],
    amount: Annotated[float, Field(gt=0)],
    reason: Annotated[str, Field(min_length=10)],
) -> dict:
    """Create a simulated refund request after validating its inputs."""
    validated = RefundInput(
        customer_id=customer_id,
        amount=amount,
        reason=reason,
    )

    if validated.customer_id not in CUSTOMERS:
        raise ValueError("Customer not found")

    refund = {
        "refund_id": f"REFUND-{len(REFUND_REQUESTS) + 1:05d}",
        "customer_id": validated.customer_id,
        "amount": validated.amount,
        "reason": validated.reason,
        "status": "pending",
    }

    REFUND_REQUESTS.append(refund)
    logging.info("Created simulated refund request %s", refund["refund_id"])

    return refund



if __name__ == "__main__":
    mcp.run(transport="stdio")
