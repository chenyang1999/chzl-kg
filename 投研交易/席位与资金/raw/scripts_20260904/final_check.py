#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""提取报告所需最终数字"""
import json

BASE = '/Users/chenyang/Downloads/demo/沧海巨浪/chzl_kg/投研交易/席位与资金/raw'
basic = json.load(open(f'{BASE}/20260904_daily_basic.json', encoding='utf-8'))
price = json.load(open(f'{BASE}/20260904_price_pos.json', encoding='utf-8'))
pledge = json.load(open(f'{BASE}/20260904_pledge.json', encoding='utf-8'))

codes = ['301498.SZ','002192.SZ','002568.SZ','600155.SH','600905.SH','002049.SZ','000801.SZ',
         '000858.SZ','300482.SZ','002456.SZ','002083.SZ','300929.SZ','920187.BJ','601668.SH',
         '688625.SH','603312.SH','301078.SZ','300832.SZ','300144.SZ']

names = {'301498.SZ':'乖宝宠物','002192.SZ':'融捷股份','002568.SZ':'百润股份','600155.SH':'华创云信',
         '600905.SH':'三峡能源','002049.SZ':'紫光国微','000801.SZ':'四川九洲','000858.SZ':'五粮液',
         '300482.SZ':'万孚生物','002456.SZ':'欧菲光','002083.SZ':'孚日股份','300929.SZ':'华骐环保',
         '920187.BJ':'通领科技','601668.SH':'中国建筑','688625.SH':'呈和科技','603312.SH':'西典新能',
         '301078.SZ':'孩子王','300832.SZ':'新产业','300144.SZ':'宋城演艺'}

for c in codes:
    b = basic.get(c, {})
    p = price.get(c, {})
    pg = pledge.get(c) or {}
    pe = b.get('pe_ttm')
    pe_s = f"{pe:.1f}" if isinstance(pe, (int, float)) and pe == pe else "亏损/NA"
    print(f"{names.get(c,c):6s} {c} 现价{p.get('last_close','?')} 52高{p.get('hi52','?')}/低{p.get('lo52','?')} "
          f"较52高{p.get('drawdown_from_hi','?')}% 总市值{b.get('total_mv_yi','?')}亿 流通{b.get('circ_mv_yi','?')}亿 "
          f"PE={pe_s} PB={b.get('pb','?')} 质押={pg.get('pledge_ratio','无')}%({pg.get('end_date','—')})")

# 减持 TOP 精确金额核对（用去重后的 DE）
import csv
from collections import defaultdict
rows = list(csv.DictReader(open(f'{BASE}/20260904_holdertrade.csv', encoding='utf-8')))
de = defaultdict(lambda: {'amt':0.0, 'holders':set(), 'ann':set()})
for r in rows:
    if r['in_de'] != 'DE':
        continue
    a = 0.0
    if r.get('avg_price') and r.get('change_vol'):
        a = float(r['avg_price']) * float(r['change_vol'])
    de[r['ts_code']]['amt'] += a
    de[r['ts_code']]['holders'].add(r['holder_name'])
    de[r['ts_code']]['ann'].add(r['ann_date'])
print("\n=== 减持 TOP12（去重后估算）===")
for code, v in sorted(de.items(), key=lambda x: -x[1]['amt'])[:12]:
    b = basic.get(code, {})
    print(f"{code} {names.get(code,'?')}: ~{v['amt']/10000:.0f}万 holder={list(v['holders'])[:2]} ann={sorted(v['ann'])[:3]}")
