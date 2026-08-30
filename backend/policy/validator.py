"""Plan validator - validates AI-generated plans against deterministic policy."""

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession

from backend.policy.constraints import get_allowed_actions, NO_ACTION, HUMAN_REVIEW
from backend.policy.scoring import calculate_expected_value


@dataclass
class ValidationResult:
    approved: bool
    reason: Optional[str] = None
    filtered_steps: Optional[List[dict]] = None


@dataclass
class PlanStep:
    action: str
    delay_minutes: int = 0
    condition: Optional[str] = None
    params: Optional[dict] = None


@dataclass
class RecoveryPlan:
    objective: str
    steps: List[PlanStep]
    stop_conditions: List[str]


def _normalize_plan(plan: Union[dict, RecoveryPlan]) -> RecoveryPlan:
    """Convert dict plan to RecoveryPlan dataclass."""
    if isinstance(plan, RecoveryPlan):
        return plan
    
    # Convert dict to RecoveryPlan
    steps = []
    for step in plan.get("steps", []):
        if isinstance(step, dict):
            steps.append(PlanStep(
                action=step.get("action", ""),
                delay_minutes=step.get("delay_minutes", 0),
                condition=step.get("condition"),
                params=step.get("params", {}),
            ))
        else:
            steps.append(step)
    
    return RecoveryPlan(
        objective=plan.get("objective", ""),
        steps=steps,
        stop_conditions=plan.get("stop_conditions", []),
    )


async def validate_plan(
    session: AsyncSession,
    plan: Union[dict, RecoveryPlan],
    order_id: str,
) -> ValidationResult:
    """Validate a recovery plan against policy."""
    plan_obj = _normalize_plan(plan)
    allowed = await get_allowed_actions(session, order_id)
    
    if not allowed:
        return ValidationResult(
            approved=False,
            reason="No actions allowed for this order",
        )
    
    # Always allow NO_ACTION and HUMAN_REVIEW
    always_allowed = {NO_ACTION, HUMAN_REVIEW}
    
    filtered_steps = []
    for step in plan_obj.steps:
        if step.action in allowed or step.action in always_allowed:
            # For immediate actions, re-check policy
            if step.delay_minutes == 0:
                if step.action not in allowed and step.action not in always_allowed:
                    return ValidationResult(
                        approved=False,
                        reason=f"Immediate action {step.action} not allowed by policy",
                    )
            filtered_steps.append({
                "action": step.action,
                "delay_minutes": step.delay_minutes,
                "condition": step.condition,
                "params": step.params,
            })
        else:
            return ValidationResult(
                approved=False,
                reason=f"Action {step.action} not in allowed actions: {allowed}",
            )
    
    return ValidationResult(
        approved=True,
        filtered_steps=filtered_steps,
    )


async def validate_and_score_plan(
    session: AsyncSession,
    plan: Union[dict, RecoveryPlan],
    order_id: str,
) -> tuple[ValidationResult, List[dict]]:
    """Validate plan and calculate ERV for each step."""
    validation = await validate_plan(session, plan, order_id)
    
    if not validation.approved:
        return validation, []
    
    scored_steps = []
    for step in validation.filtered_steps or []:
        erv = await calculate_expected_value(session, order_id, step["action"])
        step["expected_value"] = float(erv)
        scored_steps.append(step)
    
    return validation, scored_steps