#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""2026-09-04 监管内幕交易追踪 — anns_d 公告回查 v2（字段 title）"""
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

targets = {
    '301498.SZ': ['增持', '减持', '计划', '回购'],
    '002568.SZ': ['增持', '减持', '计划', '回购'],
    '002083.SZ': ['增持', '减持', '计划', '回购'],
    '000801.SZ': ['增持', '减持', '计划', '回购'],
    '300929.SZ': ['增持', '减持', '计划', '回购'],
    '002192.SZ': ['增持', '减持', '计划', '回购'],
    '002049.SZ': ['增持', '减持', '计划', '回购'],
    '002456.SZ': ['增持', '减持', '计划', '回购'],
    '920187.BJ': ['增持', '减持', '计划', '回购'],
    '300144.SZ': ['增持', '减持', '计划', '回购', '转让'],
    '600155.SH': ['增持', '减持', '计划', '回购'],
    '600905.SH': ['增持', '减持', '计划', '回购'],
    '601668.SH': ['增持', '减持', '计划', '回购'],
    '000858.SZ': ['增持', '减持', '计划', '回购'],
    '300482.SZ': ['增持', '减持', '计划', '回购'],
    '603312.SH': ['增持', '减持', '计划', '回购'],
    '688625.SH': ['增持', '减持', '计划', '回购'],
    '301078.SZ': ['增持', '减持', '计划', '回购'],
    '300832.SZ': ['增持', '减持', '计划', '回购'],
    '002870.SZ': ['增持', '减持', '计划', '回购'],
}

out = {}
for code, kws in targets.items():
    try:
        df = pro.anns_d(ts_code=code, start_date='20260601', end_date='20260904')
        hits = []
        if df is not None and not df.empty:
            for _, r in df.iterrows():
                title = str(r.get('title', ''))
                date = str(r.get('ann_date', ''))
                if any(k in title for k in kws):
                    hits.append({'date': date, 'title': title[:90]})
        out[code] = hits
        print(f"\n=== {code} ===")
        for h in hits[:12]:
            print(f"  {h['date']} {h['title']}")
        if not hits:
            print("  (无相关公告)")
    except Exception as e:
        out[code] = [{'err': str(e)}]
        print(f"\n=== {code} ERR: {e}")
    time.sleep(0.2)

with open(os.path.join(BASE, '20260904_anns.json'), 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print("\n公告回查落盘:", os.path.join(BASE, '20260904_anns.json'))
