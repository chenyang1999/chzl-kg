#!/bin/bash
# 沧海巨浪 · 退潮次日翻多检测 (盘中, 可重复运行)
# 非退潮次日自动 not_applicable; pending 时重复跑可在信号确认时补抓
set -euo pipefail
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:${PATH}"

ROOT="/Users/chenyang/Downloads/demo/沧海巨浪"
cd "$ROOT"
# 交易日门控
if [ -f .venv/bin/activate ]; then source .venv/bin/activate; fi

TRADE_DATE=$(date '+%Y%m%d')
OPEN=$(python3 -c "
import tushare as ts
from scripts.fetch.run_auction_snapshot import _load_env_value
ts.set_token(_load_env_value('TUSHARE_TOKEN'))
df = ts.pro_api().trade_cal(exchange='SSE', start_date='$TRADE_DATE', end_date='$TRADE_DATE')
print(int(df.iloc[0].is_open) if len(df) else 0)
" 2>/dev/null || echo 0)

if [ "$OPEN" != "1" ]; then
  echo "[retreat_reversal] $TRADE_DATE 非交易日, 跳过"
  exit 0
fi

PYTHONPATH=. python3 scripts/plan/run_retreat_reversal.py --date "$TRADE_DATE"
