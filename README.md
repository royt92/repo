# Инструменты для внутридневной спот‑торговли крипты

Состав:
- Чек‑лист: `checklists/intraday_checklist.md`
- Скринер сигналов: `screener.py`
- Простой бэктест: `backtest.py`
- Конфиг: `config/config.yaml`
- Шаблон журнала: `journal_template.csv`

## Установка
```bash
python3 -m pip install -r /workspace/requirements.txt
```

## Скринер
Пример запуска:
```bash
python3 /workspace/screener.py --symbols BTC/USDT,ETH/USDT --timeframe 15m --equity 10000 --risk-pct 0.75 --strategy both
```
Либо используйте конфиг:
```bash
python3 /workspace/screener.py --config /workspace/config/config.yaml
```
Вывод сохраняется в `/workspace/output/`.

## Бэктест
```bash
python3 /workspace/backtest.py --symbol BTC/USDT --timeframe 15m --lookback 1200 --strategy pullback
```
Результаты (серия R и кривая equity в R) сохраняются в `/workspace/output/`.

## Журнал
Откройте `journal_template.csv` и ведите учёт после каждой сделки. Добавляйте ссылки на скриншоты и пометки об ошибках/улучшениях.
