#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-09-04 监管内幕交易追踪 — 综合数据拉取A：金额去重 + 价格位置 + 估值"""
import os, sys, json, csv, time
from collections import defaultdict

# 读 .env token
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '..', '.env')
if not os.path.exists(env_path):
    env_path = '/Users/chenyang/Downloads/demo/沧海巨浪/.env'
token = None
with open(env_path, 'r', encoding='utf-8') as f:
    for line in f:
        line = line.strip()
        if line.startswith('TUSHARE_TOKEN='):
            token = line.split('=', 1)[1].strip().strip('"').strip("'")
print("token loaded:", bool(token))

import tushare as ts
pro = ts.pro_api(token)

BASE = '/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/投研交易/席位与资金/raw'

# ---------- 1. 集群金额去重精确计算 ----------
rows = []
with open(os.path.join(BASE, '20260904_holdertrade.csv'), 'r', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        rows.append(r)

in_rows = [r for r in rows if r['in_de'] == 'IN']
# 去重键: ts_code+holder+begin+close+vol+avg_px
seen = set()
dedup = []
for r in in_rows:
    key = (r['ts_code'], r['holder_name'], r['begin_date'], r['close_date'], r['change_vol'], r['avg_price'])
    if key in seen:
        continue
    seen.add(key)
    dedup.append(r)
print("\n增持记录去重后:", len(dedup), "(原始", len(in_rows), ")")

by_stock = defaultdict(list)
for r in dedup:
    by_stock[r['ts_code']].append(r)

print("\n=== 集群增持（去重后）按金额排序 ===")
cluster_rows = []
for code, recs in by_stock.items():
    holders = set(r['holder_name'] for r in recs)
    if len(holders) < 2:
        continue
    amt = 0.0
    for r in recs:
        if r.get('avg_price') and r.get('change_vol'):
            amt += float(r['avg_price']) * float(r['change_vol'])
    vols = sum(float(r['change_vol']) for r in recs if r.get('change_vol'))
    cluster_rows.append({'ts_code': code, 'n_holder': len(holders), 'n_trade': len(recs),
                         'amt_wan': amt / 10000, 'vol': vols,
                         'ann': ','.join(sorted(set(r['ann_date'] for r in recs)))})
cluster_rows.sort(key=lambda x: -x['amt_wan'])
for c in cluster_rows:
    print(f"  {c['ts_code']}: {c['n_holder']}人/{c['n_trade']}笔 {c['amt_wan']:.0f}万 ann={c['ann']}")

# ---------- 2. 逐只拉 daily（近一年）算价格位置 ----------
codes = [c['ts_code'] for c in cluster_rows]
# 重要单人增持
codes += ['600155.SH','000858.SZ','300482.SZ','600905.SH','601668.SH','300144.SZ','300003.SZ',
          '603328.SH','688488.SH','000425.SZ','600720.SH','301397.SZ','600757.SH','600338.SH',
          '300562.SZ','600328.SH','300192.SZ','002870.SZ']
codes = list(dict.fromkeys(codes))
print("\n需拉 daily 股票数:", len(codes))

start = '20250901'
end = '20260904'
price_pos = {}
for i, code in enumerate(codes):
    try:
        df = pro.daily(ts_code=code, start_date=start, end_date=end)
        if df is None or df.empty:
            print(f"  [WARN] {code} daily 空")
            continue
        df = df.sort_values('trade_date')
        highs = df['high'].tolist()
        lows = df['low'].tolist()
        last_close = df.iloc[-1]['close']
        last_date = df.iloc[-1]['trade_date']
        hi52 = max(highs)
        lo52 = min(lows)
        # 增持均价 vs 现价（用 close_date 附近的收盘价近似）
        price_pos[code] = {
            'last_close': float(last_close), 'last_date': last_date,
            'hi52': float(hi52), 'lo52': float(lo52),
            'drawdown_from_hi': (last_close / hi52 - 1) * 100,
            'pct_from_lo': (last_close / lo52 - 1) * 100,
        }
    except Exception as e:
        print(f"  [ERR] {code}: {e}")
    time.sleep(0.15)

print("\n=== 价格位置 ===")
for code, p in sorted(price_pos.items(), key=lambda x: x[1]['drawdown_from_hi']):
    print(f"  {code}: 收{p['last_close']:.2f}({p['last_date']}) 52高{p['hi52']:.2f}/低{p['lo52']:.2f} 较52高{p['drawdown_from_hi']:.1f}% 较低位+{p['pct_from_lo']:.0f}%")

with open(os.path.join(BASE, '20260904_price_pos.json'), 'w', encoding='utf-8') as f:
    json.dump(price_pos, f, ensure_ascii=False, indent=1)
with open(os.path.join(BASE, '20260904_cluster_amounts.json'), 'w', encoding='utf-8') as f:
    json.dump(cluster_rows, f, ensure_ascii=False, indent=1)
print("\n价格位置落盘:", os.path.join(BASE, '20260904_price_pos.json'))
print("集群金额落盘:", os.path.join(BASE, '20260904_cluster_amounts.json'))
