"""Test agent runtime integration."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from backend.agent_runtime.orchestrator import run_agent
from backend.agent_runtime.provider import MockLLMProvider
from backend.evaluator.runner import generate_pending_orders
from backend.db.models import Order, PaymentAttempt, Merchant, Customer, AgentRun, AgentEvent, RecoveryAction
from decimal import Decimal


@pytest.mark.asyncio
async def test_agent_runs_successfully(db_session: AsyncSession):
    """Test that the agent runs through all stages."""
    # Create a pending order
    orders = await generate_pending_orders(db_session, 1, seed=42)
    order_id = orders[0].order_id
    
    # Run agent with mock provider
    state = await run_agent(db_session, order_id, llm_provider=MockLLMProvider())
    
    assert state.status == "completed"
    assert state.diagnosis is not None
    assert state.candidates is not None
    assert state.plan is not None
    assert state.safety_result is not None
    assert state.execution_result is not None
    assert state.final_action is not None
    
    # Check all stages executed
    assert state.context is not None
    assert "order" in state.context
    assert "attempts" in state.context


@pytest.mark.asyncio
async def test_agent_emits_events(db_session: AsyncSession):
    """Test that agent emits events to database."""
    from backend.db.models import AgentEvent
    from sqlalchemy import select
    
    orders = await generate_pending_orders(db_session, 1, seed=999)
    order_id = orders[0].order_id
    
    state = await run_agent(db_session, order_id, llm_provider=MockLLMProvider())
    
    # Check events were persisted
    stmt = select(AgentEvent).where(AgentEvent.run_id == state.run_id)
    result = await db_session.execute(stmt)
    events = result.scalars().all()
    
    assert len(events) > 0
    event_types = [e.event_type for e in events]
    
    # Should have events for each stage
    assert "agent.run.started" in event_types or "agent.stage.started" in event_types
    assert "agent.stage.completed" in event_types


@pytest.mark.asyncio
async def test_agent_with_hard_decline(db_session: AsyncSession):
    """Test agent handles hard decline (card_blocked) correctly."""
    # Create order with card_blocked error - use unique IDs to avoid conflicts
    import uuid
    unique_suffix = uuid.uuid4().hex[:8]
    merchant_id = f"merchant_hard_{unique_suffix}"
    customer_id = f"cust_hard_{unique_suffix}"
    order_id = f"order_hard_{unique_suffix}"
    payment_id = f"pay_hard_{unique_suffix}"
    
    merchant = Merchant(merchant_id=merchant_id, max_retries=3, contact_budget_per_day=2)
    customer = Customer(
        customer_id=customer_id,
        recovery_propensity=Decimal("0.5"),
        customer_value=Decimal("10000"),
    )
    db_session.add(merchant)
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
        payment_id=payment_id,
        order_id=order_id,
        attempt_number=1,
        method="card",
        status="failed",
        error_reason="card_blocked",
    )
    db_session.add(attempt)
    await db_session.commit()
    
    try:
        state = await run_agent(db_session, order_id, llm_provider=MockLLMProvider())
        
        # For hard decline, retries should be forbidden
        # Agent should replan and choose non-retry action
        assert state.status in ("completed", "failed")
        if state.plan and state.plan.get("steps"):
            first_action = state.plan["steps"][0]["action"]
            # Should not be a retry action
            assert first_action not in ["RETRY_NOW", "RETRY_DELAYED"]
    finally:
        # Cleanup - delete in correct order to respect foreign keys
        await db_session.execute(delete(AgentEvent).where(AgentEvent.order_id == order_id))
        await db_session.execute(delete(AgentRun).where(AgentRun.order_id == order_id))
        await db_session.execute(delete(RecoveryAction).where(RecoveryAction.order_id == order_id))
        await db_session.execute(delete(PaymentAttempt).where(PaymentAttempt.order_id == order_id))
        await db_session.execute(delete(Order).where(Order.order_id == order_id))
        await db_session.execute(delete(Customer).where(Customer.customer_id == customer_id))
        await db_session.execute(delete(Merchant).where(Merchant.merchant_id == merchant_id))
        await db_session.commit()