"""Gemini provider implementation using google-genai SDK."""

import json
import os
from typing import Any, Dict, Optional

from backend.agent_runtime.provider import LLMProvider


class GeminiProvider(LLMProvider):
    """Gemini provider using google-genai SDK."""
    
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set")
        
        from google import genai
        self.client = genai.Client(api_key=self.api_key)
    
    async def structured_generate(
        self,
        *,
        system: str,
        input: Dict[str, Any],
        schema: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate structured output using Gemini."""
        # If using mock API key, return mock response
        if self.api_key in ("test_key", "mock", "development"):
            return self._mock_response(schema)
        
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=[system, json.dumps(input)],
                config={
                    "response_mime_type": "application/json",
                    "response_schema": schema,
                },
            )
            
            if response.text:
                return json.loads(response.text)
            else:
                return {}
                
        except Exception as e:
            print(f"Gemini API error: {e}")
            return self._mock_response(schema)
    
    def _mock_response(self, schema: Dict[str, Any]) -> Dict[str, Any]:
        """Generate mock response based on schema for development without API key."""
        properties = schema.get("properties", {})
        result = {}
        for key, prop in properties.items():
            prop_type = prop.get("type", "string")
            if prop_type == "string":
                enum_values = prop.get("enum", [])
                result[key] = enum_values[0] if enum_values else f"mock_{key}"
            elif prop_type == "number":
                result[key] = 0.5
            elif prop_type == "integer":
                result[key] = 1
            elif prop_type == "array":
                # Return a mock array with one item based on items schema
                items_schema = prop.get("items", {})
                if items_schema.get("type") == "object":
                    item_props = items_schema.get("properties", {})
                    mock_item = {}
                    for item_key, item_prop in item_props.items():
                        item_type = item_prop.get("type", "string")
                        if item_type == "string":
                            enum_values = item_prop.get("enum", [])
                            mock_item[item_key] = enum_values[0] if enum_values else f"mock_{item_key}"
                        elif item_type == "number":
                            mock_item[item_key] = 0.5
                        elif item_type == "integer":
                            mock_item[item_key] = 1
                        elif item_type == "object":
                            mock_item[item_key] = {}
                        elif item_type == "boolean":
                            mock_item[item_key] = True
                    result[key] = [mock_item]
                else:
                    result[key] = []
            # Special handling for plan steps array - return a valid mock step
            if "steps" in key.lower() or "step" in key.lower() or "candidates" in key.lower():
                if "candidates" in key.lower():
                    result[key] = [{
                        "action": "RETRY_DELAYED",
                        "rationale": "Mock rationale",
                        "params": {"delay_minutes": 240}
                    }]
                else:
                    result[key] = [{
                        "action": "RETRY_DELAYED",
                        "delay_minutes": 240,
                        "condition": None,
                        "params": {}
                    }]
            elif prop_type == "boolean":
                result[key] = True
            elif prop_type == "object":
                result[key] = {}
            else:
                result[key] = None
        return result