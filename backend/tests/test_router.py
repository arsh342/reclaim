"""Router + LLM explanation tests.

The router agent composes the five MCP tools and produces a Decision.
The explain layer takes that Decision and produces prose.
These tests verify the seam between deterministic policy and LLM explanation.
"""

from backend.agent.explain import explain_decision
from backend.policy.select import Decision


def _make_decision(**kwargs):
    """Helper to construct Decision with ranked as list of tuples."""
    if "alternatives" in kwargs:
        kwargs["ranked"] = list(kwargs.pop("alternatives").items())
    return Decision(
        selected_action=kwargs.get("selected_action"),
        expected_value=kwargs.get("expected_value"),
        ranked=kwargs.get("ranked", []),
        constraints_applied=kwargs.get("constraints_applied", []),
        reasons=kwargs.get("reasons", []),
    )


def test_explain_uses_only_input_json(monkeypatch):
    """The explanation must only reference fields present in the input Decision."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    decision = _make_decision(
        selected_action="payment_link",
        expected_value=1842.0,
        alternatives={"retry_now": 0.0, "alternate_method": 1690.0},
        constraints_applied=["retry forbidden: hard decline (card_blocked)"],
        reasons=["second failed card attempt on a hard decline", "alternate route has higher simulated recovery probability"],
    )

    result = explain_decision(decision)
    text = result.explanation.lower()

    # Must reference the selected action
    assert "payment link" in text

    # Must reference the constraint
    assert "hard decline" in text or "card_blocked" in text

    # Must reference the expected value
    assert "1842" in text or "1,842" in text


def test_explain_no_action_terminal_state(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    decision = _make_decision(
        selected_action="no_action",
        expected_value=0.0,
        alternatives={},
        constraints_applied=["order status is recovered"],
        reasons=["no actions survive the constraint gate"],
    )
    result = explain_decision(decision)
    text = result.explanation.lower()
    assert "no recovery action" in text or "no action" in text


def test_explain_human_review(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    decision = _make_decision(
        selected_action="human_review",
        expected_value=5000.0,
        alternatives={"payment_link": 5000.0, "alternate_method": 4900.0},
        constraints_applied=["retry forbidden: hard decline"],
        reasons=["high-value order (78000), top two ERVs within 2.0%"],
    )
    result = explain_decision(decision)
    text = result.explanation.lower()
    assert "human review" in text or "escalated" in text
    assert "78000" in text or "high-value" in text


def test_explain_fallback_when_no_api_key(monkeypatch):
    """When no GEMINI_API_KEY, the template fallback should produce valid output."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    decision = _make_decision(
        selected_action="retry_now",
        expected_value=1000.0,
        alternatives={"retry_delayed": 800.0},
        constraints_applied=[],
        reasons=["issuer_timeout on attempt 1: retry_now has highest ERV"],
    )
    result = explain_decision(decision)
    text = result.explanation.lower()
    assert "retry" in text
    assert "1000" in text
    assert result.model == "template-fallback"