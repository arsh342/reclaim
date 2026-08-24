"""Metrics aggregator for the evaluation runner."""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True)
class PolicyMetrics:
    name: str
    recovered_revenue: Decimal = Decimal("0")
    total_revenue_at_risk: Decimal = Decimal("0")
    recovery_rate: float = 0.0
    unnecessary_interventions: int = 0
    total_interventions: int = 0

    @property
    def revenue_lost(self) -> Decimal:
        return self.total_revenue_at_risk - self.recovered_revenue


@dataclass(frozen=True)
class EvaluationResult:
    seed: int
    n_orders: int
    reclaim: PolicyMetrics
    always_retry: PolicyMetrics

    def delta_recovered_revenue(self) -> Decimal:
        return self.reclaim.recovered_revenue - self.always_retry.recovered_revenue

    def delta_recovery_rate(self) -> float:
        return self.reclaim.recovery_rate - self.always_retry.recovery_rate


@dataclass(frozen=True)
class OrderOutcome:
    order_id: str
    amount: Decimal
    final_status: Literal["recovered", "lost", "pending"]
    actions_taken: list[str]


def compute_metrics(name: str, outcomes: list[OrderOutcome]) -> PolicyMetrics:
    recovered_revenue = sum(o.amount for o in outcomes if o.final_status == "recovered")
    total_revenue_at_risk = sum(o.amount for o in outcomes)
    recovery_rate = (
        float(recovered_revenue) / float(total_revenue_at_risk) if total_revenue_at_risk > 0 else 0.0
    )
    unnecessary = sum(
        1
        for o in outcomes
        if o.final_status == "recovered" and any(a != "no_action" for a in o.actions_taken)
    ) + sum(1 for o in outcomes if o.final_status == "lost" and any(a != "no_action" for a in o.actions_taken))
    total_interventions = sum(1 for o in outcomes if any(a != "no_action" for a in o.actions_taken))

    return PolicyMetrics(
        name=name,
        recovered_revenue=recovered_revenue,
        total_revenue_at_risk=total_revenue_at_risk,
        recovery_rate=recovery_rate,
        unnecessary_interventions=unnecessary,
        total_interventions=total_interventions,
    )