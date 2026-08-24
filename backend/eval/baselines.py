"""Naive baseline policy: always_retry.

Same interface as the real policy engine so the eval runner can swap
them without code changes. The only difference: constraints and scoring
are replaced by a single hardcoded choice.
"""

from backend.policy.select import Decision
from backend.policy.types import ActionType, PolicyContext

ALWAYS_RETRY_ACTION: ActionType = "retry_now"


def select_action_always_retry(ctx: PolicyContext) -> Decision:
    """Always returns RETRY_NOW if allowed, otherwise NO_ACTION."""
    if ctx.is_terminal:
        return Decision(
            selected_action="no_action",
            expected_value=0.0,
            ranked=[],
            constraints_applied=["order status is " + ctx.order.status],
            reasons=["order already resolved"],
        )

    # Check if retry_now is forbidden by constraints
    from backend.policy.constraints import get_allowed_actions
    allowed = get_allowed_actions(ctx)

    if ALWAYS_RETRY_ACTION in allowed:
        return Decision(
            selected_action=ALWAYS_RETRY_ACTION,
            expected_value=1.0,  # placeholder; real value computed by evaluator
            ranked=[(ALWAYS_RETRY_ACTION, 1.0)],
            constraints_applied=[],
            reasons=["always_retry baseline: retry_now allowed"],
        )

    return Decision(
        selected_action="no_action",
        expected_value=0.0,
        ranked=[],
        constraints_applied=[],
        reasons=["always_retry baseline: retry_now forbidden by constraints"],
    )