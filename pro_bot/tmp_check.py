import asyncio
from src.exchange.bybit_client import BybitClient

async def main():
    async with BybitClient('', '', 'live') as c:
        print('klines BTCUSDT 1m ...')
        try:
            kl = await c.fetch_klines('BTCUSDT', '1m', 5)
            print('klines_ok', len(kl))
        except Exception as e:
            print('klines_err', repr(e))

asyncio.run(main())
