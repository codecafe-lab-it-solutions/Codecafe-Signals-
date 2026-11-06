"""Advanced Market Structure & Candlestick Pattern Engine (System 1).
Implements BOS, CHOCH, FVG (Fair Value Gaps), Order Blocks, and Liquidity Sweeps.
Zero external heavy dependencies. NumPy only.
"""
from dataclasses import dataclass
from typing import Any
import numpy as np


@dataclass
class FVG:
    type: str  # "BULLISH" or "BEARISH"
    top: float
    bottom: float
    bar_index: int
    size: float


@dataclass
class OrderBlock:
    type: str  # "BULLISH" or "BEARISH"
    high: float
    low: float
    bar_index: int


def detect_fvgs(high: np.ndarray, low: np.ndarray, min_size: float = 0.0) -> list[FVG]:
    """Detect Fair Value Gaps (3-bar pattern).
    Bullish FVG: Low[i] > High[i-2]
    Bearish FVG: High[i] < Low[i-2]
    """
    fvgs = []
    n = len(high)
    for i in range(2, n):
        # Bullish gap
        if low[i] > high[i - 2]:
            gap = float(low[i] - high[i - 2])
            if gap > min_size:
                fvgs.append(FVG(type="BULLISH", top=float(low[i]), bottom=float(high[i - 2]), bar_index=i, size=gap))
        # Bearish gap
        elif high[i] < low[i - 2]:
            gap = float(low[i - 2] - high[i])
            if gap > min_size:
                fvgs.append(FVG(type="BEARISH", top=float(low[i - 2]), bottom=float(high[i]), bar_index=i, size=gap))
    return fvgs


def detect_bos_choch(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int = 5) -> dict[str, Any]:
    """Detect Break of Structure (BOS) and Change of Character (CHOCH)."""
    n = len(close)
    if n < window * 3:
        return {"events": [], "current_trend": "SIDEWAYS"}

    swing_highs = []
    swing_lows = []
    for i in range(window, n - window):
        if high[i] == max(high[i - window : i + window + 1]):
            swing_highs.append((i, float(high[i])))
        if low[i] == min(low[i - window : i + window + 1]):
            swing_lows.append((i, float(low[i])))

    events = []
    trend = "SIDEWAYS"

    # Analyze swing breaks
    for i in range(len(close)):
        p = close[i]
        # Check break of prior swing high
        prior_highs = [h for h in swing_highs if h[0] < i]
        if prior_highs and p > prior_highs[-1][1]:
            evt_type = "BOS" if trend == "BULLISH" else "CHOCH"
            events.append({"type": f"BULLISH_{evt_type}", "bar_index": i, "broken_level": prior_highs[-1][1]})
            trend = "BULLISH"

        # Check break of prior swing low
        prior_lows = [l for l in swing_lows if l[0] < i]
        if prior_lows and p < prior_lows[-1][1]:
            evt_type = "BOS" if trend == "BEARISH" else "CHOCH"
            events.append({"type": f"BEARISH_{evt_type}", "bar_index": i, "broken_level": prior_lows[-1][1]})
            trend = "BEARISH"

    return {
        "events": events[-5:],
        "current_trend": trend,
        "recent_swing_high": swing_highs[-1][1] if swing_highs else float(high.max()),
        "recent_swing_low": swing_lows[-1][1] if swing_lows else float(low.min()),
    }


