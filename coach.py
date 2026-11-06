"""Screen coach: reads a screenshot of any trading screen and returns one BUY / SELL / WAIT plan.

Provider order: Gemini (GEMINI_API_KEY, free tier) -> Claude (ANTHROPIC_API_KEY) -> a free plan from
live chart data and news when a symbol is given (no screen reading).
"""
import base64
import json
import os
import urllib.error
import urllib.request

import config  # noqa: F401  loads .env
from chart_vision import analyze_market_structure
from news_scraper import get_market_news_brief
from universal_data import fetch_universal_candles

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
# free tier: 3.8-flash hung >240s on 2026-11-06 while 3.5-flash took 14s and 3.1-flash-lite 7s,
# so fall back to the fast lite model first on 503/429/timeouts
GEMINI_FALLBACKS = [GEMINI_MODEL, "gemini-3.1-flash-lite", "gemini-flash-latest"]
FRAME = os.path.join(os.path.dirname(os.path.abspath(__file__)), "latest_frame.jpg")

SYSTEM = """You are a careful trading coach looking at a screenshot of the user's trading screen
(any broker, exchange or charting app). Read only what is visible. Never invent prices you cannot see.
Give one plan: BUY, SELL or WAIT. Prefer WAIT when the chart is unclear, the timeframe is too small to read,
or price is in the middle of a range. Every BUY/SELL needs a stop-loss at a level that proves the idea wrong
and a take-profit with at least 1.5x the risk. Use 0 for prices when the action is WAIT.
If the screen is a binary-options or betting site (fixed-time up/down bets), set action WAIT and say in risks
that these are unauthorised in India and have negative expected value.
Say exactly which button or field the user would use on that screen in what_to_click, but never claim to have clicked it.
Be honest about uncertainty: these are educational ideas, not financial advice."""

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "platform_seen": {"type": "string"},
        "symbol_seen": {"type": "string"},
        "timeframe_seen": {"type": "string"},
        "trend": {"type": "string"},
        "action": {"type": "string", "enum": ["BUY", "SELL", "WAIT"]},
        "entry": {"type": "number"},
        "sl": {"type": "number"},
        "tp": {"type": "number"},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "reasons": {"type": "array", "items": {"type": "string"}},
        "risks": {"type": "array", "items": {"type": "string"}},
        "what_to_click": {"type": "string"},
    },
    "required": ["platform_seen", "symbol_seen", "timeframe_seen", "trend", "action", "entry", "sl", "tp",
                 "confidence", "reasons", "risks", "what_to_click"],
    "additionalProperties": False,
}


def market_context(symbol):
    """Live technicals and news for the symbol, so the plan is not based on the picture alone."""
    ctx = {}
    try:
        s = analyze_market_structure(fetch_universal_candles(symbol, "H1", 100))
        ctx["technicals_H1"] = {k: s[k] for k in ("current_price", "trend", "rsi", "atr", "candlestick_patterns",
                                                  "nearest_support", "nearest_resistance")}
    except Exception as e:
        ctx["technicals_error"] = str(e)
    news = get_market_news_brief(symbol)
    ctx["news"] = {"sentiment": news.get("overall_sentiment"), "high_impact": news.get("high_impact_flags"),
                   "headlines": [a["title"] for a in news.get("articles", [])[:5]]}
    return ctx


