"""Economic Calendar & Macro Event Risk Engine (System 1.D).
Tracks high-impact macro releases (FOMC, CPI, NFP, GDP, Rate Decisions)
using zero-dependency public feeds with local caching.
"""
from datetime import datetime, timezone
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

CACHE_FILE = "calendar_cache.json"
CACHE_TTL = 3600  # 1 hour
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"

HIGH_IMPACT_PATTERNS = {
    "FOMC": r"\b(fomc|fed\s+interest\s+rate|fed\s+rate\s+decision|powell\s+speaks)\b",
    "CPI": r"\b(cpi|consumer\s+price\s+index|inflation\s+rate)\b",
    "NFP": r"\b(non-farm|nfp|payroll|unemployment\s+rate|jobs\s+report)\b",
    "GDP": r"\b(gdp|gross\s+domestic\s+product)\b",
    "RATE_DECISION": r"\b(rate\s+hike|rate\s+cut|interest\s+rate\s+decision|monetary\s+policy)\b",
    "OPEC": r"\b(opec|oil\s+output|crude\s+production|eia\s+crude)\b",
}


def _currency_for_symbol(symbol: str) -> list[str]:
    sym = symbol.upper()
    if sym in ("XAUUSD", "XAGUSD", "USOUSD", "SPX500", "US500", "ES", "WTI"):
        return ["USD"]
    if len(sym) == 6:
        return [sym[:3], sym[3:]]
    return ["USD"]


def fetch_calendar_events(force_refresh: bool = False) -> list[dict]:
    """Fetch calendar events from Google News Economic Calendar RSS."""
    now = time.time()
    if not force_refresh and os.path.exists(CACHE_FILE):
        if now - os.path.getmtime(CACHE_FILE) < CACHE_TTL:
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass

    query = urllib.parse.quote("economic calendar FOMC CPI NFP GDP interest rate")
    url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    events = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            content = resp.read()
        root = ET.fromstring(content)
        for item in root.findall(".//item"):
            title = (item.findtext("title") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            link = (item.findtext("link") or "").strip()

            impact = "LOW"
            matched_event = None
            for ev_name, pattern in HIGH_IMPACT_PATTERNS.items():
                if re.search(pattern, title, re.IGNORECASE):
                    impact = "HIGH"
                    matched_event = ev_name
                    break

            events.append({
                "title": title,
                "event_type": matched_event or "GENERAL_MACRO",
                "impact": impact,
                "date": pub_date,
                "link": link,
            })
    except Exception:
        events = []

    # Cache output
    try:
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(events, f)
    except Exception:
        pass

    return events


def check_event_risk(symbol: str, buffer_hours: int = 12) -> dict:
    """Analyze high-impact calendar risk for a symbol."""
    events = fetch_calendar_events()
    high_impact = [e for e in events if e.get("impact") == "HIGH"]

    is_oil = symbol.upper() in ("USOUSD", "USOIL", "WTI", "CL=F")
    is_gold = symbol.upper() in ("XAUUSD", "GC=F")

    relevant = []
    for e in high_impact:
        ev = e.get("event_type", "")
        if is_oil and ev in ("OPEC", "CPI", "FOMC"):
            relevant.append(e)
        elif is_gold and ev in ("CPI", "FOMC", "RATE_DECISION"):
            relevant.append(e)
        elif ev in ("FOMC", "CPI", "NFP", "RATE_DECISION"):
            relevant.append(e)

    risk_present = len(relevant) > 0
    return {
        "symbol": symbol,
        "is_risk_event_imminent": risk_present,
        "action": "REDUCE_SIZE_OR_WAIT" if risk_present else "TRADE_PERMITTED",
        "high_impact_events_found": len(relevant),
        "top_events": relevant[:3],
        "reason": f"Detected {len(relevant)} high-impact announcements (FOMC/CPI/NFP/OPEC)" if risk_present else "No active macro event blackout",
    }
