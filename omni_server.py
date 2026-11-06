"""CodeCafe Omni MCP Server: Universal Trading Intelligence & Hybrid Execution.

Combines:
- Universal multi-asset market data scraper (Yahoo Finance, Bybit, MT5)
- ASCII & SVG chart generator
- Multimodal & technical chart pattern / S&R level analyzer
- Real-time news & macro sentiment scraper
- Day-trader-skill suite bridge (ORB setups, 10,000 replay time machine, risk/budget)
- Universal hybrid trade execution (API + Screen UI fallback)
"""
import os
import subprocess
import sys
from datetime import datetime

from mcp.server.mcpserver import MCPServer

from chart_vision import analyze_market_structure, format_chart_vision_prompt
from executor import execute_trade_hybrid
from news_scraper import get_market_news_brief
from universal_data import fetch_universal_candles, render_ascii_chart, render_svg_chart

mcp = MCPServer("yo-omni")

DAY_TRADER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vendor", "day-trader-skill")


@mcp.tool()
def omni_scrape_data(symbol: str, timeframe: str = "H1", count: int = 100) -> dict:
    """Fetch real-time candles & quotes for any asset (Forex, Crypto, Stocks, Indices).

    Supports symbols like EURUSD, BTCUSDT, TSLA, AAPL, GC=F, ^GSPC.
    """
    try:
        data = fetch_universal_candles(symbol, timeframe, count)
        return {
            "symbol": data["symbol"],
            "interval": data["interval"],
            "source": data.get("source", "unknown"),
            "candle_count": len(data["close"]),
            "latest_close": float(data["close"][-1]),
            "latest_high": float(data["high"][-1]),
            "latest_low": float(data["low"][-1]),
            "latest_open": float(data["open"][-1]),
            "time_utc": datetime.fromtimestamp(int(data["time"][-1])).isoformat(),
        }
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


@mcp.tool()
def omni_chart(symbol: str, timeframe: str = "H1", count: int = 40, format: str = "ascii") -> dict:
    """Generate visual chart for a symbol. format: 'ascii' (in-chat text) or 'svg' (standalone file)."""
    try:
        candles = fetch_universal_candles(symbol, timeframe, max(count, 35))
        if format.lower() == "svg":
            chart_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), f"chart_{symbol}_{timeframe}.svg")
            render_svg_chart(candles, output_path=chart_file)
            return {"symbol": symbol, "format": "svg", "file_path": chart_file}
        else:
            text_chart = render_ascii_chart(candles, width=count)
            return {"symbol": symbol, "format": "ascii", "chart": text_chart}
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


@mcp.tool()
def omni_analyze_chart(symbol: str, timeframe: str = "H1", count: int = 100) -> dict:
    """Analyze chart structure, trend, support & resistance levels, candlestick patterns, and trade setup."""
    try:
        candles = fetch_universal_candles(symbol, timeframe, count)
        analysis = analyze_market_structure(candles)
        return analysis
    except Exception as e:
        return {"symbol": symbol, "error": str(e)}


@mcp.tool()
def omni_news(symbol: str | None = None) -> dict:
    """Scrape real-time headlines, market sentiment score, and macro event risk flags (FOMC, CPI, NFP, etc.)."""
    return get_market_news_brief(symbol)


