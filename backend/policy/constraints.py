"""Hard constraint policy gate."""

from decimal import Decimal
from typing import List, Optional, Set

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Merchant, Order, PaymentAttempt, RecoveryAction


# Action constants
RETRY_NOW = "RETRY_NOW"
RETRY_DELAYED = "RETRY_DELAYED"
PAYMENT_LINK = "PAYMENT_LINK"
WHATSAPP_NUDGE = "WHATSAPP_NUDGE"
ALTERNATE_METHOD = "ALTERNATE_METHOD"
NO_ACTION = "NO_ACTION"
HUMAN_REVIEW = "HUMAN_REVIEW"

ALL_ACTIONS = [
    RETRY_NOW,
    RETRY_DELAYED,
    PAYMENT_LINK,
    WHATSAPP_NUDGE,
    ALTERNATE_METHOD,
    NO_ACTION,
    HUMAN_REVIEW,
]

RETRY_ACTIONS = {RETRY_NOW, RETRY_DELAYED}
CONTACT_ACTIONS = {PAYMENT_LINK, WHATSAPP_NUDGE}

HARD_DECLINE_REASONS: Set[str] = {
    "card_blocked",
    "invalid_card",
    "stolen_card",
    "expired_card",
    "card_expired",
}


async def get_merchant(session: AsyncSession, merchant_id: str) -> Merchant:
    """Get merchant or create default."""
    merchant = await session.get(Merchant, merchant_id)
    if not merchant:
        merchant = Merchant(
            merchant_id=merchant_id,
            max_retries=3,
            contact_budget_per_day=2,
        )
        session.add(merchant)
        await session.flush()
    return merchant


async def get_daily_contact_count(session: AsyncSession, merchant_id: str) -> int:
    """Count contact actions today for merchant."""
    from datetime import datetime, timezone, timedelta
    
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    
    stmt = (
        select(func.count(RecoveryAction.action_id))
        .join(Order, RecoveryAction.order_id == Order.order_id)
        .where(
            Order.merchant_id == merchant_id,
            RecoveryAction.action_type.in_(CONTACT_ACTIONS),
            RecoveryAction.scheduled_at >= today_start,
            RecoveryAction.status != "cancelled",
        )
    )
    result = await session.execute(stmt)
    return result.scalar() or 0


async def get_allowed_actions(
    session: AsyncSession,
    order_id: str,
) -> List[str]:
    """Get actions allowed by deterministic policy."""
    order = await session.get(Order, order_id)
    if not order:
        return []
    
    # Terminal states: no actions allowed
    if order.status in {"recovered", "lost"}:
        return []
    
    # Get latest payment attempt
    stmt = (
        select(PaymentAttempt)
        .where(PaymentAttempt.order_id == order_id)
        .order_by(PaymentAttempt.attempt_number.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    attempt = result.scalar_one_or_none()
    
    if not attempt:
        return [NO_ACTION]
    
    merchant = await get_merchant(session, order.merchant_id)
    
    actions = ALL_ACTIONS.copy()
    
    # Max retries exceeded
    if attempt.attempt_number >= merchant.max_retries:
        actions = [a for a in actions if a not in RETRY_ACTIONS]
    
    # Hard decline
    if attempt.error_reason in HARD_DECLINE_REASONS:
        actions = [a for a in actions if a not in RETRY_ACTIONS]
    
    # Contact budget
    contact_count = await get_daily_contact_count(session, order.merchant_id)
    if contact_count >= merchant.contact_budget_per_day:
        actions = [a for a in actions if a not in CONTACT_ACTIONS]
    
    # Always allow NO_ACTION and HUMAN_REVIEW
    return actions


async def get_latest_attempt(session: AsyncSession, order_id: str) -> Optional[PaymentAttempt]:
    """Get latest payment attempt for order."""
    stmt = (
        select(PaymentAttempt)
        .where(PaymentAttempt.order_id == order_id)
        .order_by(PaymentAttempt.attempt_number.desc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()