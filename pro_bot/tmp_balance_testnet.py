import asyncio, json
from src.exchange.bybit_client import BybitClient
from src.settings import get_settings

async def main():
    s = get_settings()
    async with BybitClient(s.bybit_api_key, s.bybit_api_secret, 'testnet') as c:
        async with c.session.get(c.base_rest + '/v5/account/wallet-balance', params={'accountType':'UNIFIED'}, headers=c._sign('accountType=UNIFIED')) as r:
            print('TESTNET UNIFIED http', r.status)
            print('TESTNET body', (await r.text())[:1000])

asyncio.run(main())
