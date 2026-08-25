"""Reclaim MCP interoperability server."""

from typing import Any, Dict, List

from mcp.server import MCPServer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.mcp_server.adapters import (
    get_order_context_adapter,
    get_allowed_actions_adapter,
    estimate_recovery_adapter,
    execute_recovery_action_adapter,
    cancel_pending_action_adapter,
    start_recovery_run_adapter,
    get_agent_run_adapter,
    get_agent_events_adapter,
    get_evaluation_summary_adapter,
)
from backend.db.session import get_session


# Global session for MCP tools (in production, use proper session management)
_session: AsyncSession = None


def set_session(session: AsyncSession):
    global _session
    _session = session


def get_mcp_session() -> AsyncSession:
    if _session is None:
        raise RuntimeError("MCP session not initialized")
    return _session


mcp = MCPServer(
    "Reclaim",
    instructions=(
        "Reclaim is an AI revenue-recovery platform. "
        "Read payment state with read-only tools. "
        "All side-effecting recovery operations are guarded by "
        "Reclaim's deterministic policy and idempotent executor."
    ),
)


@mcp.tool()
async def reclaim_get_order_context(order_id: str) -> Dict[str, Any]:
    """Return order, customer, merchant, and payment-attempt context."""
    session = get_mcp_session()
    return await get_order_context_adapter(order_id, session)


@mcp.tool()
async def reclaim_get_allowed_actions(order_id: str) -> List[str]:
    """Return recovery actions currently permitted by deterministic policy."""
    session = get_mcp_session()
    return await get_allowed_actions_adapter(order_id, session)


@mcp.tool()
async def reclaim_estimate_recovery(order_id: str, action: str) -> Dict[str, Any]:
    """Return recovery probability, recoverable amount, costs, and ERV."""
    session = get_mcp_session()
    return await estimate_recovery_adapter(order_id, action, session)


@mcp.tool()
async def reclaim_execute_recovery_action(order_id: str, action: str) -> Dict[str, Any]:
    """Execute a recovery action through Reclaim's guarded executor."""
    session = get_mcp_session()
    return await execute_recovery_action_adapter(order_id, action, session)


@mcp.tool()
async def reclaim_cancel_pending_action(order_id: str) -> Dict[str, Any]:
    """Cancel scheduled recovery actions for an order."""
    session = get_mcp_session()
    return await cancel_pending_action_adapter(order_id, session)


@mcp.tool()
async def reclaim_start_recovery_run(order_id: str) -> Dict[str, Any]:
    """Start a bounded Reclaim recovery agent run."""
    session = get_mcp_session()
    return await start_recovery_run_adapter(order_id, session)


@mcp.tool()
async def reclaim_get_agent_run(run_id: str) -> Dict[str, Any]:
    """Return the current state and final result of an agent run."""
    session = get_mcp_session()
    return await get_agent_run_adapter(run_id, session)


@mcp.tool()
async def reclaim_get_agent_events(run_id: str) -> List[Dict[str, Any]]:
    """Return the persisted event timeline for an agent run."""
    session = get_mcp_session()
    return await get_agent_events_adapter(run_id, session)


@mcp.tool()
async def reclaim_get_evaluation_summary() -> Dict[str, Any]:
    """Return the latest always-retry versus Reclaim evaluation."""
    session = get_mcp_session()
    return await get_evaluation_summary_adapter(session)


def main() -> None:
    import argparse
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