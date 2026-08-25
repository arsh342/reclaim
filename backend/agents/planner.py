"""Recovery planning agent."""

from typing import Any, Dict

from backend.agent_runtime.provider import LLMProvider


PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "objective": {"type": "string"},
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "delay_minutes": {"type": "integer", "minimum": 0},
                    "condition": {"type": "string"},
                    "params": {"type": "object"},
                },
                "required": ["action"],
            },
        },
        "stop_conditions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["objective", "steps", "stop_conditions"],
}


PLAN_SYSTEM_PROMPT = """You are a recovery planner for Reclaim.

Create a bounded recovery plan based on diagnosis and counterfactual evaluations.

Output a plan with:
- objective: e.g., "maximize_expected_recovered_revenue"
- steps: ordered list of actions with delay_minutes, optional condition, and params
- stop_conditions: when to stop (order_recovered, hard_decline, contact_budget_exhausted, max_retries_exceeded)

Example:
{
  "objective": "maximize_expected_recovered_revenue",
  "steps": [
    {"action": "RETRY_DELAYED", "delay_minutes": 240, "condition": null, "params": {}},
    {"action": "PAYMENT_LINK", "delay_minutes": 0, "condition": "retry_failed", "params": {}}
  ],
  "stop_conditions": ["order_recovered", "hard_decline", "contact_budget_exhausted", "max_retries_exceeded"]
}"""


async def create_recovery_plan(
    llm: LLMProvider,
    diagnosis: Dict[str, Any],
    counterfactuals: list,
) -> Dict[str, Any]:
    """Create recovery plan using LLM."""
    input_data = {
        "diagnosis": diagnosis,
        "counterfactuals": counterfactuals,
    }
    
    return await llm.structured_generate(
        system=PLAN_SYSTEM_PROMPT,
        input=input_data,
        schema=PLAN_SCHEMA,
    )