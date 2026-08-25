"""Tool registry with metadata."""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional


@dataclass
class ToolMetadata:
    name: str
    description: str
    read_only: bool
    financial_side_effect: bool
    params_schema: Dict[str, Any]


class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Callable] = {}
        self._metadata: Dict[str, ToolMetadata] = {}
    
    def register(
        self,
        name: str,
        func: Callable,
        description: str,
        read_only: bool = True,
        financial_side_effect: bool = False,
        params_schema: Optional[Dict[str, Any]] = None,
    ):
        self._tools[name] = func
        self._metadata[name] = ToolMetadata(
            name=name,
            description=description,
            read_only=read_only,
            financial_side_effect=financial_side_effect,
            params_schema=params_schema or {},
        )
    
    async def call(self, name: str, **kwargs) -> Any:
        if name not in self._tools:
            raise ValueError(f"Tool not found: {name}")
        return await self._tools[name](**kwargs)
    
    def get_metadata(self, name: str) -> Optional[ToolMetadata]:
        return self._metadata.get(name)
    
    def list_tools(self) -> List[ToolMetadata]:
        return list(self._metadata.values())
    
    def get_tool(self, name: str) -> Optional[Callable]:
        return self._tools.get(name)


tool_registry = ToolRegistry()