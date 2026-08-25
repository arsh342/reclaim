"""Reclaim MCP interoperability server.

The MCP layer delegates to Reclaim application services. It must not contain
independent payment or policy logic.

Wire the adapter functions below to the real application services in the
main Reclaim repository before enabling side-effecting tools.
"""

from __future__ import annotations

import argparse
from typing import Any

from mcp.server import MCPServer

mcp = MCPServer(
    "Reclaim",
    instructions=(
        "Reclaim is an AI revenue-recovery platform. "
        "Read payment state with read-only tools. "
        "All side-effecting recovery operations are guarded by "
        "Reclaim's deterministic policy and idempotent executor."
    ),
)


# Application-service adapters. These deliberately contain no business logic.
async def get_order_context(order_id: str) -> dict[str, Any]:
    raise NotImplementedError("Wire to Reclaim order service")


async def get_allowed_actions(order_id: str) -> list[str]:
    raise NotImplementedError("Wire to Reclaim policy service")


async def estimate_recovery(order_id: str, action: str) -> dict[str, Any]:
    raise NotImplementedError("Wire to Reclaim recovery service")


async def execute_recovery_action(order_id: str, action: str) -> dict[str, Any]:
    raise NotImplementedError("Wire to Reclaim safe executor")


async def cancel_pending_action(order_id: str) -> dict[str, Any]:
    raise NotImplementedError("Wire to Reclaim safe executor")


async def start_recovery_run(order_id: str) -> dict[str, Any]:
    raise NotImplementedError("Wire to Reclaim agent runtime")


async def get_agent_run(run_id: str) -> dict[str, Any]:
    raise NotImplementedError("Wire to Reclaim agent runtime")


async def get_agent_events(run_id: str) -> list[dict[str, Any]]:
    raise NotImplementedError("Wire to Reclaim event store")


async def get_evaluation_summary() -> dict[str, Any]:
    raise NotImplementedError("Wire to Reclaim evaluation service")


@mcp.tool()
async def reclaim_get_order_context(order_id: str) -> dict[str, Any]:
    """Return order, customer, merchant, and payment-attempt context."""
    return await get_order_context(order_id)


@mcp.tool()
async def reclaim_get_allowed_actions(order_id: str) -> list[str]:
    """Return recovery actions currently permitted by deterministic policy."""
    return await get_allowed_actions(order_id)


@mcp.tool()
async def reclaim_estimate_recovery(order_id: str, action: str) -> dict[str, Any]:
    """Return recovery probability, recoverable amount, costs, and ERV."""
    return await estimate_recovery(order_id, action)


@mcp.tool()
async def reclaim_execute_recovery_action(order_id: str, action: str) -> dict[str, Any]:
    """Execute a recovery action through Reclaim's guarded executor."""
    return await execute_recovery_action(order_id, action)


@mcp.tool()
async def reclaim_cancel_pending_action(order_id: str) -> dict[str, Any]:
    """Cancel scheduled recovery actions for an order."""
    return await cancel_pending_action(order_id)


@mcp.tool()
async def reclaim_start_recovery_run(order_id: str) -> dict[str, Any]:
    """Start a bounded Reclaim recovery agent run."""
    return await start_recovery_run(order_id)


@mcp.tool()
async def reclaim_get_agent_run(run_id: str) -> dict[str, Any]:
    """Return the current state and final result of an agent run."""
    return await get_agent_run(run_id)


@mcp.tool()
async def reclaim_get_agent_events(run_id: str) -> list[dict[str, Any]]:
    """Return the persisted event timeline for an agent run."""
    return await get_agent_events(run_id)


@mcp.tool()
async def reclaim_get_evaluation_summary() -> dict[str, Any]:
    """Return the latest always-retry versus Reclaim evaluation."""
    return await get_evaluation_summary()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--transport",
        choices=("stdio", "streamable-http"),
        default="streamable-http",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            streamable_http_path="/mcp",
        )


if __name__ == "__main__":
    main()
