"""Autonomous Trading Orchestrator.
Glues System 1 (Intelligence), System 2 (Decision/Strategy),
and System 3 (Risk & Broker Execution) into an autonomous lifecycle.
"""
from dataclasses import asdict
import time
from typing import Any

from broker import AbstractBroker, OrderRequest, get_broker
from config import TRADING_MODE, WATCHLIST
import db
from intelligence import generate_market_intelligence
from risk_engine import RiskEngine
from strategies import StrategyManager


class AutonomousTradingOrchestrator:
    """Central engine running the complete trading pipeline."""

    def __init__(self, broker: AbstractBroker | None = None, risk_engine: RiskEngine | None = None):
        self.broker = broker or get_broker(TRADING_MODE)
        self.risk_engine = risk_engine or RiskEngine()
        self.strategy_mgr = StrategyManager()

    def run_single_cycle(self, symbol: str, execute: bool = False) -> dict[str, Any]:
        """Run an end-to-end cycle for a symbol: Intel -> Strategy -> Risk -> Order."""
        # 1. System 1: Market Intelligence
        intel = generate_market_intelligence(symbol, timeframe="H1", use_llm=False)

        # 2. System 2: Strategy Evaluation
        sig = self.strategy_mgr.evaluate_all(intel)
        if not sig or sig.action not in ("BUY", "SELL"):
            db.log_signal(symbol, "H1", "NONE", "NO_TRADE", intel["current_price"], 0.0, 0.0, 0.0, intel["market_regime"], "No setup")
            return {
                "symbol": symbol,
                "intelligence": intel,
                "signal": asdict(sig) if sig else None,
                "risk_validation": None,
                "execution": None,
                "status": "NO_SETUP",
            }

        # Log generated signal
        db.log_signal(symbol, sig.timeframe, sig.strategy_id, sig.action, sig.entry, sig.sl, sig.tp, sig.confidence, intel["market_regime"], sig.reasons)

        # 3. System 3: Independent Risk Validation
        risk_res = self.risk_engine.validate_trade(
            broker=self.broker,
            symbol=symbol,
            side=sig.action,
            entry=sig.entry,
            sl=sig.sl,
            tp=sig.tp,
            check_news=False,  # Allow signals in paper/test mode
        )

        exec_res = None
        if risk_res.allowed and execute:
            req = OrderRequest(
                symbol=symbol,
                side=sig.action,
                qty=risk_res.suggested_qty,
                sl=sig.sl,
                tp=sig.tp,
                price=sig.entry,
                comment=f"strat:{sig.strategy_id}",
            )
            exec_res = self.broker.submit_order(req)
            db.log_audit("ORCHESTRATOR_EXECUTION", {"symbol": symbol, "result": asdict(exec_res)})

        return {
            "symbol": symbol,
            "intelligence": intel,
            "signal": asdict(sig),
            "risk_validation": asdict(risk_res),
            "execution": asdict(exec_res) if exec_res else None,
            "status": "EXECUTED" if (exec_res and exec_res.ok) else ("RISK_REJECTED" if not risk_res.allowed else "READY_FOR_APPROVAL"),
        }

    def monitor_and_trail_positions(self) -> list[dict[str, Any]]:
        """Scan open positions, trail SL to breakeven at +1.5R profit."""
        positions = self.broker.get_positions()
        updates = []
        for p in positions:
            sign = 1 if p.side == "BUY" else -1
            risk = abs(p.open_price - p.sl)
            gain = (p.current_price - p.open_price) * sign

            # If gain >= 1.5R and SL is still below/above entry, move to breakeven
            if risk > 0 and gain >= risk * 1.5:
                is_unprotected = (p.sl < p.open_price) if p.side == "BUY" else (p.sl > p.open_price)
                if is_unprotected:
                    res = self.broker.modify_position(p.ticket, sl=p.open_price, tp=p.tp)
                    updates.append({"ticket": p.ticket, "action": "TRAIL_TO_BREAKEVEN", "res": asdict(res)})
                    db.log_audit("TRAIL_STOP_BREAKEVEN", {"ticket": p.ticket, "symbol": p.symbol, "new_sl": p.open_price})

        return updates

    def emergency_shutdown(self) -> dict[str, Any]:
        """Trigger emergency kill switch and close all active positions."""
        self.risk_engine.trigger_kill_switch("Emergency operator shutdown requested")
        positions = self.broker.get_positions()
        closed = []
        for p in positions:
            c_res = self.broker.close_position(p.ticket)
            closed.append({"ticket": p.ticket, "closed": c_res.ok})
        return {"kill_switch": True, "closed_positions": closed}

