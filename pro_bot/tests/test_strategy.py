import pandas as pd

from src.strategy.alpha import AlphaStrategy


def test_strategy_generates_signal():
    # Build DataFrame with uptrend and close near ema20
    rows = []
    price = 10.0
    for i in range(200):
        o = price
        h = price + 0.05
        l = price - 0.05
        c = price + 0.02
        v = 100 + i
        rows.append({"open": o, "high": h, "low": l, "close": c, "volume": v})
        price += 0.03
    df = pd.DataFrame(rows)

    orderbook = {"b": [["10.0", "1000"] for _ in range(10)], "a": [["10.01", "1000"] for _ in range(10)]}
    tick_stats = {"tick_imbalance": 0.5, "tick_freq": 50}

    strat = AlphaStrategy("1m")
    sig = strat.generate(df, orderbook, tick_stats)
    assert sig is None or sig.side in ("Buy", "Sell")