"""Tests for evaluation."""

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.evaluator.runner import run_evaluation, generate_pending_orders
from backend.evaluator.baselines import ReclaimPolicy, AlwaysRetryPolicy
from backend.policy.constraints import get_allowed_actions
from backend.policy.scoring import calculate_expected_value
from backend.db.models import Order, PaymentAttempt, Merchant
from backend.simulator.outcome import simulate_recovery_probability


@pytest.mark.asyncio
async def test_run_evaluation(db_session: AsyncSession):
    """Test evaluation runs and returns expected structure."""
    # Clear existing orders
    await db_session.execute(delete(PaymentAttempt))
    await db_session.execute(delete(Order))
    await db_session.execute(delete(Merchant))
    await db_session.commit()
    
    # Debug: check what Reclaim policy chooses on fresh pending orders
    orders = await generate_pending_orders(db_session, 5, seed=42)
    reclaim = ReclaimPolicy()
    always = AlwaysRetryPolicy()
    
    for order in orders:
        # Get latest attempt
        stmt = select(PaymentAttempt).where(PaymentAttempt.order_id == order.order_id).order_by(PaymentAttempt.attempt_number.desc()).limit(1)
        result = await db_session.execute(stmt)
        last_attempt = result.scalar_one_or_none()
        
        allowed = await get_allowed_actions(db_session, order.order_id)
        print(f'Order: {order.order_id}, Amount: {order.amount}, Status: {order.status}')
        print(f'  Last attempt: method={last_attempt.method}, error_reason={last_attempt.error_reason}')
        print(f'  Allowed: {allowed}')
        for action in allowed:
            if action not in ['NO_ACTION', 'HUMAN_REVIEW']:
                erv = await calculate_expected_value(db_session, order.order_id, action)
                prob = await simulate_recovery_probability(order, last_attempt, action)
                from backend.policy.scoring import ACTION_COSTS, FRICTION_COSTS, RISK_PENALTIES
                print(f'  {action}: prob={prob:.4f}, ERV={erv:.2f}, cost={ACTION_COSTS.get(action,0)+FRICTION_COSTS.get(action,0)+RISK_PENALTIES.get(action,0):.2f}')
        reclaim_action = await reclaim.decide_action(db_session, order.order_id)
        always_action = await always.decide_action(db_session, order.order_id)
        print(f'  Reclaim: {reclaim_action}, Always: {always_action}')
    
    result = await run_evaluation(db_session, n_orders=100, seed=42)
    
    assert result.total_orders == 100
    assert result.seed == 42
    assert result.always_retry.policy_name == "always_retry"
    assert result.reclaim.policy_name == "reclaim"
    assert result.always_retry.recovered_revenue >= 0
    assert result.reclaim.recovered_revenue >= 0
    assert result.always_retry.recovery_rate >= 0
    assert result.reclaim.recovery_rate >= 0
    assert result.always_retry.total_revenue_at_risk > 0
    assert result.reclaim.total_revenue_at_risk > 0
    
    print(f"Always retry: {result.always_retry.recovered_revenue:.2f} recovered, {result.always_retry.recovery_rate*100:.1f}% rate")
    print(f"Reclaim: {result.reclaim.recovered_revenue:.2f} recovered, {result.reclaim.recovery_rate*100:.1f}% rate")
    print(f"Incremental: {result.incremental_revenue:.2f} revenue, {result.incremental_recovery_rate*100:.1f}pp rate")
    
    # Cleanup evaluation data
    await db_session.execute(delete(PaymentAttempt))
    await db_session.execute(delete(Order))
    await db_session.execute(delete(Merchant).where(Merchant.merchant_id.like("merchant_eval_%")))
    await db_session.commit()