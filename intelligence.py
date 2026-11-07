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
from universal_data import fetch_universal_candles


def generate_market_intelligence(symbol: str, timeframe: str = "H1", use_llm: bool = True) -> dict[str, Any]:
    """Produce the complete System 1 Market Intelligence Report."""
    # 1. Price Data
    candles = fetch_universal_candles(symbol, timeframe, count=80)
    current_price = float(candles["close"][-1])
    data_timestamp = float(candles["time"][-1]) if len(candles["time"]) > 0 else time.time()

    # 2. Market Regime & Volatility
    regime_data = detect_market_regime(candles)

    # 3. Market Structure (FVGs, Order Blocks, BOS/CHOCH, Candlestick Patterns)
    structure_data = get_market_structure_report(candles)

    # 4. Support and Resistance Pivots
    pivots = find_pivots(candles["high"], candles["low"], window=5)
    support_levels = [lvl for lvl in cluster_levels(pivots["swing_lows"]) if lvl < current_price]
    resistance_levels = [lvl for lvl in cluster_levels(pivots["swing_highs"]) if lvl > current_price]

    # 5. Economic Calendar & Macro Event Risk
    macro_risk = check_event_risk(symbol)

    # 6. News & Sentiment
    news_items = fetch_symbol_news(symbol, limit=6)
    if use_llm and news_items:
        llm_impact = analyze_news_impact(news_items, symbol)
    else:
        llm_impact = {"sentiment": "NEUTRAL", "impact": "LOW", "summary": "No LLM analysis run."}

    # 7. Machine Learning Barrier Odds
    ml_odds = predict_barrier_probability(candles)

    # 8. RAG Knowledge Base Retrieval
    kb_query = f"{symbol} {regime_data['regime']} risk rules"
    retrieved_rules = search_knowledge_base(kb_query, top_k=2)

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

    if llm_impact.get("sentiment") == "BULLISH":
        trend_score += 1
    elif llm_impact.get("sentiment") == "BEARISH":
        trend_score -= 1

    direction = "BULLISH" if trend_score >= 2 else ("BEARISH" if trend_score <= -2 else "SIDEWAYS")
    confidence = min(0.95, max(0.50, 0.50 + abs(trend_score) * 0.10))

    return {
        "instrument": symbol,
        "timeframe": timeframe,
        "current_price": round(current_price, 4),
        "data_timestamp": data_timestamp,
        "data_source": candles.get("source"),  # mt5, bybit or yahoo
        "data_symbol": candles.get("symbol"),  # the feed's own ticker, e.g. GC=F for XAUUSD on Yahoo
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
        "news_sentiment": llm_impact.get("sentiment", "NEUTRAL"),
        "news_summary": llm_impact.get("summary", ""),
        "upcoming_economic_events": macro_risk.get("top_events", []),
        "event_risk_action": macro_risk.get("action", "TRADE_PERMITTED"),
        "confidence_score": round(confidence, 2),
        "ml_barrier_win_odds": ml_odds.get("barrier_win_probability", 0.50),
        "ml_high_prob_setup": ml_odds.get("is_high_probability_setup", False),
        "retrieved_trading_rules": [r["title"] for r in retrieved_rules],
    }

