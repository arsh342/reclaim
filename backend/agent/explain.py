"""LLM Explanation Layer — Gemini API call wrapper.

Receives the deterministic decision as structured JSON, returns a
human-readable prose explanation. The prompt strictly forbids the model
from asserting anything not present in the input JSON.

This is the ONLY place the LLM touches the pipeline. No financial state
transitions happen here.
"""

import json
import os
from dataclasses import dataclass

try:
    from google import genai
    _GEMINI_AVAILABLE = True
except ImportError:
    _GEMINI_AVAILABLE = False


@dataclass(frozen=True)
class ExplanationResult:
    explanation: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


SYSTEM_PROMPT = """You are an expert payment recovery analyst. You receive a deterministic decision JSON from the Reclaim recovery engine. Your ONLY job is to explain that decision in clear, professional prose.

RULES — NEVER VIOLATE:
1. NEVER assert anything not explicitly present in the input JSON.
2. NEVER invent probabilities, amounts, or reasons.
3. NEVER recommend a different action than `selected_action`.
4. If the input says `human_review`, explain WHY it was escalated (high value + close ERVs).
5. If the input says `no_action`, explain WHY (terminal state, no allowed actions, or negative ERV).
6. Reference the specific constraints from `constraints_applied` by name.
7. Keep it to 2-3 sentences. Professional tone, no hedging.

Input JSON schema:
{
  "selected_action": "retry_now|retry_delayed|payment_link|whatsapp_nudge|alternate_method|no_action|human_review",
  "expected_value": number,
  "alternatives": {"action": erv, ...},
  "constraints_applied": ["constraint description", ...],
  "reasons": ["reason description", ...]
}"""

GEMINI_MODEL = "gemini-3.6-flash"


def _format_decision_json(decision) -> str:
    """Serialize the decision dataclass to the exact JSON the prompt expects."""
    return json.dumps(
        {
            "selected_action": decision.selected_action,
            "expected_value": round(decision.expected_value, 2),
            "alternatives": {k: round(v, 2) for k, v in decision.ranked},
            "constraints_applied": decision.constraints_applied,
            "reasons": decision.reasons,
        },
        indent=2,
    )


_ACTION_TERMS = {
    "retry_now": ("retry",),
    "retry_delayed": ("retry", "delay"),
    "payment_link": ("payment link",),
    "whatsapp_nudge": ("whatsapp", "nudge"),
    "alternate_method": ("alternate", "method"),
    "human_review": ("human review", "review"),
    "no_action": ("no action", "no recovery"),
}


def _is_usable_explanation(text: str, decision) -> bool:
    """Reject truncated or unrelated model output before it reaches the DB."""
    normalized = " ".join(text.split()).strip()
    if len(normalized) < 80 or normalized.endswith(("`", "...")):
        return False

    lowered = normalized.lower()
    return any(term in lowered for term in _ACTION_TERMS.get(decision.selected_action, ()))


def explain_decision(decision) -> ExplanationResult:
    """Call Gemini with the decision JSON, return the explanation."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or not _GEMINI_AVAILABLE:
        # Deterministic fallback for tests / when no key
        return ExplanationResult(
            explanation=_template_fallback(decision),
            model="template-fallback",
        )

    client = genai.Client(api_key=api_key)
    prompt = SYSTEM_PROMPT + "\n\nDecision JSON:\n" + _format_decision_json(decision)

    try:
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=200,
                response_mime_type="text/plain",
                automatic_function_calling=genai.types.AutomaticFunctionCallingConfig(
                    disable=True,
                ),
                thinking_config=genai.types.ThinkingConfig(
                    thinking_level=genai.types.ThinkingLevel.MINIMAL,
                ),
            ),
        )
        text = response.text.strip() if response.text else ""
        if not _is_usable_explanation(text, decision):
            return ExplanationResult(
                explanation=_template_fallback(decision),
                model=f"{GEMINI_MODEL} (invalid response fallback)",
            )
        return ExplanationResult(
            explanation=text,
            model=GEMINI_MODEL,
            prompt_tokens=0,  # not exposed by genai SDK in this version
            completion_tokens=0,
        )
    except Exception:
        return ExplanationResult(
            explanation=_template_fallback(decision),
            model=f"{GEMINI_MODEL} (fallback)",
        )


def _template_fallback(decision) -> str:
    """Deterministic template explanation — used when no API key or LLM fails.
    Mirrors the exact structure the prompt asks for."""
    action = decision.selected_action
    ev = round(decision.expected_value)
    constraints = "; ".join(decision.constraints_applied) if decision.constraints_applied else "none"
    reasons = "; ".join(decision.reasons) if decision.reasons else "no reason recorded"

    if action == "no_action":
        reason = decision.reasons[0] if decision.reasons else "no action met the policy threshold"
        return f"No recovery action was taken — {reason}."
    if action == "human_review":
        return f"This order was escalated for human review because it exceeds the high-value threshold and the top two recovery actions have similar expected values. Constraints: {constraints}."
    if action == "retry_now":
        return f"An immediate retry was chosen — this is the {decision.reasons[0] if decision.reasons else 'best action'} with the highest expected recovery value of ₹{ev}. Constraints: {constraints}."
    if action == "retry_delayed":
        return f"A delayed retry was scheduled — {decision.reasons[0] if decision.reasons else 'this action has the highest expected recovery value'} (ERV ₹{ev}). Constraints: {constraints}."
    if action == "payment_link":
        return f"A payment link recovery was chosen — {decision.reasons[0] if decision.reasons else 'it has the highest expected recovery value'} (ERV ₹{ev}) instead of retrying. Constraints: {constraints}."
    if action == "whatsapp_nudge":
        return f"A WhatsApp nudge was sent — {decision.reasons[0] if decision.reasons else 'it has the highest expected recovery value'} (ERV ₹{ev}). Constraints: {constraints}."
    if action == "alternate_method":
        return f"An alternate payment method was offered — {decision.reasons[0] if decision.reasons else 'it has the highest expected recovery value'} (ERV ₹{ev}) instead of retrying the original. Constraints: {constraints}."

    return f"Action {action} selected with expected value ₹{ev}. Constraints: {constraints}."
