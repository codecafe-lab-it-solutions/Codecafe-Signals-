"""Real-time Financial News & Macro Sentiment Scraper (Stdlib only).

Reads public RSS feeds (Yahoo Finance, Google News) with zero API keys.
Extracts:
1. Breaking headlines & publication times
2. Macro / High-impact volatility flags (FOMC, CPI, NFP, Rates, SEC)
3. Lexicon-based sentiment scoring (+1 Bullish, -1 Bearish, 0 Neutral)
"""
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

BULLISH_WORDS = {
    "surge", "surges", "surged", "rally", "rallies", "rallied", "jump", "jumps", "jumped",
    "gain", "gains", "soar", "soars", "beat", "beats", "beaten", "record", "growth",
    "bullish", "upgrade", "upgrades", "breakout", "strong", "outperform", "dividend",
}

BEARISH_WORDS = {
    "drop", "drops", "dropped", "fall", "falls", "fallen", "plunge", "plunges", "plunged",
    "loss", "losses", "miss", "misses", "slump", "slumps", "bearish", "downgrade", "downgrades",
    "crash", "crashes", "weak", "probe", "lawsuit", "sanction", "default", "cut", "cuts",
}

HIGH_IMPACT_EVENTS = {
    "fomc": "Federal Reserve Rate Decision / Meeting",
    "cpi": "Consumer Price Index (Inflation)",
    "nfp": "Non-Farm Payrolls (Jobs report)",
    "interest rate": "Central Bank Interest Rate Decision",
    "powell": "Fed Chair Jerome Powell Speech",
    "sec": "Securities and Exchange Commission Action",
    "tariff": "Trade Tariff / Geopolitical Trade News",
    "earnings": "Corporate Earnings Release",
}


def _fetch_rss(url: str, timeout: int = 10) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read()
        root = ET.fromstring(content)
        items = []
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            desc = re.sub(r"<[^>]+>", "", item.findtext("description") or "").strip()
            if title:
                items.append({"title": title, "link": link, "published": pub_date, "summary": desc})
        return items
    except Exception as e:
        return []


def fetch_symbol_news(symbol: str, limit: int = 8) -> list[dict]:
    """Fetch recent headlines for a stock, crypto or forex symbol."""
    clean_sym = symbol.replace("=X", "").replace("-USD", "").replace("USDT", "")
    url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={urllib.parse.quote(clean_sym)}&region=US&lang=en-US"
    items = _fetch_rss(url)
    if not items:
        # Fallback to Google News search
        q = f"{clean_sym} stock news" if len(clean_sym) <= 5 else f"{clean_sym} market news"
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=en-US&gl=US&ceid=US:en"
        items = _fetch_rss(url)
    return items[:limit]


def fetch_macro_news(limit: int = 8) -> list[dict]:
    """Fetch global macro and market-moving headlines."""
    url = "https://news.google.com/rss/search?q=forex+economy+OR+fed+rates+OR+crypto+market&hl=en-US&gl=US&ceid=US:en"
    return _fetch_rss(url)[:limit]


def analyze_news_sentiment(items: list[dict]) -> dict:
    """Score sentiment and detect volatility flags across news articles."""
    if not items:
        return {"sentiment": "NEUTRAL", "score": 0.0, "bull_count": 0, "bear_count": 0, "risk_flags": [], "articles": []}

    bull_hits, bear_hits = 0, 0
    flags = set()
    scored_articles = []

    for item in items:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        words = re.findall(r"\b[a-z]+\b", text)

        b_count = sum(1 for w in words if w in BULLISH_WORDS)
        be_count = sum(1 for w in words if w in BEARISH_WORDS)
        bull_hits += b_count
        bear_hits += be_count

        article_sentiment = "BULLISH" if b_count > be_count else "BEARISH" if be_count > b_count else "NEUTRAL"

        # Check macro events
        for trigger, desc in HIGH_IMPACT_EVENTS.items():
            if trigger in text:
                flags.add(desc)

        scored_articles.append({
            "title": item.get("title"),
            "published": item.get("published"),
            "sentiment": article_sentiment,
            "link": item.get("link"),
        })

    total = bull_hits + bear_hits
    score = round((bull_hits - bear_hits) / (total or 1), 2)
    overall = "BULLISH" if score > 0.2 else "BEARISH" if score < -0.2 else "NEUTRAL"

    return {
        "overall_sentiment": overall,
        "sentiment_score": score,
        "bullish_signals": bull_hits,
        "bearish_signals": bear_hits,
        "high_impact_flags": list(flags),
        "articles": scored_articles,
    }


def get_market_news_brief(symbol: str | None = None) -> dict:
    """One-stop helper to get news + sentiment report."""
    articles = fetch_symbol_news(symbol) if symbol else fetch_macro_news()
    analysis = analyze_news_sentiment(articles)
    analysis["query"] = symbol or "Global Macro"
    return analysis

