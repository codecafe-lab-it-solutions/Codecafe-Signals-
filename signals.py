"""Pure indicator + signal + backtest + risk maths. No MT5 import, so it is testable offline.

Strategy v2 (picked 2026-11-04 from 32 variants on the first 70% of 8 pairs x H1/H4 history,
then confirmed on the unseen last 30%): EMA20/50 cross + RSI filter, only with the EMA200
trend, only during London/New York hours, SL 2xATR, TP 3xSL.
"""
import math

import numpy as np

FAST_EMA = 20
SLOW_EMA = 50
TREND_EMA = 200
TREND_SLOPE_BARS = 20
RSI_LEN = 14
ATR_LEN = 14
SL_ATR_MULT = 2.0
REWARD_RISK = 3.0
# Broker server time (MetaQuotes-Demo is UTC+2, UTC+3 in summer): 09-19 covers London + New York.
SESSION_HOURS = (9, 19)
MIN_BARS = TREND_EMA + TREND_SLOPE_BARS + 2


def ema(values, n):
    values = np.asarray(values, dtype=float)
    out = np.empty_like(values)
    k = 2 / (n + 1)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = values[i] * k + out[i - 1] * (1 - k)
    return out


def rsi_series(close, n=RSI_LEN):
    close = np.asarray(close, dtype=float)
    out = np.full(len(close), np.nan)
    delta = np.diff(close)
    if len(delta) < n:
        return out
    gain = np.clip(delta, 0, None)
    loss = np.clip(-delta, 0, None)
    avg_g, avg_l = gain[:n].mean(), loss[:n].mean()
    for i in range(n, len(delta) + 1):
        if i > n:  # Wilder smoothing
            avg_g = (avg_g * (n - 1) + gain[i - 1]) / n
            avg_l = (avg_l * (n - 1) + loss[i - 1]) / n
        out[i] = 100.0 if avg_l == 0 else 100 - 100 / (1 + avg_g / avg_l)
    return out


def atr_series(high, low, close, n=ATR_LEN):
    high, low, close = (np.asarray(a, dtype=float) for a in (high, low, close))
    out = np.full(len(close), np.nan)
    tr = np.maximum(high[1:] - low[1:], np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])))
    if len(tr) < n:
        return out
    val = tr[:n].mean()
    out[n] = val
    for j in range(n, len(tr)):
        val = (val * (n - 1) + tr[j]) / n
        out[j + 1] = val
    return out


def rsi(close, n=RSI_LEN):
    return float(rsi_series(close, n)[-1])


def atr(high, low, close, n=ATR_LEN):
    return float(atr_series(high, low, close, n)[-1])


def _indicators(high, low, close):
    return (ema(close, FAST_EMA), ema(close, SLOW_EMA), ema(close, TREND_EMA),
            rsi_series(close), atr_series(high, low, close))


