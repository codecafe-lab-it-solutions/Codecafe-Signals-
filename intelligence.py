"""System 1: Consolidated Market Intelligence AI Engine.
Aggregates live market data, candlestick analysis, market structure (FVG/BOS),
market regime, news sentiment, and economic event risks into a unified intelligence report.
"""
from dataclasses import asdict, dataclass
import time
from typing import Any

from chart_vision import cluster_levels, find_pivots
from economic_calendar import check_event_risk
from llm import analyze_news_impact
from market_structure import get_market_structure_report
from ml_pipeline import predict_barrier_probability
from news_scraper import fetch_symbol_news
from rag_kb import search_knowledge_base
from regime import detect_market_regime
from universal_data import closed_bars, fetch_universal_candles


def technical_report(symbol: str, timeframe: str, bars: dict, price: float, news_sentiment: str = "NEUTRAL") -> dict[str, Any]:
    """Everything the strategies read, from closed bars plus the latest price. No network, so the
    backtester replays exactly what the live scan computes."""
    regime_data = detect_market_regime(bars)
    structure_data = get_market_structure_report(bars)
    pivots = find_pivots(bars["high"], bars["low"], window=5)
    support_levels = [lvl for lvl in cluster_levels(pivots["swing_lows"]) if lvl < price]
    resistance_levels = [lvl for lvl in cluster_levels(pivots["swing_highs"]) if lvl > price]

    # Synthesize Overall Direction & Confidence
    trend_score = 0
    if "BULLISH" in regime_data["regime"]:
        trend_score += 2
    elif "BEARISH" in regime_data["regime"]:
        trend_score -= 2

    if structure_data["trend"] == "BULLISH":
        trend_score += 1
    elif structure_data["trend"] == "BEARISH":
        trend_score -= 1

    if news_sentiment == "BULLISH":
        trend_score += 1
    elif news_sentiment == "BEARISH":
        trend_score -= 1

    direction = "BULLISH" if trend_score >= 2 else ("BEARISH" if trend_score <= -2 else "SIDEWAYS")
    confidence = min(0.95, max(0.50, 0.50 + abs(trend_score) * 0.10))
    return {
        "instrument": symbol,
        "timeframe": timeframe,
        "current_price": round(price, 4),
        "market_direction": direction,
        "market_regime": regime_data["regime"],
        "volatility_condition": regime_data["volatility_status"],
        "adx": regime_data["adx"],
        "technical_structure": {
            "bos_choch_events": structure_data["structural_events"],
            "recent_swing_high": structure_data["recent_swing_high"],
            "recent_swing_low": structure_data["recent_swing_low"],
            "active_fvgs_count": structure_data["active_fvgs_count"],
            "nearest_bullish_fvg": structure_data["nearest_bullish_fvg"],
            "nearest_bearish_fvg": structure_data["nearest_bearish_fvg"],
            "order_blocks_count": len(structure_data["order_blocks"]),
        },
        "candlestick_patterns": structure_data["candlestick_patterns"],
        "support_levels": support_levels[-3:],
        "resistance_levels": resistance_levels[:3],
        "confidence_score": round(confidence, 2),
    }


def generate_market_intelligence(symbol: str, timeframe: str = "H1", use_llm: bool = True) -> dict[str, Any]:
    """Produce the complete System 1 Market Intelligence Report."""
    candles = fetch_universal_candles(symbol, timeframe, count=80)
    current_price = float(candles["close"][-1])  # live: the forming bar's close
    data_timestamp = float(candles["time"][-1]) if len(candles["time"]) > 0 else time.time()
    bars = closed_bars(candles, timeframe)  # analysis on closed bars only, so signals don't repaint

    macro_risk = check_event_risk(symbol)
    news_items = fetch_symbol_news(symbol, limit=6)
    if use_llm and news_items:
        llm_impact = analyze_news_impact(news_items, symbol)
    else:
        llm_impact = {"sentiment": "NEUTRAL", "impact": "LOW", "summary": "No LLM analysis run."}
    ml_odds = predict_barrier_probability(bars)
    tech = technical_report(symbol, timeframe, bars, current_price, llm_impact.get("sentiment", "NEUTRAL"))
    retrieved_rules = search_knowledge_base(f"{symbol} {tech['market_regime']} risk rules", top_k=2)

    return {
        **tech,
        "data_timestamp": data_timestamp,
        "data_source": candles.get("source"),  # mt5, bybit or yahoo
        "data_symbol": candles.get("symbol"),  # the feed's own ticker, e.g. GC=F for XAUUSD on Yahoo
        "news_sentiment": llm_impact.get("sentiment", "NEUTRAL"),
        "news_summary": llm_impact.get("summary", ""),
        "upcoming_economic_events": macro_risk.get("top_events", []),
        "event_risk_action": macro_risk.get("action", "TRADE_PERMITTED"),
        "ml_barrier_win_odds": ml_odds.get("barrier_win_probability", 0.50),
        "ml_high_prob_setup": ml_odds.get("is_high_probability_setup", False),
        "retrieved_trading_rules": [r["title"] for r in retrieved_rules],
    }

