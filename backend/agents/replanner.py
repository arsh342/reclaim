"""Replanning agent."""

from typing import Any, Dict

from backend.agent_runtime.provider import LLMProvider
from backend.agents.planner import PLAN_SCHEMA, PLAN_SYSTEM_PROMPT


REPLAN_SYSTEM_PROMPT = PLAN_SYSTEM_PROMPT + """

The previous plan was rejected by the safety gate. Generate a new plan that respects the constraints.
The rejection reason is provided. Do not propose the same forbidden action."""


async def replan(
    llm: LLMProvider,
    diagnosis: Dict[str, Any],
    counterfactuals: list,
    rejection_reason: str,
) -> Dict[str, Any]:
    """Replan after rejection."""
    input_data = {
        "diagnosis": diagnosis,
        "counterfactuals": counterfactuals,
        "rejection_reason": rejection_reason,
    }
    
    return await llm.structured_generate(
        system=REPLAN_SYSTEM_PROMPT,
        input=input_data,
        schema=PLAN_SCHEMA,
    )