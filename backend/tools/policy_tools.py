"""Policy tools."""

from decimal import Decimal
from typing import Any, Dict, List

from sqlalchemy.ext.asyncio import AsyncSession

from backend.policy.constraints import get_allowed_actions
from backend.policy.scoring import calculate_expected_value
from backend.tools.registry import tool_registry


async def get_allowed_actions_tool(order_id: str, session: AsyncSession) -> List[str]:
    """Get actions allowed by deterministic policy."""
    return await get_allowed_actions(session, order_id)


async def estimate_recovery(order_id: str, action: str, session: AsyncSession) -> Dict[str, Any]:
    """Estimate recovery probability and ERV for an action."""
    erv = await calculate_expected_value(session, order_id, action)
    
    # Get probability from simulator
    from backend.simulator.outcome import simulate_recovery_probability
    from backend.db.models import Order, PaymentAttempt
    from sqlalchemy import select
    
    order = await session.get(Order, order_id)
    if not order:
        return {"error": "Order not found"}
    
    stmt = select(PaymentAttempt).where(PaymentAttempt.order_id == order_id).order_by(PaymentAttempt.attempt_number.desc()).limit(1)
    result = await session.execute(stmt)
    attempt = result.scalar_one_or_none()
    
    if not attempt:
        return {"error": "No payment attempts found"}
    
    probability = await simulate_recovery_probability(order, attempt, action)
    
    from backend.policy.scoring import ACTION_COSTS, FRICTION_COSTS, RISK_PENALTIES
    
    return {
        "action": action,
        "probability": float(probability),
        "expected_value": float(erv),
        "intervention_cost": float(ACTION_COSTS.get(action, Decimal("0"))),
        "friction_cost": float(FRICTION_COSTS.get(action, Decimal("0"))),
        "risk_penalty": float(RISK_PENALTIES.get(action, Decimal("0"))),
        "recoverable_amount": float(order.amount),
    }


async def get_action_cost(action: str, session: AsyncSession) -> Dict[str, Any]:
    """Get cost breakdown for an action."""
    from backend.policy.scoring import ACTION_COSTS, FRICTION_COSTS, RISK_PENALTIES
    
    return {
        "action": action,
        "intervention_cost": float(ACTION_COSTS.get(action, Decimal("0"))),
        "friction_cost": float(FRICTION_COSTS.get(action, Decimal("0"))),
        "risk_penalty": float(RISK_PENALTIES.get(action, Decimal("0"))),
        "total_cost": float(
            ACTION_COSTS.get(action, Decimal("0")) +
            FRICTION_COSTS.get(action, Decimal("0")) +
            RISK_PENALTIES.get(action, Decimal("0"))
        ),
    }


# Register tools
tool_registry.register(
    "get_allowed_actions",
    get_allowed_actions_tool,
    "Return recovery actions permitted by deterministic policy",
    read_only=True,
    financial_side_effect=False,
)

tool_registry.register(
    "estimate_recovery",
    estimate_recovery,
    "Calculate recovery probability and expected recovery value",
    read_only=True,
    financial_side_effect=False,
)

tool_registry.register(
    "get_action_cost",
    get_action_cost,
    "Get cost breakdown for a recovery action",
    read_only=True,
    financial_side_effect=False,
)