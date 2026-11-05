
import asyncio

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main():
    server = StdioServerParameters(
        command="python",
        args=["-m", "task1_mcp_server.server"],
    )

    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools = await session.list_tools()
            print("Registered tools:", [tool.name for tool in tools.tools])

            customer = await session.call_tool(
                "get_customer_record",
                {"customer_id": "CUST-12345"},
            )
            print("Valid customer call:", customer)

            invalid = await session.call_tool(
                "get_customer_record",
                {"customer_id": "ABC123"},
            )
            print("Invalid customer call:", invalid)

            refund = await session.call_tool(
                "trigger_refund",
                {
                    "customer_id": "CUST-12345",
                    "amount": 25.50,
                    "reason": "Duplicate payment",
                },
            )
            print("Valid refund call:", refund)

            invalid_refund = await session.call_tool(
                "trigger_refund",
                {
                    "customer_id": "CUST-12345",
                    "amount": -5,
                    "reason": "Duplicate payment",
                },
            )
            print("Invalid refund call:", invalid_refund)

            short_reason = await session.call_tool(
                "trigger_refund",
                {
                    "customer_id": "CUST-12345",
                    "amount": 25.50,
                    "reason": "mistake",
                },
            )
            print("Short reason call:", short_reason)


if __name__ == "__main__":
    asyncio.run(main())
