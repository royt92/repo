from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class Allocation:
    symbol: str
    fraction: float


class Portfolio:
    def __init__(self, max_symbols: int = 3) -> None:
        self.max_symbols = max_symbols

    def allocate(self, symbols: List[str]) -> Dict[str, float]:
        take = symbols[: self.max_symbols]
        if not take:
            return {}
        frac = 1.0 / len(take)
        return {s: frac for s in take}