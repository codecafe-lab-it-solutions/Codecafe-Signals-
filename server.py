"""CodeCafe Signals MCP server: MT5 market data, auto signals and guarded order placement.

The MT5 terminal must be running and logged in to a DEMO account. No credentials live here.
"""
import os
from datetime import datetime

import MetaTrader5 as mt5
import numpy as np
from mcp.server.mcpserver import MCPServer

from signals import backtest as run_backtest, generate_signal, lot_size

# Hard limits. Claude cannot change these; edit the file to change them.
RISK_PCT = 1.0            # % of balance risked per trade when sizing
MAX_LOTS = 0.10           # absolute cap per order
MAX_DAILY_LOSS_PCT = 3.0  # block new trades after this realised loss today
MAX_OPEN_POSITIONS = 3
DEMO_ONLY = True
MAGIC = 770011
WATCHLIST = os.getenv("YO_SYMBOLS", "EURUSD,GBPUSD,USDJPY,XAUUSD").split(",")
TIMEFRAMES = {"M15": mt5.TIMEFRAME_M15, "H1": mt5.TIMEFRAME_H1, "H4": mt5.TIMEFRAME_H4, "D1": mt5.TIMEFRAME_D1}

mcp = MCPServer("yo-signals")


def connect():
    path = os.getenv("MT5_PATH")
    ok = mt5.initialize(path) if path else mt5.initialize()
    if not ok:
        raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}. Is the MT5 terminal open and logged in?")
    acc = mt5.account_info()
    if acc is None:
        raise RuntimeError(f"No MT5 account: {mt5.last_error()}")
    return acc


def symbol(name):
    if not mt5.symbol_select(name, True):
        raise ValueError(f"Unknown symbol {name!r}. Your broker may use a suffix, e.g. EURUSDm.")
    return mt5.symbol_info(name)


def closed_rates(name, timeframe, count):
    if timeframe not in TIMEFRAMES:
        raise ValueError(f"timeframe must be one of {list(TIMEFRAMES)}")
    rates = mt5.copy_rates_from_pos(name, TIMEFRAMES[timeframe], 1, count)  # start=1 skips the forming bar
    if rates is None or len(rates) == 0:
        raise RuntimeError(f"No candles for {name}: {mt5.last_error()}")
    return rates


def todays_pnl():
    # MT5 stamps deals in broker server time, so take "today" from a server tick, not the local clock.
    now = mt5.symbol_info_tick(WATCHLIST[0]).time
    deals = mt5.history_deals_get(datetime.fromtimestamp(now - now % 86400), datetime.fromtimestamp(now + 3600)) or []
    trades = [d for d in deals if d.type in (mt5.DEAL_TYPE_BUY, mt5.DEAL_TYPE_SELL)]  # skip deposits/withdrawals
    return round(sum(d.profit + d.commission + d.swap for d in trades), 2)


def suggested_lots(info, balance, entry, sl):
    risk_money = balance * RISK_PCT / 100
    lots = lot_size(risk_money, abs(entry - sl), info.trade_tick_size, info.trade_tick_value,
                    info.volume_min, info.volume_step, info.volume_max)
    return min(lots, MAX_LOTS)


def filling_mode(info):
    if info.filling_mode & 1:
        return mt5.ORDER_FILLING_FOK
    if info.filling_mode & 2:
        return mt5.ORDER_FILLING_IOC
    return mt5.ORDER_FILLING_RETURN


@mcp.tool()
def account() -> dict:
    """Account summary: balance, equity, demo flag, today's realised P/L and the hard limits."""
    acc = connect()
    return {
        "login": acc.login, "server": acc.server, "currency": acc.currency,
        "is_demo": acc.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO,
        "balance": acc.balance, "equity": acc.equity, "leverage": acc.leverage,
        "today_pnl": todays_pnl(),
        "limits": {"risk_pct": RISK_PCT, "max_lots": MAX_LOTS, "max_daily_loss_pct": MAX_DAILY_LOSS_PCT,
                   "max_open_positions": MAX_OPEN_POSITIONS, "demo_only": DEMO_ONLY},
    }


@mcp.tool()
def price(name: str) -> dict:
    """Live bid/ask and spread for one symbol."""
    connect()
    info = symbol(name)
    tick = mt5.symbol_info_tick(name)
    return {"symbol": name, "bid": tick.bid, "ask": tick.ask,
            "spread_points": round((tick.ask - tick.bid) / info.point), "time": datetime.fromtimestamp(tick.time).isoformat()}


@mcp.tool()
def candles(name: str, timeframe: str = "H1", count: int = 100) -> list[dict]:
    """Closed OHLC candles (oldest first). timeframe: M15, H1, H4, D1. count capped at 500."""
    connect()
    symbol(name)
    rates = closed_rates(name, timeframe, min(count, 500))
    return [{"time": datetime.fromtimestamp(int(r["time"])).isoformat(), "open": float(r["open"]),
             "high": float(r["high"]), "low": float(r["low"]), "close": float(r["close"])} for r in rates]


