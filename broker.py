"""Modular Broker Abstraction Layer (QuantConnect LEAN inspired).
Provides a unified interface (AbstractBroker) for Paper, MT5, and future broker apps.
"""
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
import time
from typing import Any

from config import MAGIC_NUMBER, MAX_DAILY_LOSS_PCT, MAX_LOTS, MAX_OPEN_POSITIONS, RISK_PCT, TRADING_MODE
import db


@dataclass
class OrderRequest:
    symbol: str
    side: str  # "BUY" or "SELL"
    qty: float
    sl: float
    tp: float | None = None
    order_type: str = "MARKET"
    price: float | None = None
    comment: str = "yo-signals"
    magic: int = MAGIC_NUMBER


@dataclass
class OrderResult:
    ok: bool
    ticket: str
    symbol: str
    side: str
    qty: float
    price: float
    comment: str
    retcode: int | None = None
    error: str | None = None


@dataclass
class Position:
    ticket: str
    symbol: str
    side: str
    qty: float
    open_price: float
    current_price: float
    sl: float
    tp: float
    profit: float


@dataclass
class AccountInfo:
    broker: str
    balance: float
    equity: float
    margin: float
    free_margin: float
    currency: str
    is_demo: bool


class AbstractBroker(ABC):
    """Base broker interface inspired by QuantConnect LEAN's IBrokerage."""

    name: str = "abstract"

    @abstractmethod
    def connect(self) -> bool:
        """Establish connection to broker."""
        pass

    @abstractmethod
    def get_account(self) -> AccountInfo:
        """Fetch current account balances and margin."""
        pass

    @abstractmethod
    def get_positions(self, symbol: str | None = None) -> list[Position]:
        """Fetch active open positions."""
        pass

    @abstractmethod
    def submit_order(self, req: OrderRequest) -> OrderResult:
        """Submit a new order with mandatory Stop Loss."""
        pass

    @abstractmethod
    def close_position(self, ticket: str | int) -> OrderResult:
        """Close an existing position by ticket."""
        pass

    @abstractmethod
    def modify_position(self, ticket: str | int, sl: float, tp: float) -> OrderResult:
        """Update Stop Loss and Take Profit levels."""
        pass

    def reconcile_positions(self) -> dict[str, Any]:
        """Reconcile broker open positions with internal SQLite database records."""
        live_positions = {str(p.ticket): p for p in self.get_positions()}
        db_trades = {str(t["ticket"]): t for t in db.get_open_trades(broker=self.name)}

        closed_externally = []
        synced_new = []

        # 1. Closed on broker but still marked OPEN in DB
        for ticket, t in db_trades.items():
            if ticket not in live_positions:
                db.update_trade_close(ticket, exit_price=t["entry_price"], pnl=0.0, notes="Reconciliation: closed by broker")
                db.log_audit("RECONCILE_CLOSED", {"ticket": ticket, "broker": self.name})
                closed_externally.append(ticket)

        # 2. Open on broker but missing in DB
        for ticket, p in live_positions.items():
            if ticket not in db_trades:
                db.record_trade(ticket, self.name, p.symbol, p.side, p.qty, p.open_price, p.sl, p.tp, status="OPEN", notes="Reconciliation: external open")
                synced_new.append(ticket)

        return {"closed_externally": closed_externally, "synced_new": synced_new, "total_live": len(live_positions)}


