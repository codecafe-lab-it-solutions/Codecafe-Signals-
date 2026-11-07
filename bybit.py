"""Minimal Bybit V5 REST client (stdlib only).

Market data comes from mainnet public endpoints (real prices, no key needed).
Trading goes ONLY to Bybit Demo Trading (default) or the testnet, never to a real-money endpoint.
Pick with BYBIT_NET=demo|testnet; keys come from BYBIT_KEY / BYBIT_SECRET.
"""
import hashlib
import hmac
import json
import os
import time
import urllib.parse
import urllib.request

import numpy as np

MAINNET = "https://api.bybit.com"
TESTNET = "https://api-testnet.bybit.com"
DEMO = "https://api-demo.bybit.com"
NET = os.getenv("BYBIT_NET", "demo")
if NET not in ("demo", "testnet"):
    raise RuntimeError("BYBIT_NET must be demo or testnet; real-money trading is not allowed")
TRADE = DEMO if NET == "demo" else TESTNET
TRADE_DATA = MAINNET if NET == "demo" else TESTNET  # demo fills at real prices; testnet has its own
INTERVALS = {"M15": "15", "H1": "60", "H4": "240", "D1": "D"}
RECV_WINDOW = "10000"


def _call(base, method, path, params=None, signed=False):
    params = {k: v for k, v in (params or {}).items() if v is not None}
    query = urllib.parse.urlencode(params) if method == "GET" else ""
    body = json.dumps(params) if method == "POST" else ""
    headers = {"Content-Type": "application/json"}
    if signed:
        key, secret = os.getenv("BYBIT_KEY"), os.getenv("BYBIT_SECRET")
        if not key or not secret:
            raise RuntimeError("Set BYBIT_KEY and BYBIT_SECRET (a Demo Trading API key from bybit.com).")
        ts = str(int(time.time() * 1000))
        sign = hmac.new(secret.encode(), (ts + key + RECV_WINDOW + (query or body)).encode(), hashlib.sha256)
        headers.update({"X-BAPI-API-KEY": key, "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": RECV_WINDOW,
                        "X-BAPI-SIGN": sign.hexdigest()})
    url = base + path + ("?" + query if query else "")
    req = urllib.request.Request(url, data=body.encode() if body else None, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15) as r:
        data = json.load(r)
    if data.get("retCode") != 0:
        raise RuntimeError(f"Bybit {path}: {data.get('retCode')} {data.get('retMsg')}")
    return data["result"]


def public(path, **params):
    return _call(MAINNET, "GET", path, params)


def private(method, path, **params):
    return _call(TRADE, method, path, params, signed=True)


def klines(symbol, timeframe="H1", count=1000, closed=True):
    """Spot candles, oldest first (closed=False keeps the forming one, whose close is the live price), as numpy arrays keyed time(s, UTC)/open/high/low/close."""
    if timeframe not in INTERVALS:
        raise ValueError(f"timeframe must be one of {list(INTERVALS)}")
    rows, end = {}, None
    while len(rows) < count + 1:
        page = public("/v5/market/kline", category="spot", symbol=symbol, interval=INTERVALS[timeframe],
                      limit=1000, end=end)["list"]  # newest first
        if not page:
            break
        for r in page:
            rows[int(r[0])] = r
        oldest = int(page[-1][0])
        if len(page) < 1000:
            break
        end = oldest - 1
    data = [rows[k] for k in sorted(rows)]
    data = (data[:-1] if closed else data)[-count:]  # closed: drop the still-forming last candle
    if not data:
        raise RuntimeError(f"No candles for {symbol}")
    a = np.array([[float(x) for x in r[:5]] for r in data])
    return {"time": a[:, 0] // 1000, "open": a[:, 1], "high": a[:, 2], "low": a[:, 3], "close": a[:, 4]}
