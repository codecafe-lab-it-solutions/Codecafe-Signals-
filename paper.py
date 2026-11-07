"""Paper broker: fake money, real prices, for any symbol universal_data can fetch.

Works with no account and no API key: crypto (BTCUSDT), forex (EURUSD), US stocks (AAPL),
Indian stocks (RELIANCE.NS, TCS.BO), indices and commodities (GC=F).
Each login has its own account, kept in store.py (Supabase in the cloud, ./data locally); the web server
sets USER per request. Stop-loss and take-profit are checked against real candles every time positions() runs.
"""
import contextvars
import json
import os
import threading
import time

import store
from universal_data import fetch_universal_candles

USER = contextvars.ContextVar("paper_user", default="local")
LEGACY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "paper_account.json")
START = {"USD": 10000.0, "INR": 1000000.0}
MAX_RISK_PCT = 2.0  # refuse a trade that loses more than this % of the balance if SL is hit
fetch = fetch_universal_candles  # tests swap this for fake candles
# Every load-change-save runs under this lock, and price fetches stay outside it: a save from a slow
# request must never overwrite a trade another request saved meanwhile.
# shortcut: one lock per process; Render runs one process, add a DB row lock if it ever runs several
_lock = threading.Lock()


def currency(symbol):
    # shortcut: everything not on NSE/BSE is booked in USD, so JPY-quoted forex P&L is off; split per quote currency if that matters
    return "INR" if symbol.upper().endswith((".NS", ".BO")) else "USD"


def load():
    acct = store.get(f"paper:{USER.get()}")
    if acct is None and USER.get() == "local" and os.path.exists(LEGACY_FILE):
        with open(LEGACY_FILE) as f:  # keeps the account made before per-user storage existed
            acct = json.load(f)
    return acct or {"balance": dict(START), "trades": []}


def save(acct):
    store.put(f"paper:{USER.get()}", acct)


def daily_pnl():
    """Realised P&L of trades closed since 00:00 UTC, summed across currencies."""
    start = time.time() - time.time() % 86400
    return round(sum(t.get("pnl", 0) for t in load()["trades"] if t.get("closed", 0) >= start), 2)


def last_price(symbol):
    return float(fetch(symbol, "M15", 50)["close"][-1])


def open_trade(symbol, side, qty, sl, tp=None, price=None):
    side = side.upper()
    if side not in ("BUY", "SELL") or qty <= 0 or not sl or sl <= 0:
        raise ValueError("Need side BUY/SELL, qty > 0 and a stop-loss.")
    entry = price or last_price(symbol)
    sign = 1 if side == "BUY" else -1
    if (entry - sl) * sign <= 0 or (tp and (tp - entry) * sign <= 0):
        raise ValueError(f"{side} at {entry}: SL must be on the losing side and TP on the winning side.")
    cur = currency(symbol)
    risk = abs(entry - sl) * qty
    with _lock:
        acct = load()
        if risk > acct["balance"][cur] * MAX_RISK_PCT / 100:
            raise ValueError(f"Refused: risk {risk:.2f} {cur} is over {MAX_RISK_PCT}% of the {cur} balance.")
        trade = {"id": len(acct["trades"]) + 1, "symbol": symbol, "side": side, "qty": qty, "entry": entry,
                 "sl": sl, "tp": tp, "currency": cur, "opened": time.time(), "status": "OPEN"}
        acct["trades"].append(trade)
        save(acct)
    return {"ok": True, "platform": "paper", "trade": trade}


def _settle(acct, t, exit_price, why):
    sign = 1 if t["side"] == "BUY" else -1
    t.update(status=why, exit=exit_price, closed=time.time(), pnl=round((exit_price - t["entry"]) * t["qty"] * sign, 2))
    acct["balance"][t["currency"]] += t["pnl"]


def positions():
    """Close trades whose SL/TP was touched by real candles, then report balances and open P&L."""
    out, hits = [], {}
    for t in (t for t in load()["trades"] if t["status"] == "OPEN"):
        c = fetch(t["symbol"], "M15", 200)  # shortcut: only the last 200 M15 bars are checked
        sign = 1 if t["side"] == "BUY" else -1
        for tm, hi, lo in zip(c["time"], c["high"], c["low"]):
            if tm < t["opened"]:
                continue
            worst, best = (lo, hi) if sign == 1 else (hi, lo)
            if (worst - t["sl"]) * sign <= 0:  # SL first when both are touched in one bar: the cautious guess
                hits[t["id"]] = (t["sl"], "STOP_LOSS")
                break
            if t["tp"] and (best - t["tp"]) * sign >= 0:
                hits[t["id"]] = (t["tp"], "TAKE_PROFIT")
                break
        else:
            now = float(c["close"][-1])
            out.append({**t, "price": now, "open_pnl": round((now - t["entry"]) * t["qty"] * sign, 2)})
    with _lock:  # re-read: trades opened or closed during the fetches above must survive this save
        acct = load()
        settled = [t for t in acct["trades"] if t["status"] == "OPEN" and t["id"] in hits]
        for t in settled:
            _settle(acct, t, *hits[t["id"]])
        if settled:
            save(acct)
    return {"balance": acct["balance"], "open": out,
            "closed": [t for t in acct["trades"] if t["status"] != "OPEN"][-10:],
            "settled": settled}  # closed by this call, for alerts


def close_trade(trade_id, price=None):
    raw_id = int(str(trade_id).split("-")[-1])
    is_open = lambda t: t["id"] == raw_id and t["status"] == "OPEN"  # noqa: E731
    t = next((t for t in load()["trades"] if is_open(t)), None)
    if not t:
        raise ValueError(f"No open paper trade {trade_id}")
    price = price or last_price(t["symbol"])  # network fetch, so outside the lock
    with _lock:
        acct = load()
        t = next((t for t in acct["trades"] if is_open(t)), None)
        if not t:
            raise ValueError(f"Paper trade {trade_id} was already closed")
        _settle(acct, t, price, "CLOSED")
        save(acct)
    return {"ok": True, "trade": t, "balance": acct["balance"]}