class PaperBroker(AbstractBroker):
    """Simulated execution engine. Zero credentials, real market prices, records to local SQLite."""

    name: str = "paper"

    def __init__(self, starting_balance: float = 100000.0, currency: str = "USD"):
        self.starting_balance = starting_balance
        self.currency = currency
        self._connected = True

    def connect(self) -> bool:
        return True

    def get_account(self) -> AccountInfo:
        import paper
        acct = paper.load()
        bal = acct.get("balance", {}).get(self.currency, self.starting_balance)
        positions = self.get_positions()
        unrealized = sum(p.profit for p in positions)
        return AccountInfo(
            broker=self.name,
            balance=round(bal, 2),
            equity=round(bal + unrealized, 2),
            margin=0.0,
            free_margin=round(bal, 2),
            currency=self.currency,
            is_demo=True,
        )

    def get_positions(self, symbol: str | None = None) -> list[Position]:
        import paper
        report = paper.positions()
        trades = report.get("open", [])
        res = []
        user_prefix = f"{paper.USER.get()}-" if paper.USER.get() != "local" else ""
        for t in trades:
            if symbol and t["symbol"].upper() != symbol.upper():
                continue
            res.append(Position(
                ticket=f"{user_prefix}{t['id']}",
                symbol=t["symbol"],
                side=t["side"],
                qty=float(t["qty"]),
                open_price=float(t["entry"]),
                current_price=float(t.get("price", t["entry"])),
                sl=float(t["sl"]),
                tp=float(t["tp"] or 0.0),
                profit=float(t.get("open_pnl", 0.0)),
            ))
        return res

    def submit_order(self, req: OrderRequest) -> OrderResult:
        import paper
        side = req.side.upper()
        if side not in ("BUY", "SELL"):
            return OrderResult(ok=False, ticket="", symbol=req.symbol, side=side, qty=req.qty, price=0.0, comment="Invalid side", error="Invalid side")
        if not req.sl or req.sl <= 0:
            return OrderResult(ok=False, ticket="", symbol=req.symbol, side=side, qty=req.qty, price=0.0, comment="Missing mandatory SL", error="Missing mandatory SL")

        try:
            res = paper.open_trade(req.symbol, side, req.qty, req.sl, req.tp, price=req.price)
            t = res["trade"]
            user_prefix = f"{paper.USER.get()}-" if paper.USER.get() != "local" else ""
            ticket = f"{user_prefix}{t['id']}"
            db.record_trade(ticket, self.name, req.symbol, side, req.qty, t["entry"], req.sl, req.tp, status="OPEN", notes=req.comment)
            db.log_audit("ORDER_FILLED", {"broker": self.name, "ticket": ticket, "symbol": req.symbol, "side": side, "qty": req.qty, "price": t["entry"], "user": paper.USER.get()})
            return OrderResult(ok=True, ticket=ticket, symbol=req.symbol, side=side, qty=req.qty, price=t["entry"], comment="Filled paper order")
        except Exception as e:
            db.log_audit("ORDER_REJECTED", {"broker": self.name, "error": str(e), "user": paper.USER.get()})
            return OrderResult(ok=False, ticket="", symbol=req.symbol, side=side, qty=req.qty, price=0.0, comment=str(e), error=str(e))

    def close_position(self, ticket: str | int) -> OrderResult:
        import paper
        try:
            res = paper.close_trade(ticket)
            t = res["trade"]
            db.update_trade_close(ticket, exit_price=t.get("exit", 0.0), pnl=t.get("pnl", 0.0), notes="Paper closed")
            db.log_audit("POSITION_CLOSED", {"broker": self.name, "ticket": str(ticket), "pnl": t.get("pnl", 0.0), "user": paper.USER.get()})
            return OrderResult(ok=True, ticket=str(ticket), symbol=t["symbol"], side=t["side"], qty=t["qty"], price=t.get("exit", 0.0), comment="Paper trade closed")
        except Exception as e:
            return OrderResult(ok=False, ticket=str(ticket), symbol="", side="", qty=0.0, price=0.0, comment=str(e), error=str(e))

    def modify_position(self, ticket: str | int, sl: float, tp: float) -> OrderResult:
        import paper
        acct = paper.load()
        for t in acct.get("trades", []):
            if str(t["id"]) == str(ticket) and t["status"] == "OPEN":
                t["sl"] = sl
                t["tp"] = tp
                paper.save(acct)
                return OrderResult(ok=True, ticket=str(ticket), symbol=t["symbol"], side=t["side"], qty=t["qty"], price=t["entry"], comment="Modified SL/TP")
        return OrderResult(ok=False, ticket=str(ticket), symbol="", side="", qty=0.0, price=0.0, comment="Ticket not found", error="Ticket not found")


