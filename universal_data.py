"""Universal Market Data Scraper & Chart Generator (Stdlib + NumPy only).

Fetches OHLCV candles & quotes from:
1. Yahoo Finance (Stocks, Forex pairs like EURUSD=X, Crypto like BTC-USD, Commodities like GC=F)
2. Bybit (via bybit.py for Crypto spot)
3. MT5 (via MetaTrader5 for Forex/CFD if terminal is open)

Also generates text/ASCII charts and self-contained SVG candle charts without external plotting libs.
"""
import json
import math
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import numpy as np

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
YF_INTERVALS = {"M1": "1m", "M5": "5m", "M15": "15m", "H1": "60m", "H4": "1h", "D1": "1d"}


def fetch_yahoo_candles(symbol: str, interval: str = "H1", count: int = 100) -> dict:
    """Fetch candles from Yahoo Finance v8 chart API using stdlib."""
    yf_interval = YF_INTERVALS.get(interval.upper(), "60m")
    # Yahoo range based on interval
    range_map = {"1m": "1d", "5m": "5d", "15m": "5d", "60m": "1mo", "1h": "1mo", "1d": "1y"}
    yf_range = range_map.get(yf_interval, "1mo")
    
    url = f"https://query2.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(symbol)}?interval={yf_interval}&range={yf_range}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    
    with urllib.request.urlopen(req, timeout=12) as resp:
        data = json.loads(resp.read().decode())
    
    result = data["chart"]["result"][0]
    timestamps = result.get("timestamp", [])
    quotes = result["indicators"]["quote"][0]
    
    opens = quotes.get("open", [])
    highs = quotes.get("high", [])
    lows = quotes.get("low", [])
    closes = quotes.get("close", [])
    volumes = quotes.get("volume", [])
    
    # Filter valid non-null rows
    valid = []
    for i in range(len(timestamps)):
        if all(quotes[k][i] is not None for k in ("open", "high", "low", "close")):
            valid.append({
                "time": timestamps[i],
                "open": float(opens[i]),
                "high": float(highs[i]),
                "low": float(lows[i]),
                "close": float(closes[i]),
                "volume": float(volumes[i] or 0),
            })
            
    if not valid:
        raise RuntimeError(f"No candle data returned for {symbol}")
        
    valid = valid[-count:]
    return {
        "symbol": symbol,
        "interval": interval,
        "source": "yahoo",
        "time": np.array([x["time"] for x in valid], dtype=int),
        "open": np.array([x["open"] for x in valid], dtype=float),
        "high": np.array([x["high"] for x in valid], dtype=float),
        "low": np.array([x["low"] for x in valid], dtype=float),
        "close": np.array([x["close"] for x in valid], dtype=float),
        "volume": np.array([x["volume"] for x in valid], dtype=float),
    }


def fetch_universal_candles(symbol: str, timeframe: str = "H1", count: int = 100) -> dict:
    """Intelligently route symbol to MT5, Bybit, or Yahoo Finance."""
    # 1. Try MT5 if MT5 is initialized or available
    try:
        import MetaTrader5 as mt5
        from server import closed_rates, connect
        connect()
        r = closed_rates(symbol, timeframe, count)
        if r is not None and len(r) > 0:
            return {
                "symbol": symbol, "interval": timeframe, "source": "mt5",
                "time": r["time"].astype(int), "open": r["open"].astype(float),
                "high": r["high"].astype(float), "low": r["low"].astype(float),
                "close": r["close"].astype(float), "volume": r["tick_volume"].astype(float),
            }
    except Exception:
        pass  # Fall through to Bybit / Yahoo
            
    # 2. Try Bybit if crypto symbol ends with USDT
    if symbol.upper().endswith("USDT"):
        try:
            import bybit
            k = bybit.klines(symbol.upper(), timeframe, count)
            k["symbol"] = symbol.upper()
            k["interval"] = timeframe
            k["source"] = "bybit"
            k["volume"] = np.zeros_like(k["close"])
            return k
        except Exception:
            pass
            
    # 3. Yahoo Finance fallback for Commodities, Stocks, Crypto (BTC-USD), Index (^GSPC), Forex (EURUSD=X)
    commodity_map = {
        "XAUUSD": "GC=F",
        "GOLD": "GC=F",
        "XAGUSD": "SI=F",
        "SILVER": "SI=F",
        "USOUSD": "CL=F",
        "USOIL": "CL=F",
        "WTI": "CL=F",
        "CRUDE": "CL=F",
        "SPX500": "ES=F",
        "US500": "ES=F",
        "ES": "ES=F",
    }
    yf_symbol = commodity_map.get(symbol.upper(), symbol)
    if yf_symbol == symbol:
        if len(symbol) == 6 and symbol.isupper() and not symbol.endswith("USDT") and "=" not in symbol:
            yf_symbol = f"{symbol}=X"  # e.g., EURUSD -> EURUSD=X
        elif symbol.upper().endswith("USDT"):
            yf_symbol = f"{symbol[:-4]}-USD"  # BTCUSDT -> BTC-USD
        
    return fetch_yahoo_candles(yf_symbol, timeframe, count)


