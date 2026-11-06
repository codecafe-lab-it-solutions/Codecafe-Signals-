"""Technical Chart Pattern & Level Analyzer (Offline Math + Vision Prompting).

Analyzes OHLCV data to detect:
1. Support and Resistance zones (dynamic pivot clusters)
2. Candlestick patterns (Pin bars / Hammers, Engulfing, Doji, Inside bars)
3. Trend direction & momentum
4. Exact trade levels: Suggested Entry, Stop Loss, Take Profit (1:2 to 1:3 R:R), and Invalidation.
"""
import numpy as np

from signals import atr_series, ema, rsi_series


def find_pivots(high: np.ndarray, low: np.ndarray, window: int = 5) -> dict:
    """Find local swing highs and swing lows."""
    highs, lows = [], []
    n = len(high)
    for i in range(window, n - window):
        if high[i] == max(high[i - window : i + window + 1]):
            highs.append(float(high[i]))
        if low[i] == min(low[i - window : i + window + 1]):
            lows.append(float(low[i]))
    return {"swing_highs": sorted(highs), "swing_lows": sorted(lows)}


def detect_candlestick_pattern(open_: float, high: float, low: float, close: float, prev_open: float, prev_close: float) -> list[str]:
    """Identify price action patterns on the latest closed candle."""
    patterns = []
    body = abs(close - open_)
    candle_range = high - low
    if candle_range <= 0:
        return patterns

    upper_wick = high - max(open_, close)
    lower_wick = min(open_, close) - low
    is_bull = close > open_
    prev_bull = prev_close > prev_open

    # 1. Doji (tiny body compared to range)
    if body <= candle_range * 0.10:
        patterns.append("Doji (Indecision)")

    # 2. Hammer / Bullish Pin Bar (long lower shadow, small upper body)
    if lower_wick >= body * 2.0 and upper_wick <= body * 0.5:
        patterns.append("Hammer / Bullish Pin Bar")

    # 3. Shooting Star / Bearish Pin Bar (long upper shadow, small lower body)
    if upper_wick >= body * 2.0 and lower_wick <= body * 0.5:
        patterns.append("Shooting Star / Bearish Pin Bar")

    # 4. Bullish Engulfing
    if is_bull and not prev_bull and close >= prev_open and open_ <= prev_close and body > abs(prev_close - prev_open):
        patterns.append("Bullish Engulfing")

    # 5. Bearish Engulfing
    if not is_bull and prev_bull and close <= prev_open and open_ >= prev_close and body > abs(prev_close - prev_open):
        patterns.append("Bearish Engulfing")

    return patterns


def cluster_levels(levels: list[float], tolerance_pct: float = 0.005) -> list[float]:
    """Consolidate clustered price levels within tolerance."""
    if not levels:
        return []
    levels = sorted(levels)
    clusters = [[levels[0]]]
    for x in levels[1:]:
        if abs(x - clusters[-1][-1]) / clusters[-1][-1] <= tolerance_pct:
            clusters[-1].append(x)
        else:
            clusters.append([x])
    return [round(float(np.mean(c)), 4) for c in clusters]


