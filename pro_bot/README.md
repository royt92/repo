## Bybit Spot Scalper Bot (Async, Paper/Live)

Production-grade, async Python 3.11+ scalper bot for Bybit Spot with:
- Accurate daily screening of 300+ USDT pairs (liquidity, spread, RVOL, trend/momentum)
- Top-3 symbols trading concurrently
- REST v5 + Public/Private WebSocket support (low latency)
- Auto balance detection, risk-per-trade sizing, post-only orders with fallback
- SQLite storage for orders/trades/state
- Telegram notifications (startup, candidates, trades, exits, daily PnL)
- Paper and live modes
- Docker and tests

### Quick Start

1) Clone and prepare env
```
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

2) Fill `.env` (no API keys needed for paper/public data)

3) Run in paper mode
```
python -m src.app once
python -m src.app daemon
```

4) Backtest (simplified)
```
python -m src.app backtest --symbol BTCUSDT --days 30
```

### Docker
```
docker compose up --build -d
```

### .env
```
BYBIT_API_KEY=your_key
BYBIT_API_SECRET=your_secret
BYBIT_ENV=live
TELEGRAM_BOT_TOKEN=your_token
TELEGRAM_CHAT_ID=123456789
MODE=paper
RISK_PER_TRADE=0.003
MAX_DAILY_LOSS=0.02
MAX_CONCURRENT_SYMBOLS=3
SCREENER_MIN_RVOL=1.5
SCREENER_MAX_SPREAD_BP=8
SCREENER_MIN_DEPTH_USDT=50000
RESCAN_MINUTES=15
TIMEFRAME=1m
LOG_LEVEL=INFO
```

### Strategy
- Long-only trend/pullback: EMA20 > EMA50 > EMA200, price near EMA20 within ~0.25 ATR
- Orderbook buy imbalance and recent tick volume spike
- ATR-based SL/TP, default post-only; fallback to IOC/market

### Screener
- Filters: USDT spot only, spread ≤ threshold, depth ≥ threshold, RVOL ≥ min
- Metrics: spread, depth, RVOL, ADX, EMA slope, tick imbalance
- Weighted ranking and selection of top-3, re-scan every RESCAN_MINUTES

### Risk Management
- Risk-per-trade sizing (balance auto-detected in live, fixed 1000 USDT in paper)
- Daily loss limit and losing-streak cooldown (basic)
- Validate spread and liquidity before entry; lot/step and min notional enforced

### Tests
```
pytest -q
```

### Notes
- This project avoids hardcoding secrets. Use .env only.
- WebSocket streams are wired in the client and ready for extension; executor uses REST for simplicity and robustness.
- Backtest mode is a sanity-check scaffold; expand as needed.
