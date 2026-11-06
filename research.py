"""Strategy research: pick on the first 70% of history (in-sample), confirm on the last 30% (out-of-sample)."""
import itertools
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from signals import atr_series, ema, rsi_series  # noqa: E402

DATA = sys.argv[1]
SYMBOLS = ["EURUSD", "GBPUSD", "USDJPY", "XAUUSD", "AUDUSD", "USDCAD", "USDCHF", "NZDUSD"]
POINT = {"USDJPY": 0.001, "XAUUSD": 0.01}
SPLIT = 0.7


def load(sym, tf):
    r = np.load(f"{DATA}/{sym}_{tf}.npy")
    return r, float(np.median(r["spread"])) * POINT.get(sym, 0.00001)


def entries(r, kind, session):
    o, h, l, c = (r[k].astype(float) for k in ("open", "high", "low", "close"))
    e20, e50, e200 = ema(c, 20), ema(c, 50), ema(c, 200)
    rs, at = rsi_series(c), atr_series(h, l, c)
    prev = lambda x: np.r_[np.nan, x[:-1]]
    up = (e50 > e200) & (e200 > np.r_[np.full(20, np.nan), e200[:-20]])
    dn = (e50 < e200) & (e200 < np.r_[np.full(20, np.nan), e200[:-20]])
    cross_up = (prev(e20) <= prev(e50)) & (e20 > e50)
    cross_dn = (prev(e20) >= prev(e50)) & (e20 < e50)
    if kind == "baseline":
        sig = np.where(cross_up & (rs >= 50) & (rs <= 70), 1, np.where(cross_dn & (rs >= 30) & (rs <= 50), -1, 0))
    elif kind == "baseline+trend":
        sig = np.where(cross_up & (rs >= 50) & (rs <= 70) & up, 1, np.where(cross_dn & (rs >= 30) & (rs <= 50) & dn, -1, 0))
    elif kind == "pullback":
        sig = np.where(up & (prev(rs) < 50) & (rs >= 50) & (c > e50), 1,
                       np.where(dn & (prev(rs) > 50) & (rs <= 50) & (c < e50), -1, 0))
    elif kind == "breakout":
        hh = np.r_[np.full(20, np.nan), [h[i - 20:i].max() for i in range(20, len(h))]]
        ll = np.r_[np.full(20, np.nan), [l[i - 20:i].min() for i in range(20, len(l))]]
        sig = np.where(up & (c > hh), 1, np.where(dn & (c < ll), -1, 0))
    if session:
        hour = (r["time"] // 3600) % 24  # broker server time (MetaQuotes = UTC+2/+3)
        sig = np.where((hour >= 9) & (hour < 19), sig, 0)
    sig[:220] = 0
    return o, h, l, c, sig, at


def simulate(o, h, l, sig, at, sl_mult, rr, spread, lo, hi):
    rs, i = [], max(lo, 220)
    while i < hi - 1:
        if sig[i] == 0:
            i += 1
            continue
        s, entry, d = sig[i], o[i + 1], sl_mult * at[i]
        sl, tp = entry - s * d, entry + s * d * rr
        out = None
        for j in range(i + 1, hi):
            if (l[j] <= sl) if s > 0 else (h[j] >= sl):
                out = -1.0
                break
            if (h[j] >= tp) if s > 0 else (l[j] <= tp):
                out = rr
                break
        if out is None:
            break
        rs.append(out - spread / d)
        i = j
    return np.array(rs)


def stats(rs):
    if len(rs) == 0:
        return dict(n=0, r=0.0, pf=0.0, dd=0.0)
    eq = np.r_[0, np.cumsum(rs)]
    loss = -rs[rs < 0].sum()
    return dict(n=len(rs), r=round(rs.sum(), 1), pf=round(rs[rs > 0].sum() / loss, 2) if loss else 99,
                dd=round((np.maximum.accumulate(eq) - eq).max(), 1), win=round((rs > 0).mean(), 3))


def run(kind, session, sl_mult, rr, part):
    per = {}
    for sym, tf in itertools.product(SYMBOLS, ("H1", "H4")):
        r, spread = load(sym, tf)
        o, h, l, c, sig, at = entries(r, kind, session)
        cut = int(len(c) * SPLIT)
        lo, hi = (0, cut) if part == "in" else (cut, len(c))
        per[f"{sym}_{tf}"] = simulate(o, h, l, sig, at, sl_mult, rr, spread, lo, hi)
    allr = np.concatenate(list(per.values()))
    s = stats(allr)
    s["pos_markets"] = sum(v.sum() > 0 for v in per.values())
    return s, per


if __name__ == "__main__":
    mode = sys.argv[2]
    if mode == "grid":
        rows = []
        for kind, session, (slm, rr) in itertools.product(
                ("baseline", "baseline+trend", "pullback", "breakout"), (False, True),
                ((1.5, 2.0), (2.0, 2.0), (2.0, 3.0), (1.5, 1.5))):
            s, _ = run(kind, session, slm, rr, "in")
            rows.append((kind, session, slm, rr, s))
            print(f"{kind:15} session={session!s:5} sl={slm} rr={rr}  {s}", flush=True)
    else:  # validate one config: python research.py DATA validate kind session sl rr
        kind, session, slm, rr = sys.argv[3], sys.argv[4] == "1", float(sys.argv[5]), float(sys.argv[6])
        for part in ("in", "out"):
            s, per = run(kind, session, slm, rr, part)
            print(part, s)
            print("  ", {k: round(float(v.sum()), 1) for k, v in per.items()})