def technical_plan(symbol, why="No AI key"):
    """Free plan from live candles + news. It does not read the screenshot."""
    s = analyze_market_structure(fetch_universal_candles(symbol, "H1", 100))
    rec = s["recommendation"]
    news = get_market_news_brief(symbol)
    risks = [f"{why}: this plan comes from live H1 chart data and news, not from your screenshot.",
             "The chart-pattern rules behind it have not been backtested."]
    if news.get("high_impact_flags"):
        risks.append("High-impact news: " + ", ".join(news["high_impact_flags"]))
    return {"platform_seen": "live data (no screen reading)", "symbol_seen": symbol, "timeframe_seen": "H1",
            "trend": f"{s['trend']}, RSI {s['rsi']}, news {news.get('overall_sentiment', 'NEUTRAL')}",
            "action": rec["action"], "entry": rec["entry"] or 0, "sl": rec["sl"] or 0, "tp": rec["tp"] or 0,
            "confidence": "low",
            "reasons": rec["reasons"] + [f"Support {s['nearest_support']}, resistance {s['nearest_resistance']}"],
            "risks": risks, "what_to_click": "Place it yourself on your platform if you agree, or practise it as a paper trade."}


def _last_text(node):
    """Last {"type": "text", "text": ...} item anywhere in a response (the Interactions API shape isn't documented)."""
    found = None
    if isinstance(node, dict):
        if isinstance(node.get("text"), str) and node.get("type", "text") == "text":
            found = node["text"]
        for v in node.values():
            found = _last_text(v) or found
    elif isinstance(node, list):
        for v in node:
            found = _last_text(v) or found
    return found


def _gemini(image_b64, text):
    last_err = None
    for model in dict.fromkeys(GEMINI_FALLBACKS):  # de-duplicated, order kept
        body = {"model": model,
                "input": [{"type": "text", "text": SYSTEM + "\n\n" + text},
                          {"type": "image", "data": image_b64, "mime_type": "image/jpeg"}],
                "response_format": {"type": "text", "mime_type": "application/json", "schema": PLAN_SCHEMA}}
        req = urllib.request.Request(
            "https://generativelanguage.googleapis.com/v1beta/interactions", data=json.dumps(body).encode(),
            headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"], "Content-Type": "application/json",
                     "Api-Revision": "2026-05-20"})
        try:
            with urllib.request.urlopen(req, timeout=45) as r:
                data = json.load(r)
            break
        except urllib.error.HTTPError as e:
            last_err = f"Gemini {e.code} ({model}): {e.read().decode(errors='ignore')[:300]}"
            if e.code not in (429, 500, 503):
                raise RuntimeError(last_err) from None
        except (TimeoutError, urllib.error.URLError) as e:  # a hung free-tier model: try the next one
            last_err = f"Gemini timeout ({model}): {e}"
    else:
        raise RuntimeError(last_err + " All fallback models were busy; try again in a minute.")
    out = data.get("output_text") or _last_text(data)
    if not out:
        raise RuntimeError("Gemini returned no text.")
    return json.loads(out)


def _claude(image_b64, text):
    import anthropic
    resp = anthropic.Anthropic().beta.messages.create(
        model="claude-opus-5-5",
        max_tokens=16000,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        system=SYSTEM,
        output_config={"effort": "medium", "format": {"type": "json_schema", "schema": PLAN_SCHEMA}},
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": image_b64}},
            {"type": "text", "text": text},
        ]}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError("The model declined this request.")
    if resp.stop_reason == "max_tokens":
        raise RuntimeError("The answer was cut off; try again.")
    return json.loads(next(b.text for b in resp.content if b.type == "text"))


def analyze(image_b64, symbol="", note=""):
    if not os.getenv("SPACE_ID"):  # local only: lets Claude Code "read my screen"; never keep client screens in the cloud
        with open(FRAME, "wb") as f:
            f.write(base64.b64decode(image_b64))
    text = "Analyse this trading screen and give one trade plan."
    if symbol:
        text += f"\nSymbol: {symbol}\nLive market context (JSON): {json.dumps(market_context(symbol), default=float)}"
    if note:
        text += f"\nUser note: {note}"
    if os.getenv("GEMINI_API_KEY"):
        return _gemini(image_b64, text)
    if os.getenv("ANTHROPIC_API_KEY"):
        return _claude(image_b64, text)
    if symbol:
        return technical_plan(symbol)
    raise ValueError("No AI key is set. Type a symbol for a free plan from live data.")
