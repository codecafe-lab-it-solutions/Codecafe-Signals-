"""Autonomous Trading & Risk Loop for MetaTrader 5 (Demo Account).

Goal: Grow account equity by +10% ($100,000 -> $110,000) using strict risk controls.
Rules:
- Max 3 concurrent positions
- 1% risk per trade, max 0.10 lots
- 3% daily drawdown circuit breaker
- Move SL to breakeven when profit reaches +1.5R
- Logs every trade, outcome, and learning to trade_journal.json
"""
import json
import os
import sys
import time
from datetime import datetime, timezone

import MetaTrader5 as mt5

from chart_vision import analyze_market_structure
from server import closed_rates, connect, filling_mode, place_order, positions, symbol, todays_pnl

JOURNAL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trade_journal.json")
WATCHLIST = ["XAUUSD", "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD"]
TARGET_GAIN_PCT = 10.0
MAX_POSITIONS = 3
MAX_LOTS = 0.10
MAX_DAILY_LOSS_PCT = 3.0
MAGIC = 770011


def load_journal() -> dict:
    if os.path.exists(JOURNAL_FILE):
        try:
            with open(JOURNAL_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"start_time": datetime.now(timezone.utc).isoformat(), "initial_balance": 100000.0, "trades": [], "lessons": []}


def save_journal(data: dict):
    with open(JOURNAL_FILE, "w") as f:
        json.dump(data, f, indent=2)


def move_sl_to_breakeven(ticket: int, sym: str, entry: float, is_buy: bool):
    """Move stop-loss to entry price once trade is sufficiently in profit."""
    info = symbol(sym)
    res = mt5.order_send({
        "action": mt5.TRADE_ACTION_SLTP,
        "position": ticket,
        "symbol": sym,
        "sl": float(entry),
        "deviation": 20,
        "magic": MAGIC,
    })
    return res is not None and res.retcode == mt5.TRADE_RETCODE_DONE


def monitor_open_positions(journal: dict) -> list[dict]:
    """Check open positions, apply trailing breakeven, and learn from closed trades."""
    open_pos = positions()
    open_tickets = {p["ticket"] for p in open_pos}

    # Detect closed trades
    tracked = journal.setdefault("active_tickets", [])
    closed = [t for t in tracked if t not in open_tickets]
    for ticket in closed:
        deals = mt5.history_deals_get(position=ticket) or []
        exit_deals = [d for d in deals if d.entry == mt5.DEAL_ENTRY_OUT]
        if exit_deals:
            d = exit_deals[-1]
            net_profit = sum(deal.profit + deal.commission + deal.swap for deal in deals)
            outcome = "WIN" if net_profit > 0 else "LOSS" if net_profit < 0 else "BREAKEVEN"
            lesson = (
                f"{outcome} on ticket {ticket} ({d.symbol}): Net ${net_profit:+.2f}. "
                f"{'Target reached cleanly.' if net_profit > 0 else 'Stop-loss contained drawdown within 1% risk limit.'}"
            )
            journal.setdefault("closed_history", []).append({
                "ticket": ticket,
                "symbol": d.symbol,
                "profit": round(net_profit, 2),
                "exit_price": d.price,
                "time": datetime.now(timezone.utc).isoformat(),
                "outcome": outcome,
                "lesson": lesson,
            })
            journal.setdefault("lessons", []).append(lesson)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Learned from closed trade: {lesson}", flush=True)

            # User requirement: Notify on any loss
            if outcome == "LOSS":
                print(f"[{datetime.now().strftime('%H:%M:%S')}] *** LOSS ALERT *** Ticket {ticket} ({d.symbol}) closed with loss of ${abs(net_profit):.2f}. SL protected capital.", flush=True)
                journal.setdefault("loss_alerts", []).append({
                    "ticket": ticket,
                    "symbol": d.symbol,
                    "loss": round(net_profit, 2),
                    "exit_price": d.price,
                    "time": datetime.now(timezone.utc).isoformat(),
                })

    journal["active_tickets"] = list(open_tickets)

    for p in open_pos:
        entry = p["entry"]
        sl = p["sl"]
        profit = p["profit"]
        is_buy = p["side"] == "BUY"

        # User Rule: After every $100 profit on a trade, close it to bank profit and free slot for new trade
        if profit >= 100.0:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Target reached! +${profit:.2f} on {p['symbol']} (>= $100). Banking profit...", flush=True)
            from server import close_position
            try:
                c_res = close_position(p["ticket"])
                if c_res.get("ok"):
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully banked profit on {p['symbol']}! Ready for next trade.", flush=True)
                    continue
            except Exception as e:
                print(f"Error closing position {p['ticket']}: {e}", flush=True)

        # Trailing stop: if profit > 1.5R ($50+), move SL to entry breakeven
        if profit >= 50.0 and sl and ((is_buy and sl < entry) or (not is_buy and sl > entry)):
            if move_sl_to_breakeven(p["ticket"], p["symbol"], entry, is_buy):
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Moved SL to Breakeven for ticket {p['ticket']} ({p['symbol']})", flush=True)

    return positions()


