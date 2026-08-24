"""ERV scoring — formula components + monotonicity invariants."""

from decimal import Decimal

from backend.policy.config_loader import load_policy_config
from backend.policy.scoring import expected_value
from backend.policy.types import (
    AttemptView,
    CustomerView,
    Merchant,
    OrderView,
    PolicyContext,
)


def _ctx(*, amount: int = 25000, error_reason: str = "issuer_timeout",
         attempt_number: int = 1, propensity: float = 0.5, method: str = "card") -> PolicyContext:
    return PolicyContext(
        order=OrderView(order_id="o1", amount=Decimal(amount), status="pending"),
        attempt=AttemptView(attempt_number=attempt_number, method=method, error_reason=error_reason),
        merchant=Merchant(merchant_id="m1", max_retries=3, contact_budget_per_day=2),
        customer=CustomerView(recovery_propensity=propensity),
    )


def test_retry_now_has_higher_erv_than_whatsapp_nudge_on_soft_decline():
    """For issuer_timeout + card, immediate retry should beat a WhatsApp nudge.
    Sanity check that the formula respects the action_fit ordering."""
    retry = expected_value(_ctx(), "retry_now")
    nudge = expected_value(_ctx(), "whatsapp_nudge")
    assert retry > nudge


def test_retry_erv_lower_on_hard_decline_than_on_soft_decline():
    """On card_blocked, retry_now's probability is 0, so ERV collapses to just cost.
    On issuer_timeout, retry_now has high probability and positive ERV."""
    hard = expected_value(_ctx(error_reason="card_blocked"), "retry_now")
    soft = expected_value(_ctx(error_reason="issuer_timeout"), "retry_now")
    assert hard < 0  # cost without recovery
    assert soft > 0  # expected recovery minus small cost


def test_higher_recovery_propensity_yields_higher_erv():
    low = expected_value(_ctx(propensity=0.1), "retry_now")
    high = expected_value(_ctx(propensity=0.9), "retry_now")
    assert high > low


def test_higher_order_amount_scales_erv_proportionally():
    small = expected_value(_ctx(amount=10000), "retry_now")
    big = expected_value(_ctx(amount=50000), "retry_now")
    assert big > small


def test_friction_grows_with_attempt_number():
    """Same action, higher attempt number → higher friction → lower ERV."""
    first = expected_value(_ctx(attempt_number=1), "whatsapp_nudge")
    fifth = expected_value(_ctx(attempt_number=5), "whatsapp_nudge")
    assert first > fifth


def test_no_action_and_human_review_return_zero():
    assert expected_value(_ctx(), "no_action") == 0.0
    assert expected_value(_ctx(), "human_review") == 0.0


def test_unknown_error_reason_returns_zero():
    """If we don't know the failure reason, we can't score."""
    ctx = _ctx(error_reason=None)
    assert expected_value(ctx, "retry_now") == 0.0


def test_erv_components_sum_correctly():
    """ERV = p × amount − intervention_cost − friction − risk_penalty.
    Spot-check by recomputing the components."""
    cfg = load_policy_config()
    ctx = _ctx(amount=25000, error_reason="issuer_timeout", propensity=0.5)
    erv = expected_value(ctx, "retry_now")

    from backend.simulator.config_loader import load_config
    sim = load_config()
    p = sim.probability("issuer_timeout", "card", "retry_now", 0.5)
    expected = p * 25000 - cfg.intervention_cost.retry_now - 0 - cfg.risk_penalty.retry_now
    assert abs(erv - expected) < 0.01
