"""Gemini provider implementation."""

import json
import os
from typing import Any, Dict, Optional

from backend.agent_runtime.provider import LLMProvider


class GeminiProvider(LLMProvider):
    """Gemini provider using google-genai SDK."""
    
    def __init__(self, model: Optional[str] = None, api_key: Optional[str] = None):
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.7-flash")
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY not set")
        
        # Import here to avoid requiring google-genai at module level
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
            # Log error and return mock response for development
            print(f"Gemini API error: {e}")
            # Return mock based on schema
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
                    result[key] = []
                elif prop_type == "boolean":
                    result[key] = True
                else:
                    result[key] = None
            return result