@mcp.tool()
def omni_daytrader(action: str, symbol: str = "TSLA", setup: str = "orb", stop_rule: str = "or-mid") -> dict:
    """Bridge to day-trader-skill suite.

    action:
    - 'scan_orb': Scan opening range breakouts.
    - 'check_entry': Check entry trigger for symbol.
    - 'plan_exit': Calculate stop & target.
    - 'timemachine': Run 10,000 session replay odds.
    """
    if not os.path.exists(DAY_TRADER_DIR):
        return {"error": "vendor/day-trader-skill not found"}

    try:
        if action == "scan_orb":
            cmd = [sys.executable, os.path.join(DAY_TRADER_DIR, "trader-scanner", "scan.py"), "orb"]
        elif action == "check_entry":
            cmd = [sys.executable, os.path.join(DAY_TRADER_DIR, "trader-entry", "entry.py"), "check", symbol, "--setup", setup]
        elif action == "plan_exit":
            cmd = [sys.executable, os.path.join(DAY_TRADER_DIR, "trader-exit", "exit.py"), "plan", "--stop", stop_rule, "--target", "2R"]
        elif action == "timemachine":
            cmd = [sys.executable, os.path.join(DAY_TRADER_DIR, "trader-timemachine", "timemachine.py"), "run"]
        else:
            return {"error": f"Unknown action: {action}. Use 'scan_orb', 'check_entry', 'plan_exit', or 'timemachine'."}

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=25, cwd=DAY_TRADER_DIR)
        return {"action": action, "symbol": symbol, "output": res.stdout.strip() or res.stderr.strip()}
    except Exception as e:
        return {"action": action, "error": str(e)}


@mcp.tool()
def omni_plan_trade(symbol: str, timeframe: str = "H1") -> dict:
    """Synthesize chart patterns, key levels, technical indicators, and news sentiment into a complete trade plan."""
    candles = fetch_universal_candles(symbol, timeframe, 100)
    chart_struct = analyze_market_structure(candles)
    news = get_market_news_brief(symbol)

    rec = chart_struct["recommendation"]
    sentiment = news.get("overall_sentiment", "NEUTRAL")
    macro_flags = news.get("high_impact_flags", [])

    # Cross-reference with news
    warning = []
    if macro_flags:
        warning.append(f"High-impact macro event risk detected: {', '.join(macro_flags)}")
    if rec["action"] == "BUY" and sentiment == "BEARISH":
        warning.append("Technical signal is BUY but news sentiment is BEARISH.")
    elif rec["action"] == "SELL" and sentiment == "BULLISH":
        warning.append("Technical signal is SELL but news sentiment is BULLISH.")

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "current_price": chart_struct["current_price"],
        "technical_trend": chart_struct["trend"],
        "candlestick_patterns": chart_struct["candlestick_patterns"],
        "key_support": chart_struct["nearest_support"],
        "key_resistance": chart_struct["nearest_resistance"],
        "news_sentiment": sentiment,
        "high_impact_news_flags": macro_flags,
        "trade_action": rec["action"],
        "entry_price": rec["entry"],
        "stop_loss": rec["sl"],
        "take_profit": rec["tp"],
        "risk_reward_ratio": rec["rr_ratio"],
        "reasons": rec["reasons"],
        "cautions": warning or ["None - technicals and macro aligned."],
        "execution_ready": rec["action"] in ("BUY", "SELL") and len(warning) == 0,
    }


@mcp.tool()
def omni_execute_trade(
    platform: str,
    symbol: str,
    side: str,
    qty: float,
    sl: float,
    tp: float | None = None,
    method: str = "api",
    confirm: bool = False,
    window_keyword: str = "",
) -> dict:
    """Execute a trade on MT5, Bybit, Paper broker, or Screen UI.

    Guarded: confirm=True is required to execute. Always requires Stop Loss.
    """
    return execute_trade_hybrid(
        platform=platform,
        symbol=symbol,
        side=side,
        qty=qty,
        sl=sl,
        tp=tp,
        method=method,
        confirm=confirm,
        window_keyword=window_keyword,
    )


@mcp.tool()
def omni_paper_positions() -> dict:
    """Paper account (fake money, real prices): balances, open trades with P&L, last 10 closed.
    SL/TP hits are settled against real candles on every call."""
    import paper
    return paper.positions()


@mcp.tool()
def omni_paper_close(trade_id: int) -> dict:
    """Close one open paper trade at the current real price. Only after the user approves."""
    import paper
    return paper.close_trade(trade_id)


if __name__ == "__main__":
    mcp.run()

