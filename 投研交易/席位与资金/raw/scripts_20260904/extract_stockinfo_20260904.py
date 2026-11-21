#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提取 stock_basic 映射 + 生成候选股票清单"""
import json, re, os, csv

SPILL = '/Users/chenyang/.hermes/cache/spillover/call_ud38uxhent1hb9130zuvvba8.txt'
BASE = '/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/投研交易/席位与资金/raw'

with open(SPILL, 'r', encoding='utf-8') as f:
    raw = f.read()
m = re.search(r'\{.*\}', raw, re.S)
data = json.loads(m.group(0))
rows = json.loads(data['result'])
print("stock_basic 记录:", len(rows))

name_map = {}
for r in rows:
    name_map[r['ts_code']] = {
        'name': r['name'],
        'industry': r['industry'],
        'market': r['market'],
        'list_date': r['list_date'],
    }

# 19 家集群股票
clusters = ['688625.SH','603312.SH','301498.SZ','300010.SZ','002049.SZ','300832.SZ','920187.BJ',
            '002024.SZ','000801.SZ','600328.SH','600340.SH','002146.SZ','002456.SZ','002568.SZ',
            '301078.SZ','301429.SZ','300929.SZ','002083.SZ','002192.SZ']

print("\n=== 集群股票信息 ===")
for c in clusters:
    info = name_map.get(c, {})
    nm = info.get('name', '???')
    is_st = 'ST' in nm
    print(f"{c} | {nm} | {info.get('industry','?')} | {info.get('market','?')} | ST={is_st}")

# 单人增持大额候选（金额>2000万）+ 主要公司主体
singles = ['600155.SH','300144.SZ','000858.SZ','603328.SH','300562.SZ','300482.SZ','600905.SH',
           '300192.SZ','601668.SH','600757.SH','301397.SZ','300521.SZ','688488.SH','002109.SZ',
           '300003.SZ','600338.SH','000425.SZ','600720.SH','002870.SZ','600328.SH','600340.SH']
print("\n=== 单人增持重要候选 ===")
for c in singles:
    info = name_map.get(c, {})
    nm = info.get('name', '???')
    is_st = 'ST' in nm
    print(f"{c} | {nm} | {info.get('industry','?')} | {info.get('market','?')} | ST={is_st}")

# 减持 TOP 名称
de_top = ['002602.SZ','300033.SZ','688525.SH','300751.SZ','688147.SH','920045.BJ','001301.SZ',
          '603619.SH','688213.SH','300144.SZ','688485.SH','688479.SH','688535.SH','601020.SH','603120.SH']
print("\n=== 减持 TOP 名称 ===")
for c in de_top:
    info = name_map.get(c, {})
    print(f"{c} | {info.get('name','???')} | {info.get('industry','?')}")

# 保存映射
with open(os.path.join(BASE, '20260904_stock_info.csv'), 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=['ts_code','name','industry','market','list_date'])
    w.writeheader()
    for c, info in name_map.items():
        w.writerow({'ts_code': c, **info})
print("\nstock_info 落盘:", os.path.join(BASE, '20260904_stock_info.csv'))
