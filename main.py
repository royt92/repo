from __future__ import annotations

import signal
import time
from typing import List

from bot.config import load_settings
from bot.exchange import BybitClient
from bot.order_manager import OrderManager
from bot.screener import screen_symbols
from bot.strategy import generate_signal
from bot.telegram_client import TelegramClient
from bot.risk import compute_position_plan
from bot.utils import fmt_pct, fmt_usd


def main() -> None:
    settings = load_settings()
    tg = TelegramClient(
        settings.telegram_bot_token,
        settings.telegram_chat_id,
        dry_run=settings.dry_run,
        force_send=settings.telegram_force_send,
    )
    client = BybitClient(
        api_key=settings.bybit_api_key,
        api_secret=settings.bybit_api_secret,
        subaccount=settings.bybit_subaccount,
        dry_run=settings.dry_run,
        use_testnet=settings.use_testnet,
        http_proxy=settings.http_proxy,
        https_proxy=settings.https_proxy,
    )
    client.load_markets()

    # Determine budget
    budget_usd = settings.base_budget_usd
    if settings.auto_budget_from_balance:
        try:
            bal = client.fetch_balance()
            quote = settings.quote_asset
            free = 0.0
            # ccxt balance structure: {'free': {'USDT': 10}, 'total': {...}}
            if isinstance(bal, dict):
                acct = bal.get(quote) or {}
                # some exchanges put balances under 'free' dict
                free_map = (bal.get('free', {}) or {})
                total_map = (bal.get('total', {}) or {})
                free = float(free_map.get(quote, acct.get('free', 0.0)) or 0.0)
                total = float(total_map.get(quote, acct.get('total', 0.0)) or 0.0)
                if free <= 0 and total > 0:
                    free = total
            budget_usd = max(free, 0.0)
        except Exception as e:
            tg.send_message(f"Balance fetch failed, using configured budget: {e}")
            budget_usd = settings.base_budget_usd

    orders = OrderManager(client)

    running = True

    def handle_sigint(signum, frame):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, handle_sigint)
    signal.signal(signal.SIGTERM, handle_sigint)

    tg.send_message(
        "Bybit Spot Scalper started\n"
        f"Mode: {'DRY-RUN' if settings.dry_run else 'LIVE'} | Quote: {settings.quote_asset} | TF: {settings.timeframe}\n"
        f"Budget: {fmt_usd(budget_usd)} | Risk/trade: {fmt_pct(settings.risk_per_trade_pct)} | TP: {fmt_pct(settings.take_profit_pct)} | SL: {fmt_pct(settings.stop_loss_pct)}\n"
        f"DCA: {settings.dca_levels} steps at {settings.dca_step_pcts}"
    )

    while running:
        try:
            tickers = client.fetch_tickers()
            screened = screen_symbols(
                tickers,
                quote_asset=settings.quote_asset,
                ohlc_provider=lambda s, tf, limit=120: client.fetch_ohlcv(s, tf, limit),
                timeframe=settings.timeframe,
                top_n=settings.screen_top_n,
            )

            # Manage existing positions first
            for sym in list(orders.positions.keys()):
                profit = orders.maybe_take_profit(sym)
                if profit is not None:
                    tg.send_message(f"TP hit on {sym} | Profit: {fmt_usd(profit)}")
                    continue
                dca_spent = orders.maybe_execute_dca(
                    sym,
                    dca_steps_down_pct=settings.dca_step_pcts,
                    dca_allocations_usd=compute_position_plan(
                        budget_usd,
                        settings.risk_per_trade_pct,
                        settings.dca_levels,
                        settings.dca_step_pcts,
                    ).dca_allocations_usd,
                )
                if dca_spent is not None:
                    tg.send_message(f"DCA executed on {sym} | Added: {fmt_usd(dca_spent)}")
                    continue
                stopped = orders.maybe_stop_loss(sym)
                if stopped:
                    tg.send_message(f"Stop-loss triggered on {sym}")

            if len(orders.positions) >= settings.max_concurrent_positions:
                time.sleep(settings.loop_sleep_seconds)
                continue

            for item in screened:
                if item.symbol in orders.positions:
                    continue
                if len(orders.positions) >= settings.max_concurrent_positions:
                    break
                try:
                    ohlcv = client.fetch_ohlcv(item.symbol, settings.timeframe, limit=120)
                    closes: List[float] = [c[4] for c in ohlcv]
                    sig = generate_signal(closes)
                    if sig.side == "buy":
                        plan = compute_position_plan(
                            budget_usd,
                            settings.risk_per_trade_pct,
                            settings.dca_levels,
                            settings.dca_step_pcts,
                        )
                        pos = orders.open_position(
                            item.symbol,
                            usd_amount=plan.entry_allocation_usd,
                            take_profit_pct=settings.take_profit_pct,
                            stop_loss_pct=settings.stop_loss_pct,
                        )
                        if pos:
                            tg.send_message(
                                "Opened position\n"
                                f"{item.symbol} | Entry: {pos.avg_price:.6f} | Qty: {pos.quantity}\n"
                                f"TP: {fmt_pct(settings.take_profit_pct)} | SL: {fmt_pct(settings.stop_loss_pct)}\n"
                                f"Plan: entry {fmt_usd(plan.entry_allocation_usd)}, dca {plan.dca_allocations_usd}"
                            )
                except Exception as e:
                    tg.send_message(f"Error processing {item.symbol}: {e}")

            time.sleep(settings.loop_sleep_seconds)
        except Exception as e:
            tg.send_message(f"Main loop error: {e}")
            time.sleep(settings.loop_sleep_seconds)

    tg.send_message("Bot stopped")


if __name__ == "__main__":
    main()