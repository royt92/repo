# Bybit Spot Scalper Bot (Dry-run capable)

Quick-start:

1. Create env

   ```bash
   cp .env.example .env
   # fill BYBIT and TELEGRAM configs; keep DRY_RUN=true for testing
   ```

2. Install deps

   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```

3. Run (dry-run)

   ```bash
   python main.py
   ```

Notes:
- Dry-run prints Telegram messages to stdout and simulates orders without sending to Bybit.
- In LIVE mode set `DRY_RUN=false` and provide valid API keys and Telegram token/chat id.
- Strategy: EMA(9/21) cross with RSI filter; TP/SL and DCA are configurable via env.