def server_hour(t):
    """Hour of an MT5 bar/tick timestamp (seconds, broker server time)."""
    return int(t // 3600 % 24)


def _evaluate(i, time, close, fast, slow, trend_ema, r, a, session=SESSION_HOURS):
    """Signal on closed bar i. Shared by live scans and the backtester so both use identical rules.
    session: (start, end) hours in the timestamps' own clock, or None to trade around the clock."""
    price, rv = float(close[i]), float(r[i])
    trend_up = slow[i] > trend_ema[i] and trend_ema[i] > trend_ema[i - TREND_SLOPE_BARS]
    trend_down = slow[i] < trend_ema[i] and trend_ema[i] < trend_ema[i - TREND_SLOPE_BARS]
    trend = "up" if trend_up else "down" if trend_down else "sideways"
    crossed_up = fast[i - 1] <= slow[i - 1] and fast[i] > slow[i]
    crossed_down = fast[i - 1] >= slow[i - 1] and fast[i] < slow[i]
    hour = server_hour(time[i])
    in_session = session is None or session[0] <= hour < session[1]
    result = {"signal": "WAIT", "price": price, "trend": trend, "ema_fast": round(float(fast[i]), 6),
              "ema_slow": round(float(slow[i]), 6), "ema_trend": round(float(trend_ema[i]), 6),
              "rsi": round(rv, 2), "atr": round(float(a[i]), 6), "reasons": []}
    reasons = result["reasons"]

    if not (crossed_up or crossed_down):
        reasons.append(f"No EMA{FAST_EMA}/{SLOW_EMA} cross on the last closed bar; trend is {trend}, RSI {rv:.0f}")
        return result
    sign = 1 if crossed_up else -1
    word = "above" if sign > 0 else "below"
    reasons.append(f"EMA{FAST_EMA} crossed {word} EMA{SLOW_EMA}")
    blockers = []
    if not ((50 <= rv <= 70) if sign > 0 else (30 <= rv <= 50)):
        blockers.append(f"RSI {rv:.0f} is outside the {'50-70' if sign > 0 else '30-50'} filter")
    if not (trend_up if sign > 0 else trend_down):
        blockers.append(f"the EMA{TREND_EMA} trend is {trend}, not {'up' if sign > 0 else 'down'}")
    if not in_session:
        blockers.append(f"bar hour {hour}:00 is outside London/New York hours ({session[0]}-{session[1]})")
    if blockers:
        reasons.append("but " + "; ".join(blockers))
        return result

    result["signal"] = "BUY" if sign > 0 else "SELL"
    reasons += [f"RSI {rv:.0f} confirms momentum without being stretched",
                f"EMA{SLOW_EMA} is {word} a {'rising' if sign > 0 else 'falling'} EMA{TREND_EMA}: trading with the trend",
                "London/New York session: the most liquid hours" if session else "24/7 market: no session filter"]
    sl_dist = SL_ATR_MULT * float(a[i])
    result["sl"] = round(price - sign * sl_dist, 6)
    result["tp"] = round(price + sign * sl_dist * REWARD_RISK, 6)
    result["invalidation"] = (f"close {'below' if sign > 0 else 'above'} {result['sl']} or "
                              f"EMA{SLOW_EMA} crossing back {'below' if sign > 0 else 'above'} EMA{TREND_EMA}")
    return result


def generate_signal(time, high, low, close, session=SESSION_HOURS):
    """BUY/SELL/WAIT on the last closed bar with reasons, SL/TP and invalidation.

    Pass closed bars only.
    """
    if len(close) < MIN_BARS:
        raise ValueError(f"need at least {MIN_BARS} bars, got {len(close)}")
    return _evaluate(len(close) - 1, time, close, *_indicators(high, low, close), session=session)


def backtest(time, open_, high, low, close, spread=0.0, session=SESSION_HOURS, cost_pct=0.0, sides=("BUY", "SELL")):
    """Replay the strategy bar by bar. One trade at a time, entry at next bar's open,
    exit at SL or TP. Results are in R (1R = the amount risked per trade).
    spread is in price units and is charged once per trade; cost_pct (e.g. 0.2 for two 0.1% fees)
    is a percentage of the entry price, also charged once per trade. sides=("BUY",) is long-only (spot)."""
    open_, high, low, close = (np.asarray(x, dtype=float) for x in (open_, high, low, close))
    ind = _indicators(high, low, close)
    a = ind[-1]
    trades, i = [], MIN_BARS - 1
    while i < len(close) - 1:
        s = _evaluate(i, time, close, *ind, session=session)
        if s["signal"] not in sides:  # WAIT, or a SELL on a long-only spot market
            i += 1
            continue
        sign = 1 if s["signal"] == "BUY" else -1
        entry = open_[i + 1]
        sl_dist = SL_ATR_MULT * a[i]
        sl, tp = entry - sign * sl_dist, entry + sign * sl_dist * REWARD_RISK
        outcome = None
        for j in range(i + 1, len(close)):
            hit_sl = low[j] <= sl if sign > 0 else high[j] >= sl
            hit_tp = high[j] >= tp if sign > 0 else low[j] <= tp
            if hit_sl:  # if SL and TP fall in the same bar, assume the worse case
                outcome = -1.0
                break
            if hit_tp:
                outcome = REWARD_RISK
                break
        if outcome is None:  # still open when the data ends
            break
        trades.append({"bar": i, "side": s["signal"], "r": round(outcome - (spread + entry * cost_pct / 100) / sl_dist, 4)})
        i = j
    return summarize(trades)


def summarize(trades):
    rs = np.array([t["r"] for t in trades], dtype=float)
    if len(rs) == 0:
        return {"trades": 0}
    equity = np.cumsum(rs)
    gains, losses = rs[rs > 0].sum(), -rs[rs < 0].sum()
    return {
        "trades": len(rs),
        "win_rate": round(float((rs > 0).mean()), 3),
        "total_r": round(float(rs.sum()), 2),
        "avg_r": round(float(rs.mean()), 3),
        "profit_factor": round(float(gains / losses), 2) if losses else None,
        "max_drawdown_r": round(float((np.maximum.accumulate(np.r_[0, equity]) - np.r_[0, equity]).max()), 2),
    }


def lot_size(risk_money, sl_distance, tick_size, tick_value, vol_min, vol_step, vol_max):
    """Lots so that hitting SL loses about risk_money. Rounds down to the broker's step."""
    if sl_distance <= 0 or tick_size <= 0 or tick_value <= 0:
        raise ValueError("sl_distance, tick_size and tick_value must be positive")
    loss_per_lot = sl_distance / tick_size * tick_value
    lots = math.floor(risk_money / loss_per_lot / vol_step + 1e-9) * vol_step
    return round(min(lots, vol_max), 2) if lots >= vol_min else 0.0
