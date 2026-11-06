"""Offline checks for signals.py. Run: uv run python test_core.py"""
import numpy as np

from signals import (MIN_BARS, REWARD_RISK, SESSION_HOURS, _evaluate, _indicators, atr, backtest, ema,
                     generate_signal, lot_size, rsi, server_hour)

# EMA of a constant is the constant
assert np.allclose(ema([5.0] * 30, 10), 5.0)

# RSI: only rising -> 100, mixed -> between 0 and 100
assert rsi(np.arange(1, 40, dtype=float)) == 100.0
mixed = 1.1 + 0.01 * np.sin(np.arange(80))
assert 0 < rsi(mixed) < 100

# ATR of bars with a fixed 0.002 range and flat closes is 0.002
c = np.full(40, 1.1)
assert abs(atr(c + 0.001, c - 0.001, c) - 0.002) < 1e-12

assert server_hour(3600 * 24 * 100 + 3600 * 13 + 59) == 13


def hourly(n, start_hour=0):
    return (np.arange(n) + start_hour) * 3600


# Noisy trends: every signal obeys every rule; WAIT always explains itself
seen = set()
for seed in range(40):
    rng = np.random.default_rng(seed)
    drift = rng.choice([-1, 1]) * 0.0002
    close = 1.1 + np.cumsum(drift + rng.normal(0, 0.0015, 600))
    high, low, t = close + 0.0005, close - 0.0005, hourly(600, seed)
    full = _indicators(high, low, close)
    for i in range(MIN_BARS, 600):
        s = _evaluate(i, t, close, *full)
        assert s["reasons"], "every signal, WAIT included, must explain itself"
        if s["signal"] != "WAIT":
            assert SESSION_HOURS[0] <= server_hour(t[i]) < SESSION_HOURS[1]
            assert s["invalidation"]
        if s["signal"] == "BUY":
            assert s["trend"] == "up" and 50 <= s["rsi"] <= 70 and s["sl"] < s["price"] < s["tp"]
        elif s["signal"] == "SELL":
            assert s["trend"] == "down" and 30 <= s["rsi"] <= 50 and s["tp"] < s["price"] < s["sl"]
        else:
            assert "sl" not in s
        seen.add(s["signal"])
assert {"BUY", "SELL", "WAIT"} <= seen, seen

# Same bars outside the session never trade
rng = np.random.default_rng(3)
close = 1.1 + np.cumsum(0.0002 + rng.normal(0, 0.0015, 3000))
high, low = close + 0.0005, close - 0.0005
night = np.full(3000, 2 * 3600)  # every bar stamped 02:00
full = _indicators(high, low, close)
assert all(_evaluate(i, night, close, *full)["signal"] == "WAIT" for i in range(MIN_BARS, 3000))

# Backtester uses exactly the live rules: full-series evaluation equals prefix evaluation
rng = np.random.default_rng(7)
close = 1.1 + np.cumsum(rng.normal(0, 0.001, 3000))
high, low, t = close + 0.0006, close - 0.0006, hourly(3000)
full = _indicators(high, low, close)
for i in range(MIN_BARS, 3000, 37):
    p = slice(0, i + 1)
    assert _evaluate(i, t, close, *full)["signal"] == generate_signal(t[p], high[p], low[p], close[p])["signal"]

# Backtest stats are consistent; every trade is a full loss or a full win
open_ = np.r_[close[0], close[:-1]]
bt = backtest(t, open_, high, low, close)
assert bt["trades"] > 5, bt
assert 0 <= bt["win_rate"] <= 1 and bt["max_drawdown_r"] >= 0
wins = round(bt["win_rate"] * bt["trades"])  # win_rate is rounded, so recover the integer count
assert abs(bt["total_r"] - (wins * REWARD_RISK - (bt["trades"] - wins))) < 0.01
# Spread can only make results worse
assert backtest(t, open_, high, low, close, spread=0.0002)["total_r"] < bt["total_r"]
assert backtest(t[:50], open_[:50], high[:50], low[:50], close[:50]) == {"trades": 0}

# Crypto options: 24/7 trades at least as often as session-only; long-only never shorts; fees only hurt
bt247 = backtest(t, open_, high, low, close, session=None)
assert bt247["trades"] >= bt["trades"]
longs = backtest(t, open_, high, low, close, sides=("BUY",))
assert 0 < longs["trades"] <= bt["trades"]
assert backtest(t, open_, high, low, close, sides=("BUY",), cost_pct=0.2)["total_r"] < longs["total_r"]
assert generate_signal(t, high, low, close, session=None)["reasons"]

# Lot size: EURUSD-like, $10 risk, 20 pip SL, $1 per 0.00001 tick per lot -> 0.05 lots
assert lot_size(10, 0.0020, 0.00001, 1.0, 0.01, 0.01, 100) == 0.05
# Risk too small for min lot -> 0
assert lot_size(0.1, 0.0020, 0.00001, 1.0, 0.01, 0.01, 100) == 0.0
# Capped at vol_max
assert lot_size(1e9, 0.0020, 0.00001, 1.0, 0.01, 0.01, 2.0) == 2.0

print("all checks passed")
