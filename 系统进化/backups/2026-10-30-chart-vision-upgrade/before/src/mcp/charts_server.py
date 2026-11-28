#!/usr/bin/env python3
"""K 线/分时出图 MCP — 按需调试。"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.mcp import tools as T

_USE_FASTMCP = False
try:
    from mcp.server.fastmcp import FastMCP  # noqa: F401

    _USE_FASTMCP = True
except ImportError:
    pass

if _USE_FASTMCP:
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("canghai-charts")

    @mcp.tool()
    def chart_fast_render_kline(ts_code: str, name: str = "", fq: int = 2) -> str:
        """极速四周期 K 线拼图 PNG。"""
        return json.dumps(T.chart_fast_render_kline(ts_code=ts_code, name=name, fq=fq), ensure_ascii=False)

    @mcp.tool()
    def chart_fast_render_intraday(ts_code: str, name: str = "", trade_date: str = "", fq: int = 1) -> str:
        """极速分时图 PNG。"""
        return json.dumps(
            T.chart_fast_render_intraday(ts_code=ts_code, name=name, trade_date=trade_date, fq=fq),
            ensure_ascii=False,
        )

    @mcp.tool()
    def chart_vision_analyze(ts_code: str, name: str = "", fq: int = 2, data_only: bool = False) -> str:
        """出图 + 多模态 LLM 技术面分析。"""
        return json.dumps(
            T.chart_vision_analyze(ts_code=ts_code, name=name, fq=fq, data_only=data_only),
            ensure_ascii=False,
        )

    @mcp.tool()
    def chart_lwc_render_kline(ts_code: str, name: str = "", fq: int = 2) -> str:
        """Lightweight Charts 无头出图。"""
        return json.dumps(T.chart_lwc_render_kline(ts_code=ts_code, name=name, fq=fq), ensure_ascii=False)

else:
    from src.mcp.stdio_jsonrpc import StdioMcpServer

    mcp = StdioMcpServer("canghai-charts")

    @mcp.tool(description="极速四周期 K 线拼图 PNG")
    def chart_fast_render_kline(ts_code: str, name: str = "", fq: int = 2) -> str:
        return json.dumps(T.chart_fast_render_kline(ts_code=ts_code, name=name, fq=fq), ensure_ascii=False)

    @mcp.tool(description="极速分时图 PNG")
    def chart_fast_render_intraday(ts_code: str, name: str = "", trade_date: str = "", fq: int = 1) -> str:
        return json.dumps(
            T.chart_fast_render_intraday(ts_code=ts_code, name=name, trade_date=trade_date, fq=fq),
            ensure_ascii=False,
        )

    @mcp.tool(description="出图 + 多模态 LLM 技术面分析")
    def chart_vision_analyze(ts_code: str, name: str = "", fq: int = 2, data_only: bool = False) -> str:
        return json.dumps(
            T.chart_vision_analyze(ts_code=ts_code, name=name, fq=fq, data_only=data_only),
            ensure_ascii=False,
        )

    @mcp.tool(description="Lightweight Charts 无头出图")
    def chart_lwc_render_kline(ts_code: str, name: str = "", fq: int = 2) -> str:
        return json.dumps(T.chart_lwc_render_kline(ts_code=ts_code, name=name, fq=fq), ensure_ascii=False)


if __name__ == "__main__":
    mcp.run()
