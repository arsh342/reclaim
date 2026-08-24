"""Router Agent — the orchestration loop.

The agent is a thin, deterministic coordinator. It does NOT make
financial decisions. It calls the five MCP tools in sequence:
  1. get_order_context
  2. get_allowed_actions
  3. estimate_recovery for each allowed action
  4. select_action (the deterministic policy engine)
  5. execute_recovery_action (if action is not no_action/human_review)

The LLM sits AFTER this loop — it receives the Decision JSON and
produces ONLY the explanation. The LLM never decides an action.

Source of truth: docs/reclaim-build-plan.md §6 + docs/reclaim-system-design.md §4.3.
"""

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.agent.tools import (
    AllowedActionsResult,
    EstimateRecoveryResult,
    ExecuteRecoveryResult,
    OrderContext,
    cancel_pending_action,
    execute_recovery_action,
    estimate_recovery,
    get_allowed_actions,
    get_order_context,
)
from backend.db.models import Order, Customer, PaymentAttempt
from backend.policy.select import Decision, select_action
from backend.policy.types import (
    PolicyContext,
    OrderView,
    AttemptView,
    Merchant as MerchantView,
    CustomerView,
)
from backend.db.models import Merchant as MerchantModel


@dataclass(frozen=True)
class AgentDecision:
    """The output of the router agent — deterministic decision + execution result.
    Explanation is generated separately by the webhook handler via explain_decision()."""
    order_id: str
    selected_action: str
    expected_value: float
    alternatives: dict[str, float]
    constraints_applied: list[str]
    reasons: list[str]
    action_id: int | None


def run_agent(db: Session, order_id: str) -> AgentDecision:
    """Orchestration loop: context → allowed → estimate each → select → execute.
    Does NOT generate explanation — that's the webhook handler's responsibility."""
    # 1. Get full context (for tool calls)
    context = get_order_context(db, order_id)

    # 2. Hard-constraint gate
    allowed_result = get_allowed_actions(db, order_id)

    # 3. Score each allowed action
    estimates: dict[str, EstimateRecoveryResult] = {}
    for action in allowed_result.allowed_actions:
        estimates[action] = estimate_recovery(db, order_id, action)

    # 4. Build PolicyContext for the deterministic selector
    order = db.execute(select(Order).where(Order.order_id == order_id)).scalar_one()
    merchant = db.execute(select(MerchantModel).where(MerchantModel.merchant_id == order.merchant_id)).scalar_one_or_none()
    customer = None
    if order.customer_id and order.customer_id.strip():
        customer = db.execute(select(Customer).where(Customer.customer_id == order.customer_id)).scalar_one_or_none()
    attempt = db.execute(
        select(PaymentAttempt)
        .where(PaymentAttempt.order_id == order_id)
        .order_by(PaymentAttempt.attempt_number.desc())
        .limit(1)
    ).scalar_one()

    policy_ctx = PolicyContext(
        order=OrderView(order_id=order.order_id, amount=order.amount, status=order.status),
        attempt=AttemptView(
            attempt_number=attempt.attempt_number,
            method=attempt.method,
            error_reason=attempt.error_reason,
        ),
        merchant=MerchantView(
            merchant_id=merchant.merchant_id if merchant else "default",
            max_retries=merchant.max_retries if merchant else 3,
            contact_budget_per_day=merchant.contact_budget_per_day if merchant else 2,
        ),
        customer=CustomerView(
            recovery_propensity=float(customer.recovery_propensity) if customer else 0.5,
            contact_count_today=0,
        ),
    )

    # 5. Deterministic selection (includes NO_ACTION / HUMAN_REVIEW)
    decision = select_action(policy_ctx)

    # 6. Execute if actionable
    exec_result = None
    if decision.selected_action not in ("no_action", "human_review"):
        exec_result = execute_recovery_action(db, order_id, decision.selected_action)

    # 7. Build AgentDecision for webhook handler + API
    return AgentDecision(
        order_id=order_id,
        selected_action=decision.selected_action,
        expected_value=decision.expected_value,
        alternatives=dict(decision.ranked),
        constraints_applied=decision.constraints_applied,
        reasons=decision.reasons,
        action_id=(exec_result.action_id if exec_result and exec_result.action_id > 0 else None),
    )
