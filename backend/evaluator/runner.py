"""Evaluation runner - compare always_retry vs reclaim policies."""

from decimal import Decimal
from typing import List

from sqlalchemy import select, delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Order, PaymentAttempt
from backend.evaluator.baselines import AlwaysRetryPolicy, ReclaimPolicy
from backend.api.schemas import EvalSummary, PolicyMetrics
from backend.simulator.outcome import simulate_outcome
from backend.policy.constraints import (
    RETRY_NOW,
    RETRY_DELAYED,
    PAYMENT_LINK,
    WHATSAPP_NUDGE,
    ALTERNATE_METHOD,
    NO_ACTION,
    HUMAN_REVIEW,
)
from backend.executor.executor import cancel_pending_actions


async def run_evaluation(
    session: AsyncSession,
    n_orders: int = 2000,
    seed: int = 42,
) -> EvalSummary:
    """Run evaluation comparing always_retry vs reclaim."""
    
    # Use a unique evaluation merchant per run to avoid conflicts
    import uuid
    EVAL_MERCHANT_ID = f"merchant_eval_{uuid.uuid4().hex[:8]}"
    
    from backend.db.models import Merchant
    merchant = Merchant(
        merchant_id=EVAL_MERCHANT_ID,
        max_retries=3,
        contact_budget_per_day=2,
    )
    session.add(merchant)
    await session.flush()
    
    # Generate orders that are all pending (for evaluation)
    orders = await generate_pending_orders(session, n_orders, seed, EVAL_MERCHANT_ID)
    
    # Run both policies - single decision per order
    always_retry = AlwaysRetryPolicy()
    reclaim = ReclaimPolicy()
    
    always_result = await simulate_single_decision(session, always_retry, orders, seed)
    reclaim_result = await simulate_single_decision(session, reclaim, orders, seed + 1000)
    
    return EvalSummary(
        always_retry=PolicyMetrics(**always_result),
        reclaim=PolicyMetrics(**reclaim_result),
        incremental_revenue=reclaim_result["recovered_revenue"] - always_result["recovered_revenue"],
        incremental_recovery_rate=reclaim_result["recovery_rate"] - always_result["recovery_rate"],
        total_orders=n_orders,
        seed=seed,
    )


async def generate_pending_orders(
    session: AsyncSession,
    n: int,
    seed: int = 42,
    merchant_id: str = "merchant_default",
) -> List[Order]:
    """Generate n orders with payment attempts, all pending."""
    import random
    from decimal import Decimal
    
    random.seed(seed)
    
    from backend.db.models import Merchant, Customer
    
    merchant = await session.get(Merchant, merchant_id)
    if not merchant:
        merchant = Merchant(
            merchant_id=merchant_id,
            max_retries=3,
            contact_budget_per_day=2,
        )
        session.add(merchant)
        await session.flush()
    
    ERROR_REASONS = [
        "insufficient_funds",
        "issuer_timeout",
        "card_blocked",
        "invalid_card",
        "network_error",
    ]
    ERROR_REASON_WEIGHTS = [0.35, 0.25, 0.10, 0.05, 0.25]
    
    METHODS = ["card", "upi", "netbanking"]
    METHOD_WEIGHTS = [0.6, 0.25, 0.15]
    
    orders = []
    # Extract unique suffix from merchant_id (e.g., "merchant_eval_abc123" -> "abc123")
    merchant_suffix = merchant_id.replace("merchant_eval_", "") if merchant_id.startswith("merchant_eval_") else "eval"
    for i in range(n):
        order_id = f"order_{i:04d}_{merchant_suffix}"
        customer_id = f"cust_{i:04d}_{merchant_suffix}"
        
        # Create customer
        customer = await session.get(Customer, customer_id)
        if not customer:
            customer = Customer(
                customer_id=customer_id,
                recovery_propensity=Decimal(str(round(random.uniform(0.2, 0.8), 2))),
                payment_method_preference=random.choice(METHODS),
                historical_success_rate=Decimal(str(round(random.uniform(0.3, 0.9), 2))),
                customer_value=Decimal(str(round(random.uniform(1000, 50000), 2))),
            )
            session.add(customer)
        
        # Create order - always pending for evaluation
        amount = Decimal(str(round(random.uniform(500, 25000), 2)))
        order = Order(
            order_id=order_id,
            merchant_id=merchant_id,
            customer_id=customer_id,
            amount=amount,
            currency="INR",
            status="pending",
        )
        session.add(order)
        await session.flush()
        
        # Generate 1-3 payment attempts (all failed)
        n_attempts = random.randint(1, 3)
        for attempt_num in range(1, n_attempts + 1):
            method = random.choices(METHODS, weights=METHOD_WEIGHTS)[0]
            error_reason = random.choices(ERROR_REASONS, weights=ERROR_REASON_WEIGHTS)[0]
            
            attempt = PaymentAttempt(
                payment_id=f"pay_{order_id}_{attempt_num}",
                order_id=order_id,
                attempt_number=attempt_num,
                method=method,
                status="failed",
                error_reason=error_reason,
                error_source="customer" if error_reason != "network_error" else "network",
                error_step="payment_authentication",
            )
            session.add(attempt)
        
        orders.append(order)
    
    await session.commit()
    return orders


async def simulate_single_decision(
    session: AsyncSession,
    policy,
    orders: List[Order],
    seed: int,
) -> dict:
    """Simulate a single decision per order for both policies."""
    import random
    random.seed(seed)
    
    recovered_revenue = Decimal("0")
    total_revenue_at_risk = Decimal("0")
    recovered_count = 0
    total_interventions = 0
    contact_count = 0
    policy_rejections = 0
    
    for order in orders:
        total_revenue_at_risk += order.amount
        
        # Get last attempt for this order
        stmt = (
            select(PaymentAttempt)
            .where(PaymentAttempt.order_id == order.order_id)
            .order_by(PaymentAttempt.attempt_number.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        last_attempt = result.scalar_one_or_none()
        
        if not last_attempt:
            continue
        
        # Policy makes ONE decision
        action = await policy.decide_action(session, order.order_id)
        if action is None or action in {NO_ACTION, HUMAN_REVIEW}:
            continue
        
        if action in {RETRY_NOW, RETRY_DELAYED, PAYMENT_LINK, WHATSAPP_NUDGE, ALTERNATE_METHOD}:
            total_interventions += 1
            if action in {PAYMENT_LINK, WHATSAPP_NUDGE}:
                contact_count += 1
            
            # Simulate outcome of this single action
            success = simulate_outcome(order, last_attempt, action, seed=seed)
            if success:
                recovered_revenue += order.amount
                recovered_count += 1
    
    return {
        "policy_name": policy.name(),
        "recovered_revenue": float(recovered_revenue),
        "recovery_rate": float(recovered_count / len(orders)) if orders else 0,
        "total_revenue_at_risk": float(total_revenue_at_risk),
        "unnecessary_interventions": total_interventions - recovered_count,
        "contact_count": contact_count,
        "avg_time_to_resolution_hours": 2.0,
        "policy_rejections": policy_rejections,
    }