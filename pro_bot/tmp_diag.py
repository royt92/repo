import asyncio
import numpy as np
import pandas as pd
from src.exchange.bybit_client import BybitClient
from src.data.market_data import klines_to_df, compute_spread_bps, compute_depth, trades_to_tick_stats
from src.utils.math import ema, atr, adx

async def main():
    async with BybitClient('', '', 'live') as c:
        sym='BTCUSDT'
        print('orderbook ...')
        ob = await c.fetch_orderbook(sym, 50)
        print('spread', compute_spread_bps(ob))
        depth = compute_depth(ob, 0.002)
        print('depth_total', depth.total)
        print('klines 600 ...')
        kl = await c.fetch_klines(sym, '1m', 600)
        print('klines_len', len(kl))
        df = klines_to_df(kl)
        print('df_cols', list(df.columns), df.head(2).to_dict('records'))
        df['ret']= np.log(df['close']).diff()
        df['ema20']=ema(df['close'],20)
        df['ema50']=ema(df['close'],50)
        df['ema200']=ema(df['close'],200)
        df['atr14']=atr(df['high'],df['low'],df['close'],14)
        df['adx14']=adx(df['high'],df['low'],df['close'],14)
        print('ok_indicators', float(df['ema20'].iloc[-1]))
        tr = await c.fetch_trades(sym, 100)
        print('trades', len(tr))

asyncio.run(main())
