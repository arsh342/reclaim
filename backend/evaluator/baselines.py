"""Baseline policies for evaluation."""

from abc import ABC, abstractmethod
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Order, PaymentAttempt
from backend.policy.constraints import (
    get_allowed_actions,
    RETRY_NOW,
    RETRY_DELAYED,
    PAYMENT_LINK,
    WHATSAPP_NUDGE,
    ALTERNATE_METHOD,
    NO_ACTION,
    HUMAN_REVIEW,
)
from backend.policy.scoring import calculate_expected_value
from backend.executor.executor import execute_recovery_action, cancel_pending_actions


class BasePolicy(ABC):
    @abstractmethod
    async def decide_action(
        self,
        session: AsyncSession,
        order_id: str,
    ) -> Optional[str]:
        pass
    
    @abstractmethod
    def name(self) -> str:
        pass


class AlwaysRetryPolicy(BasePolicy):
    """Baseline: always retry if allowed."""
    
    def name(self) -> str:
        return "always_retry"
    
    async def decide_action(
        self,
        session: AsyncSession,
        order_id: str,
    ) -> Optional[str]:
        allowed = await get_allowed_actions(session, order_id)
        
        # Prefer RETRY_NOW, then RETRY_DELAYED
        for action in [RETRY_NOW, RETRY_DELAYED]:
            if action in allowed:
                return action
        
        return NO_ACTION if NO_ACTION in allowed else None


class ReclaimPolicy(BasePolicy):
    """Reclaim deterministic policy: choose highest ERV action."""
    
    def name(self) -> str:
        return "reclaim"
    
    async def decide_action(
        self,
        session: AsyncSession,
        order_id: str,
    ) -> Optional[str]:
        allowed = await get_allowed_actions(session, order_id)
        
        if not allowed:
            return None
        
        # Calculate ERV for each allowed action
        best_action = None
        best_erv = Decimal("-Infinity")
        
        for action in allowed:
            if action in {NO_ACTION, HUMAN_REVIEW}:
                continue
            
            erv = await calculate_expected_value(session, order_id, action)
            if erv > best_erv:
                best_erv = erv
                best_action = action
        
        # If no positive ERV action, use NO_ACTION
        if best_action is None:
            return NO_ACTION if NO_ACTION in allowed else (HUMAN_REVIEW if HUMAN_REVIEW in allowed else None)
        
        return best_action


async def simulate_policy(
    session: AsyncSession,
    policy: BasePolicy,
    orders: List[Order],
    seed: int = 42,
) -> dict:
    """Simulate a policy against a list of orders."""
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
        
        # Simulate payment attempts until recovery or max retries
        attempt_number = 0
        max_attempts = 3
        
        while attempt_number < max_attempts:
            attempt_number += 1
            
            # Simulate failure for first attempts
            if attempt_number < max_attempts:
                action = await policy.decide_action(session, order.order_id)
                if action is None:
                    break
                
                if action in {RETRY_NOW, RETRY_DELAYED, PAYMENT_LINK, WHATSAPP_NUDGE, ALTERNATE_METHOD}:
                    total_interventions += 1
                    if action in {PAYMENT_LINK, WHATSAPP_NUDGE}:
                        contact_count += 1
                    
                    # Simulate outcome
                    from backend.simulator.outcome import simulate_outcome
                    # Create mock attempt
                    mock_attempt = PaymentAttempt(
                        payment_id=f"pay_{order.order_id}_{attempt_number}",
                        order_id=order.order_id,
                        attempt_number=attempt_number,
                        method="card",
                        status="failed",
                        error_reason="issuer_timeout",
                    )
                    success = simulate_outcome(order, mock_attempt, action, seed=seed + attempt_number)
                    if success:
                        recovered_revenue += order.amount
                        recovered_count += 1
                        # Cancel any pending actions
                        await cancel_pending_actions(session, order.order_id, "Recovery successful")
                        break
                elif action == NO_ACTION:
                    break
            else:
                # Final attempt - check if captured
                action = await policy.decide_action(session, order.order_id)
                if action and action in {RETRY_NOW, RETRY_DELAYED}:
                    from backend.simulator.outcome import simulate_outcome
                    mock_attempt = PaymentAttempt(
                        payment_id=f"pay_{order.order_id}_{attempt_number}",
                        order_id=order.order_id,
                        attempt_number=attempt_number,
                        method="card",
                        status="failed",
                        error_reason="issuer_timeout",
                    )
                    success = simulate_outcome(order, mock_attempt, action, seed=seed + attempt_number)
                    if success:
                        recovered_revenue += order.amount
                        recovered_count += 1
                break
    
    return {
        "policy_name": policy.name(),
        "recovered_revenue": float(recovered_revenue),
        "recovery_rate": float(recovered_count / len(orders)) if orders else 0,
        "total_revenue_at_risk": float(total_revenue_at_risk),
        "unnecessary_interventions": total_interventions - recovered_count,
        "contact_count": contact_count,
        "avg_time_to_resolution_hours": 2.0,  # Simplified
        "policy_rejections": policy_rejections,
    }