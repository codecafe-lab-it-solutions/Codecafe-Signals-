"""LLM Intelligence Layer for CodeCafe Signals.
Uses free Groq API endpoint with fallback. Zero heavy dependencies.
"""
import json
import urllib.error
import urllib.request
from typing import Any

from config import GROQ_API_KEY, GROQ_MODEL

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


def query_llm(prompt: str, system: str = "You are a senior quantitative trading analyst.", model: str = GROQ_MODEL) -> str:
    """Send chat completion request to Groq API."""
    if not GROQ_API_KEY:
        return "LLM unavailable: GROQ_API_KEY missing."

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
        "User-Agent": "CodeCafeSignals/1.0 (Windows NT 10.0; Win64; x64)",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "max_tokens": 800,
    }

    try:
        req = urllib.request.Request(
            GROQ_ENDPOINT,
            headers=headers,
            data=json.dumps(payload).encode("utf-8"),
        )
        with urllib.request.urlopen(req, timeout=15) as res:
            data = json.loads(res.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return f"Groq HTTP Error {e.code}: {err_msg}"
    except Exception as e:
        return f"Groq Error: {str(e)}"


def analyze_news_impact(headlines: list[dict], symbol: str) -> dict[str, Any]:
    """Summarize financial news impact on a given symbol."""
    if not headlines:
        return {"sentiment": "NEUTRAL", "impact": "LOW", "summary": "No recent headlines found."}

    news_text = "\n".join([f"- {h.get('title', '')} ({h.get('publisher', 'News')})" for h in headlines[:8]])
    prompt = f"""Analyze these breaking news headlines for symbol {symbol}:
{news_text}

Respond in strict JSON with keys:
"sentiment": "BULLISH" | "BEARISH" | "NEUTRAL",
"impact": "HIGH" | "MEDIUM" | "LOW",
"summary": "1-2 sentence concise explanation"
JSON:"""

    raw = query_llm(prompt, system="You analyze financial market news impact. Output JSON only.")
    try:
        # Extract JSON block if wrapped in markdown
        cleaned = raw
        if "```json" in cleaned:
            cleaned = cleaned.split("```json")[1].split("```")[0].strip()
        elif "```" in cleaned:
            cleaned = cleaned.split("```")[1].split("```")[0].strip()
        return json.loads(cleaned)
    except Exception:
        return {"sentiment": "NEUTRAL", "impact": "MEDIUM", "summary": raw[:200]}

