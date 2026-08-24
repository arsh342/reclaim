"""Select a concrete payment method for the alternate-method action."""

from typing import Literal

from backend.policy.types import PolicyContext

AlternateMethod = Literal["upi", "another_card"]


def recommend_alternate_method(ctx: PolicyContext) -> AlternateMethod:
    """Choose the least-friction alternate route for the failure context."""
    if ctx.attempt.error_reason in {
        "insufficient_funds",
        "card_blocked",
        "invalid_card",
        "stolen_card",
    }:
        return "upi"
    return "another_card"
