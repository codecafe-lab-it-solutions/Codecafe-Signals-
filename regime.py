"""Market Regime Detection Engine (System 1.F).
Classifies market condition into measurable regimes:
- STRONG_BULL / WEAK_BULL
- STRONG_BEAR / WEAK_BEAR
- RANGING / CONSOLIDATION
- HIGH_VOLATILITY / LOW_VOLATILITY
Zero external ML libraries required. NumPy mathematical models.
"""
from dataclasses import dataclass
from typing import Any
import numpy as np

from signals import atr_series, ema


def calculate_adx(high: np.ndarray, low: np.ndarray, close: np.ndarray, period: int = 14) -> np.ndarray:
    """Calculate Average Directional Index (ADX) using NumPy."""
    n = len(close)
    if n < period * 2:
        return np.full(n, 20.0)

    up_move = high[1:] - high[:-1]
    down_move = low[:-1] - low[1:]

    plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0.0)
    minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0.0)

    tr = np.maximum(high[1:] - low[1:], np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])))

    # Smoothed sums
    def smooth(arr: np.ndarray, p: int) -> np.ndarray:
        out = np.zeros_like(arr)
        out[p - 1] = arr[:p].sum()
        for i in range(p, len(arr)):
            out[i] = out[i - 1] - (out[i - 1] / p) + arr[i]
        return out

    sm_tr = smooth(tr, period)
    sm_plus = smooth(plus_dm, period)
    sm_minus = smooth(minus_dm, period)

    with np.errstate(divide="ignore", invalid="ignore"):
        plus_di = 100.0 * (sm_plus / np.where(sm_tr == 0, 1.0, sm_tr))
        minus_di = 100.0 * (sm_minus / np.where(sm_tr == 0, 1.0, sm_tr))
        di_diff = abs(plus_di - minus_di)
        di_sum = plus_di + minus_di
        dx = 100.0 * np.where(di_sum == 0, 0.0, di_diff / np.where(di_sum == 0, 1.0, di_sum))

    adx = np.zeros(n)
    # smooth() keeps Wilder's running *sum*; dividing by period gives the average, so ADX stays in 0-100
    adx[1:][period * 2 - 2 :] = smooth(dx[period - 1 :], period)[period - 1 :] / period
    return adx


def detect_market_regime(candles: dict) -> dict[str, Any]:
    """Classify current market regime based on ADX, EMA alignment, and ATR volatility."""
    close = np.asarray(candles["close"], dtype=float)
    high = np.asarray(candles["high"], dtype=float)
    low = np.asarray(candles["low"], dtype=float)
    n = len(close)
    if n < 30:
        return {"regime": "SIDEWAYS", "volatility": "NORMAL", "adx": 20.0, "details": "Insufficient bars"}

    # EMAs
    e20 = ema(close, 20)
    e50 = ema(close, 50)
    curr_close = close[-1]
    curr_e20 = e20[-1]
    curr_e50 = e50[-1]

    # ADX trend strength
    adx_arr = calculate_adx(high, low, close, 14)
    curr_adx = float(adx_arr[-1]) if not np.isnan(adx_arr[-1]) else 20.0

    # ATR volatility relative to price
    atrs = atr_series(high, low, close, 14)
    curr_atr = float(atrs[-1]) if not np.isnan(atrs[-1]) else float((high - low).mean())
    volatility_pct = (curr_atr / curr_close) * 100.0

    # Volatility condition
    hist_vol = [float(a / c) * 100.0 for a, c in zip(atrs[-30:], close[-30:]) if not np.isnan(a)]
    median_vol = float(np.median(hist_vol)) if hist_vol else volatility_pct

    if volatility_pct > median_vol * 1.5:
        vol_status = "HIGH_VOLATILITY"
    elif volatility_pct < median_vol * 0.7:
        vol_status = "LOW_VOLATILITY"
    else:
        vol_status = "NORMAL_VOLATILITY"

    # Regime decision
    is_bull = curr_close > curr_e20 > curr_e50
    is_bear = curr_close < curr_e20 < curr_e50

    if curr_adx >= 28:
        regime = "STRONG_BULLISH_TREND" if is_bull else ("STRONG_BEARISH_TREND" if is_bear else "BREAKOUT_VOLATILE")
    elif curr_adx >= 20:
        regime = "WEAK_BULLISH_TREND" if is_bull else ("WEAK_BEARISH_TREND" if is_bear else "CONSOLIDATING")
    else:
        regime = "RANGING_SIDEWAYS"

    return {
        "regime": regime,
        "volatility_status": vol_status,
        "adx": round(curr_adx, 2),
        "atr": round(curr_atr, 4),
        "volatility_pct": round(volatility_pct, 3),
        "trend_aligned": bool(is_bull or is_bear),
        "ema_slope": "UP" if curr_e20 > curr_e50 else "DOWN",
    }

