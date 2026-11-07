"""System 3.C & 3.D: Independent Risk Management & Kill Switch Engine.
Enforces hard mathematical risk limits independent of strategy or AI models.
"""
from dataclasses import dataclass
from typing import Any

from broker import AbstractBroker, AccountInfo, OrderRequest
from config import MAGIC_NUMBER, MAX_DAILY_LOSS_PCT, MAX_LOTS, MAX_OPEN_POSITIONS, RISK_PCT
import db
from economic_calendar import check_event_risk


@dataclass
class RiskValidationResult:
    allowed: bool
    reason: str
    suggested_qty: float
    risk_dollars: float
    risk_pct: float


class RiskEngine:
    """Independent financial safety gatekeeper."""

    def __init__(self, risk_pct: float = RISK_PCT, max_daily_loss_pct: float = MAX_DAILY_LOSS_PCT, max_positions: int = MAX_OPEN_POSITIONS):
        self.risk_pct = risk_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_positions = max_positions
        self._stopped_users: set[str] = set()

    @property
    def kill_switch_active(self) -> bool:
        """Per login: one client's kill switch never stops other clients (paper.USER is set per request)."""
        import paper
        return paper.USER.get() in self._stopped_users

    def trigger_kill_switch(self, reason: str = "Operator manual emergency stop") -> None:
        import paper
        self._stopped_users.add(paper.USER.get())
        db.log_audit("KILL_SWITCH_ENGAGED", {"reason": reason, "user": paper.USER.get()})

    def reset_kill_switch(self) -> None:
        import paper
        self._stopped_users.discard(paper.USER.get())
        db.log_audit("KILL_SWITCH_RESET", {"status": "normal", "user": paper.USER.get()})

    SL_COOLDOWN_MIN = 60  # no new trade on a symbol for this long after it hit its stop-loss
    MAX_LOSS_STREAK = 3  # losing trades in a row (closed today, UTC) that pause trading until tomorrow

    def protection_refusal(self, symbol: str, now: float | None = None) -> str | None:
        """Reason to refuse a new paper trade, or None. Rules modelled on freqtrade's protections."""
        import time

        import paper
        now = now or time.time()
        closed = sorted((t for t in paper.load()["trades"] if t.get("closed")), key=lambda t: t["closed"])
        last_sl = max((t["closed"] for t in closed if t["symbol"] == symbol and t["status"] == "STOP_LOSS"), default=0)
        wait = last_sl + self.SL_COOLDOWN_MIN * 60 - now
        if wait > 0:
            return f"Refused: {symbol} hit its stop-loss recently; cooldown ends in {wait / 60:.0f} min."
        today = [t for t in closed if t["closed"] >= now - now % 86400]
        streak = 0
        for t in reversed(today):
            if t.get("pnl", 0) >= 0:
                break
            streak += 1
        if streak >= self.MAX_LOSS_STREAK:
            return f"Refused: {streak} losing trades in a row today; trading pauses until 00:00 UTC."
        return None

    def calculate_position_size(self, balance: float, entry: float, sl: float, symbol: str) -> float:
        """Calculate lot / contract size based on 1% balance risk and stop loss distance."""
        sl_distance = abs(entry - sl)
        if sl_distance <= 0:
            return 0.01

        risk_dollars = balance * (self.risk_pct / 100.0)
        # Sizing formula: risk_dollars / sl_distance
        raw_qty = risk_dollars / sl_distance

        # Commodity / Forex lot normalization
        sym = symbol.upper()
        if sym in ("XAUUSD", "GC=F", "USOUSD", "CL=F", "XAGUSD", "SI=F"):
            qty = min(MAX_LOTS, max(0.01, round(raw_qty * 0.01, 2)))
        elif len(sym) == 6:  # standard forex pair
            qty = min(MAX_LOTS, max(0.01, round(raw_qty / 1000.0, 2)))
        else:
            qty = min(MAX_LOTS, max(0.01, round(raw_qty, 2)))

        return qty

    def validate_trade(
        self,
        broker: AbstractBroker,
        symbol: str,
        side: str,
        entry: float,
        sl: float,
        tp: float | None = None,
        check_news: bool = True,
    ) -> RiskValidationResult:
        """Independently validate proposed trade against hard account limits."""
        # 1. Emergency kill switch
        if self.kill_switch_active:
            return RiskValidationResult(False, "Refused: Emergency kill switch active.", 0.0, 0.0, 0.0)

        # 2. Mandatory Stop Loss
        if not sl or sl <= 0:
            return RiskValidationResult(False, "Refused: Stop Loss is strictly mandatory.", 0.0, 0.0, 0.0)

        # 3. Directional SL/TP sanity
        side = side.upper()
        if side == "BUY" and sl >= entry:
            return RiskValidationResult(False, f"Refused: BUY SL ({sl}) must be below entry ({entry}).", 0.0, 0.0, 0.0)
        if side == "SELL" and sl <= entry:
            return RiskValidationResult(False, f"Refused: SELL SL ({sl}) must be above entry ({entry}).", 0.0, 0.0, 0.0)

        # 4. Minimum Risk/Reward Ratio (>= 1.5)
        if tp and tp > 0:
            risk = abs(entry - sl)
            reward = abs(tp - entry)
            rr = reward / risk if risk > 0 else 0
            if rr < 1.49:
                return RiskValidationResult(False, f"Refused: Risk/Reward ratio {rr:.2f} is below minimum 1.50.", 0.0, 0.0, 0.0)

        # 5. Account Balances and Daily Drawdown
        try:
            acct = broker.get_account()
            balance = acct.balance
        except Exception as e:
            return RiskValidationResult(False, f"Refused: Broker account query failed: {e}", 0.0, 0.0, 0.0)

        if broker.name == "paper":
            import paper
            daily_loss = paper.daily_pnl()
        else:
            daily_loss = db.get_daily_realized_pnl()
        max_permitted_loss = -balance * (self.max_daily_loss_pct / 100.0)
        if daily_loss <= max_permitted_loss:
            return RiskValidationResult(False, f"Refused: Daily loss limit reached ({daily_loss:.2f} <= {max_permitted_loss:.2f}).", 0.0, 0.0, 0.0)

        # 5b. Protections (paper accounts): pause a symbol after its stop-loss, stop after a losing streak
        if broker.name == "paper":
            refusal = self.protection_refusal(symbol)
            if refusal:
                return RiskValidationResult(False, refusal, 0.0, 0.0, 0.0)

        # 6. Max Open Positions Cap
        open_positions = broker.get_positions()
        if len(open_positions) >= self.max_positions:
            return RiskValidationResult(False, f"Refused: Maximum open positions ({self.max_positions}) reached.", 0.0, 0.0, 0.0)

        # 7. Imminent High-Impact Macro News Blackout
        if check_news:
            news_risk = check_event_risk(symbol)
            if news_risk.get("is_risk_event_imminent"):
                # Rather than completely blocking, allow trade with half-size or reject if configured
                return RiskValidationResult(False, f"Refused: Macro event blackout active: {news_risk.get('reason')}", 0.0, 0.0, 0.0)

        # 8. Position Sizing
        qty = self.calculate_position_size(balance, entry, sl, symbol)
        risk_dollars = abs(entry - sl) * qty
        risk_pct = (risk_dollars / balance) * 100.0

        return RiskValidationResult(
            allowed=True,
            reason="All risk parameters satisfied.",
            suggested_qty=qty,
            risk_dollars=round(risk_dollars, 2),
            risk_pct=round(risk_pct, 2),
        )

