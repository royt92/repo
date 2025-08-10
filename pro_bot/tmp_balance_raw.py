import asyncio, json, aiohttp
from src.settings import get_settings
from src.exchange.bybit_client import BybitClient

async def main():
    s = get_settings()
    async with BybitClient(s.bybit_api_key, s.bybit_api_secret, s.bybit_env) as c:
        base = c.base_rest
        async with c.session.get(base + '/v5/account/wallet-balance', params={'accountType':'UNIFIED'}, headers=c._sign('')) as r:
            print('UNIFIED http', r.status)
            data = await r.json(content_type=None)
            print('UNIFIED body', json.dumps(data)[:1000])
        async with c.session.get(base + '/v5/account/wallet-balance', params={'accountType':'SPOT'}, headers=c._sign('')) as r:
            print('SPOT http', r.status)
            data = await r.json(content_type=None)
            print('SPOT body', json.dumps(data)[:1000])

asyncio.run(main())
