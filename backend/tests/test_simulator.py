"""Simulator tests.

The two contracts that matter:
  1. Same seed → same dataset AND same outcomes. Two callers running
     `generate_world(n, seed)` then `simulate_outcome(...)` in the same
     order see identical results.
  2. The probability formula is monotonic in obvious directions: more
     propensity → higher expected probability; better-suited action →
     higher probability.
"""

import random

import pytest

from backend.simulator.config_loader import load_config
from backend.simulator.generate import generate_world, simulate_outcome


def test_same_seed_produces_identical_world():
    a = generate_world(n_orders=50, seed=123, attempts_per_order=1)
    b = generate_world(n_orders=50, seed=123, attempts_per_order=1)

    assert len(a.orders) == len(b.orders)
    assert [o.order_id for o in a.orders] == [o.order_id for o in b.orders]
    assert [o.amount for o in a.orders] == [o.amount for o in b.orders]
    assert [a_.error_reason for a_ in a.attempts] == [b_.error_reason for b_ in b.attempts]


def test_same_seed_produces_identical_outcomes():
    world = generate_world(n_orders=50, seed=99, attempts_per_order=1)
    rng_a = random.Random(100)
    rng_b = random.Random(100)

    customers_by_id = {c.customer_id: c for c in world.customers}

    outcomes_a, outcomes_b = [], []
    for attempt in world.attempts:
        order = next(o for o in world.orders if o.order_id == attempt.order_id)
        customer = customers_by_id[order.customer_id]
        outcomes_a.append(
            simulate_outcome(
                reason=attempt.error_reason,
                method=attempt.method,
                action="retry_now",
                propensity=customer.recovery_propensity,
                rng=rng_a,
            )
        )
        outcomes_b.append(
            simulate_outcome(
                reason=attempt.error_reason,
                method=attempt.method,
                action="retry_now",
                propensity=customer.recovery_propensity,
                rng=rng_b,
            )
        )

    assert outcomes_a == outcomes_b


def test_higher_propensity_higher_probability():
    cfg = load_config()
    low = cfg.probability("issuer_timeout", "card", "retry_now", 0.0)
    high = cfg.probability("issuer_timeout", "card", "retry_now", 1.0)
    assert low < high


def test_retry_now_is_better_than_alternate_method_for_soft_decline():
    cfg = load_config()
    retry = cfg.probability("issuer_timeout", "card", "retry_now", 0.5)
    alternate = cfg.probability("issuer_timeout", "card", "alternate_method", 0.5)
    assert retry > alternate


def test_card_blocked_retry_actions_have_zero_probability():
    cfg = load_config()
    assert cfg.probability("card_blocked", "card", "retry_now", 1.0) == 0.0
    assert cfg.probability("card_blocked", "card", "retry_delayed", 1.0) == 0.0
    assert cfg.probability("card_blocked", "card", "alternate_method", 1.0) > 0.0


def test_probability_is_clipped():
    cfg = load_config()
    # network_error with high everything should hit the 0.95 clip ceiling
    p = cfg.probability("network_error", "upi", "retry_now", 1.0)
    assert p <= cfg.clip.max


def test_config_validates_all_cells_present(tmp_path):
    import yaml

    bad = {
        "base_rate": {"issuer_timeout": 0.5},  # missing 4 reasons
        "method_factor": {"card": 1.0},
        "action_fit": {},
        "allowed_zero": [],
        "customer_factor": {"shape": "linear_centered", "intercept": 0.5, "slope": 1.0, "min": 0.5, "max": 1.5},
        "clip": {"min": 0.0, "max": 0.95},
    }
    path = tmp_path / "bad.yaml"
    path.write_text(yaml.safe_dump(bad))

    with pytest.raises(ValueError, match="missing"):
        load_config(str(path))