@mcp.tool()
def scan(symbols: list[str] | None = None, timeframe: str = "H1") -> list[dict]:
    """Run strategy v2 (EMA20/50 cross + RSI, with the EMA200 trend, London/New York hours only)
    on the watchlist. Every symbol gets BUY/SELL/WAIT with reasons; BUY/SELL also get SL, TP,
    invalidation and a risk-sized lot suggestion.
    Signals are suggestions only: explain them to the user, never trade without approval."""
    acc = connect()
    out = []
    for name in symbols or WATCHLIST:
        try:
            info = symbol(name)
            r = closed_rates(name, timeframe, 1000)  # long enough for EMA200 to settle
            s = generate_signal(r["time"], r["high"], r["low"], r["close"])
            s["symbol"], s["timeframe"] = name, timeframe
            if s["signal"] != "WAIT":
                s["suggested_lots"] = suggested_lots(info, acc.balance, s["price"], s["sl"])
            out.append(s)
        except Exception as e:  # one bad symbol must not hide the others
            out.append({"symbol": name, "error": str(e)})
    return out


@mcp.tool()
def backtest(name: str, timeframe: str = "H1", bars: int = 10000) -> dict:
    """Replay the live strategy on past candles (max 50000) with the symbol's typical spread.
    Results are in R: 1R = the amount risked per trade (1% of balance by default).
    Past results do not guarantee future results; say so when reporting."""
    connect()
    info = symbol(name)
    count = min(bars, 50000)
    while True:  # MT5 refuses counts above the history it holds, so halve until it fits
        try:
            r = closed_rates(name, timeframe, count)
            break
        except RuntimeError:
            if count <= 500:
                raise
            count //= 2
    spread = float(np.median(r["spread"])) * info.point
    result = run_backtest(r["time"], r["open"], r["high"], r["low"], r["close"], spread)
    result.update({"symbol": name, "timeframe": timeframe, "bars": len(r), "spread_used": spread,
                   "from": datetime.fromtimestamp(int(r["time"][0])).date().isoformat(),
                   "to": datetime.fromtimestamp(int(r["time"][-1])).date().isoformat()})
    return result


@mcp.tool()
def positions() -> list[dict]:
    """Open positions with ticket, side, lots, entry, SL, TP and floating profit."""
    connect()
    return [{"ticket": p.ticket, "symbol": p.symbol, "side": "BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
             "lots": p.volume, "entry": p.price_open, "sl": p.sl, "tp": p.tp, "profit": p.profit}
            for p in (mt5.positions_get() or [])]


@mcp.tool()
def place_order(name: str, side: str, lots: float, sl: float, tp: float) -> dict:
    """Place a market order. ONLY call after the user has explicitly approved this exact trade
    (symbol, side, lots, SL, TP) in chat. Every order must have a stop-loss."""
    acc = connect()
    side = side.upper()
    if side not in ("BUY", "SELL"):
        raise ValueError("side must be BUY or SELL")
    if DEMO_ONLY and acc.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
        raise PermissionError("Refused: account is not a demo account and DEMO_ONLY is on.")
    if not sl or sl <= 0:
        raise ValueError("Refused: stop-loss is required.")
    if lots <= 0 or lots > MAX_LOTS:
        raise ValueError(f"Refused: lots must be > 0 and <= {MAX_LOTS}.")
    if len(mt5.positions_get() or []) >= MAX_OPEN_POSITIONS:
        raise PermissionError(f"Refused: already {MAX_OPEN_POSITIONS} open positions.")
    if todays_pnl() <= -acc.balance * MAX_DAILY_LOSS_PCT / 100:
        raise PermissionError(f"Refused: daily loss limit of {MAX_DAILY_LOSS_PCT}% reached.")

    info = symbol(name)
    tick = mt5.symbol_info_tick(name)
    entry = tick.ask if side == "BUY" else tick.bid
    if side == "BUY" and not (sl < entry and (not tp or tp > entry)):
        raise ValueError(f"Refused: BUY needs SL below and TP above price {entry}.")
    if side == "SELL" and not (sl > entry and (not tp or tp < entry)):
        raise ValueError(f"Refused: SELL needs SL above and TP below price {entry}.")

    result = mt5.order_send({
        "action": mt5.TRADE_ACTION_DEAL, "symbol": name, "volume": float(lots),
        "type": mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL,
        "price": entry, "sl": float(sl), "tp": float(tp or 0), "deviation": 20, "magic": MAGIC,
        "comment": "yo-signals", "type_time": mt5.ORDER_TIME_GTC, "type_filling": filling_mode(info),
    })
    if result is None:
        raise RuntimeError(f"order_send failed: {mt5.last_error()}")
    return {"ok": result.retcode == mt5.TRADE_RETCODE_DONE, "retcode": result.retcode, "comment": result.comment,
            "order": result.order, "price": result.price, "lots": result.volume}


@mcp.tool()
def close_position(ticket: int) -> dict:
    """Close one open position by ticket. Only after the user approves."""
    connect()
    found = mt5.positions_get(ticket=ticket)
    if not found:
        raise ValueError(f"No open position with ticket {ticket}")
    p = found[0]
    info = symbol(p.symbol)
    tick = mt5.symbol_info_tick(p.symbol)
    is_buy = p.type == mt5.POSITION_TYPE_BUY
    result = mt5.order_send({
        "action": mt5.TRADE_ACTION_DEAL, "symbol": p.symbol, "volume": p.volume, "position": p.ticket,
        "type": mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY,
        "price": tick.bid if is_buy else tick.ask, "deviation": 20, "magic": MAGIC,
        "comment": "yo-signals close", "type_time": mt5.ORDER_TIME_GTC, "type_filling": filling_mode(info),
    })
    if result is None:
        raise RuntimeError(f"order_send failed: {mt5.last_error()}")
    return {"ok": result.retcode == mt5.TRADE_RETCODE_DONE, "retcode": result.retcode, "comment": result.comment}


if __name__ == "__main__":
    mcp.run()
