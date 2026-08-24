"""Simulator config loader.

Strict mode: any missing cell raises at load time. The point of having
the config in YAML rather than code is auditable single-source-of-truth;
silent defaults defeat that.
"""

from functools import lru_cache
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

_REASONS = ("insufficient_funds", "issuer_timeout", "card_blocked", "invalid_card", "network_error")
_METHODS = ("card", "upi", "netbanking")
_ACTIONS = ("retry_now", "retry_delayed", "payment_link", "whatsapp_nudge", "alternate_method")
_ALTERNATE_METHODS = ("upi", "another_card")

Reason = Literal[_REASONS]
Method = Literal[_METHODS]
Action = Literal[_ACTIONS]
AlternateMethod = Literal[_ALTERNATE_METHODS]


class CustomerFactor(BaseModel):
    shape: Literal["linear_centered"] = "linear_centered"
    intercept: float = 0.5
    slope: float = 1.0
    min: float = 0.5
    max: float = 1.5

    def multiplier(self, propensity: float) -> float:
        raw = self.intercept + self.slope * propensity
        return max(self.min, min(self.max, raw))


class Clip(BaseModel):
    min: float = 0.0
    max: float = 0.95


class SimulatorConfig(BaseModel):
    base_rate: dict[Reason, float]
    method_factor: dict[Method, float]
    action_fit: dict[Reason, dict[Action, float]]
    alternate_method_fit: dict[Reason, dict[AlternateMethod, float]]
    allowed_zero: frozenset[str] = frozenset()
    customer_factor: CustomerFactor = Field(default_factory=CustomerFactor)
    clip: Clip = Field(default_factory=Clip)

    @field_validator("base_rate", mode="before")
    @classmethod
    def _validate_base_rate(cls, v: dict) -> dict:
        missing = set(_REASONS) - set(v.keys())
        if missing:
            raise ValueError(f"base_rate missing reasons: {missing}")
        return v

    @field_validator("method_factor", mode="before")
    @classmethod
    def _validate_method_factor(cls, v: dict) -> dict:
        missing = set(_METHODS) - set(v.keys())
        if missing:
            raise ValueError(f"method_factor missing methods: {missing}")
        return v

    @field_validator("action_fit", mode="before")
    @classmethod
    def _validate_action_fit(cls, v: dict) -> dict:
        for reason in _REASONS:
            if reason not in v:
                raise ValueError(f"action_fit missing reason: {reason}")
            missing = set(_ACTIONS) - set(v[reason].keys())
            if missing:
                raise ValueError(f"action_fit missing cells for {reason}: {missing}")
        return v

    @field_validator("alternate_method_fit", mode="before")
    @classmethod
    def _validate_alternate_method_fit(cls, v: dict) -> dict:
        for reason in _REASONS:
            if reason not in v:
                raise ValueError(f"alternate_method_fit missing reason: {reason}")
            missing = set(_ALTERNATE_METHODS) - set(v[reason].keys())
            if missing:
                raise ValueError(f"alternate_method_fit missing cells for {reason}: {missing}")
        return v

    @field_validator("allowed_zero", mode="before")
    @classmethod
    def _validate_allowed_zero(cls, v: list[str]) -> frozenset[str]:
        for entry in v:
            reason, _, action = entry.partition(".")
            if reason not in _REASONS or action not in _ACTIONS:
                raise ValueError(f"allowed_zero references unknown cell: {entry}")
        return frozenset(v)

    def customer_multiplier(self, propensity: float) -> float:
        return self.customer_factor.multiplier(propensity)

    def probability(
        self,
        reason: Reason,
        method: Method,
        action: Action,
        propensity: float,
        alternate_method: AlternateMethod | None = None,
    ) -> float:
        try:
            base = self.base_rate[reason]
            method_f = self.method_factor[method]
            action_f = self.action_fit[reason][action]
            if action == "alternate_method":
                selected_method: AlternateMethod = alternate_method or "another_card"
                action_f *= self.alternate_method_fit[reason][selected_method]
        except KeyError as e:
            raise ValueError(f"missing config cell: {e}") from e

        raw = base * method_f * action_f * self.customer_multiplier(propensity)
        return max(self.clip.min, min(self.clip.max, raw))


@lru_cache
def load_config(path: str | None = None) -> SimulatorConfig:
    config_path = Path(path) if path else (Path(__file__).parent / "simulator_config.yaml")
    with open(config_path) as f:
        raw = yaml.safe_load(f)
    return SimulatorConfig(**raw)