def detect_order_blocks(open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> list[OrderBlock]:
    """Identify recent bullish and bearish order blocks.
    Bullish OB: Last down candle before strong up move breaking recent high.
    Bearish OB: Last up candle before strong down move breaking recent low.
    """
    obs = []
    n = len(close)
    if n < 5:
        return obs

    for i in range(1, n - 2):
        body = abs(close[i] - open_[i])
        next_body = abs(close[i + 1] - open_[i + 1])
        # Bullish displacement
        if close[i] < open_[i] and close[i + 1] > open_[i + 1] and next_body > body * 1.5 and close[i + 1] > high[i]:
            obs.append(OrderBlock(type="BULLISH", high=float(high[i]), low=float(low[i]), bar_index=i))
        # Bearish displacement
        elif close[i] > open_[i] and close[i + 1] < open_[i + 1] and next_body > body * 1.5 and close[i + 1] < low[i]:
            obs.append(OrderBlock(type="BEARISH", high=float(high[i]), low=float(low[i]), bar_index=i))
    return obs[-6:]  # Keep last 6


def detect_liquidity_sweeps(high: np.ndarray, low: np.ndarray, close: np.ndarray, window: int = 10) -> list[dict]:
    """Detect liquidity sweeps (wick breaches swing point but closes back inside)."""
    sweeps = []
    n = len(close)
    if n < window + 2:
        return sweeps

    for i in range(window, n):
        prev_high = float(high[i - window : i].max())
        prev_low = float(low[i - window : i].min())

        # Bullish sweep (swept low and closed above)
        if low[i] < prev_low and close[i] > prev_low:
            sweeps.append({"type": "BULLISH_SWEEP", "level": prev_low, "bar_index": i})
        # Bearish sweep (swept high and closed below)
        elif high[i] > prev_high and close[i] < prev_high:
            sweeps.append({"type": "BEARISH_SWEEP", "level": prev_high, "bar_index": i})
    return sweeps[-4:]


def detect_extended_candlesticks(open_: np.ndarray, high: np.ndarray, low: np.ndarray, close: np.ndarray) -> list[str]:
    """Identify comprehensive candlestick patterns on recent bars."""
    patterns = []
    n = len(close)
    if n < 3:
        return patterns

    o1, h1, l1, c1 = open_[-3], high[-3], low[-3], close[-3]
    o2, h2, l2, c2 = open_[-2], high[-2], low[-2], close[-2]
    o3, h3, l3, c3 = open_[-1], high[-1], low[-1], close[-1]

    # Morning Star (Bearish, Small/Doji, Strong Bullish)
    if c1 < o1 and abs(c2 - o2) < abs(c1 - o1) * 0.4 and c3 > o3 and c3 > (o1 + c1) / 2:
        patterns.append("Morning Star")

    # Evening Star (Bullish, Small/Doji, Strong Bearish)
    if c1 > o1 and abs(c2 - o2) < abs(c1 - o1) * 0.4 and c3 < o3 and c3 < (o1 + c1) / 2:
        patterns.append("Evening Star")

    # Three White Soldiers
    if c1 > o1 and c2 > o2 and c3 > o3 and c3 > c2 > c1 and o2 > o1 and o3 > o2:
        patterns.append("Three White Soldiers")

    # Three Black Crows
    if c1 < o1 and c2 < o2 and c3 < o3 and c3 < c2 < c1 and o2 < o1 and o3 < o2:
        patterns.append("Three Black Crows")

    # Inside Bar
    if h3 <= h2 and l3 >= l2:
        patterns.append("Inside Bar")

    return patterns


def get_market_structure_report(candles: dict) -> dict[str, Any]:
    """Full comprehensive market structure assessment."""
    open_ = np.asarray(candles["open"], dtype=float)
    high = np.asarray(candles["high"], dtype=float)
    low = np.asarray(candles["low"], dtype=float)
    close = np.asarray(candles["close"], dtype=float)

    bos_data = detect_bos_choch(high, low, close)
    fvgs = detect_fvgs(high, low)
    obs = detect_order_blocks(open_, high, low, close)
    sweeps = detect_liquidity_sweeps(high, low, close)
    candlesticks = detect_extended_candlesticks(open_, high, low, close)

    # Active nearest FVG
    current_p = float(close[-1])
    active_bull_fvg = [f for f in fvgs if f.type == "BULLISH" and f.top < current_p]
    active_bear_fvg = [f for f in fvgs if f.type == "BEARISH" and f.bottom > current_p]

    return {
        "trend": bos_data["current_trend"],
        "structural_events": bos_data["events"],
        "recent_swing_high": bos_data["recent_swing_high"],
        "recent_swing_low": bos_data["recent_swing_low"],
        "active_fvgs_count": len(fvgs),
        "nearest_bullish_fvg": active_bull_fvg[-1].__dict__ if active_bull_fvg else None,
        "nearest_bearish_fvg": active_bear_fvg[-1].__dict__ if active_bear_fvg else None,
        "order_blocks": [ob.__dict__ for ob in obs],
        "liquidity_sweeps": sweeps,
        "candlestick_patterns": candlesticks,
    }