class MT5Broker(AbstractBroker):
    """MetaTrader 5 Python Broker Adapter."""

    name: str = "mt5"

    def __init__(self, demo_only: bool = True):
        self.demo_only = demo_only

    def connect(self) -> bool:
        import MetaTrader5 as mt5
        if not mt5.initialize():
            raise RuntimeError(f"MT5 initialize failed: {mt5.last_error()}. Open MT5 terminal.")
        return True

    def get_account(self) -> AccountInfo:
        import MetaTrader5 as mt5
        self.connect()
        acc = mt5.account_info()
        if acc is None:
            raise RuntimeError(f"MT5 account_info failed: {mt5.last_error()}")
        if self.demo_only and acc.trade_mode != mt5.ACCOUNT_TRADE_MODE_DEMO:
            raise PermissionError("Refused: MT5 account is LIVE. Demo accounts only.")
        return AccountInfo(
            broker=self.name,
            balance=float(acc.balance),
            equity=float(acc.equity),
            margin=float(acc.margin),
            free_margin=float(acc.margin_free),
            currency=acc.currency,
            is_demo=acc.trade_mode == mt5.ACCOUNT_TRADE_MODE_DEMO,
        )

    def get_positions(self, symbol: str | None = None) -> list[Position]:
        import MetaTrader5 as mt5
        self.connect()
        raw = mt5.positions_get(symbol=symbol) if symbol else mt5.positions_get()
        res = []
        for p in (raw or []):
            res.append(Position(
                ticket=str(p.ticket),
                symbol=p.symbol,
                side="BUY" if p.type == mt5.POSITION_TYPE_BUY else "SELL",
                qty=float(p.volume),
                open_price=float(p.price_open),
                current_price=float(p.price_current),
                sl=float(p.sl),
                tp=float(p.tp),
                profit=float(p.profit),
            ))
        return res

    def _filling_mode(self, symbol_info) -> int:
        import MetaTrader5 as mt5
        m = symbol_info.filling_mode
        if m & mt5.ORDER_FILLING_IOC:
            return mt5.ORDER_FILLING_IOC
        if m & mt5.ORDER_FILLING_FOK:
            return mt5.ORDER_FILLING_FOK
        return mt5.ORDER_FILLING_RETURN

    def submit_order(self, req: OrderRequest) -> OrderResult:
        import MetaTrader5 as mt5
        self.connect()
        acc = self.get_account()

        # Risk validations
        if req.qty > MAX_LOTS:
            return OrderResult(ok=False, ticket="", symbol=req.symbol, side=req.side, qty=req.qty, price=0.0, comment=f"Lots exceed {MAX_LOTS}", error="Lot size cap exceeded")
        if not req.sl or req.sl <= 0:
            return OrderResult(ok=False, ticket="", symbol=req.symbol, side=req.side, qty=req.qty, price=0.0, comment="Stop loss mandatory", error="Missing SL")

        # Symbol check
        if not mt5.symbol_select(req.symbol, True):
            return OrderResult(ok=False, ticket="", symbol=req.symbol, side=req.side, qty=req.qty, price=0.0, comment="Symbol not found", error="Unknown symbol")
        info = mt5.symbol_info(req.symbol)
        tick = mt5.symbol_info_tick(req.symbol)
        if not tick:
            return OrderResult(ok=False, ticket="", symbol=req.symbol, side=req.side, qty=req.qty, price=0.0, comment="No price tick", error="Market data unavailable")

        side = req.side.upper()
        order_type = mt5.ORDER_TYPE_BUY if side == "BUY" else mt5.ORDER_TYPE_SELL
        entry = tick.ask if side == "BUY" else tick.bid

        order_data = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": req.symbol,
            "volume": float(req.qty),
            "type": order_type,
            "price": entry,
            "sl": float(req.sl),
            "tp": float(req.tp or 0.0),
            "deviation": 20,
            "magic": req.magic,
            "comment": req.comment,
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_mode(info),
        }

        # Pre-check order
        check_result = mt5.order_check(order_data)
        if check_result is None or check_result.retcode != 0:
            err = f"Check failed: {getattr(check_result, 'comment', mt5.last_error())}"
            return OrderResult(ok=False, ticket="", symbol=req.symbol, side=side, qty=req.qty, price=entry, comment=err, error=err)

        # Send order
        res = mt5.order_send(order_data)
        if res is None:
            err = f"order_send failed: {mt5.last_error()}"
            return OrderResult(ok=False, ticket="", symbol=req.symbol, side=side, qty=req.qty, price=entry, comment=err, error=err)

        ok = res.retcode == mt5.TRADE_RETCODE_DONE
        ticket = str(res.order)
        if ok:
            db.record_trade(ticket, self.name, req.symbol, side, req.qty, res.price or entry, req.sl, req.tp, status="OPEN", notes=req.comment)
            db.log_audit("ORDER_FILLED", {"broker": self.name, "ticket": ticket, "symbol": req.symbol, "retcode": res.retcode})
        else:
            db.log_audit("ORDER_REJECTED", {"broker": self.name, "retcode": res.retcode, "comment": res.comment})

        return OrderResult(
            ok=ok,
            ticket=ticket,
            symbol=req.symbol,
            side=side,
            qty=res.volume,
            price=res.price or entry,
            comment=res.comment,
            retcode=res.retcode,
            error=None if ok else res.comment,
        )

    def close_position(self, ticket: str | int) -> OrderResult:
        import MetaTrader5 as mt5
        self.connect()
        positions = mt5.positions_get(ticket=int(ticket))
        if not positions:
            return OrderResult(ok=False, ticket=str(ticket), symbol="", side="", qty=0.0, price=0.0, comment="Position not found", error="Position not found")

        p = positions[0]
        info = mt5.symbol_info(p.symbol)
        tick = mt5.symbol_info_tick(p.symbol)
        is_buy = p.type == mt5.POSITION_TYPE_BUY
        order_type = mt5.ORDER_TYPE_SELL if is_buy else mt5.ORDER_TYPE_BUY
        price = tick.bid if is_buy else tick.ask

        res = mt5.order_send({
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": p.symbol,
            "volume": p.volume,
            "position": p.ticket,
            "type": order_type,
            "price": price,
            "deviation": 20,
            "magic": MAGIC_NUMBER,
            "comment": "yo-signals close",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": self._filling_mode(info),
        })

        if res is None:
            return OrderResult(ok=False, ticket=str(ticket), symbol=p.symbol, side="", qty=p.volume, price=price, comment=f"Close error: {mt5.last_error()}", error=str(mt5.last_error()))

        ok = res.retcode == mt5.TRADE_RETCODE_DONE
        if ok:
            db.update_trade_close(str(ticket), exit_price=price, pnl=p.profit, notes="MT5 closed")
            db.log_audit("POSITION_CLOSED", {"broker": self.name, "ticket": str(ticket), "profit": p.profit})

        return OrderResult(ok=ok, ticket=str(ticket), symbol=p.symbol, side="CLOSE", qty=p.volume, price=price, comment=res.comment, retcode=res.retcode)

    def modify_position(self, ticket: str | int, sl: float, tp: float) -> OrderResult:
        import MetaTrader5 as mt5
        self.connect()
        positions = mt5.positions_get(ticket=int(ticket))
        if not positions:
            return OrderResult(ok=False, ticket=str(ticket), symbol="", side="", qty=0.0, price=0.0, comment="Position not found", error="Position not found")

        p = positions[0]
        res = mt5.order_send({
            "action": mt5.TRADE_ACTION_SLTP,
            "symbol": p.symbol,
            "position": p.ticket,
            "sl": float(sl),
            "tp": float(tp),
        })
        ok = res is not None and res.retcode == mt5.TRADE_RETCODE_DONE
        return OrderResult(
            ok=ok,
            ticket=str(ticket),
            symbol=p.symbol,
            side="MODIFY",
            qty=p.volume,
            price=p.price_open,
            comment=res.comment if res else str(mt5.last_error()),
            retcode=res.retcode if res else None,
        )


def get_broker(name: str | None = None) -> AbstractBroker:
    """Factory to retrieve broker implementation."""
    selected = (name or TRADING_MODE).lower()
    if selected in ("mt5", "metatrader", "demo"):
        try:
            b = MT5Broker(demo_only=True)
            b.connect()
            return b
        except Exception:
            # Fall back to PaperBroker if MT5 terminal is not open
            return PaperBroker()
    return PaperBroker()
