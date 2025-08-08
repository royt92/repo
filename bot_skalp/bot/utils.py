from __future__ import annotations


def fmt_usd(value: float) -> str:
    return f"$ {value:,.2f}"


def fmt_pct(value: float) -> str:
    return f"{value:.2f}%"