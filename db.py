"""Local SQLite Database for CodeCafe Signals prototype.
Zero-dependency, thread-safe persistence for signals, orders, and audit trail.
"""
import json
import sqlite3
import time
from typing import Any

from config import DB_PATH


def get_connection(path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path: str = DB_PATH) -> None:
    with get_connection(path) as conn:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            strategy TEXT NOT NULL,
            signal TEXT NOT NULL,
            entry REAL,
            sl REAL,
            tp REAL,
            confidence REAL,
            regime TEXT,
            reasons TEXT
        );

        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket TEXT UNIQUE,
            broker TEXT NOT NULL,
            symbol TEXT NOT NULL,
            side TEXT NOT NULL,
            qty REAL NOT NULL,
            entry_price REAL NOT NULL,
            exit_price REAL,
            sl REAL NOT NULL,
            tp REAL,
            pnl REAL DEFAULT 0.0,
            status TEXT NOT NULL,
            opened_at REAL NOT NULL,
            closed_at REAL,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            event_type TEXT NOT NULL,
            payload TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS market_intelligence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            symbol TEXT NOT NULL,
            timeframe TEXT NOT NULL,
            regime TEXT,
            sentiment_score REAL,
            summary TEXT
        );
        """)


def log_signal(
    symbol: str,
    timeframe: str,
    strategy: str,
    signal: str,
    entry: float | None,
    sl: float | None,
    tp: float | None,
    confidence: float = 0.0,
    regime: str = "",
    reasons: list[str] | str = "",
    path: str = DB_PATH,
) -> int:
    reasons_str = json.dumps(reasons) if isinstance(reasons, list) else str(reasons)
    with get_connection(path) as conn:
        cur = conn.execute(
            """INSERT INTO signals (timestamp, symbol, timeframe, strategy, signal, entry, sl, tp, confidence, regime, reasons)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (time.time(), symbol, timeframe, strategy, signal, entry, sl, tp, confidence, regime, reasons_str),
        )
        return cur.lastrowid or 0


def record_trade(
    ticket: str | int,
    broker: str,
    symbol: str,
    side: str,
    qty: float,
    entry_price: float,
    sl: float,
    tp: float | None = None,
    status: str = "OPEN",
    notes: str = "",
    path: str = DB_PATH,
) -> int:
    with get_connection(path) as conn:
        cur = conn.execute(
            """INSERT OR REPLACE INTO trades (ticket, broker, symbol, side, qty, entry_price, sl, tp, status, opened_at, notes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (str(ticket), broker, symbol, side.upper(), qty, entry_price, sl, tp, status, time.time(), notes),
        )
        return cur.lastrowid or 0


def update_trade_close(
    ticket: str | int,
    exit_price: float,
    pnl: float,
    notes: str = "",
    path: str = DB_PATH,
) -> bool:
    with get_connection(path) as conn:
        cur = conn.execute(
            """UPDATE trades
               SET exit_price = ?, pnl = ?, status = 'CLOSED', closed_at = ?, notes = notes || ' | ' || ?
               WHERE ticket = ?""",
            (exit_price, pnl, time.time(), notes, str(ticket)),
        )
        return cur.rowcount > 0


def get_open_trades(broker: str | None = None, path: str = DB_PATH) -> list[dict[str, Any]]:
    with get_connection(path) as conn:
        if broker:
            rows = conn.execute("SELECT * FROM trades WHERE status = 'OPEN' AND broker = ?", (broker,)).fetchall()
        else:
            rows = conn.execute("SELECT * FROM trades WHERE status = 'OPEN'").fetchall()
        return [dict(r) for r in rows]


def get_daily_realized_pnl(path: str = DB_PATH) -> float:
    start_of_day = time.time() - (time.time() % 86400)
    with get_connection(path) as conn:
        row = conn.execute(
            "SELECT SUM(pnl) as total FROM trades WHERE status = 'CLOSED' AND closed_at >= ?",
            (start_of_day,),
        ).fetchone()
        return float(row["total"] or 0.0) if row else 0.0


def log_audit(event_type: str, payload: dict | str, path: str = DB_PATH) -> None:
    data = json.dumps(payload) if isinstance(payload, dict) else str(payload)
    with get_connection(path) as conn:
        conn.execute(
            "INSERT INTO audit_log (timestamp, event_type, payload) VALUES (?, ?, ?)",
            (time.time(), event_type, data),
        )


# Auto-initialize tables on module import
init_db()

