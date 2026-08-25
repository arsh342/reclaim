"""Failure diagnosis agent."""

from typing import Any, Dict

from backend.agent_runtime.provider import LLMProvider


DIAGNOSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "failure_class": {
            "type": "string",
            "enum": ["temporary_financial", "technical", "hard_decline", "customer_action_required", "unknown"]
        },
        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
        "recoverability": {"type": "string", "enum": ["high", "medium", "low"]},
        "key_factors": {"type": "array", "items": {"type": "string"}},
        "candidate_strategy": {"type": "string", "enum": ["immediate_retry", "delayed_retry", "payment_link", "alternate_method", "customer_contact", "no_action"]},
    },
    "required": ["failure_class", "severity", "recoverability", "key_factors", "candidate_strategy"],
}


DIAGNOSIS_SYSTEM_PROMPT = """You are a payment failure diagnosis expert for Reclaim, an AI revenue recovery system.

Analyze the failed payment context and classify the failure. Output ONLY the JSON schema.

Failure classes:
- temporary_financial: insufficient_funds, issuer_timeout, network_error
- technical: gateway_error, processing_error
- hard_decline: card_blocked, invalid_card, stolen_card, expired_card
- customer_action_required: authentication_failed, cvv_mismatch, address_mismatch
- unknown: unclear failure reason

Strategies:
- immediate_retry: for transient issues like network_error
- delayed_retry: for insufficient_funds (wait for funds)
- payment_link: for customer_action_required
- alternate_method: for card issues
- customer_contact: for high-value customers needing nudge
- no_action: for hard_declines"""


async def diagnose_failure(llm: LLMProvider, context: Dict[str, Any]) -> Dict[str, Any]:
    """Diagnose payment failure using LLM."""
    input_data = {
        "order": context.get("order"),
        "attempts": context.get("attempts", []),
        "customer": context.get("customer"),
        "latest_error": context.get("latest_error"),
    }
    
    return await llm.structured_generate(
        system=DIAGNOSIS_SYSTEM_PROMPT,
        input=input_data,
        schema=DIAGNOSIS_SCHEMA,
    )