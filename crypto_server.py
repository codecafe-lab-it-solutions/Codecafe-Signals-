"""Yo Crypto MCP server: Bybit spot signals on real prices, guarded orders on Bybit Demo Trading (or testnet) only.

Keys: BYBIT_KEY / BYBIT_SECRET env vars from a Demo Trading API key. BYBIT_NET=demo|testnet.
Spot only: BUY opens a long with SL/TP attached; a SELL signal means "exit / stay out", never a short.
"""
import json
import math
import os
from datetime import datetime, timezone

from mcp.server.mcpserver import MCPServer

import bybit
from signals import backtest as run_backtest, generate_signal

# Hard limits. Claude cannot change these; edit the file to change them.
RISK_PCT = 1.0               # % of demo equity risked per trade when sizing
MAX_NOTIONAL_USDT = 1000.0   # absolute cap on one order's size
MAX_DAILY_LOSS_PCT = 3.0     # block new buys once equity is this far below today's start
MAX_OPEN_POSITIONS = 3
FEE_PCT_ROUND_TRIP = 0.2     # Bybit spot taker 0.1% in + 0.1% out, used in backtests
SESSION_UTC = (7, 17)        # London/New York hours in UTC; None = 24/7
WATCHLIST = os.getenv("YO_CRYPTO_SYMBOLS", "BTCUSDT,ETHUSDT").split(",")
DAY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".crypto_day.json")

mcp = MCPServer("yo-crypto")


def wallet():
    return bybit.private("GET", "/v5/account/wallet-balance", accountType="UNIFIED")["list"][0]


def instrument(name):
    found = bybit._call(bybit.TRADE_DATA, "GET", "/v5/market/instruments-info", {"category": "spot", "symbol": name})["list"]
    if not found:
        raise ValueError(f"Unknown spot symbol {name!r} on Bybit")
    return found[0]


def fill_ticker(name):
    return bybit._call(bybit.TRADE_DATA, "GET", "/v5/market/tickers", {"category": "spot", "symbol": name})["list"][0]


def holdings(w):
    return {c["coin"]: float(c["walletBalance"]) for c in w["coin"] if c["coin"] != "USDT" and float(c["walletBalance"] or 0) > 0}


def day_start_equity(equity):
    """Equity at the first check of the UTC day, kept in a small file so the daily limit survives restarts."""
    today = datetime.now(timezone.utc).date().isoformat()
    try:
        with open(DAY_FILE) as f:
            saved = json.load(f)
    except (OSError, ValueError):
        saved = {}
    if saved.get("date") != today:
        saved = {"date": today, "equity": equity}
        with open(DAY_FILE, "w") as f:
            json.dump(saved, f)
    return saved["equity"]


def round_down(x, step):
    step = float(step)
    return math.floor(x / step + 1e-9) * step


@mcp.tool()
def account() -> dict:
    """Bybit demo/testnet account: equity, USDT, coins held, today's change and the hard limits."""
    w = wallet()
    equity = float(w["totalEquity"])
    start = day_start_equity(equity)
    usdt = next((float(c["walletBalance"]) for c in w["coin"] if c["coin"] == "USDT"), 0.0)
    return {"network": bybit.NET, "equity_usd": equity, "usdt": usdt, "holdings": holdings(w),
            "today_change_usd": round(equity - start, 2),
            "limits": {"risk_pct": RISK_PCT, "max_notional_usdt": MAX_NOTIONAL_USDT,
                       "max_daily_loss_pct": MAX_DAILY_LOSS_PCT, "max_open_positions": MAX_OPEN_POSITIONS}}


@mcp.tool()
def price(name: str) -> dict:
    """Real (mainnet) and testnet bid/ask for one spot symbol, e.g. BTCUSDT. Orders fill at the demo/testnet price."""
    real = bybit.public("/v5/market/tickers", category="spot", symbol=name)["list"][0]
    test = fill_ticker(name)
    return {"symbol": name, "real_bid": float(real["bid1Price"]), "real_ask": float(real["ask1Price"]),
            "fill_bid": float(test["bid1Price"] or 0), "fill_ask": float(test["ask1Price"] or 0)}


@mcp.tool()
def scan(symbols: list[str] | None = None, timeframe: str = "H1") -> list[dict]:
    """Run strategy v2 on real Bybit spot candles. BUY = open a long; SELL = exit any holding / stay out.
    WARNING: v2 was validated on forex, not crypto; on crypto backtests it mostly lost. Say so.
    Signals are suggestions only: never trade without the user's approval."""
    out = []
    for name in symbols or WATCHLIST:
        try:
            k = bybit.klines(name, timeframe, 1000)
            s = generate_signal(k["time"], k["high"], k["low"], k["close"], session=SESSION_UTC)
            s.update(symbol=name, timeframe=timeframe, market="spot, long-only")
            if s["signal"] == "SELL":
                s["note"] = "Spot can't short: this means sell any holding or stay out."
                s.pop("sl"), s.pop("tp")
            out.append(s)
        except Exception as e:  # one bad symbol must not hide the others
            out.append({"symbol": name, "error": str(e)})
    return out


