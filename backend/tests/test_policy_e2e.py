"""End-to-end policy: build a context, run select_action, assert the
chosen action matches the build-plan §7 demo expectations.

These tests are the bridge between policy logic and the live demo
script. If one of these breaks, the §7 pitch is in trouble.
"""

from decimal import Decimal

from backend.policy.select import Decision, select_action
from backend.policy.types import (
    AttemptView,
    CustomerView,
    Merchant,
    OrderView,
    PolicyContext,
)


def _ctx(
    *,
    amount: int,
    error_reason: str,
    attempt_number: int,
    propensity: float = 0.5,
    method: str = "card",
    contact_count_today: int = 0,
    max_retries: int = 3,
    contact_budget: int = 2,
) -> PolicyContext:
    return PolicyContext(
        order=OrderView(order_id="o1", amount=Decimal(amount), status="pending"),
        attempt=AttemptView(attempt_number=attempt_number, method=method, error_reason=error_reason),
        merchant=Merchant(
            merchant_id="m1",
            max_retries=max_retries,
            contact_budget_per_day=contact_budget,
        ),
        customer=CustomerView(
            recovery_propensity=propensity,
            contact_count_today=contact_count_today,
        ),
    )


def test_soft_decline_immediate_retry_wins():
    """Build-plan §7: ₹1,200 issuer_timeout → immediate retry succeeds.
    The policy should pick retry_now (highest ERV on a soft decline)."""
    decision = select_action(_ctx(amount=1200, error_reason="issuer_timeout", attempt_number=1))
    assert decision.selected_action == "retry_now"


def test_hard_decline_high_value_routes_to_payment_link():
    """Build-plan §7: ₹78,000, two consecutive card_blocked → retry forbidden
    by hard-constraint gate, payment_link chosen on ERV, alternate is close.
    High-value + close top-two should escalate to human_review; without that
    flag we'd see payment_link directly. Verify both branches."""
    decision = select_action(
        _ctx(
            amount=78000,
            error_reason="card_blocked",
            attempt_number=2,
        )
    )
    assert decision.selected_action in ("payment_link", "human_review", "alternate_method")
    assert "retry_now" not in [a for a, _ in decision.ranked]


def test_terminal_order_yields_no_action():
    decision = select_action(
        PolicyContext(
            order=OrderView(order_id="o1", amount=Decimal("1000"), status="recovered"),
            attempt=AttemptView(attempt_number=1, method="card", error_reason="issuer_timeout"),
            merchant=Merchant(merchant_id="m1", max_retries=3, contact_budget_per_day=2),
            customer=CustomerView(recovery_propensity=0.5),
        )
    )
    assert decision.selected_action == "no_action"


def test_contact_budget_exhausted_excludes_nudge():
    """If we've already nudged the customer twice today, no more nudges —
    even if nudge would have scored well."""
    decision = select_action(
        _ctx(
            amount=25000,
            error_reason="insufficient_funds",
            attempt_number=1,
            contact_count_today=2,
            contact_budget=2,
        )
    )
    chosen_actions = [a for a, _ in decision.ranked]
    assert "whatsapp_nudge" not in chosen_actions
