"""Policy engine — config loader."""

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


@dataclass(frozen=True)
class InterventionCost:
    retry_now: float
    retry_delayed: float
    payment_link: float
    whatsapp_nudge: float
    alternate_method: float
    no_action: float
    human_review: float


@dataclass(frozen=True)
class FrictionCost:
    per_attempt: float
    whatsapp_multiplier: float


@dataclass(frozen=True)
class RiskPenalty:
    retry_now: float
    retry_delayed: float
    payment_link: float
    whatsapp_nudge: float
    alternate_method: float
    no_action: float
    human_review: float


@dataclass(frozen=True)
class HumanReview:
    high_value_threshold: float
    erv_gap_fraction: float


@dataclass(frozen=True)
class PolicyConfig:
    intervention_cost: InterventionCost
    friction_cost: FrictionCost
    risk_penalty: RiskPenalty
    human_review: HumanReview
    no_action_threshold: float

    def cost_for(self, action: str) -> float:
        return getattr(self.intervention_cost, action, 0.0)

    def risk_for(self, action: str) -> float:
        return getattr(self.risk_penalty, action, 0.0)


@lru_cache
def load_policy_config(path: str | None = None) -> PolicyConfig:
    config_path = Path(path) if path else (Path(__file__).parent / "policy_config.yaml")
    with open(config_path) as f:
        raw = yaml.safe_load(f)

    return PolicyConfig(
        intervention_cost=InterventionCost(**raw["intervention_cost"]),
        friction_cost=FrictionCost(**raw["friction_cost"]),
        risk_penalty=RiskPenalty(**raw["risk_penalty"]),
        human_review=HumanReview(**raw["human_review"]),
        no_action_threshold=raw["no_action_threshold"],
    )
