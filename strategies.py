"""System 2: Modular Quantitative Strategy Engine.
Implements AbstractStrategy interface with Trend Following, Breakout,
and Mean Reversion strategies, coordinated by StrategyManager.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class StrategySignal:
    strategy_id: str
    symbol: str
    timeframe: str
    action: str  # BUY, SELL, HOLD, NO_TRADE
    entry: float
    sl: float
    tp: float
    risk_reward: float
    confidence: float
    reasons: list[str]


class AbstractStrategy(ABC):
    """Base strategy interface."""

    id: str = "base"
    name: str = "Base Strategy"
    active: bool = True

    @abstractmethod
    def evaluate(self, intel: dict[str, Any]) -> StrategySignal | None:
        """Evaluate market intelligence report and return a trade signal if conditions are met."""
        pass


class TrendFollowingStrategy(AbstractStrategy):
    """Trend Following: Trades in direction of Strong Trend with pullback to key support/resistance."""

    id: str = "trend_following"
    name: str = "Trend Following with BOS/FVG"

    def evaluate(self, intel: dict[str, Any]) -> StrategySignal | None:
        regime = intel["market_regime"]
        p = intel["current_price"]
        symbol = intel["instrument"]
        tf = intel["timeframe"]
        struct = intel["technical_structure"]
        supports = intel["support_levels"]
        resistances = intel["resistance_levels"]

        # Bullish setup
        if "BULLISH" in regime and intel["market_direction"] == "BULLISH":
            sl = supports[-1] if supports else round(p * 0.99, 4)
            risk = p - sl
            if risk <= 0:
                risk = p * 0.005
                sl = round(p - risk, 4)
            tp = round(p + risk * 2.0, 4)
            rr = round((tp - p) / risk, 2)
            return StrategySignal(
                strategy_id=self.id,
                symbol=symbol,
                timeframe=tf,
                action="BUY",
                entry=p,
                sl=sl,
                tp=tp,
                risk_reward=rr,
                confidence=min(0.90, intel["confidence_score"] + 0.05),
                reasons=[f"Aligned with {regime}", f"BOS trend: {intel['market_direction']}", f"Targeting 1:{rr} R:R"],
            )

        # Bearish setup
        elif "BEARISH" in regime and intel["market_direction"] == "BEARISH":
            sl = resistances[0] if resistances else round(p * 1.01, 4)
            risk = sl - p
            if risk <= 0:
                risk = p * 0.005
                sl = round(p + risk, 4)
            tp = round(p - risk * 2.0, 4)
            rr = round((p - tp) / risk, 2)
            return StrategySignal(
                strategy_id=self.id,
                symbol=symbol,
                timeframe=tf,
                action="SELL",
                entry=p,
                sl=sl,
                tp=tp,
                risk_reward=rr,
                confidence=min(0.90, intel["confidence_score"] + 0.05),
                reasons=[f"Aligned with {regime}", f"BOS trend: {intel['market_direction']}", f"Targeting 1:{rr} R:R"],
            )

        return None


class MeanReversionStrategy(AbstractStrategy):
    """Mean Reversion: Fades overextended market extremes in ranging or high volatility regimes."""

    id: str = "mean_reversion"
    name: str = "Mean Reversion Rejection"

    def evaluate(self, intel: dict[str, Any]) -> StrategySignal | None:
        patterns = intel["candlestick_patterns"]
        p = intel["current_price"]
        symbol = intel["instrument"]
        tf = intel["timeframe"]
        supports = intel["support_levels"]
        resistances = intel["resistance_levels"]

        # Long rejection at support
        if any(pat in ("Hammer / Bullish Pin Bar", "Morning Star", "Bullish Engulfing") for pat in patterns):
            if supports:
                sl = round(supports[-1] * 0.998, 4)
                risk = p - sl
                if risk > 0:
                    tp = round(p + risk * 2.0, 4)
                    return StrategySignal(
                        strategy_id=self.id,
                        symbol=symbol,
                        timeframe=tf,
                        action="BUY",
                        entry=p,
                        sl=sl,
                        tp=tp,
                        risk_reward=2.0,
                        confidence=0.75,
                        reasons=[f"Bullish reversal pattern: {patterns}", "Bounce off confirmed support pivot"],
                    )

        # Short rejection at resistance
        if any(pat in ("Shooting Star / Bearish Pin Bar", "Evening Star", "Bearish Engulfing") for pat in patterns):
            if resistances:
                sl = round(resistances[0] * 1.002, 4)
                risk = sl - p
                if risk > 0:
                    tp = round(p - risk * 2.0, 4)
                    return StrategySignal(
                        strategy_id=self.id,
                        symbol=symbol,
                        timeframe=tf,
                        action="SELL",
                        entry=p,
                        sl=sl,
                        tp=tp,
                        risk_reward=2.0,
                        confidence=0.75,
                        reasons=[f"Bearish reversal pattern: {patterns}", "Rejection at confirmed resistance pivot"],
                    )

        return None


class BreakoutStrategy(AbstractStrategy):
    """Breakout Strategy: Catches explosive breakouts through swing highs/lows with volatility expansion."""

    id: str = "breakout"
    name: str = "Structural Pivot Breakout"

    def evaluate(self, intel: dict[str, Any]) -> StrategySignal | None:
        p = intel["current_price"]
        struct = intel["technical_structure"]
        symbol = intel["instrument"]
        tf = intel["timeframe"]
        swing_h = struct.get("recent_swing_high", 0.0)
        swing_l = struct.get("recent_swing_low", 0.0)

        if swing_h > 0 and p > swing_h * 1.001 and intel["volatility_condition"] in ("HIGH_VOLATILITY", "NORMAL_VOLATILITY"):
            sl = swing_h * 0.997
            risk = p - sl
            tp = p + risk * 2.5
            return StrategySignal(
                strategy_id=self.id,
                symbol=symbol,
                timeframe=tf,
                action="BUY",
                entry=p,
                sl=round(sl, 4),
                tp=round(tp, 4),
                risk_reward=2.5,
                confidence=0.82,
                reasons=[f"Breakout above swing high {swing_h}", "Volatility expansion confirmation"],
            )

        if swing_l > 0 and p < swing_l * 0.999 and intel["volatility_condition"] in ("HIGH_VOLATILITY", "NORMAL_VOLATILITY"):
            sl = swing_l * 1.003
            risk = sl - p
            tp = p - risk * 2.5
            return StrategySignal(
                strategy_id=self.id,
                symbol=symbol,
                timeframe=tf,
                action="SELL",
                entry=p,
                sl=round(sl, 4),
                tp=round(tp, 4),
                risk_reward=2.5,
                confidence=0.82,
                reasons=[f"Breakout below swing low {swing_l}", "Volatility expansion confirmation"],
            )

        return None


class StrategyManager:
    """Coordinates and evaluates all active trading strategies."""

    def __init__(self):
        self.strategies: dict[str, AbstractStrategy] = {
            "trend_following": TrendFollowingStrategy(),
            "mean_reversion": MeanReversionStrategy(),
            "breakout": BreakoutStrategy(),
        }

    def set_strategy_active(self, strategy_id: str, active: bool) -> bool:
        if strategy_id in self.strategies:
            self.strategies[strategy_id].active = active
            return True
        return False

    def evaluate_all(self, intel: dict[str, Any]) -> StrategySignal | None:
        """Run all active strategies on intelligence report and return highest-confidence signal."""
        candidates: list[StrategySignal] = []
        for strat in self.strategies.values():
            if not strat.active:
                continue
            sig = strat.evaluate(intel)
            if sig and sig.action in ("BUY", "SELL"):
                candidates.append(sig)

        if not candidates:
            return StrategySignal(
                strategy_id="none",
                symbol=intel["instrument"],
                timeframe=intel["timeframe"],
                action="NO_TRADE",
                entry=intel["current_price"],
                sl=0.0,
                tp=0.0,
                risk_reward=0.0,
                confidence=0.0,
                reasons=["No active strategy setup triggered"],
            )

        # Sort by confidence descending
        candidates.sort(key=lambda s: s.confidence, reverse=True)
        return candidates[0]

