"""Simulator configuration models."""

from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class SimulatorConfig(BaseModel):
    base_rate: Dict[str, float]
    method_factor: Dict[str, float]
    action_fit: Dict[str, Dict[str, float]]
    allowed_zero: List[str] = Field(default_factory=list)
    linear_centered: bool = True