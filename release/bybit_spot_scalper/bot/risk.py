from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class PositionPlan:
    base_allocation_usd: float
    entry_allocation_usd: float
    dca_allocations_usd: List[float]
    dca_steps_down_pct: List[float]


def compute_position_plan(
    total_budget_usd: float,
    risk_per_trade_pct: float,
    dca_levels: int,
    dca_step_pcts: List[float],
) -> PositionPlan:
    risk_budget = total_budget_usd * (risk_per_trade_pct / 100.0)
    # Allocate 60% to initial, remaining across DCA levels equally
    entry_alloc = risk_budget * 0.6
    remaining = max(risk_budget - entry_alloc, 0.0)
    if dca_levels > 0:
        per_dca = remaining / dca_levels
        dca_allocs = [per_dca for _ in range(dca_levels)]
    else:
        dca_allocs = []
    steps = (dca_step_pcts or [])[:dca_levels]
    # pad if needed
    while len(steps) < dca_levels:
        steps.append(steps[-1] if steps else 2.0)
    return PositionPlan(
        base_allocation_usd=risk_budget,
        entry_allocation_usd=entry_alloc,
        dca_allocations_usd=dca_allocs,
        dca_steps_down_pct=steps,
    )