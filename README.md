# Инструменты для внутридневной спот‑торговли крипты

Состав:
- Чек‑лист: `checklists/intraday_checklist.md`
- Скринер сигналов: `screener.py`
- Простой бэктест: `backtest.py`
- Торговый бот (Bybit, spot): `bot.py`
- Конфиг: `config/config.yaml`
- Шаблон журнала: `journal_template.csv`

## Установка
```bash
python3 -m pip install -r /workspace/requirements.txt --break-system-packages
```

## Скринер
```bash
python3 /workspace/screener.py --config /workspace/config/config.yaml
```
Вывод сохраняется в `/workspace/output/`.

## Бэктест
```bash
python3 /workspace/backtest.py --exchange kraken --symbol BTC/USDT --timeframe 15m --lookback 1200 --strategy pullback
```

## Торговый бот (Bybit, spot)
1) Создайте API‑ключ на Bybit (Spot), включите разрешение на спот‑торговлю. Запишите `apiKey` и `secret`.
2) Создайте телеграм‑бота через @BotFather, получите токен. Узнайте свой `chat_id` (например, через бота @userinfobot).
3) Установите переменные окружения:
```bash
export BYBIT_API_KEY="ВАШ_API_KEY"
export BYBIT_API_SECRET="ВАШ_SECRET"
export TELEGRAM_BOT_TOKEN="ВАШ_TG_TOKEN"
export TELEGRAM_CHAT_ID="ВАШ_CHAT_ID"
```
4) Отредактируйте `config/config.yaml` при необходимости:
- `trading.per_order_usd`: сумма одной покупки (минимум $5)
- `trading.max_budget_per_symbol`: общий бюджет на монету (с учётом DCA)
- `trading.max_open_positions`: максимум одновременно открытых монет
- `universe.*`: отбор монет (по объёму, количеству)
5) Запуск:
```bash
python3 /workspace/bot.py
```
Бот:
- Сам выбирает ликвидные пары USDT (по объёму) и использует 15m таймфрейм
- Покупает маркетом на сигналах (pullback/breakout в ап‑тренде)
- Докупает (DCA) на ступенях −0.5/−1.0/−1.5×ATR, пока не исчерпан бюджет на монету
- Выходит по трейлингу (2×ATR) и/или если цена уходит ниже EMA(200)
- Шлёт уведомления в Telegram (старт, вход, докупка, выход, ошибки)

Фоновой запуск:
```bash
nohup python3 /workspace/bot.py >/workspace/output/bot.log 2>&1 &
```
Остановить (найдите PID через `ps aux | grep bot.py` и `kill PID`).

Важно: храните ключи в переменных окружения, не в гите. Все риски на вашей стороне; торговля высокорискованна.

## Журнал
Откройте `journal_template.csv` и ведите учёт после каждой сделки. Добавляйте ссылки на скриншоты и пометки об ошибках/улучшениях.
