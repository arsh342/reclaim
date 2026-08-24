"""MCP Tool Functions — the five functions the router agent calls.

These are the tool surface defined in build-plan §6. Each is a pure
function over the database (or simulated world for estimate_recovery).
The router agent composes them; they have no agent logic themselves.

Source of truth: docs/reclaim-build-plan.md §6 + docs/reclaim-system-design.md §4.3.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from backend.agent.query_repo import QueryRepository
from backend.db.models import (
    Customer,
    Merchant,
    Order,
    PaymentAttempt,
    RecoveryAction,
    WebhookEvent,
)
from backend.policy.alternate import recommend_alternate_method
from backend.policy.constraints import get_allowed_actions as policy_get_allowed_actions
from backend.policy.select import Decision, select_action
from backend.policy.scoring import expected_value
from backend.policy.types import (
    ActionType,
    AttemptView,
    CustomerView,
    Merchant as MerchantView,
    OrderView,
    PolicyContext,
)
from backend.simulator.config_loader import load_config as load_sim_config


@dataclass(frozen=True)
class OrderContext:
    order_id: str
    status: str
    amount: Decimal
    currency: str
    merchant: dict
    customer: dict
    attempts: list[dict]


@dataclass(frozen=True)
class AllowedActionsResult:
    allowed_actions: list[ActionType]
    constraints_applied: list[str]


@dataclass(frozen=True)
class EstimateRecoveryResult:
    probability: float
    recoverable_amount: float
    cost: float
    friction: float
    risk_penalty: float
    expected_value: float


@dataclass(frozen=True)
class ExecuteRecoveryResult:
    action_id: int
    order_id: str
    action_type: str
    expected_value: float
    status: str
    executed_at: Optional[str] = None
    scheduled_at: Optional[str] = None
    reason: Optional[str] = None


# ----------------------------------------------------------------------
# Tool 1: get_order_context
# ----------------------------------------------------------------------
def get_order_context(db: Session, order_id: str) -> OrderContext:
    repo = QueryRepository(db)
    ctx = repo.get_order_context(order_id)

    return OrderContext(
        order_id=ctx["order"].order_id,
        status=ctx["order"].status,
        amount=ctx["order"].amount,
        currency=ctx["order"].currency,
        merchant={
            "merchant_id": ctx["merchant"].merchant_id if ctx["merchant"] else None,
            "max_retries": ctx["merchant"].max_retries if ctx["merchant"] else 3,
            "contact_budget_per_day": ctx["merchant"].contact_budget_per_day if ctx["merchant"] else 2,
        } if ctx["merchant"] else {},
        customer={
            "customer_id": ctx["customer"].customer_id if ctx["customer"] else None,
            "recovery_propensity": float(ctx["customer"].recovery_propensity) if ctx["customer"] else 0.5,
            "payment_method_preference": ctx["customer"].payment_method_preference if ctx["customer"] else "card",
            "historical_success_rate": float(ctx["customer"].historical_success_rate) if ctx["customer"] else 0.5,
            "customer_value": float(ctx["customer"].customer_value) if ctx["customer"] else 0.0,
        } if ctx["customer"] else {},
        attempts=[
            {
                "payment_id": a.payment_id,
                "attempt_number": a.attempt_number,
                "method": a.method,
                "status": a.status,
                "error_code": a.error_code,
                "error_reason": a.error_reason,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in ctx["attempts"]
        ],
    )


# ----------------------------------------------------------------------
# Tool 2: get_allowed_actions
# ----------------------------------------------------------------------
def get_allowed_actions(db: Session, order_id: str) -> AllowedActionsResult:
    repo = QueryRepository(db)
    ctx = repo.get_allowed_actions_context(order_id)

    policy_ctx = repo.build_allowed_actions_policy_ctx(order_id)

    actions = policy_get_allowed_actions(policy_ctx)
    constraints = _collect_constraints(policy_ctx)

    return AllowedActionsResult(
        allowed_actions=actions,
        constraints_applied=constraints,
    )


# ----------------------------------------------------------------------
# Tool 3: estimate_recovery
# ----------------------------------------------------------------------
def estimate_recovery(db: Session, order_id: str, action: ActionType) -> EstimateRecoveryResult:
    repo = QueryRepository(db)
    ctx = repo.get_estimate_recovery_context(order_id)

    sim = load_sim_config()
    policy = load_policy_config()

    policy_ctx = repo.build_estimate_recovery_policy_ctx(order_id)

    alternate_method = (
        recommend_alternate_method(policy_ctx) if action == "alternate_method" else None
    )
    p = sim.probability(
        reason=ctx["attempt"].error_reason or "unknown",
        method=ctx["attempt"].method,
        action=action,
        propensity=policy_ctx.customer.recovery_propensity,
        alternate_method=alternate_method,
    )

    recoverable = float(ctx["order"].amount)
    cost = policy.cost_for(action)
    friction = _friction_for(policy, action, ctx["attempt"].attempt_number)
    risk = policy.risk_for(action)
    ev = p * recoverable - cost - friction - risk

    return EstimateRecoveryResult(
        probability=p,
        recoverable_amount=recoverable,
        cost=cost,
        friction=friction,
        risk_penalty=risk,
        expected_value=ev,
    )


# ----------------------------------------------------------------------
# Tool 4: execute_recovery_action
# ----------------------------------------------------------------------
def execute_recovery_action(db: Session, order_id: str, action: ActionType) -> ExecuteRecoveryResult:
    """Idempotent execution: checks order status first, no-ops if already resolved,
    row-locks on order_id. Returns the created or existing recovery action."""
    repo = QueryRepository(db)

    # Row-lock the order
    order = repo.get_order_locked(order_id)

    if order is None:
        raise ValueError(f"order {order_id} not found")

    # If already resolved, return existing or no-op
    if order.status in ("recovered", "lost"):
        existing = db.execute(
            select(RecoveryAction)
            .where(RecoveryAction.order_id == order_id, RecoveryAction.action_type == action)
            .order_by(RecoveryAction.scheduled_at.desc())
        ).scalar_one_or_none()
        if existing:
            return ExecuteRecoveryResult(
                action_id=existing.action_id,
                order_id=order_id,
                action_type=existing.action_type,
                expected_value=float(existing.expected_value),
                status=existing.status,
                executed_at=existing.executed_at.isoformat() if existing.executed_at else None,
            )
        return ExecuteRecoveryResult(
            action_id=-1,
            order_id=order_id,
            action_type=action,
            expected_value=0.0,
            status="no_action",
            reason=f"order already {order.status}",
        )

    # Compute expected value for this action
    ctx = repo.get_execute_recovery_context(order_id, lock=True)
    policy_ctx = repo.build_execute_recovery_policy_ctx(order_id, lock=True)

    ev = expected_value(policy_ctx, action)

    # Check if this exact action was already scheduled
    existing = db.execute(
        select(RecoveryAction)
        .where(
            RecoveryAction.order_id == order_id,
            RecoveryAction.action_type == action,
            RecoveryAction.status == "scheduled",
        )
    ).scalar_one_or_none()

    if existing:
        return ExecuteRecoveryResult(
            action_id=existing.action_id,
            order_id=order_id,
            action_type=action,
            expected_value=float(existing.expected_value),
            status="scheduled",
            scheduled_at=existing.scheduled_at.isoformat() if existing.scheduled_at else None,
        )

    # Create new scheduled action
    new_action = RecoveryAction(
        order_id=order_id,
        action_type=action,
        expected_value=Decimal(str(ev)),
        status="scheduled",
    )
    db.add(new_action)
    db.flush()

    return ExecuteRecoveryResult(
        action_id=new_action.action_id,
        order_id=order_id,
        action_type=action,
        expected_value=ev,
        status="scheduled",
        scheduled_at=new_action.scheduled_at.isoformat() if new_action.scheduled_at else None,
    )


# ----------------------------------------------------------------------
# Tool 5: cancel_pending_action
# ----------------------------------------------------------------------
def cancel_pending_action(db: Session, order_id: str) -> None:
    """Called automatically when an order is recovered — cancels all scheduled
    recovery actions for that order. Idempotent: safe to call multiple times."""
    db.execute(
        update(RecoveryAction)
        .where(
            RecoveryAction.order_id == order_id,
            RecoveryAction.status == "scheduled",
        )
        .values(
            status="cancelled",
            cancelled_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            reason="order recovered",
        )
    )


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _collect_constraints(ctx: PolicyContext) -> list[str]:
    notes: list[str] = []
    if ctx.is_terminal:
        notes.append(f"order status is {ctx.order.status}")
    if ctx.attempt.attempt_number > ctx.merchant.max_retries:
        notes.append(f"attempt_number ({ctx.attempt.attempt_number}) > max_retries ({ctx.merchant.max_retries})")
    if ctx.attempt.error_reason in {"card_blocked", "invalid_card", "stolen_card"}:
        notes.append(f"retry forbidden: hard decline ({ctx.attempt.error_reason})")
    if ctx.customer.contact_count_today >= ctx.merchant.contact_budget_per_day:
        notes.append(
            f"nudge forbidden: contact budget exhausted ({ctx.customer.contact_count_today}/{ctx.merchant.contact_budget_per_day})"
        )
    return notes


def _friction_for(policy, action: ActionType, attempt_number: int) -> float:
    from backend.policy.config_loader import FrictionCost
    base = policy.friction_cost.per_attempt * max(0, attempt_number - 1)
    if action == "whatsapp_nudge":
        return base * policy.friction_cost.whatsapp_multiplier
    return base


# ----------------------------------------------------------------------
# Config loader import (inline to avoid circular)
# ----------------------------------------------------------------------
def load_policy_config():
    from backend.policy.config_loader import load_policy_config as _load
    return _load()