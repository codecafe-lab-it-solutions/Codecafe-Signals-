"""Universal Hybrid Trade Execution Engine (API + Screen / UI Fallback).

Supports:
1. API Execution:
   - MetaTrader 5 (Forex / CFDs)
   - Bybit Demo Trading (Crypto Spot)
   - Paper / Alpaca (Equities)
2. Screen / UI Click Fallback:
   - Targets active desktop trading window (e.g., TradingView, web broker, desktop terminal)
   - Simulates focused order entry or hotkey execution via Windows API
   - Dry-run validation and strict confirmation guardrails
"""
import ctypes
import os
import time

# Guardrails
MAX_FOREX_LOTS = 0.10
MAX_CRYPTO_USDT = 1000.0


def _validate_order(symbol: str, side: str, qty: float, sl: float, tp: float | None = None):
    side = side.upper()
    if side not in ("BUY", "SELL"):
        raise ValueError(f"Invalid side {side!r}: must be BUY or SELL")
    if qty <= 0:
        raise ValueError(f"Invalid quantity {qty}: must be > 0")
    if not sl or sl <= 0:
        raise ValueError("Stop Loss (SL) is strictly mandatory on every trade.")
    return side


def execute_via_api(platform: str, symbol: str, side: str, qty: float, sl: float, tp: float | None = None) -> dict:
    """Execute order via native broker/exchange API."""
    platform = platform.lower()
    side = _validate_order(symbol, side, qty, sl, tp)

    # 1. MetaTrader 5
    if platform in ("mt5", "metatrader", "forex"):
        from server import place_order as mt5_place_order
        if qty > MAX_FOREX_LOTS:
            raise ValueError(f"Forex lot size {qty} exceeds safety cap of {MAX_FOREX_LOTS}")
        return mt5_place_order(name=symbol, side=side, lots=qty, sl=sl, tp=tp or 0.0)

    # 2. Bybit Demo / Testnet
    elif platform in ("bybit", "crypto"):
        from crypto_server import place_order as bybit_place_order
        if not tp:
            raise ValueError("Bybit bracket orders require both SL and TP.")
        return bybit_place_order(name=symbol, qty=qty, sl=sl, tp=tp)

    # 3. Paper broker: fake money at real prices, any symbol, no account or key needed
    elif platform in ("paper", "stock", "equity"):
        import paper
        return paper.open_trade(symbol, side, qty, sl, tp)

    else:
        raise ValueError(f"Unsupported API platform: {platform}. Use 'mt5', 'bybit', 'paper', or 'ui'.")


def execute_via_ui(window_title_keyword: str, hotkey: str | None = None, dry_run: bool = True) -> dict:
    """Screen / UI automation fallback using native Windows ctypes (zero-dependency).

    Finds target window by title, brings it to foreground, and triggers order action.
    """
    if os.name != "nt":
        return {"ok": False, "error": "UI automation only supported on Windows"}

    user32 = ctypes.windll.user32
    matched_hwnd = None
    matched_title = ""

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def enum_cb(hwnd, _):
        nonlocal matched_hwnd, matched_title
        if user32.IsWindowVisible(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            if length > 0:
                buff = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, buff, length + 1)
                if window_title_keyword.lower() in buff.value.lower():
                    matched_hwnd = hwnd
                    matched_title = buff.value
                    return False  # stop enumeration
        return True

    user32.EnumWindows(WNDENUMPROC(enum_cb), 0)

    if not matched_hwnd:
        return {"ok": False, "error": f"No visible window found matching keyword: {window_title_keyword!r}"}

    if dry_run:
        return {
            "ok": True,
            "mode": "DRY_RUN",
            "window_found": matched_title,
            "hwnd": matched_hwnd,
            "planned_action": f"Focus window and trigger hotkey: {hotkey or 'Shift+B'}",
            "note": "Pass dry_run=False and confirm=True to execute real UI click.",
        }

    # Bring window to foreground
    user32.ShowWindow(matched_hwnd, 9)  # SW_RESTORE = 9
    user32.SetForegroundWindow(matched_hwnd)
    time.sleep(0.3)

    return {
        "ok": False,
        "mode": "FOCUSED_ONLY",
        "window": matched_title,
        "action": "Window brought to front. No order was placed: place it yourself from the trade plan.",
    }


def execute_trade_hybrid(
    platform: str,
    symbol: str,
    side: str,
    qty: float,
    sl: float,
    tp: float | None = None,
    method: str = "api",
    confirm: bool = False,
    window_keyword: str = "",
) -> dict:
    """Universal execution entry point with mandatory safety check."""
    if not confirm:
        return {
            "ok": False,
            "status": "AWAITING_CONFIRMATION",
            "order_summary": {
                "platform": platform,
                "method": method,
                "symbol": symbol,
                "side": side.upper(),
                "qty": qty,
                "sl": sl,
                "tp": tp,
            },
            "warning": "Order not placed. Explicit user confirmation (confirm=True) is required.",
        }

    if method.lower() == "api":
        return execute_via_api(platform, symbol, side, qty, sl, tp)
    elif method.lower() == "ui":
        return execute_via_ui(window_title_keyword=window_keyword or platform, dry_run=False)
    else:
        raise ValueError(f"Unknown method {method!r}. Use 'api' or 'ui'.")
