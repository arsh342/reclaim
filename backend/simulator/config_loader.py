"""Simulator config loader."""

import os
from functools import lru_cache
from typing import Optional

import yaml

from backend.simulator.config import SimulatorConfig


CONFIG_PATH = os.path.join(os.path.dirname(__file__), "simulator_config.yaml")


@lru_cache
def load_config(config_path: Optional[str] = None) -> SimulatorConfig:
    """Load simulator config from YAML."""
    path = config_path or CONFIG_PATH
    
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    
    return SimulatorConfig(**data)