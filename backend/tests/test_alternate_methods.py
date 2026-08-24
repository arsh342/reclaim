"""Concrete method recommendations for the alternate-method action."""

from decimal import Decimal

from backend.policy.alternate import recommend_alternate_method
from backend.policy.scoring import expected_value
from backend.policy.select import select_action
from backend.policy.types import (
    AttemptView,
    CustomerView,
    Merchant,
    OrderView,
    PolicyContext,
)


def _ctx(error_reason: str) -> PolicyContext:
    return PolicyContext(
        order=OrderView(order_id="o1", amount=Decimal("1200"), status="pending"),
        attempt=AttemptView(
            attempt_number=1,
            method="card",
            error_reason=error_reason,
        ),
        merchant=Merchant(merchant_id="m1", max_retries=3, contact_budget_per_day=2),
        customer=CustomerView(recovery_propensity=0.5),
    )


def test_hard_card_failures_recommend_upi():
    assert recommend_alternate_method(_ctx("invalid_card")) == "upi"
    assert recommend_alternate_method(_ctx("card_blocked")) == "upi"


def test_other_failures_recommend_another_card():
    assert recommend_alternate_method(_ctx("issuer_timeout")) == "another_card"


def test_invalid_card_can_select_upi_alternate_method():
    ctx = _ctx("invalid_card")

    assert expected_value(ctx, "alternate_method") > 0
    assert select_action(ctx).selected_action == "alternate_method"
