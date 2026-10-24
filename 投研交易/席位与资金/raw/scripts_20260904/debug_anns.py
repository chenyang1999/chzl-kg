#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""debug anns_d"""
import os
env_path = '/Users/chenyang/Downloads/demo/沧海巨浪/.env'
token = None
with open(env_path, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line.startswith('TUSHARE_TOKEN='):
            token = line.split('=', 1)[1].strip().strip('"').strip("'")
import tushare as ts
pro = ts.pro_api(token)

# 单只测试
df = pro.anns_d(ts_code='301498.SZ', start_date='20260601', end_date='20260904')
print("anns_d 301498:", type(df), "shape:", None if df is None else df.shape)
if df is not None and not df.empty:
    print("columns:", list(df.columns))
    print(df.head(8).to_string())
else:
    print("空结果")

# 用 trade_cal 测试接口可用性
print("\n--- 测试 anns_d 用 ann_date 参数 ---")
try:
    df2 = pro.anns_d(ts_code='600155.SH', start_date='20260801', end_date='20260904')
    print("600155 anns:", None if df2 is None else df2.shape)
    if df2 is not None and not df2.empty:
        print(df2[['ann_date','ann_title']].head(10).to_string())
except Exception as e:
    print("ERR:", e)
