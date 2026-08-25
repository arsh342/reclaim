"""Tests for simulator."""

import pytest
from decimal import Decimal
from sqlalchemy.ext.asyncio import AsyncSession

from backend.simulator.config_loader import load_config
from backend.simulator.outcome import simulate_recovery_probability, simulate_outcome
from backend.db.models import Order, PaymentAttempt, Merchant, Customer
from backend.simulator.generator import generate_orders


async def _create_test_merchant_and_customer(db_session: AsyncSession, merchant_id: str = "merchant_default", customer_id: str = "cust_test") -> tuple[Merchant, Customer]:
    """Helper to create merchant and customer for tests."""
    merchant = Merchant(
        merchant_id=merchant_id,
        max_retries=3,
        contact_budget_per_day=2,
    )
    db_session.add(merchant)
    
    customer = Customer(
        customer_id=customer_id,
        recovery_propensity=Decimal("0.5"),
        customer_value=Decimal("10000"),
    )
    db_session.add(customer)
    await db_session.flush()
    return merchant, customer


@pytest.mark.asyncio
async def test_config_loading():
    """Test simulator config loads correctly."""
    config = load_config()
    
    assert "insufficient_funds" in config.base_rate
    assert "issuer_timeout" in config.base_rate
    assert config.base_rate["issuer_timeout"] == 0.55
    assert config.method_factor["upi"] == 1.15
    assert config.action_fit["issuer_timeout"]["RETRY_NOW"] == 1.6


@pytest.mark.asyncio
async def test_simulate_recovery_probability(db_session: AsyncSession):
    """Test probability calculation."""
    await _create_test_merchant_and_customer(db_session)
    
    order = Order(
        order_id="order_test",
        merchant_id="merchant_default",
        customer_id="cust_test",
        amount=Decimal("5000"),
        currency="INR",
        status="pending",
    )
    db_session.add(order)
    
    attempt = PaymentAttempt(
        payment_id="pay_test",
        order_id="order_test",
        attempt_number=1,
        method="card",
        status="failed",
        error_reason="issuer_timeout",
    )
    db_session.add(attempt)
    await db_session.flush()
    
    prob = await simulate_recovery_probability(order, attempt, "RETRY_DELAYED")
    
    # base_rate(0.55) * method_factor(1.0) * action_fit(1.0) = 0.55
    assert prob == Decimal("0.55")


@pytest.mark.asyncio
async def test_simulate_recovery_probability_insufficient_funds(db_session: AsyncSession):
    """Test probability for insufficient funds with delayed retry."""
    await _create_test_merchant_and_customer(db_session, "merchant_default", "cust_test2")
    
    order = Order(
        order_id="order_test2",
        merchant_id="merchant_default",
        customer_id="cust_test2",
        amount=Decimal("5000"),
        currency="INR",
        status="pending",
    )
    db_session.add(order)
    
    attempt = PaymentAttempt(
        payment_id="pay_test2",
        order_id="order_test2",
        attempt_number=1,
        method="card",
        status="failed",
        error_reason="insufficient_funds",
    )
    db_session.add(attempt)
    await db_session.flush()
    
    prob = await simulate_recovery_probability(order, attempt, "RETRY_DELAYED")
    
    # base_rate(0.35) * method_factor(1.0) * action_fit(1.4) = 0.49
    assert abs(prob - Decimal("0.49")) < Decimal("0.001")


@pytest.mark.asyncio
async def test_simulate_recovery_probability_card_blocked(db_session: AsyncSession):
    """Test probability for hard decline (card_blocked)."""
    await _create_test_merchant_and_customer(db_session, "merchant_default", "cust_test3")
    
    order = Order(
        order_id="order_test3",
        merchant_id="merchant_default",
        customer_id="cust_test3",
        amount=Decimal("5000"),
        currency="INR",
        status="pending",
    )
    db_session.add(order)
    
    attempt = PaymentAttempt(
        payment_id="pay_test3",
        order_id="order_test3",
        attempt_number=1,
        method="card",
        status="failed",
        error_reason="card_blocked",
    )
    db_session.add(attempt)
    await db_session.flush()
    
    # RETRY_NOW should be 0.0
    prob = await simulate_recovery_probability(order, attempt, "RETRY_NOW")
    assert prob == Decimal("0")
    
    # ALTERNATE_METHOD should be 1.4 * 0.02 = 0.028
    prob = await simulate_recovery_probability(order, attempt, "ALTERNATE_METHOD")
    assert abs(prob - Decimal("0.028")) < Decimal("0.001")


