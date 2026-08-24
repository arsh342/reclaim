"""Evaluation runner — applies a policy to a simulated world and records
per-order outcomes. Deterministic: same seed → same world → same metrics.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from backend.policy.select import Decision, select_action
from backend.policy.alternate import recommend_alternate_method
from backend.policy.types import (
    AttemptView,
    CustomerView,
    Merchant,
    OrderView,
    PolicyContext,
)
from backend.simulator.generate import generate_world, simulate_outcome

from .baselines import select_action_always_retry
from .metrics import EvaluationResult, OrderOutcome, compute_metrics


ACTIONS = ("retry_now", "retry_delayed", "payment_link", "whatsapp_nudge", "alternate_method")


@dataclass(frozen=True)
class PolicyFunction:
    name: str
    select: callable


def run_policy(
    policy_fn: PolicyFunction,
    *,
    n_orders: int = 2000,
    seed: int = 42,
    max_steps: int = 10,
) -> list[OrderOutcome]:
    """Run one policy against a generated world.

    Each order gets up to `max_steps` webhook events (failed attempts)
    until it recovers, is lost, or we give up. This is a simplification
    of the real event stream but captures the policy's decision loop.
    """
    world = generate_world(n_orders=n_orders, seed=seed, attempts_per_order=1)
    rng = __import__("random").Random(seed + 1000)

    customers_by_id = {c.customer_id: c for c in world.customers}
    merchants_by_id = {m.merchant_id: m for m in world.merchants}

    outcomes: list[OrderOutcome] = []

    for order in world.orders:
        merchant = merchants_by_id[order.merchant_id]
        customer = customers_by_id[order.customer_id]
        attempt_number = 1
        actions_taken: list[str] = []
        current_amount = order.amount
        status: Literal["recovered", "lost", "pending"] = "pending"

        # First attempt comes from the generated world
        attempt = next(a for a in world.attempts if a.order_id == order.order_id)
        attempt_number = attempt.attempt_number

        while status == "pending" and attempt_number <= max_steps:
            ctx = PolicyContext(
                order=OrderView(order_id=order.order_id, amount=current_amount, status="pending"),
                attempt=AttemptView(
                    attempt_number=attempt_number,
                    method=attempt.method,
                    error_reason=attempt.error_reason,
                ),
                merchant=Merchant(
                    merchant_id=merchant.merchant_id,
                    max_retries=merchant.max_retries,
                    contact_budget_per_day=merchant.contact_budget_per_day,
                ),
                customer=CustomerView(
                    recovery_propensity=customer.recovery_propensity,
                    contact_count_today=0,
                ),
            )

            decision = policy_fn.select(ctx)
            action = decision.selected_action

            if action in ("no_action", "human_review"):
                # Policy chose to do nothing — outcome determined by next attempt
                actions_taken.append(action)
                attempt_number += 1
                continue

            actions_taken.append(action)
            if action == "whatsapp_nudge":
                pass  # nudge is a contact action but we don't track contact_events
            elif action in ("retry_now",):
                pass
            elif action in ("retry_delayed",):
                pass
            else:
                pass  # payment_link, alternate_method

            # Sample outcome from simulator
            recovered = simulate_outcome(
                reason=attempt.error_reason or "unknown",
                method=attempt.method,
                action=action,
                propensity=customer.recovery_propensity,
                rng=rng,
                alternate_method=(
                    recommend_alternate_method(ctx)
                    if action == "alternate_method"
                    else None
                ),
            )

            if recovered:
                status = "recovered"
                break

            attempt_number += 1

            # Next attempt: sample a new reason (in reality this comes from
            # the next webhook). We reuse the simulator's reason distribution
            # for this order's merchant/customer profile.
            from backend.simulator.config_loader import load_config
            sim = load_config()
            reason = rng.choice(list(sim.base_rate.keys()))
            attempt = attempt.__class__(
                payment_id=f"{attempt.payment_id}_{attempt_number}",
                order_id=attempt.order_id,
                attempt_number=attempt_number,
                method=attempt.method,
                status="failed",
                error_code="BAD_REQUEST_PAYMENT_FAILED",
                error_reason=reason,
                error_source="customer",
                error_step="payment_authentication",
            )

        if status != "recovered":
            status = "lost"

        outcomes.append(
            OrderOutcome(
                order_id=order.order_id,
                amount=order.amount,
                final_status=status,
                actions_taken=actions_taken,
            )
        )

    return outcomes


def run_evaluation(
    n_orders: int = 2000,
    seed: int = 42,
) -> EvaluationResult:
    reclaim_outcomes = run_policy(
        PolicyFunction(name="reclaim", select=select_action),
        n_orders=n_orders,
        seed=seed,
    )
    always_retry_outcomes = run_policy(
        PolicyFunction(name="always_retry", select=select_action_always_retry),
        n_orders=n_orders,
        seed=seed,
    )

    return EvaluationResult(
        seed=seed,
        n_orders=n_orders,
        reclaim=compute_metrics("reclaim", reclaim_outcomes),
        always_retry=compute_metrics("always_retry", always_retry_outcomes),
    )
