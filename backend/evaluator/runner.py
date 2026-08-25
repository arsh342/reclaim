"""Evaluation runner."""

from decimal import Decimal
from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Order
from backend.evaluator.baselines import AlwaysRetryPolicy, ReclaimPolicy, simulate_policy
from backend.api.schemas import EvalSummary, PolicyMetrics
from backend.simulator.generator import generate_orders


async def run_evaluation(
    session: AsyncSession,
    n_orders: int = 2000,
    seed: int = 42,
) -> EvalSummary:
    """Run evaluation comparing always_retry vs reclaim."""
    
    # Generate or get orders
    orders = await generate_orders(session, n_orders, seed)
    
    if not orders:
        # Create synthetic orders for evaluation
        orders = await generate_orders(session, n_orders, seed)
    
    # Run both policies
    always_retry = AlwaysRetryPolicy()
    reclaim = ReclaimPolicy()
    
    always_result = await simulate_policy(session, always_retry, orders, seed)
    reclaim_result = await simulate_policy(session, reclaim, orders, seed + 1000)
    
    return EvalSummary(
        always_retry=PolicyMetrics(**always_result),
        reclaim=PolicyMetrics(**reclaim_result),
        incremental_revenue=reclaim_result["recovered_revenue"] - always_result["recovered_revenue"],
        incremental_recovery_rate=reclaim_result["recovery_rate"] - always_result["recovery_rate"],
        total_orders=n_orders,
        seed=seed,
    )