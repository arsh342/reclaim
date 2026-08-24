"""Evaluation runner tests.

The eval runner is the source of the headline number for the pitch.
Key invariants:
  - Same seed → same metrics (deterministic)
  - Reclaim always beats always_retry on this simulator (the config
    was designed so the policy has signal)
  - Metrics are non-negative and internally consistent
"""

from decimal import Decimal

import pytest

from backend.eval.runner import run_evaluation
from backend.eval.metrics import PolicyMetrics


def test_same_seed_produces_identical_metrics():
    a = run_evaluation(n_orders=100, seed=123)
    b = run_evaluation(n_orders=100, seed=123)
    assert a.reclaim.recovered_revenue == b.reclaim.recovered_revenue
    assert a.always_retry.recovered_revenue == b.always_retry.recovered_revenue
    assert a.reclaim.recovery_rate == b.reclaim.recovery_rate
    assert a.always_retry.recovery_rate == b.always_retry.recovery_rate


def test_reclaim_beats_always_retry():
    """The whole point of the policy is that it outperforms the naive baseline.
    With the current simulator config, this must hold — if it doesn't, the
    config or the policy is broken.
    """
    result = run_evaluation(n_orders=500, seed=42)
    assert result.reclaim.recovery_rate > result.always_retry.recovery_rate
    assert result.reclaim.recovered_revenue > result.always_retry.recovered_revenue


def test_metrics_are_non_negative():
    result = run_evaluation(n_orders=100, seed=99)
    for m in (result.reclaim, result.always_retry):
        assert m.recovered_revenue >= 0
        assert m.recovery_rate >= 0
        assert m.unnecessary_interventions >= 0
        assert m.total_interventions >= 0


def test_metrics_are_internally_consistent():
    result = run_evaluation(n_orders=100, seed=42)
    for m in (result.reclaim, result.always_retry):
        # recovery_rate must match recovered / at_risk (within float precision)
        if m.total_revenue_at_risk > 0:
            expected_rate = float(m.recovered_revenue) / float(m.total_revenue_at_risk)
            assert abs(m.recovery_rate - expected_rate) < 1e-9


def test_delta_computation():
    result = run_evaluation(n_orders=100, seed=42)
    assert result.delta_recovered_revenue() == (
        result.reclaim.recovered_revenue - result.always_retry.recovered_revenue
    )
    assert abs(
        result.delta_recovery_rate()
        - (result.reclaim.recovery_rate - result.always_retry.recovery_rate)
    ) < 1e-9


def test_metrics_object_interface():
    """PolicyMetrics should be a clean dataclass with the right fields."""
    m = PolicyMetrics(
        name="test",
        recovered_revenue=Decimal("1000"),
        total_revenue_at_risk=Decimal("2000"),
        recovery_rate=0.5,
        unnecessary_interventions=5,
        total_interventions=10,
    )
    assert m.name == "test"
    assert m.revenue_lost == Decimal("1000")


def test_eval_summary_endpoint_returns_correct_structure():
    """Verify the API response shape matches the dashboard's expectations."""
    from fastapi.testclient import TestClient
    from backend.api.main import app

    client = TestClient(app)
    response = client.get("/eval/summary?n_orders=50&seed=42")
    assert response.status_code == 200
    data = response.json()

    required_keys = {"seed", "n_orders", "reclaim", "always_retry", "delta"}
    assert set(data.keys()) == required_keys

    for policy in ("reclaim", "always_retry"):
        policy_keys = {"recovered_revenue", "total_revenue_at_risk", "recovery_rate", "unnecessary_interventions",
                       "total_interventions"}
        assert set(data[policy].keys()) == policy_keys

    delta_keys = {"recovered_revenue", "recovery_rate"}
    assert set(data["delta"].keys()) == delta_keys


def test_deterministic_across_runs():
    """Running eval twice in a row with same seed gives identical JSON."""
    from fastapi.testclient import TestClient
    from backend.api.main import app

    client = TestClient(app)
    a = client.get("/eval/summary?n_orders=50&seed=42").json()
    b = client.get("/eval/summary?n_orders=50&seed=42").json()
    assert a == b