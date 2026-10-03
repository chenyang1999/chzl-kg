#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-09-04 监管内幕交易追踪 — 综合数据拉取B：金额估算 + 估值市值 + 公告回查"""
import os, json, csv, time, re
from collections import defaultdict

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

# ---------- 1. daily_basic 全市场估值 ----------
basic = {}
for trade_date in ['20260904', '20260903']:
    try:
        df = pro.daily_basic(trade_date=trade_date,
                             fields='ts_code,trade_date,turnover_rate,pe_ttm,pb,total_mv,circ_mv,close')
        if df is not None and not df.empty:
            for _, r in df.iterrows():
                basic[r['ts_code']] = {
                    'trade_date': r['trade_date'], 'pe_ttm': r['pe_ttm'], 'pb': r['pb'],
                    'total_mv_yi': r['total_mv'] / 10000, 'circ_mv_yi': r['circ_mv'] / 10000,
                    'close': r['close'], 'turnover_rate': r['turnover_rate'],
                }
            print(f"daily_basic {trade_date}: {len(df)} 条")
            if trade_date == '20260904':
                break
    except Exception as e:
        print(f"daily_basic {trade_date} ERR: {e}")
    time.sleep(0.3)

with open(os.path.join(BASE, '20260904_daily_basic.json'), 'w', encoding='utf-8') as f:
    json.dump(basic, f, ensure_ascii=False)
print("daily_basic 落盘:", len(basic), "只")

# ---------- 2. 金额估算（avg_price 缺失用 close_date 附近收盘价） ----------
rows = []
with open(os.path.join(BASE, '20260904_holdertrade.csv'), 'r', encoding='utf-8') as f:
    for r in csv.DictReader(f):
        rows.append(r)

price_pos = json.load(open(os.path.join(BASE, '20260904_price_pos.json'), encoding='utf-8'))

# 用 close_date 附近的收盘价：从 daily 全量里找——重新拉每只股票的 close 序列太贵，
# 直接用 price_pos 的 last_close 近似 + 对明显长跨度的用 52 低中位？不行，还是逐只拉 close_date 日线。
# 更精确：拉每只股票 20260601~20260904 的日线，建 trade_date->close 映射
need = ['002568.SZ','002083.SZ','002456.SZ','301078.SZ','301429.SZ','300929.SZ','002192.SZ',
        '002146.SZ','600340.SH','600328.SH','000801.SZ','300010.SZ','002024.SZ','301498.SZ',
        '920187.BJ','002049.SZ']
close_map = {}
for code in need:
    try:
        df = pro.daily(ts_code=code, start_date='20260601', end_date='20260904',
                       fields='trade_date,close')
        close_map[code] = dict(zip(df['trade_date'], df['close']))
    except Exception as e:
        print(f"  [ERR] {code} daily2: {e}")
    time.sleep(0.15)

def est_price(code, close_date):
    cm = close_map.get(code, {})
    if close_date in cm:
        return cm[close_date]
    # 向前找最近交易日
    if close_date:
        d = int(close_date)
        for _ in range(15):
            d -= 1
            if str(d) in cm:
                return cm[str(d)]
    return price_pos.get(code, {}).get('last_close')

# 去重 + 估算
seen = set()
dedup = []
for r in rows:
    if r['in_de'] != 'IN':
        continue
    key = (r['ts_code'], r['holder_name'], r['begin_date'], r['close_date'], r['change_vol'], r['avg_price'])
    if key in seen:
        continue
    seen.add(key)
    dedup.append(r)

by_stock = defaultdict(list)
for r in dedup:
    by_stock[r['ts_code']].append(r)

print("\n=== 集群增持（估算后）===")
final_clusters = []
for code, recs in by_stock.items():
    holders = set(r['holder_name'] for r in recs)
    if len(holders) < 2:
        continue
    amt = 0.0
    detail = []
    for r in recs:
        px = None
        if r.get('avg_price'):
            px = float(r['avg_price'])
        else:
            px = est_price(code, r['close_date'])
        a = 0.0
        if px and r.get('change_vol'):
            a = px * float(r['change_vol'])
        amt += a
        detail.append({'holder': r['holder_name'], 'vol': r['change_vol'], 'px_est': round(px, 2) if px else None,
                       'amt_wan': round(a / 10000, 1), 'ann': r['ann_date'],
                       'begin': r['begin_date'], 'close': r['close_date'], 'type': r['holder_type'],
                       'after_ratio': r['after_ratio']})
    final_clusters.append({'ts_code': code, 'n_holder': len(holders), 'amt_wan': round(amt / 10000, 1),
                           'detail': detail, 'anns': sorted(set(r['ann_date'] for r in recs))})
final_clusters.sort(key=lambda x: -x['amt_wan'])
for c in final_clusters:
    b = basic.get(c['ts_code'], {})
    nm = ''
    print(f"{c['ts_code']}: {c['n_holder']}人 {c['amt_wan']:.0f}万 ann={c['anns']} "
          f"总市值={b.get('total_mv_yi','?')}亿 流通={b.get('circ_mv_yi','?')}亿 PE={b.get('pe_ttm','?')} PB={b.get('pb','?')}")

with open(os.path.join(BASE, '20260904_cluster_final.json'), 'w', encoding='utf-8') as f:
    json.dump(final_clusters, f, ensure_ascii=False, indent=1)
print("\n最终集群落盘:", os.path.join(BASE, '20260904_cluster_final.json'))
