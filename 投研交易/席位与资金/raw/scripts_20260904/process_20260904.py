#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-09-04 监管内幕交易追踪 — 数据处理"""
import json, re, os, csv, sys
from collections import Counter, OrderedDict, defaultdict

SPILL = '/Users/chenyang/.hermes/cache/spillover/call_2803r87pwk81kdazwwrrjg6e.txt'
BASE = '/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/投研交易/席位与资金/raw'

with open(SPILL, 'r', encoding='utf-8') as f:
    raw = f.read()

# 提取 JSON
m = re.search(r'\{.*\}', raw, re.S)
data = json.loads(m.group(0))
rows = json.loads(data['result'])
print("总记录:", len(rows))

keys = list(rows[0].keys())
cols = OrderedDict((k, []) for k in keys)
for r in rows:
    for k in keys:
        cols[k].append(r.get(k))

in_de_cnt = Counter(r['in_de'] for r in rows)
holder_cnt = Counter(r['holder_type'] for r in rows)
stocks = set(r['ts_code'] for r in rows)
print("IN/DE:", dict(in_de_cnt))
print("holder_type:", dict(holder_cnt))
print("涉及股票数:", len(stocks))
print("公告日期范围:", min(r['ann_date'] for r in rows), "~", max(r['ann_date'] for r in rows))

os.makedirs(BASE, exist_ok=True)
csv_path = os.path.join(BASE, '20260904_holdertrade.csv')
with open(csv_path, 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=keys)
    w.writeheader()
    for r in rows:
        w.writerow(r)
print("raw CSV 落盘:", csv_path, os.path.getsize(csv_path), "bytes")

# ---- 集群判定：IN 增持，按股票聚合 distinct holder ----
in_rows = [r for r in rows if r['in_de'] == 'IN']
print("\n增持记录数:", len(in_rows))

by_stock = defaultdict(list)
for r in in_rows:
    by_stock[r['ts_code']].append(r)

clusters = []
for code, recs in by_stock.items():
    holders = set(r['holder_name'] for r in recs)
    if len(holders) >= 2:
        amt = 0.0
        for r in recs:
            price = r.get('avg_price')
            vol = r.get('change_vol')
            if price and vol:
                amt += float(price) * float(vol)
        clusters.append((code, len(holders), len(recs), amt, holders))

clusters.sort(key=lambda x: (-x[3], -x[1]))
print("\n集群增持（≥2 distinct holder）公司数:", len(clusters))
for code, nh, nr, amt, holders in clusters:
    print(f"  {code}: {nh}人/{nr}笔 金额≈{amt/10000:.0f}万 holders={sorted(holders)[:6]}")

# 全部股票 + 人数（含单人）供参考
print("\n全部增持股票 distinct holder 数（>1 已列出，单人也列出前若干）:")
singles = []
for code, recs in by_stock.items():
    holders = set(r['holder_name'] for r in recs)
    if len(holders) == 1:
        amt = 0.0
        for r in recs:
            if r.get('avg_price') and r.get('change_vol'):
                amt += float(r['avg_price']) * float(r['change_vol'])
        singles.append((code, 1, len(recs), amt, list(holders)[0]))
singles.sort(key=lambda x: -x[3])
print("单人增持公司数:", len(singles))
for code, nh, nr, amt, h in singles[:30]:
    print(f"  {code}: 1人/{nr}笔 金额≈{amt/10000:.0f}万 holder={h}")

# 输出集群明细到文件供后续分析
detail = os.path.join(BASE, '20260904_cluster_detail.txt')
with open(detail, 'w', encoding='utf-8') as f:
    f.write("=== 集群增持明细（≥2 distinct holder）===\n")
    for code, nh, nr, amt, holders in clusters:
        f.write(f"\n### {code}  {nh}人 {amt/10000:.0f}万\n")
        for r in by_stock[code]:
            f.write(f"  ann={r['ann_date']} {r['holder_name']} [{r['holder_type']}] "
                    f"vol={r['change_vol']} ratio={r['change_ratio']} avg_px={r['avg_price']} "
                    f"after_ratio={r['after_ratio']} begin={r['begin_date']} close={r['close_date']}\n")
    f.write("\n=== 单人增持（金额>50万）===\n")
    for code, nh, nr, amt, h in singles:
        if amt > 500000:
            f.write(f"### {code}  {h}  {amt/10000:.0f}万\n")
            for r in by_stock[code]:
                f.write(f"  ann={r['ann_date']} {r['holder_name']} vol={r['change_vol']} avg_px={r['avg_price']} begin={r['begin_date']} close={r['close_date']}\n")
print("\n明细落盘:", detail)

# 同期减持 TOP（反向对照）
de_rows = [r for r in rows if r['in_de'] == 'DE']
de_amt = defaultdict(float)
de_info = {}
for r in de_rows:
    amt = 0.0
    if r.get('avg_price') and r.get('change_vol'):
        amt = float(r['avg_price']) * float(r['change_vol'])
    de_amt[r['ts_code']] += amt
    if r['ts_code'] not in de_info:
        de_info[r['ts_code']] = (r['holder_name'], r['ann_date'])
top_de = sorted(de_amt.items(), key=lambda x: -x[1])[:15]
print("\n同期减持 TOP15（按金额，均价缺失≈0 需注意）:")
for code, amt in top_de:
    print(f"  {code}: ~{amt/10000:.0f}万  {de_info[code][0]}  ann={de_info[code][1]}")
