"""Recovery tools - side-effecting tools."""

from decimal import Decimal
from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from backend.executor.executor import (
    create_recovery_action,
    execute_recovery_action,
    cancel_pending_actions as executor_cancel_pending_actions,
)
from backend.tools.registry import tool_registry


async def create_recovery_action_tool(
    order_id: str,
    action: str,
    expected_value: float,
    session: AsyncSession,
) -> Dict[str, Any]:
    """Schedule a recovery action."""
    action_record = await create_recovery_action(session, order_id, action, Decimal(str(expected_value)))
    return {
        "action_id": action_record.action_id,
        "order_id": action_record.order_id,
        "action_type": action_record.action_type,
        "expected_value": float(action_record.expected_value),
        "status": action_record.status,
        "scheduled_at": action_record.scheduled_at.isoformat() if action_record.scheduled_at else None,
    }


async def execute_recovery_action_tool(
    order_id: str,
    action: str,
    session: AsyncSession,
) -> Dict[str, Any]:
    """Execute a recovery action through safe executor."""
    result = await execute_recovery_action(session, order_id, action)
    return {
        "success": result.success,
        "action_id": result.action_id,
        "reason": result.reason,
        "scheduled_at": result.scheduled_at.isoformat() if result.scheduled_at else None,
    }


async def cancel_pending_action_tool(
    order_id: str,
    session: AsyncSession,
) -> Dict[str, Any]:
    """Cancel all pending recovery actions for an order."""
    count = await executor_cancel_pending_actions(session, order_id, "Cancelled via tool")
    return {
        "cancelled_count": count,
        "order_id": order_id,
    }


# Register tools
tool_registry.register(
    "create_recovery_action",
    create_recovery_action_tool,
    "Schedule a recovery action (idempotent)",
    read_only=False,
    financial_side_effect=True,
)

tool_registry.register(
    "execute_recovery_action",
    execute_recovery_action_tool,
    "Execute a recovery action through safe executor",
    read_only=False,
    financial_side_effect=True,
)

tool_registry.register(
    "cancel_pending_action",
    cancel_pending_action_tool,
    "Cancel scheduled recovery actions for an order",
    read_only=False,
    financial_side_effect=True,
)