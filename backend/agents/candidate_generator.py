"""Candidate generation agent."""

from typing import Any, Dict, List

from backend.agent_runtime.provider import LLMProvider
from backend.policy.constraints import (
    RETRY_NOW,
    RETRY_DELAYED,
    PAYMENT_LINK,
    WHATSAPP_NUDGE,
    ALTERNATE_METHOD,
    NO_ACTION,
    HUMAN_REVIEW,
)


CANDIDATE_SCHEMA = {
    "type": "object",
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": [RETRY_NOW, RETRY_DELAYED, PAYMENT_LINK, WHATSAPP_NUDGE, ALTERNATE_METHOD, NO_ACTION, HUMAN_REVIEW]
                    },
                    "rationale": {"type": "string"},
                    "params": {"type": "object"},
                },
                "required": ["action", "rationale", "params"],
            },
        },
    },
    "required": ["candidates"],
}


CANDIDATE_SYSTEM_PROMPT = """You are a recovery candidate generator for Reclaim.

Given a failure diagnosis and allowed actions, propose 1-3 relevant recovery interventions.

Actions:
- RETRY_NOW: Immediate retry (for transient errors)
- RETRY_DELAYED: Retry after delay (for insufficient funds)
- PAYMENT_LINK: Send payment link to customer
- WHATSAPP_NUDGE: Send WhatsApp reminder
- ALTERNATE_METHOD: Switch payment method
- NO_ACTION: Do nothing (for hard declines)
- HUMAN_REVIEW: Escalate to human

Only propose actions from the allowed_actions list. Provide rationale and any params (e.g., delay_minutes)."""


async def generate_candidates(
    llm: LLMProvider,
    diagnosis: Dict[str, Any],
    allowed_actions: List[str],
) -> List[Dict[str, Any]]:
    """Generate recovery candidates using LLM."""
    input_data = {
        "diagnosis": diagnosis,
        "allowed_actions": allowed_actions,
    }
    
    result = await llm.structured_generate(
        system=CANDIDATE_SYSTEM_PROMPT,
        input=input_data,
        schema=CANDIDATE_SCHEMA,
    )
    
    # Filter to only allowed actions
    candidates = result.get("candidates", [])
    filtered = [c for c in candidates if c.get("action") in allowed_actions]
    
    # If LLM returns no valid candidates, provide sensible defaults based on allowed actions
    if not filtered:
        # Priority order for default candidates
        default_priority = [RETRY_DELAYED, RETRY_NOW, PAYMENT_LINK, ALTERNATE_METHOD, WHATSAPP_NUDGE, HUMAN_REVIEW, NO_ACTION]
        for action in default_priority:
            if action in allowed_actions:
                filtered = [{"action": action, "rationale": f"Default candidate for {action}", "params": {}}]
                break
    
    return filtered