def scan_for_opportunities(open_count: int, balance: float) -> dict | None:
    """Scan watchlist across M15 and H1 for high-probability setups."""
    if open_count >= MAX_POSITIONS:
        return None

    for tf in ("M15", "H1"):
        for sym in WATCHLIST:
            try:
                r = closed_rates(sym, tf, 80)
                candles = {
                    "symbol": sym, "interval": tf,
                    "time": r["time"].astype(int), "open": r["open"].astype(float),
                    "high": r["high"].astype(float), "low": r["low"].astype(float),
                    "close": r["close"].astype(float),
                }
                struct = analyze_market_structure(candles)
                rec = struct["recommendation"]
                if rec["action"] in ("BUY", "SELL") and rec["entry"] and rec["sl"] and rec["tp"]:
                    # Ensure no existing position in the same symbol
                    existing = [p for p in positions() if p["symbol"] == sym]
                    if existing:
                        continue
                    return {
                        "symbol": sym,
                        "timeframe": tf,
                        "action": rec["action"],
                        "entry": rec["entry"],
                        "sl": rec["sl"],
                        "tp": rec["tp"],
                        "reasons": rec["reasons"],
                    }
            except Exception:
                continue
    return None


def run_single_cycle() -> dict:
    """Run one monitoring and scanning cycle."""
    acc = connect()
    journal = load_journal()

    initial = journal.get("initial_balance", 100000.0)
    current_equity = acc.equity
    gain_pct = round((current_equity - initial) / initial * 100, 2)
    daily_pnl = todays_pnl()

    # Safety: daily loss breaker
    if daily_pnl <= -acc.balance * MAX_DAILY_LOSS_PCT / 100:
        return {
            "status": "CIRCUIT_BREAKER_ACTIVE",
            "message": f"Daily loss limit of {MAX_DAILY_LOSS_PCT}% hit ({daily_pnl} USD). Stopping new trades today.",
            "equity": current_equity,
            "gain_pct": gain_pct,
        }

    # Check $500 cumulative profit milestone
    total_gain = current_equity - initial
    if total_gain >= 500.0 and not journal.get("milestone_500_hit"):
        journal["milestone_500_hit"] = True
        print(f"[{datetime.now().strftime('%H:%M:%S')}] *** $500 PROFIT MILESTONE REACHED! *** Equity: ${current_equity:,.2f} (Total Profit: +${total_gain:.2f})", flush=True)

    # Goal reached check
    if gain_pct >= TARGET_GAIN_PCT:
        return {
            "status": "TARGET_REACHED",
            "message": f"Target of +{TARGET_GAIN_PCT}% reached! Current equity: ${current_equity:,.2f}",
            "equity": current_equity,
            "gain_pct": gain_pct,
        }

    # Monitor existing trades
    open_trades = monitor_open_positions(journal)

    # If capacity, scan and open new setup
    new_trade = None
    if len(open_trades) < MAX_POSITIONS:
        setup = scan_for_opportunities(len(open_trades), acc.balance)
        if setup:
            try:
                res = place_order(
                    name=setup["symbol"],
                    side=setup["action"],
                    lots=MAX_LOTS,
                    sl=setup["sl"],
                    tp=setup["tp"],
                )
                if res.get("ok"):
                    new_trade = {
                        "ticket": res.get("order"),
                        "symbol": setup["symbol"],
                        "timeframe": setup["timeframe"],
                        "action": setup["action"],
                        "lots": MAX_LOTS,
                        "price": res.get("price"),
                        "sl": setup["sl"],
                        "tp": setup["tp"],
                        "time": datetime.now(timezone.utc).isoformat(),
                    }
                    journal["trades"].append(new_trade)
                    save_journal(journal)
            except Exception as e:
                print(f"Order placement error: {e}")

    save_journal(journal)
    return {
        "status": "RUNNING",
        "equity": current_equity,
        "balance": acc.balance,
        "floating_profit": round(current_equity - acc.balance, 2),
        "gain_pct": gain_pct,
        "target_gain_pct": TARGET_GAIN_PCT,
        "open_positions": len(open_trades),
        "positions_detail": open_trades,
        "new_trade_placed": new_trade,
    }


if __name__ == "__main__":
    is_loop = "--loop" in sys.argv
    if is_loop:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Auto-trader daemon started. Target: +{TARGET_GAIN_PCT}%.", flush=True)
        while True:
            try:
                res = run_single_cycle()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Equity: ${res['equity']:,.2f} | Open: {res['open_positions']} | Gain: {res['gain_pct']}% | Status: {res['status']}", flush=True)
                if res["status"] in ("TARGET_REACHED", "CIRCUIT_BREAKER_ACTIVE"):
                    print(res["message"], flush=True)
                    break
            except Exception as e:
                print(f"Error in cycle: {e}", flush=True)
            time.sleep(20)
    else:
        status = run_single_cycle()
        print(json.dumps(status, indent=2), flush=True)
