from src.risk.risk_manager import RiskManager, SymbolRules


def test_size_position_basic():
    rm = RiskManager(0.01, 0.05)
    rules = SymbolRules(min_qty=0.001, min_notional=5.0, qty_step=0.001, price_step=0.0001)
    qty = rm.size_position(balance_usdt=1000, entry_price=10.0, sl_price=9.9, rules=rules)
    # risk = 10, sl_distance 0.1 -> 100 qty -> stepped to 100.0
    assert qty >= 50


def test_validate_spread_depth():
    rm = RiskManager(0.01, 0.05)
    assert rm.validate_spread_and_depth(5, 8, 10000, 5000)
    assert not rm.validate_spread_and_depth(10, 8, 10000, 5000)
    assert not rm.validate_spread_and_depth(5, 8, 1000, 5000)