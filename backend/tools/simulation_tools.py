"""Simulation tools."""

from typing import Any, Dict

from sqlalchemy.ext.asyncio import AsyncSession

from backend.simulator.outcome import simulate_recovery_probability, simulate_outcome
from backend.db.models import Order, PaymentAttempt
from sqlalchemy import select
from backend.tools.registry import tool_registry


async def simulate_outcome_tool(
    order_id: str,
    action: str,
    session: AsyncSession,
) -> Dict[str, Any]:
    """Simulate outcome for an order and action."""
    order = await session.get(Order, order_id)
    if not order:
        return {"error": "Order not found"}
    
    stmt = select(PaymentAttempt).where(PaymentAttempt.order_id == order_id).order_by(PaymentAttempt.attempt_number.desc()).limit(1)
    result = await session.execute(stmt)
    attempt = result.scalar_one_or_none()
    
    if not attempt:
        return {"error": "No payment attempts found"}
    
    probability = await simulate_recovery_probability(order, attempt, action)
    success = simulate_outcome(order, attempt, action)
    
    return {
        "order_id": order_id,
        "action": action,
        "probability": float(probability),
        "simulated_success": success,
    }


# Register tool
tool_registry.register(
    "simulate_outcome",
    simulate_outcome_tool,
    "Simulate recovery outcome for an action",
    read_only=True,
    financial_side_effect=False,
)