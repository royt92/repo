import asyncio, json
from src.exchange.bybit_client import BybitClient
from src.settings import get_settings

async def main():
    s = get_settings()
    print('env', s.bybit_env, 'mode', s.mode)
    async with BybitClient(s.bybit_api_key, s.bybit_api_secret, s.bybit_env) as c:
        for t in ('UNIFIED','SPOT'):
            try:
                res = await c.fetch_balance(t)
                coins = []
                for acc in res.get('list', []):
                    for coin in acc.get('coin', []):
                        if coin.get('coin') == 'USDT':
                            coins.append(coin)
                print(t, 'ok', json.dumps(coins)[:500])
            except Exception as e:
                print(t, 'err', repr(e))

asyncio.run(main())
