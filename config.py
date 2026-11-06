"""Configuration settings for CodeCafe Signals.
Reads from environment variables and local .env file.
"""
import os
from pathlib import Path

# Load .env without extra dependencies
env_path = Path(__file__).resolve().parent / ".env"
if env_path.exists():
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

# LLM
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")

# Database
DB_PATH = os.getenv("DB_PATH", "trades.db")

# Mode: paper | demo | live
TRADING_MODE = os.getenv("TRADING_MODE", "paper").lower()

# Watchlist: Gold, Silver, Crude Oil, S&P 500 (ES)
DEFAULT_SYMBOLS = ["XAUUSD", "XAGUSD", "USOUSD", "SPX500"]
WATCHLIST = [s.strip() for s in os.getenv("YO_SYMBOLS", ",".join(DEFAULT_SYMBOLS)).split(",") if s.strip()]

# Commodity & Index Yahoo ticker fallback mapping
YAHOO_MAPPING = {
    "XAUUSD": "GC=F",
    "XAGUSD": "SI=F",
    "USOUSD": "CL=F",
    "SPX500": "ES=F",
    "US500": "^GSPC",
}

# Risk Management Limits
RISK_PCT = float(os.getenv("RISK_PCT", "1.0"))
MAX_LOTS = float(os.getenv("MAX_LOTS", "0.10"))
MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "3.0"))
MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", "3"))
MAGIC_NUMBER = 770011

