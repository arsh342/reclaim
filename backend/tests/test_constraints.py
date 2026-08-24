"""Hard-constraint gate — every rule individually.

Each test exercises one constraint in isolation so a regression points
straight at the rule that broke, not at a tangled scenario.
"""

from decimal import Decimal

import pytest

from backend.policy.constraints import get_allowed_actions
from backend.policy.types import (
    AttemptView,
    CustomerView,
    Merchant,
    OrderView,
    PolicyContext,
)


def _ctx(
    *,
    status: str = "pending",
    attempt_number: int = 1,
    max_retries: int = 3,
    error_reason: str | None = "issuer_timeout",
    contact_count_today: int = 0,
    contact_budget_per_day: int = 2,
) -> PolicyContext:
    return PolicyContext(
        order=OrderView(order_id="o1", amount=Decimal("25000"), status=status),
        attempt=AttemptView(attempt_number=attempt_number, method="card", error_reason=error_reason),
        merchant=Merchant(merchant_id="m1", max_retries=max_retries, contact_budget_per_day=contact_budget_per_day),
        customer=CustomerView(recovery_propensity=0.5, contact_count_today=contact_count_today),
    )


def test_pending_soft_decline_allows_everything():
    allowed = get_allowed_actions(_ctx())
    assert "retry_now" in allowed
    assert "retry_delayed" in allowed
    assert "payment_link" in allowed
    assert "whatsapp_nudge" in allowed
    assert "alternate_method" in allowed
    assert len(allowed) == 5


def test_terminal_order_returns_empty_set():
    assert get_allowed_actions(_ctx(status="recovered")) == []
    assert get_allowed_actions(_ctx(status="lost")) == []


def test_attempts_over_max_retries_forbid_retry():
    ctx = _ctx(attempt_number=4, max_retries=3)
    allowed = get_allowed_actions(ctx)
    assert "retry_now" not in allowed
    assert "retry_delayed" not in allowed
    assert "payment_link" in allowed


def test_hard_decline_forbids_retry():
    for reason in ("card_blocked", "invalid_card", "stolen_card"):
        allowed = get_allowed_actions(_ctx(error_reason=reason))
        assert "retry_now" not in allowed, f"retry_now leaked for {reason}"
        assert "retry_delayed" not in allowed, f"retry_delayed leaked for {reason}"
        assert "payment_link" in allowed
        assert "alternate_method" in allowed


def test_contact_budget_exhausted_forbids_nudge():
    ctx = _ctx(contact_count_today=2, contact_budget_per_day=2)
    allowed = get_allowed_actions(ctx)
    assert "whatsapp_nudge" not in allowed
    assert "retry_now" in allowed


def test_combined_constraints():
    """Hard decline + over budget + high attempt number: only payment_link & alternate."""
    ctx = _ctx(
        attempt_number=5,
        max_retries=3,
        error_reason="card_blocked",
        contact_count_today=5,
        contact_budget_per_day=2,
    )
    allowed = get_allowed_actions(ctx)
    assert set(allowed) == {"payment_link", "alternate_method"}


@pytest.mark.parametrize(
    "status",
    ["recovered", "lost"],
)
def test_terminal_states_have_no_actions(status: str):
    assert get_allowed_actions(_ctx(status=status)) == []
