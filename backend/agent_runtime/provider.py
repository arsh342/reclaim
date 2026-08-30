"""LLM Provider interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict
import json


class LLMProvider(ABC):
    """Abstract interface for LLM providers."""
    
    @abstractmethod
    async def structured_generate(
        self,
        *,
        system: str,
        input: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate structured output from LLM."""
        pass


class MockLLMProvider(LLMProvider):
    """Mock provider for testing without API calls.
    
    Returns scenario-aware mock responses based on the system prompt
    and input data to enable realistic testing.
    """
    
    async def structured_generate(
        self,
        *,
        system: str,
        input: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        # Determine scenario from system prompt or input
        is_diagnosis = "diagnosis" in system.lower() or "diagnos" in system.lower()
        is_candidates = "candidate" in system.lower() or "candidates" in schema.get("properties", {})
        is_planning = "plan" in system.lower() or "planning" in system.lower()
        is_replanning = "replan" in system.lower()
        
        # Get context from input
        diagnosis = input.get("diagnosis", {})
        allowed_actions = input.get("allowed_actions", [])
        candidates = input.get("candidates", [])
        counterfactuals = input.get("counterfactuals", [])
        rejection_reason = input.get("reason", "")
        
        properties = schema.get("properties", {})
        result = {}
        
        for key, prop in properties.items():
            prop_type = prop.get("type", "string")
            
            if key == "failure_class":
                # Determine failure class from error_reason in context
                context = input.get("context", {})
                latest_error = context.get("latest_error", "")
                if "card_blocked" in latest_error or "invalid_card" in latest_error or "stolen_card" in latest_error:
                    result[key] = "hard_decline"
                elif "insufficient_funds" in latest_error:
                    result[key] = "insufficient_funds"
                elif "timeout" in latest_error or "network_error" in latest_error:
                    result[key] = "soft_decline"
                else:
                    result[key] = "unknown"
            elif key == "severity":
                result[key] = "high" if "card_blocked" in str(input) else "medium"
            elif key == "recoverability":
                context = input.get("context", {})
                latest_error = context.get("latest_error", "")
                if "card_blocked" in latest_error or "invalid_card" in latest_error or "stolen_card" in latest_error:
                    result[key] = "non_recoverable"
                elif "insufficient_funds" in latest_error:
                    result[key] = "recoverable_with_method_change"
                else:
                    result[key] = "recoverable"
            elif key == "key_factors":
                result[key] = ["mock_factor"]
            elif key == "candidate_strategy":
                context = input.get("context", {})
                latest_error = context.get("latest_error", "")
                if "card_blocked" in latest_error or "invalid_card" in latest_error or "stolen_card" in latest_error:
                    result[key] = "use_alternate_method_or_payment_link"
                elif "insufficient_funds" in latest_error:
                    result[key] = "retry_delayed_or_alternate_method"
                else:
                    result[key] = "retry_with_delay"
            elif key == "candidates":
                # Generate candidates based on allowed actions
                if allowed_actions:
                    # For hard declines, don't suggest retries
                    context = input.get("context", {})
                    latest_error = context.get("latest_error", "")
                    is_hard_decline = any(h in latest_error for h in ["card_blocked", "invalid_card", "stolen_card", "expired_card"])
                    
                    mock_candidates = []
                    for action in allowed_actions:
                        if is_hard_decline and action in ["RETRY_NOW", "RETRY_DELAYED"]:
                            continue
                        mock_candidates.append({
                            "action": action,
                            "rationale": f"Mock rationale for {action}",
                            "params": {"delay_minutes": 240} if action == "RETRY_DELAYED" else {}
                        })
                        if len(mock_candidates) >= 3:
                            break
                    
                    if not mock_candidates and allowed_actions:
                        mock_candidates = [{
                            "action": allowed_actions[0],
                            "rationale": f"Default for {allowed_actions[0]}",
                            "params": {}
                        }]
                    
                    result[key] = mock_candidates
                else:
                    result[key] = []
            elif key == "objective":
                result[key] = "maximize_expected_recovered_revenue"
            elif key == "steps":
                # Generate plan steps based on counterfactuals
                if counterfactuals:
                    # Pick best counterfactual
                    best = max(counterfactuals, key=lambda c: c.get("expected_value", 0))
                    best_action = best.get("action", "RETRY_DELAYED")
                    result[key] = [{
                        "action": best_action,
                        "delay_minutes": 240 if best_action == "RETRY_DELAYED" else 0,
                        "condition": None,
                        "params": {}
                    }]
                elif allowed_actions:
                    # Default to first allowed action that's not NO_ACTION/HUMAN_REVIEW
                    for action in allowed_actions:
                        if action not in ["NO_ACTION", "HUMAN_REVIEW"]:
                            result[key] = [{
                                "action": action,
                                "delay_minutes": 240 if action == "RETRY_DELAYED" else 0,
                                "condition": None,
                                "params": {}
                            }]
                            break
                    else:
                        result[key] = [{
                            "action": "NO_ACTION",
                            "delay_minutes": 0,
                            "condition": None,
                            "params": {}
                        }]
                else:
                    result[key] = [{
                        "action": "NO_ACTION",
                        "delay_minutes": 0,
                        "condition": None,
                        "params": {}
                    }]
            elif key == "stop_conditions":
                result[key] = ["order_recovered", "hard_decline", "contact_budget_exhausted", "max_retries_exceeded"]
            elif prop_type == "string":
                result[key] = f"mock_{key}"
            elif prop_type == "number":
                result[key] = 0.5
            elif prop_type == "integer":
                result[key] = 1
            elif prop_type == "array":
                result[key] = []
            elif prop_type == "boolean":
                result[key] = True
            else:
                result[key] = None
        
        return result