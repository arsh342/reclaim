"""Hard-constraint gate.

The constraint gate is the small interface policy exposes: a list of
allowed actions for a given context. Nothing here knows about scores.
Nothing here knows about the LLM. Hard rules only.

Source of truth: docs/reclaim-build-plan.md §4 + docs/reclaim-system-design.md §4.4.
"""

from backend.policy.types import ActionType, ALL_ACTIONS, PolicyContext

HARD_DECLINE_REASONS = frozenset({"card_blocked", "invalid_card", "stolen_card"})


def get_allowed_actions(ctx: PolicyContext) -> list[ActionType]:
    """Return the subset of candidate actions that survive the constraint gate.

    Order of checks matters: terminal state short-circuits to empty.
    Otherwise, drop forbidden actions one by one.
    """
    if ctx.is_terminal:
        return []

    forbidden: set[ActionType] = set()

    if ctx.attempt.attempt_number > ctx.merchant.max_retries:
        forbidden.update({"retry_now", "retry_delayed"})

    if ctx.attempt.error_reason in HARD_DECLINE_REASONS:
        forbidden.update({"retry_now", "retry_delayed"})

    if ctx.customer.contact_count_today >= ctx.merchant.contact_budget_per_day:
        forbidden.add("whatsapp_nudge")

    return [a for a in ALL_ACTIONS if a not in forbidden]
