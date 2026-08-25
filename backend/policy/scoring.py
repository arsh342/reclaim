"""ERV (Expected Recovery Value) calculation."""

from decimal import Decimal
from typing import Dict, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Order, PaymentAttempt
from backend.simulator.outcome import simulate_recovery_probability
from backend.policy.constraints import RETRY_NOW, RETRY_DELAYED, PAYMENT_LINK, WHATSAPP_NUDGE, ALTERNATE_METHOD


ACTION_COSTS: Dict[str, Decimal] = {
    RETRY_NOW: Decimal("0"),
    RETRY_DELAYED: Decimal("0"),
    PAYMENT_LINK: Decimal("5"),
    WHATSAPP_NUDGE: Decimal("2"),
    ALTERNATE_METHOD: Decimal("10"),
}

FRICTION_COSTS: Dict[str, Decimal] = {
    RETRY_NOW: Decimal("1"),
    RETRY_DELAYED: Decimal("0.5"),
    PAYMENT_LINK: Decimal("3"),
    WHATSAPP_NUDGE: Decimal("1"),
    ALTERNATE_METHOD: Decimal("5"),
}

RISK_PENALTIES: Dict[str, Decimal] = {
    RETRY_NOW: Decimal("0"),
    RETRY_DELAYED: Decimal("0"),
    PAYMENT_LINK: Decimal("0"),
    WHATSAPP_NUDGE: Decimal("0"),
    ALTERNATE_METHOD: Decimal("0"),
}


async def calculate_expected_value(
    session: AsyncSession,
    order_id: str,
    action: str,
) -> Decimal:
    """Calculate ERV for an action."""
    order = await session.get(Order, order_id)
    if not order:
        return Decimal("0")
    
    # Get latest attempt
    stmt = (
        select(PaymentAttempt)
        .where(PaymentAttempt.order_id == order_id)
        .order_by(PaymentAttempt.attempt_number.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    attempt = result.scalar_one_or_none()
    
    if not attempt:
        return Decimal("0")
    
    # Get recovery probability from simulator
    probability = await simulate_recovery_probability(order, attempt, action)
    
    recoverable = order.amount
    intervention_cost = ACTION_COSTS.get(action, Decimal("0"))
    friction_cost = FRICTION_COSTS.get(action, Decimal("0"))
    risk_penalty = RISK_PENALTIES.get(action, Decimal("0"))
    
    erv = (probability * recoverable) - intervention_cost - friction_cost - risk_penalty
    
    return max(erv, Decimal("0"))