def analyze_market_structure(candles: dict) -> dict:
    """Full technical structure analysis on OHLCV data."""
    close = np.asarray(candles["close"], dtype=float)
    high = np.asarray(candles["high"], dtype=float)
    low = np.asarray(candles["low"], dtype=float)
    open_ = np.asarray(candles["open"], dtype=float)
    n = len(close)

    if n < 30:
        raise ValueError(f"Need at least 30 candles, got {n}")

    # Moving averages & indicators
    e20 = ema(close, min(20, n // 2))
    e50 = ema(close, min(50, n // 2))
    atrs = atr_series(high, low, close, 14)
    current_atr = float(atrs[-1]) if not np.isnan(atrs[-1]) else float((high - low).mean())
    rsis = rsi_series(close, 14)
    current_rsi = float(rsis[-1]) if not np.isnan(rsis[-1]) else 50.0

    curr_p = float(close[-1])
    pivots = find_pivots(high, low, window=min(5, n // 6))
    resistance_levels = [lvl for lvl in cluster_levels(pivots["swing_highs"]) if lvl > curr_p]
    support_levels = [lvl for lvl in cluster_levels(pivots["swing_lows"]) if lvl < curr_p]

    nearest_res = resistance_levels[0] if resistance_levels else round(curr_p + 2.5 * current_atr, 4)
    nearest_sup = support_levels[-1] if support_levels else round(curr_p - 2.5 * current_atr, 4)

    # Trend evaluation
    is_uptrend = e20[-1] > e50[-1] and curr_p > e20[-1]
    is_downtrend = e20[-1] < e50[-1] and curr_p < e20[-1]
    trend = "Uptrend" if is_uptrend else "Downtrend" if is_downtrend else "Consolidation / Sideways"

    # Candle patterns on the last 2 bars
    patterns = detect_candlestick_pattern(open_[-1], high[-1], low[-1], close[-1], open_[-2], close[-2])

    # Trade logic
    action = "WAIT"
    entry, sl, tp, rr = None, None, None, None
    reasons = []

    if is_uptrend and any("Bullish" in p or "Hammer" in p for p in patterns):
        action = "BUY"
        entry = curr_p
        sl = round(max(nearest_sup - 0.5 * current_atr, entry - 2.0 * current_atr), 4)
        risk = entry - sl
        tp = round(max(nearest_res, entry + 2.5 * risk), 4)
        rr = round((tp - entry) / risk, 2) if risk > 0 else 2.5
        reasons.append(f"Uptrend confirmed (EMA20 > EMA50) with bullish pattern: {', '.join(patterns)}")
    elif is_downtrend and any("Bearish" in p or "Shooting" in p for p in patterns):
        action = "SELL"
        entry = curr_p
        sl = round(min(nearest_res + 0.5 * current_atr, entry + 2.0 * current_atr), 4)
        risk = sl - entry
        tp = round(min(nearest_sup, entry - 2.5 * risk), 4)
        rr = round((entry - tp) / risk, 2) if risk > 0 else 2.5
        reasons.append(f"Downtrend confirmed (EMA20 < EMA50) with bearish pattern: {', '.join(patterns)}")
    else:
        reasons.append(f"Market in {trend} (RSI: {current_rsi:.1f}). Patterns: {patterns or 'None'}. Waiting for clear rejection at key level.")

    return {
        "symbol": candles.get("symbol", "UNKNOWN"),
        "interval": candles.get("interval", "H1"),
        "current_price": curr_p,
        "trend": trend,
        "rsi": round(current_rsi, 1),
        "atr": round(current_atr, 4),
        "candlestick_patterns": patterns,
        "nearest_support": nearest_sup,
        "nearest_resistance": nearest_res,
        "recommendation": {
            "action": action,
            "entry": entry,
            "sl": sl,
            "tp": tp,
            "rr_ratio": rr,
            "reasons": reasons,
            "invalidation": f"Price crosses {'below ' + str(sl) if action == 'BUY' else 'above ' + str(sl)}" if action != "WAIT" else "N/A",
        },
    }


def format_chart_vision_prompt(image_path: str, context: dict | None = None) -> str:
    """Generate multimodal analysis prompt for LLMs reading chart screenshots."""
    ctx_str = ""
    if context:
        ctx_str = f"\nMarket context: Symbol {context.get('symbol', '')}, Timeframe {context.get('interval', '')}, Current Price {context.get('current_price', '')}"
    return f"""Analyze this financial chart image:{ctx_str}
1. Identify primary trend: Bullish, Bearish, or Ranging.
2. Highlight major Support and Resistance horizontal zones or trendlines.
3. Identify notable candlestick patterns on the latest bars (e.g. Pin bar, Engulfing, Consolidation).
4. Provide structured Trade Setup:
   - Action: BUY / SELL / WAIT
   - Entry Price
   - Invalidation / Stop Loss level
   - Take Profit target (minimum 1:2 R:R)
   - Risk warning / conditions to cancel trade.
"""

