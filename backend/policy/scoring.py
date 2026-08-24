"""Expected-value scoring.

ERV formula (build-plan §4):
    ERV(action) = P(recovery | context, action) × recoverable_amount
                  − intervention_cost(action)
                  − friction_cost(action, attempt_number)
                  − risk_penalty(action)

The simulator gives us `P(recovery | ...)`. Everything else is config.
The score is a pure function of (context, action) — no I/O, no side
effects. That makes it cheap to test and trivial to reuse.
"""

from decimal import Decimal

from backend.policy.config_loader import load_policy_config
from backend.policy.alternate import recommend_alternate_method
from backend.policy.types import ActionType, PolicyContext
from backend.simulator.config_loader import load_config as load_sim_config


def _friction_for(cfg, action: ActionType, attempt_number: int) -> float:
    base = cfg.friction_cost.per_attempt * max(0, attempt_number - 1)
    if action == "whatsapp_nudge":
        return base * cfg.friction_cost.whatsapp_multiplier
    return base


def expected_value(ctx: PolicyContext, action: ActionType) -> float:
    sim = load_sim_config()
    policy = load_policy_config()

    if action in ("no_action", "human_review"):
        return 0.0

    if ctx.attempt.error_reason is None:
        return 0.0

    alternate_method = (
        recommend_alternate_method(ctx) if action == "alternate_method" else None
    )
    p = sim.probability(
        reason=ctx.attempt.error_reason,
        method=ctx.attempt.method,
        action=action,
        propensity=ctx.customer.recovery_propensity,
        alternate_method=alternate_method,
    )

    recoverable = float(ctx.order.amount)
    cost = policy.cost_for(action)
    friction = _friction_for(policy, action, ctx.attempt.attempt_number)
    risk = policy.risk_for(action)

    return p * recoverable - cost - friction - risk
