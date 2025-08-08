from __future__ import annotations

import logging
import signal
import time
from typing import List

from bot.config import load_settings
from bot.exchange import BybitClient
from bot.logger import setup_logger
from bot.order_manager import OrderManager
from bot.screener import screen_symbols
from bot.strategy import generate_signal
from bot.telegram_client import TelegramClient
from bot.risk import compute_position_plan
from bot.utils import fmt_pct, fmt_usd


def main() -> None:
    logger = setup_logger(logging.INFO)
    settings = load_settings()
    if settings.dotenv_path:
        print(f"[CONFIG] Loaded .env from: {settings.dotenv_path}")
    else:
        print("[CONFIG] .env not found; using environment defaults")
    tg = TelegramClient(
        settings.telegram_bot_token,
        settings.telegram_chat_id,
        dry_run=settings.dry_run,
        force_send=settings.telegram_force_send,
    )
    logger.info("Starting Bybit Spot Scalper | mode=%s | quote=%s | tf=%s | autobudget=%s | base_budget=%s", "DRY" if settings.dry_run else "LIVE", settings.quote_asset, settings.timeframe, settings.auto_budget_from_balance, fmt_usd(settings.base_budget_usd))
    client = BybitClient(
        api_key=settings.bybit_api_key,
        api_secret=settings.bybit_api_secret,
        subaccount=settings.bybit_subaccount,
        dry_run=settings.dry_run,
        use_testnet=settings.use_testnet,
        http_proxy=settings.http_proxy,
        https_proxy=settings.https_proxy,
    )
    logger.info("Loading markets...")
    client.load_markets()
    logger.info("Markets loaded")

    # Determine budget
    budget_usd = settings.base_budget_usd
    if settings.auto_budget_from_balance:
        logger.info("Fetching balance for budget (quote=%s)...", settings.quote_asset)
        try:
            bal = client.fetch_balance()
            quote = settings.quote_asset
            free = 0.0
            if isinstance(bal, dict):
                acct = bal.get(quote) or {}
                free_map = (bal.get('free', {}) or {})
                total_map = (bal.get('total', {}) or {})
                free = float(free_map.get(quote, acct.get('free', 0.0)) or 0.0)
                total = float(total_map.get(quote, acct.get('total', 0.0)) or 0.0)
                if free <= 0 and total > 0:
                    free = total
            budget_usd = max(free, 0.0)
            logger.info("Budget resolved from balance: %s", fmt_usd(budget_usd))
        except Exception as e:
            logger.warning("Balance fetch failed: %s. Using configured budget: %s", e, fmt_usd(settings.base_budget_usd))
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
            logger.info("Fetching tickers and screening top=%d...", settings.screen_top_n)
            tickers = client.fetch_tickers()
            screened = screen_symbols(
                tickers,
                quote_asset=settings.quote_asset,
                ohlc_provider=lambda s, tf, limit=120: client.fetch_ohlcv(s, tf, limit),
                timeframe=settings.timeframe,
                top_n=settings.screen_top_n,
            )
            logger.info("Screened symbols: %s", ", ".join([s.symbol for s in screened]) or "none")

            # Manage existing positions first
            for sym in list(orders.positions.keys()):
                logger.info("Check TP/SL/DCA for %s", sym)
                profit = orders.maybe_take_profit(sym)
                if profit is not None:
                    logger.info("TP hit on %s profit=%s", sym, fmt_usd(profit))
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
                    logger.info("DCA executed on %s added=%s", sym, fmt_usd(dca_spent))
                    tg.send_message(f"DCA executed on {sym} | Added: {fmt_usd(dca_spent)}")
                    continue
                stopped = orders.maybe_stop_loss(sym)
                if stopped:
                    logger.info("Stop-loss triggered on %s", sym)
                    tg.send_message(f"Stop-loss triggered on {sym}")

            if len(orders.positions) >= settings.max_concurrent_positions:
                logger.info("Reached max concurrent positions=%d, sleeping...", settings.max_concurrent_positions)
                time.sleep(settings.loop_sleep_seconds)
                continue

            for item in screened:
                if item.symbol in orders.positions:
                    continue
                if len(orders.positions) >= settings.max_concurrent_positions:
                    break
                try:
                    logger.info("Fetching ohlcv for %s", item.symbol)
                    ohlcv = client.fetch_ohlcv(item.symbol, settings.timeframe, limit=120)
                    closes: List[float] = [c[4] for c in ohlcv]
                    sig = generate_signal(closes)
                    logger.info("Signal for %s: %s", item.symbol, sig.side or sig.reason)
                    if sig.side == "buy":
                        plan = compute_position_plan(
                            budget_usd,
                            settings.risk_per_trade_pct,
                            settings.dca_levels,
                            settings.dca_step_pcts,
                        )
                        logger.info("Attempt open %s entry_usd=%s", item.symbol, fmt_usd(plan.entry_allocation_usd))
                        pos = orders.open_position(
                            item.symbol,
                            usd_amount=plan.entry_allocation_usd,
                            take_profit_pct=settings.take_profit_pct,
                            stop_loss_pct=settings.stop_loss_pct,
                        )
                        if pos:
                            logger.info("Opened %s entry=%.8f qty=%s", item.symbol, pos.avg_price, pos.quantity)
                            tg.send_message(
                                "Opened position\n"
                                f"{item.symbol} | Entry: {pos.avg_price:.6f} | Qty: {pos.quantity}\n"
                                f"TP: {fmt_pct(settings.take_profit_pct)} | SL: {fmt_pct(settings.stop_loss_pct)}\n"
                                f"Plan: entry {fmt_usd(plan.entry_allocation_usd)}, dca {plan.dca_allocations_usd}"
                            )
                        else:
                            logger.info("Skip open %s (min cost/balance/order failure)", item.symbol)
                except Exception as e:
                    logger.error("Error processing %s: %s", item.symbol, e)
                    tg.send_message(f"Error processing {item.symbol}: {e}")

            time.sleep(settings.loop_sleep_seconds)
        except Exception as e:
            logger.error("Main loop error: %s", e)
            tg.send_message(f"Main loop error: {e}")
            time.sleep(settings.loop_sleep_seconds)

    tg.send_message("Bot stopped")


if __name__ == "__main__":
    main()