@pytest.mark.asyncio
async def test_probability_clipping(db_session: AsyncSession):
    """Test probability is clipped to [0, 0.95]."""
    await _create_test_merchant_and_customer(db_session, "merchant_default", "cust_test4")
    
    order = Order(
        order_id="order_test4",
        merchant_id="merchant_default",
        customer_id="cust_test4",
        amount=Decimal("5000"),
        currency="INR",
        status="pending",
    )
    db_session.add(order)
    
    attempt = PaymentAttempt(
        payment_id="pay_test4",
        order_id="order_test4",
        attempt_number=1,
        method="upi",
        status="failed",
        error_reason="network_error",
    )
    db_session.add(attempt)
    await db_session.flush()
    
    # network_error: base=0.6, upi=1.15, RETRY_NOW=1.2 => 0.828 (under 0.95)
    prob = await simulate_recovery_probability(order, attempt, "RETRY_NOW")
    assert prob <= Decimal("0.95")
    assert prob >= Decimal("0")


@pytest.mark.asyncio
async def test_simulate_outcome_deterministic(db_session: AsyncSession):
    """Test outcome simulation is deterministic with seed."""
    await _create_test_merchant_and_customer(db_session, "merchant_default", "cust_test5")
    
    order = Order(
        order_id="order_test5",
        merchant_id="merchant_default",
        customer_id="cust_test5",
        amount=Decimal("5000"),
        currency="INR",
        status="pending",
    )
    db_session.add(order)
    
    attempt = PaymentAttempt(
        payment_id="pay_test5",
        order_id="order_test5",
        attempt_number=1,
        method="card",
        status="failed",
        error_reason="issuer_timeout",
    )
    db_session.add(attempt)
    await db_session.flush()
    
    result1 = simulate_outcome(order, attempt, "RETRY_DELAYED", seed=42)
    result2 = simulate_outcome(order, attempt, "RETRY_DELAYED", seed=42)
    result3 = simulate_outcome(order, attempt, "RETRY_DELAYED", seed=43)
    
    assert result1 == result2
    # Different seed may give different result


@pytest.mark.asyncio
async def test_generate_orders(db_session: AsyncSession):
    """Test order generation."""
    orders = await generate_orders(db_session, 10, seed=123)
    
    assert len(orders) == 10
    for order in orders:
        assert order.order_id.startswith("order_")
        assert order.amount > 0
        assert order.status in ("pending", "recovered")
        
        # Check attempts exist
        from sqlalchemy import select
        stmt = select(PaymentAttempt).where(PaymentAttempt.order_id == order.order_id)
        result = await db_session.execute(stmt)
        attempts = result.scalars().all()
        assert len(attempts) >= 1
        assert len(attempts) <= 3


@pytest.mark.asyncio
async def test_generate_orders_reproducible(db_session: AsyncSession):
    """Test order generation is reproducible with same seed."""
    # Clear any existing orders
    from sqlalchemy import delete
    await db_session.execute(delete(PaymentAttempt))
    await db_session.execute(delete(Order))
    await db_session.commit()
    
    orders1 = await generate_orders(db_session, 5, seed=999)
    order_ids1 = [o.order_id for o in orders1]
    
    # Clear and regenerate
    await db_session.execute(delete(PaymentAttempt))
    await db_session.execute(delete(Order))
    await db_session.commit()
    
    orders2 = await generate_orders(db_session, 5, seed=999)
    order_ids2 = [o.order_id for o in orders2]
    
    assert order_ids1 == order_ids2