#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pledge_stat v2 字段修正"""
import os, json, time

env_path = '/Users/chenyang/Downloads/demo/沧海巨浪/.env'
token = None
with open(env_path, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line.startswith('TUSHARE_TOKEN='):
            token = line.split('=', 1)[1].strip().strip('"').strip("'")
import tushare as ts
pro = ts.pro_api(token)

BASE = '/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/投研交易/席位与资金/raw'

# 先看字段
df0 = pro.pledge_stat(ts_code='002049.SZ')
print("pledge_stat columns:", list(df0.columns))

pledge_codes = ['301498.SZ','002568.SZ','002083.SZ','000801.SZ','300929.SZ','002192.SZ',
                '002049.SZ','002456.SZ','920187.BJ','600155.SH','600905.SH','601668.SH',
                '000858.SZ','300482.SZ','688625.SH','603312.SH','301078.SZ','300832.SZ']
print("\n=== pledge_stat ===")
pledge_out = {}
for code in pledge_codes:
    try:
        df = pro.pledge_stat(ts_code=code)
        if df is not None and not df.empty:
            df = df.sort_values('end_date', ascending=False)
            latest = df.iloc[0]
            rec = {c: latest[c] for c in df.columns if c in ['end_date','pledge_count','pledge_ratio','pledge_ratio_avg','pledge_ratio_max']}
            # 取最近有质押比例的记录（若最新无数据则往前）
            rec = dict(latest)
            pledge_out[code] = {k: (str(v) if not isinstance(v, (int, float)) else v) for k, v in rec.items()}
            print(f"  {code}: {dict(list(rec.items())[:8])}")
        else:
            pledge_out[code] = None
            print(f"  {code}: 无质押数据")
    except Exception as e:
        pledge_out[code] = {'err': str(e)}
        print(f"  {code}: ERR {e}")
    time.sleep(0.2)

with open(os.path.join(BASE, '20260904_pledge.json'), 'w', encoding='utf-8') as f:
    json.dump(pledge_out, f, ensure_ascii=False, indent=1, default=str)
print("\n质押落盘:", os.path.join(BASE, '20260904_pledge.json'))
