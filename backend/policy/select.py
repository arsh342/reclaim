"""Action selection: rank allowed actions by ERV, then apply NO_ACTION
and HUMAN_REVIEW rules.

The hard cut between constraints and scoring lives here: we never fold
constraint logic into the score (build-plan §4). HUMAN_REVIEW is a
post-score routing decision, not a constraint — the constraint gate
never says "forbid all actions", it says "this action has zero chance
of helping".
"""

from dataclasses import dataclass

from backend.policy.config_loader import load_policy_config
from backend.policy.constraints import get_allowed_actions
from backend.policy.scoring import expected_value
from backend.policy.types import ActionType, PolicyContext


@dataclass(frozen=True)
class Decision:
    selected_action: ActionType
    expected_value: float
    ranked: list[tuple[ActionType, float]]
    constraints_applied: list[str]
    reasons: list[str]


def select_action(ctx: PolicyContext) -> Decision:
    policy = load_policy_config()
    allowed = get_allowed_actions(ctx)
    constraints_applied = _collect_constraints(ctx)

    if not allowed:
        return Decision(
            selected_action="no_action",
            expected_value=0.0,
            ranked=[],
            constraints_applied=constraints_applied,
            reasons=["no actions survive the constraint gate"],
        )

    scored = [(action, expected_value(ctx, action)) for action in allowed]
    scored.sort(key=lambda x: x[1], reverse=True)
    top_action, top_erv = scored[0]

    if top_erv <= policy.no_action_threshold:
        return Decision(
            selected_action="no_action",
            expected_value=top_erv,
            ranked=scored,
            constraints_applied=constraints_applied,
            reasons=[f"top ERV {top_erv:.0f} ≤ no_action_threshold"],
        )

    if (
        len(scored) >= 2
        and float(ctx.order.amount) >= policy.human_review.high_value_threshold
    ):
        second_erv = scored[1][1]
        gap_fraction = (top_erv - second_erv) / max(abs(top_erv), 1e-9)
        if gap_fraction < policy.human_review.erv_gap_fraction:
            return Decision(
                selected_action="human_review",
                expected_value=top_erv,
                ranked=scored,
                constraints_applied=constraints_applied,
                reasons=[
                    f"high-value order ({float(ctx.order.amount):.0f}), "
                    f"top two ERVs within {gap_fraction:.1%}",
                ],
            )

    reasons = _reasons_for(ctx, top_action, scored)
    return Decision(
        selected_action=top_action,
        expected_value=top_erv,
        ranked=scored,
        constraints_applied=constraints_applied,
        reasons=reasons,
    )


def _collect_constraints(ctx: PolicyContext) -> list[str]:
    notes: list[str] = []
    if ctx.is_terminal:
        notes.append(f"order status is {ctx.order.status}")
    if ctx.attempt.attempt_number > ctx.merchant.max_retries:
        notes.append(
            f"attempt_number ({ctx.attempt.attempt_number}) > max_retries ({ctx.merchant.max_retries})"
        )
    if ctx.attempt.error_reason in {"card_blocked", "invalid_card", "stolen_card"}:
        notes.append(f"retry forbidden: hard decline ({ctx.attempt.error_reason})")
    if ctx.customer.contact_count_today >= ctx.merchant.contact_budget_per_day:
        notes.append(
            f"nudge forbidden: contact budget exhausted "
            f"({ctx.customer.contact_count_today}/{ctx.merchant.contact_budget_per_day})"
        )
    return notes


def _reasons_for(
    ctx: PolicyContext, top_action: ActionType, scored: list[tuple[ActionType, float]]
) -> list[str]:
    reasons: list[str] = []
    reasons.append(
        f"{ctx.attempt.error_reason or 'unknown'} on attempt {ctx.attempt.attempt_number}: "
        f"{top_action} has highest ERV"
    )
    if len(scored) >= 2:
        second = scored[1]
        reasons.append(
            f"next best {second[0]} ERV {second[1]:.0f}, "
            f"gap {scored[0][1] - second[1]:.0f}"
        )
    return reasons