def render_ascii_chart(candles: dict, height: int = 15, width: int = 60) -> str:
    """Render portable terminal ASCII candlestick / line chart from candle dict."""
    closes = candles["close"][-width:]
    highs = candles["high"][-width:]
    lows = candles["low"][-width:]

    if len(closes) == 0:
        return "No data to render."

    min_p, max_p = float(lows.min()), float(highs.max())
    p_range = max_p - min_p or 1.0

    grid = [[" " for _ in range(len(closes))] for _ in range(height)]

    for x, (h, l, c, o) in enumerate(zip(highs, lows, closes, candles["open"][-width:])):
        y_high = int((h - min_p) / p_range * (height - 1))
        y_low = int((l - min_p) / p_range * (height - 1))
        y_close = int((c - min_p) / p_range * (height - 1))
        y_open = int((o - min_p) / p_range * (height - 1))

        # draw wick
        for y in range(min(y_low, y_high), max(y_low, y_high) + 1):
            grid[height - 1 - y][x] = "|"

        # draw body (# for bull, o for bear)
        body_char = "#" if c >= o else "o"
        for y in range(min(y_open, y_close), max(y_open, y_close) + 1):
            grid[height - 1 - y][x] = body_char

    lines = []
    lines.append(f"--- {candles.get('symbol', 'CHART')} [{candles.get('interval', 'H1')}] (Source: {candles.get('source', 'auto')}) ---")
    for r, row in enumerate(grid):
        val = max_p - (r / (height - 1)) * p_range
        lines.append(f"{val:>9.4f} + {''.join(row)}")

    first_dt = datetime.fromtimestamp(candles["time"][-len(closes)], timezone.utc).strftime("%m-%d %H:%M")
    last_dt = datetime.fromtimestamp(candles["time"][-1], timezone.utc).strftime("%m-%d %H:%M")
    lines.append(f"          +{'=' * len(closes)}")
    lines.append(f"           {first_dt}{' ' * max(0, len(closes) - 24)}{last_dt} UTC")
    lines.append(f"Latest: {closes[-1]:.4f} | Low: {min_p:.4f} | High: {max_p:.4f} | Bars: {len(closes)}")
    return "\n".join(lines)


def render_svg_chart(candles: dict, width: int = 800, height: int = 400, output_path: str | None = None) -> str:
    """Generate clean standalone SVG candlestick chart file/string."""
    closes = candles["close"]
    opens = candles["open"]
    highs = candles["high"]
    lows = candles["low"]
    n = len(closes)
    
    pad_left, pad_right, pad_top, pad_bot = 60, 20, 30, 40
    plot_w = width - pad_left - pad_right
    plot_h = height - pad_top - pad_bot
    
    min_p, max_p = float(lows.min()), float(highs.max())
    p_range = max_p - min_p or 1.0
    
    candle_w = max(2, plot_w / n * 0.7)
    
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" style="background:#121212; font-family:monospace; color:#ccc;">',
        f'<rect width="{width}" height="{height}" fill="#181818"/>',
        f'<text x="{pad_left}" y="20" fill="#fff" font-size="14" font-weight="bold">{candles.get("symbol")} - {candles.get("interval")} ({candles.get("source")})</text>',
    ]
    
    # Grid lines & Y-axis labels
    for i in range(5):
        y = pad_top + (plot_h / 4) * i
        val = max_p - (i / 4.0) * p_range
        svg.append(f'<line x1="{pad_left}" y1="{y}" x2="{width - pad_right}" y2="{y}" stroke="#2a2a2a" stroke-width="1"/>')
        svg.append(f'<text x="10" y="{y + 4}" fill="#888" font-size="11">{val:.4f}</text>')
        
    for i in range(n):
        cx = pad_left + (i + 0.5) * (plot_w / n)
        is_up = closes[i] >= opens[i]
        color = "#26a69a" if is_up else "#ef5350"
        
        y_high = pad_top + (max_p - highs[i]) / p_range * plot_h
        y_low = pad_top + (max_p - lows[i]) / p_range * plot_h
        y_open = pad_top + (max_p - opens[i]) / p_range * plot_h
        y_close = pad_top + (max_p - closes[i]) / p_range * plot_h
        
        top_body = min(y_open, y_close)
        body_h = max(1.0, abs(y_close - y_open))
        
        # Wick
        svg.append(f'<line x1="{cx}" y1="{y_high}" x2="{cx}" y2="{y_low}" stroke="{color}" stroke-width="1"/>')
        # Body
        svg.append(f'<rect x="{cx - candle_w/2}" y="{top_body}" width="{candle_w}" height="{body_h}" fill="{color}"/>')
        
    svg.append('</svg>')
    out = "\n".join(svg)
    if output_path:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(out)
    return out
