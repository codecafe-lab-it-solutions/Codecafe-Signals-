"""Offline Test Suite for CodeCafe Omni Universal Trading Assistant.
Run: uv run python test_omni.py
"""
import numpy as np

from chart_vision import (
    analyze_market_structure,
    cluster_levels,
    detect_candlestick_pattern,
    find_pivots,
)
from executor import execute_trade_hybrid
from news_scraper import analyze_news_sentiment
from universal_data import render_ascii_chart, render_svg_chart

# 1. Candlestick pattern recognition
# Hammer
hammer = detect_candlestick_pattern(open_=99.5, high=101.0, low=95.0, close=100.5, prev_open=102.0, prev_close=100.0)
assert "Hammer / Bullish Pin Bar" in hammer, hammer

# Bullish Engulfing
engulf = detect_candlestick_pattern(open_=98.0, high=103.0, low=97.0, close=102.5, prev_open=101.0, prev_close=99.0)
assert "Bullish Engulfing" in engulf, engulf

# Doji
doji = detect_candlestick_pattern(open_=100.0, high=102.0, low=98.0, close=100.05, prev_open=100.0, prev_close=101.0)
assert "Doji (Indecision)" in doji, doji

# 2. Pivot Clustering & Levels
levels = cluster_levels([1.1010, 1.1012, 1.1014, 1.1500, 1.1502])
assert len(levels) == 2, levels
assert 1.1010 <= levels[0] <= 1.1015
assert 1.1499 <= levels[1] <= 1.1505

# 3. Market Structure & Trade Plan
n = 100
t = np.arange(n) * 3600
drift = np.linspace(100, 120, n)
c = drift + np.sin(np.linspace(0, 10, n)) * 2
mock_candles = {
    "symbol": "MOCK",
    "interval": "H1",
    "source": "test",
    "time": t,
    "open": c - 0.5,
    "high": c + 1.0,
    "low": c - 1.0,
    "close": c,
}
struct = analyze_market_structure(mock_candles)
assert struct["trend"] == "Uptrend"
assert struct["nearest_support"] > 0
assert struct["nearest_resistance"] > 0
assert "recommendation" in struct

# 4. Chart Rendering
ascii_txt = render_ascii_chart(mock_candles, height=10, width=30)
assert "MOCK" in ascii_txt and "Latest:" in ascii_txt

svg_txt = render_svg_chart(mock_candles, width=400, height=200)
assert "<svg" in svg_txt and "</svg>" in svg_txt

# 5. News Sentiment Scoring
mock_articles = [
    {"title": "Tech stocks surge as profits beat estimates", "summary": "Record rally continues."},
    {"title": "Fed announces upcoming FOMC interest rate decision", "summary": "Inflation update."},
    {"title": "Company shares slump following earnings miss", "summary": "Downgrade by analysts."},
]
sentiment = analyze_news_sentiment(mock_articles)
assert sentiment["bullish_signals"] > 0
assert sentiment["bearish_signals"] > 0
assert any("FOMC" in f or "Rate" in f for f in sentiment["high_impact_flags"])

# 6. Hybrid Executor Safety Guardrails
# Rejects without confirmation
unconfirmed = execute_trade_hybrid("paper", "AAPL", "BUY", 10, sl=140.0, tp=160.0, confirm=False)
assert unconfirmed["status"] == "AWAITING_CONFIRMATION"

# Rejects missing Stop Loss
try:
    execute_trade_hybrid("paper", "AAPL", "BUY", 10, sl=0.0, tp=160.0, confirm=True)
    assert False, "Should fail without SL"
except ValueError:
    pass

# Paper broker: offline, on fake candles and a temp account file
import os
import tempfile
import time

import paper

import store

store.URL, store.DIR = "", tempfile.mkdtemp()  # never touch the real account or database
paper.USER.set("test")
now = time.time()
bars = {"time": np.array([now - 900, now + 1, now + 2]), "high": np.array([150.0, 151.0, 161.0]),
        "low": np.array([139.0, 149.0, 150.0]), "close": np.array([150.0, 150.0, 160.0])}
paper.fetch = lambda *a: bars

paper_res = execute_trade_hybrid("paper", "AAPL", "BUY", 10, sl=140.0, tp=170.0, confirm=True)
assert paper_res["ok"] is True and paper_res["trade"]["entry"] == 160.0  # filled at the latest close
try:
    paper.open_trade("AAPL", "BUY", 10, sl=170.0, price=150.0)
    assert False, "BUY with SL above entry must fail"
except ValueError:
    pass
try:
    paper.open_trade("AAPL", "BUY", 1000, sl=140.0, price=150.0)  # risks 10000 USD = 100% of balance
    assert False, "over-risk trade must fail"
except ValueError:
    pass
paper.open_trade("AAPL", "BUY", 10, sl=145.0, tp=160.5, price=150.0)  # id 2: bar 3 high 161 hits TP
paper.open_trade("AAPL", "SELL", 10, sl=160.5, tp=140.0, price=150.0)  # id 3: bar 3 high 161 hits SL
pos = paper.positions()
closed = {t["id"]: t for t in pos["closed"]}
assert closed[2]["status"] == "TAKE_PROFIT" and closed[2]["pnl"] == 105.0, closed
assert closed[3]["status"] == "STOP_LOSS" and closed[3]["pnl"] == -105.0, closed
assert [t["id"] for t in pos["open"]] == [1]  # bar 1 low 139 is before it opened, so no SL
assert paper.close_trade(1, price=165.0)["trade"]["pnl"] == 50.0
assert paper.load()["balance"]["USD"] == 10050.0
assert paper.currency("RELIANCE.NS") == "INR"
assert paper.daily_pnl() == 50.0  # +105 TP, -105 SL, +50 manual close
paper.USER.set("someone_else")
assert paper.load()["balance"]["USD"] == 10000.0  # accounts are separate per login
paper.USER.set("test")

# UI Dry-run check
ui_dry = execute_trade_hybrid("ui", "AAPL", "BUY", 10, sl=140.0, tp=160.0, method="ui", confirm=True, window_keyword="notepad")
assert "ok" in ui_dry  # Returns result or clean error if window not found

# Screen vision optical frame analysis
from screen_vision import analyze_chart_frame
from PIL import Image, ImageDraw
import io
img = Image.new("RGB", (800, 600), color=(18, 18, 18))
d = ImageDraw.Draw(img)
for i, x in enumerate(range(600, 750, 20)):
    d.rectangle([x, 400 - i * 20, x + 12, 500 - i * 20], fill=(38, 166, 154))
b = io.BytesIO()
img.save(b, format="JPEG")
v_res = analyze_chart_frame(b.getvalue())
assert v_res["action"] == "CALL / BUY" and v_res["confidence"] > 70

print("All CodeCafe Omni tests passed successfully!")
