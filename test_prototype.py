"""Verification Suite for CodeCafe Signals Prototype (System 1, System 2, System 3).
Run: uv run python test_prototype.py
"""
import os
import tempfile
import time

from broker import OrderRequest, get_broker
from config import WATCHLIST
import db
from llm import analyze_news_impact
from universal_data import fetch_universal_candles

# 1. Config & Watchlist Verification
assert "XAUUSD" in WATCHLIST, WATCHLIST
assert "XAGUSD" in WATCHLIST, WATCHLIST
assert "USOUSD" in WATCHLIST, WATCHLIST
assert "SPX500" in WATCHLIST, WATCHLIST
print("[OK] Watchlist contains Gold, Silver, Crude Oil, S&P 500")

# 2. Local Database & Audit Trail
temp_db = os.path.join(tempfile.mkdtemp(), "test_trades.db")
db.init_db(temp_db)

sig_id = db.log_signal("XAUUSD", "H1", "EMA_CROSS", "BUY", 4120.0, 4080.0, 4200.0, confidence=0.85, path=temp_db)
assert sig_id > 0

trade_id = db.record_trade("T101", "paper", "XAUUSD", "BUY", 0.1, 4120.0, 4080.0, 4200.0, path=temp_db)
assert trade_id > 0
open_trades = db.get_open_trades("paper", path=temp_db)
assert len(open_trades) == 1
assert open_trades[0]["ticket"] == "T101"

closed = db.update_trade_close("T101", exit_price=4150.0, pnl=3.0, notes="Target reached", path=temp_db)
assert closed is True
assert db.get_daily_realized_pnl(path=temp_db) == 3.0

db.log_audit("TEST_EVENT", {"status": "success"}, path=temp_db)
print("[OK] SQLite Local Database & Audit Log operational")

# 3. LEAN-style Broker Abstraction
broker = get_broker("paper")
acct = broker.get_account()
assert acct.balance > 0
assert acct.is_demo is True

# Stop loss is strictly mandatory
bad_order = OrderRequest(symbol="XAUUSD", side="BUY", qty=0.1, sl=0.0)
bad_res = broker.submit_order(bad_order)
assert bad_res.ok is False
assert "SL" in str(bad_res.comment)

# Valid order execution
valid_order = OrderRequest(symbol="XAUUSD", side="BUY", qty=0.1, sl=4000.0, tp=4300.0, price=4120.0)
valid_res = broker.submit_order(valid_order)
assert valid_res.ok is True
assert valid_res.ticket != ""
print("[OK] QuantConnect LEAN Broker Abstraction (PaperBroker) operational")

# 4. Market Data for Commodities
gold_candles = fetch_universal_candles("XAUUSD", "H1", 5)
assert len(gold_candles["close"]) > 0
assert gold_candles["close"][-1] > 1000.0
print(f"[OK] Live Market Data: Gold price = {gold_candles['close'][-1]:.2f}")

# 5. Groq LLM Intelligence Layer
impact = analyze_news_impact([{"title": "OPEC considers oil production cuts", "publisher": "Reuters"}], "USOUSD")
assert "sentiment" in impact
assert "summary" in impact
print(f"[OK] Groq LLM Intelligence: Crude Oil sentiment = {impact['sentiment']} ({impact['summary'][:60]}...)")

print("\nAll Prototype Verification Tests Passed Successfully!")

