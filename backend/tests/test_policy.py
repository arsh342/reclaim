"""Tests for policy constraints and scoring."""

import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Order, PaymentAttempt, Merchant, Customer
from backend.policy.constraints import get_allowed_actions, RETRY_NOW, RETRY_DELAYED, PAYMENT_LINK, WHATSAPP_NUDGE, NO_ACTION, HUMAN_REVIEW
from backend.policy.scoring import calculate_expected_value


async def _create_test_setup(db_session: AsyncSession, order_id: str = "order_test", merchant_id: str = "merchant_default", customer_id: str = "cust_test") -> tuple[Order, PaymentAttempt]:
    """Helper to create test order with attempt."""
    # Get or create merchant
    merchant = await db_session.get(Merchant, merchant_id)
    if not merchant:
        merchant = Merchant(
            merchant_id=merchant_id,
            max_retries=3,
            contact_budget_per_day=2,
        )
        db_session.add(merchant)
    
    # Get or create customer
    customer = await db_session.get(Customer, customer_id)
    if not customer:
        customer = Customer(
            customer_id=customer_id,
            recovery_propensity=Decimal("0.5"),
            customer_value=Decimal("10000"),
        )
        db_session.add(customer)
    
    order = Order(
        order_id=order_id,
        merchant_id=merchant_id,
        customer_id=customer_id,
        amount=Decimal("5000"),
        currency="INR",
        status="pending",
    )
    db_session.add(order)
    
    attempt = PaymentAttempt(
        payment_id=f"pay_{order_id}",
        order_id=order_id,
        attempt_number=1,
        method="card",
        status="failed",
        error_reason="issuer_timeout",
    )
    db_session.add(attempt)
    await db_session.flush()
    return order, attempt


@pytest.mark.asyncio
async def test_terminal_order_returns_empty(db_session: AsyncSession):
    """Recovered/lost orders should have no allowed actions."""
    order, _ = await _create_test_setup(db_session)
    order.status = "recovered"
    
    allowed = await get_allowed_actions(db_session, order.order_id)
    assert allowed == []


@pytest.mark.asyncio
async def test_lost_order_returns_empty(db_session: AsyncSession):
    """Lost orders should have no allowed actions."""
    order, _ = await _create_test_setup(db_session)
    order.status = "lost"
    
    allowed = await get_allowed_actions(db_session, order.order_id)
    assert allowed == []


@pytest.mark.asyncio
async def test_max_retries_exceeded_forbids_retry(db_session: AsyncSession):
    """Orders exceeding max retries should not allow retry actions."""
    order, attempt = await _create_test_setup(db_session)
    attempt.attempt_number = 4  # Exceeds default max_retries=3
    
    allowed = await get_allowed_actions(db_session, order.order_id)
    assert RETRY_NOW not in allowed
    assert RETRY_DELAYED not in allowed
    # But other actions should be allowed
    assert PAYMENT_LINK in allowed


@pytest.mark.asyncio
async def test_hard_decline_forbids_retry(db_session: AsyncSession):
    """Hard decline error reasons should forbid retry actions."""
    for reason in ["card_blocked", "invalid_card", "stolen_card", "expired_card"]:
        order, attempt = await _create_test_setup(db_session, order_id=f"order_{reason}", customer_id=f"cust_{reason}")
        attempt.error_reason = reason
        
        allowed = await get_allowed_actions(db_session, order.order_id)
        assert RETRY_NOW not in allowed, f"RETRY_NOW should be forbidden for {reason}"
        assert RETRY_DELAYED not in allowed, f"RETRY_DELAYED should be forbidden for {reason}"


@pytest.mark.asyncio
async def test_contact_budget_exhausted_forbids_nudge(db_session: AsyncSession):
    """Exhausted contact budget should forbid contact actions."""
    order, _ = await _create_test_setup(db_session)
    
    # Create 2 contact actions (default budget is 2)
    from backend.db.models import RecoveryAction
    from datetime import datetime, timezone
    
    action1 = RecoveryAction(
        order_id=order.order_id,
        action_type=PAYMENT_LINK,
        expected_value=Decimal("1000"),
        status="scheduled",
        scheduled_at=datetime.now(timezone.utc),
    )
    action2 = RecoveryAction(
        order_id=order.order_id,
        action_type=WHATSAPP_NUDGE,
        expected_value=Decimal("500"),
        status="scheduled",
        scheduled_at=datetime.now(timezone.utc),
    )
    db_session.add_all([action1, action2])
    await db_session.flush()
    
    allowed = await get_allowed_actions(db_session, order.order_id)
    assert PAYMENT_LINK not in allowed
    assert WHATSAPP_NUDGE not in allowed
    # But retry should still be allowed
    assert RETRY_DELAYED in allowed


@pytest.mark.asyncio
async def test_pending_soft_decline_allows_retry(db_session: AsyncSession):
    """Soft decline (issuer_timeout) should allow retry actions."""
    order, _ = await _create_test_setup(db_session)
    
    allowed = await get_allowed_actions(db_session, order.order_id)
    assert RETRY_NOW in allowed
    assert RETRY_DELAYED in allowed
    assert PAYMENT_LINK in allowed
    assert WHATSAPP_NUDGE in allowed
    assert NO_ACTION in allowed
    assert HUMAN_REVIEW in allowed


@pytest.mark.asyncio
async def test_calculate_expected_value(db_session: AsyncSession):
    """Test ERV calculation returns a value."""
    order, _ = await _create_test_setup(db_session)
    
    erv = await calculate_expected_value(db_session, order.order_id, RETRY_DELAYED)
    
    assert erv >= Decimal("0")
    assert isinstance(erv, Decimal)


@pytest.mark.asyncio
async def test_expected_value_higher_for_better_action(db_session: AsyncSession):
    """Test that better actions have higher ERV."""
    order, _ = await _create_test_setup(db_session)
    
    erv_retry = await calculate_expected_value(db_session, order.order_id, RETRY_DELAYED)
    erv_link = await calculate_expected_value(db_session, order.order_id, PAYMENT_LINK)
    
    # For issuer_timeout, RETRY_DELAYED has action_fit 1.0, PAYMENT_LINK has 0.7
    # So RETRY_DELAYED should have higher ERV
    assert erv_retry > erv_link