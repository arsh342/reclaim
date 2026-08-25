"""LLM Provider interface."""

from abc import ABC, abstractmethod
from typing import Any, Dict


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
    """Mock provider for testing without API calls."""
    
    async def structured_generate(
        self,
        *,
        system: str,
        input: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        # Return mock responses based on schema
        properties = schema.get("properties", {})
        result = {}
        for key, prop in properties.items():
            prop_type = prop.get("type", "string")
            if prop_type == "string":
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