@mcp.tool()
def backtest(name: str, timeframe: str = "H1", bars: int = 20000) -> dict:
    """Replay v2 long-only on real Bybit spot history (max 50000 bars), fees included.
    Results in R (1R = amount risked per trade). Past results do not guarantee future results."""
    k = bybit.klines(name, timeframe, min(bars, 50000))
    r = run_backtest(k["time"], k["open"], k["high"], k["low"], k["close"], session=SESSION_UTC,
                     cost_pct=FEE_PCT_ROUND_TRIP, sides=("BUY",))
    r.update(symbol=name, timeframe=timeframe, bars=len(k["close"]),
             **{"from": datetime.fromtimestamp(k["time"][0], timezone.utc).date().isoformat(),
                "to": datetime.fromtimestamp(k["time"][-1], timezone.utc).date().isoformat()})
    return r


@mcp.tool()
def positions() -> dict:
    """Coins held and open (TP/SL) orders on the demo account."""
    orders = bybit.private("GET", "/v5/order/realtime", category="spot")["list"]
    return {"holdings": holdings(wallet()),
            "open_orders": [{k: o.get(k) for k in ("symbol", "side", "orderType", "qty", "price", "triggerPrice",
                                                    "stopOrderType", "orderId")} for o in orders]}


@mcp.tool()
def suggest_size(name: str, sl: float) -> dict:
    """Base-coin quantity that loses about RISK_PCT of equity if the fill price falls to sl."""
    entry = float(fill_ticker(name)["ask1Price"])
    if not 0 < sl < entry:
        raise ValueError(f"sl must be below the fill price {entry}")
    info = instrument(name)
    equity = float(wallet()["totalEquity"])
    qty = equity * RISK_PCT / 100 / (entry - sl)
    qty = min(qty, MAX_NOTIONAL_USDT / entry)
    return {"symbol": name, "fill_entry": entry, "qty": round_down(qty, info["lotSizeFilter"]["basePrecision"]),
            "notional_usdt": round(qty * entry, 2)}


@mcp.tool()
def place_order(name: str, qty: float, sl: float, tp: float) -> dict:
    """Market BUY on Bybit demo/testnet with stop-loss and take-profit attached. ONLY call after the
    user has explicitly approved this exact trade (symbol, qty, SL, TP) in chat."""
    if not sl or sl <= 0 or not tp:
        raise ValueError("Refused: stop-loss and take-profit are required.")
    w = wallet()
    equity = float(w["totalEquity"])
    if equity <= day_start_equity(equity) * (1 - MAX_DAILY_LOSS_PCT / 100):
        raise PermissionError(f"Refused: daily loss limit of {MAX_DAILY_LOSS_PCT}% reached.")
    held = holdings(w)
    base = name.removesuffix("USDT")
    if base not in held and len(held) >= MAX_OPEN_POSITIONS:
        raise PermissionError(f"Refused: already holding {MAX_OPEN_POSITIONS} coins.")
    info = instrument(name)
    entry = float(fill_ticker(name)["ask1Price"])
    if not sl < entry < tp:
        raise ValueError(f"Refused: BUY needs SL below and TP above the fill price {entry}.")
    qty = round_down(qty, info["lotSizeFilter"]["basePrecision"])
    if qty <= 0 or qty * entry > MAX_NOTIONAL_USDT:
        raise ValueError(f"Refused: order must be > 0 and <= {MAX_NOTIONAL_USDT} USDT (got {qty * entry:.2f}).")
    tick = info["priceFilter"]["tickSize"]
    res = bybit.private("POST", "/v5/order/create", category="spot", symbol=name, side="Buy", orderType="Market",
                        qty=f"{qty:f}".rstrip("0").rstrip("."), marketUnit="baseCoin",
                        stopLoss=str(round_down(sl, tick)), takeProfit=str(round_down(tp, tick)),
                        orderLinkId=f"yo-{int(datetime.now().timestamp() * 1000)}")
    return {"ok": True, "orderId": res["orderId"], "qty": qty, "approx_entry": entry, "sl": sl, "tp": tp}


@mcp.tool()
def close_position(name: str) -> dict:
    """Cancel the symbol's open TP/SL orders and market-sell the whole holding. Only after the user approves."""
    base = name.removesuffix("USDT")
    bybit.private("POST", "/v5/order/cancel-all", category="spot", symbol=name)
    qty = holdings(wallet()).get(base, 0.0)
    qty = round_down(qty, instrument(name)["lotSizeFilter"]["basePrecision"])
    if qty <= 0:
        raise ValueError(f"No {base} to sell")
    res = bybit.private("POST", "/v5/order/create", category="spot", symbol=name, side="Sell", orderType="Market",
                        qty=f"{qty:f}".rstrip("0").rstrip("."), marketUnit="baseCoin")
    return {"ok": True, "orderId": res["orderId"], "sold": qty}


if __name__ == "__main__":
    mcp.run()
