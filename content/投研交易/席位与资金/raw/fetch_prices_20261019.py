#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-10-19 监管内幕交易追踪 — 价格位置/估值拉取"""
import os, json, csv, time

env_path = '/Users/chenyang/Downloads/demo/沧海巨浪/.env'
token = None
with open(env_path, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line.startswith('TUSHARE_TOKEN='):
            token = line.split('=', 1)[1].strip().strip('"').strip("'")
print('token loaded:', bool(token))

import tushare as ts
pro = ts.pro_api(token)

BASE = '/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/投研交易/席位与资金/raw'

# 候选：clean_clusters 中金额>0 的全部 + 新增 600960 + 成都路桥/湖南黄金等观察
candidates = [
 '002568.SZ','002655.SZ','688625.SH','002601.SZ','300806.SZ','002296.SZ','000988.SZ',
 '002416.SZ','603312.SH','002083.SZ','002637.SZ','300286.SZ','002049.SZ','688328.SH',
 '301498.SZ','300498.SZ','002146.SZ','002353.SZ','601717.SH','003015.SZ','002615.SZ',
 '002096.SZ','301089.SZ','688557.SH','603768.SH','000656.SZ','002456.SZ','301078.SZ',
 '603927.SH','688478.SH','300832.SZ','688720.SH','002480.SZ','300176.SZ','601005.SH',
 '000801.SZ','600022.SH','603733.SH','688155.SH','601127.SH','002628.SZ','600960.SH',
 '002155.SZ','300929.SZ','002803.SZ'
]

# 交易日历：20261016 为上一交易日收盘
trade_date = '20261016'

basic_rows = []
for code in candidates:
    try:
        df = pro.daily_basic(ts_code=code, trade_date=trade_date,
                             fields='ts_code,trade_date,close,pe_ttm,pb,total_mv,circ_mv,turnover_rate')
        if len(df):
            basic_rows.append(df.iloc[0].to_dict())
        time.sleep(0.12)
    except Exception as e:
        print('ERR basic', code, e)
print('daily_basic rows:', len(basic_rows))
with open(os.path.join(BASE, '20261019_daily_basic.json'), 'w', encoding='utf-8') as f:
    json.dump(basic_rows, f, ensure_ascii=False, default=str)

# 52周高低 + YTD 起点（20260101）收盘
daily_out = {}
for code in candidates:
    try:
        df = pro.daily(ts_code=code, start_date='20251201', end_date='20261016',
                       fields='ts_code,trade_date,close')
        if len(df):
            df = df.sort_values('trade_date')
            hi = df['close'].max()
            lo = df['close'].min()
            ytd_start = df[df['trade_date'] >= '20260101']['close'].iloc[0]
            last = df['close'].iloc[-1]
            daily_out[code] = {'52w_high': float(hi), '52w_low': float(lo),
                               'ytd_start': float(ytd_start), 'last_close': float(last),
                               'ytd_pct': round((last/ytd_start-1)*100, 1)}
        time.sleep(0.12)
    except Exception as e:
        print('ERR daily', code, e)
print('daily rows:', len(daily_out))
with open(os.path.join(BASE, '20261019_price_pos.json'), 'w', encoding='utf-8') as f:
    json.dump(daily_out, f, ensure_ascii=False, default=str)
print('DONE')
