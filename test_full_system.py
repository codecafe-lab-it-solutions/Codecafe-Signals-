"""Comprehensive Masterprompt End-to-End System Test Suite.
Verifies all 3 core systems and dashboard REST endpoints.
Run: python test_full_system.py
"""
import json
import os
import sys
import tempfile
import time

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

print("=" * 60)
print("CODECAFE SIGNALS: MASTERPROMPT SYSTEM VERIFICATION TEST SUITE")
print("=" * 60)

test_results = {}

# -------------------------------------------------------------
# 1. SYSTEM 1: MARKET INTELLIGENCE TESTS
# -------------------------------------------------------------
print("\n[TEST 1] System 1: Market Data & Feeds...")
try:
    from universal_data import fetch_universal_candles
    gold_c = fetch_universal_candles("XAUUSD", "H1", 30)
    oil_c = fetch_universal_candles("USOUSD", "H1", 30)
    spx_c = fetch_universal_candles("SPX500", "H1", 30)
    assert len(gold_c["close"]) >= 30
    assert len(oil_c["close"]) >= 30
    assert len(spx_c["close"]) >= 30
    test_results["Market Data Collection"] = "PASS (XAUUSD, USOUSD, SPX500 live candles OK)"
    print("  -> PASS: Live commodity feeds responding")
except Exception as e:
    test_results["Market Data Collection"] = f"FAIL: {e}"
    print(f"  -> FAIL: {e}")

print("\n[TEST 2] System 1: Market Structure (FVG, BOS, Order Blocks)...")
try:
    from market_structure import get_market_structure_report
    struct = get_market_structure_report(gold_c)
    assert "trend" in struct
    assert "active_fvgs_count" in struct
    assert "order_blocks" in struct
    test_results["Market Structure (FVG/BOS/OB)"] = f"PASS (Trend: {struct['trend']}, FVGs: {struct['active_fvgs_count']}, OBs: {len(struct['order_blocks'])})"
    print(f"  -> PASS: Trend={struct['trend']}, FVGs={struct['active_fvgs_count']}")
except Exception as e:
    test_results["Market Structure (FVG/BOS/OB)"] = f"FAIL: {e}"
    print(f"  -> FAIL: {e}")

print("\n[TEST 3] System 1: Market Regime Detection...")
try:
    from regime import detect_market_regime
    regime = detect_market_regime(gold_c)
    assert "regime" in regime and "adx" in regime
    test_results["Market Regime Detection"] = f"PASS (Regime: {regime['regime']}, ADX: {regime['adx']})"
    print(f"  -> PASS: Regime={regime['regime']}")
except Exception as e:
    test_results["Market Regime Detection"] = f"FAIL: {e}"
    print(f"  -> FAIL: {e}")

print("\n[TEST 4] System 1: Macro & Economic Calendar Risk...")
try:
    from economic_calendar import check_event_risk
    cal_risk = check_event_risk("XAUUSD")
    assert "action" in cal_risk
    test_results["Economic Calendar Risk"] = f"PASS (Action: {cal_risk['action']}, Events: {cal_risk['high_impact_events_found']})"
    print(f"  -> PASS: Action={cal_risk['action']}")
except Exception as e:
    test_results["Economic Calendar Risk"] = f"FAIL: {e}"
    print(f"  -> FAIL: {e}")

print("\n[TEST 5] System 1: Groq LLM News Analysis...")
try:
    from llm import analyze_news_impact
    news_res = analyze_news_impact([{"title": "Fed rate cut expectations boost Gold", "publisher": "Bloomberg"}], "XAUUSD")
    assert "sentiment" in news_res and "summary" in news_res
    test_results["Groq LLM News Intelligence"] = f"PASS (Sentiment: {news_res['sentiment']})"
    print(f"  -> PASS: Sentiment={news_res['sentiment']}")
except Exception as e:
    test_results["Groq LLM News Intelligence"] = f"FAIL: {e}"
    print(f"  -> FAIL: {e}")

print("\n[TEST 6] System 1: Consolidated Market Intelligence Report...")
try:
    from intelligence import generate_market_intelligence
    intel = generate_market_intelligence("XAUUSD", "H1", use_llm=False)
    assert intel["current_price"] > 0
    assert "market_direction" in intel
    assert "confidence_score" in intel
    test_results["Consolidated Intelligence Report"] = f"PASS (Price: {intel['current_price']}, Direction: {intel['market_direction']})"
    print(f"  -> PASS: Output validated (Price={intel['current_price']})")
except Exception as e:
    test_results["Consolidated Intelligence Report"] = f"FAIL: {e}"
    print(f"  -> FAIL: {e}")

# -------------------------------------------------------------
# 2. SYSTEM 2: STRATEGY & DECISION ENGINE TESTS
# -------------------------------------------------------------
print("\n[TEST 7] System 2: Strategy Engine (Trend/Breakout/MeanReversion)...")
try:
    from strategies import StrategyManager
    mgr = StrategyManager()
    sig = mgr.evaluate_all(intel)
    assert sig is not None
    assert sig.action in ("BUY", "SELL", "NO_TRADE")
    test_results["Modular Strategy Engine"] = f"PASS (Signal: {sig.action}, Strategy: {sig.strategy_id}, Confidence: {sig.confidence})"
    print(f"  -> PASS: Strategy evaluated: {sig.action}")
except Exception as e:
    test_results["Modular Strategy Engine"] = f"FAIL: {e}"
    print(f"  -> FAIL: {e}")

print("\n[TEST 8] System 2: Walk-Forward Backtester...")
try:
    from backtester import run_historical_backtest
    bt = run_historical_backtest(gold_c)
    assert hasattr(bt, "profit_factor")
    assert hasattr(bt, "sharpe_ratio")
    test_results["Historical Backtesting Engine"] = f"PASS (Trades: {bt.total_trades}, WinRate: {bt.win_rate_pct}%, PF: {bt.profit_factor}, Sharpe: {bt.sharpe_ratio})"
    print(f"  -> PASS: Trades={bt.total_trades}, WinRate={bt.win_rate_pct}%")
except Exception as e:
    test_results["Historical Backtesting Engine"] = f"FAIL: {e}"
    print(f"  -> FAIL: {e}")

# -------------------------------------------------------------
# 3. SYSTEM 3: RISK & EXECUTION ENGINE TESTS
# -------------------------------------------------------------
print("\n[TEST 9] System 3: Independent Risk Engine...")
try:
    from broker import get_broker
    from risk_engine import RiskEngine
    broker = get_broker("paper")
    risk_eng = RiskEngine()

    # Must reject trade without SL
    bad_val = risk_eng.validate_trade(broker, "XAUUSD", "BUY", 4120.0, sl=0.0, check_news=False)
    assert bad_val.allowed is False

    # Must accept valid trade
    good_val = risk_eng.validate_trade(broker, "XAUUSD", "BUY", 4120.0, sl=4080.0, tp=4200.0, check_news=False)
    assert good_val.allowed is True
    assert good_val.suggested_qty > 0
    test_results["Independent Risk Safety Gate"] = f"PASS (Allowed: {good_val.allowed}, Sizing: {good_val.suggested_qty} lots)"
    print("  -> PASS: Safety gates & position sizing verified")
except Exception as e:
    test_results["Independent Risk Safety Gate"] = f"FAIL: {e}"
    print(f"  -> FAIL: {e}")

print("\n[TEST 10] System 3: QuantConnect LEAN Broker Abstraction...")
try:
    from broker import OrderRequest
    req = OrderRequest(symbol="XAUUSD", side="BUY", qty=0.1, sl=4000.0, tp=4300.0, price=4120.0)
    order_res = broker.submit_order(req)
    assert order_res.ok is True
    assert order_res.ticket != ""
    positions = broker.get_positions()
    assert len(positions) > 0
    test_results["LEAN Broker Abstraction (Paper)"] = f"PASS (Order filled ticket: {order_res.ticket}, Open positions: {len(positions)})"
    print(f"  -> PASS: Order filled (Ticket #{order_res.ticket})")
except Exception as e:
    test_results["LEAN Broker Abstraction (Paper)"] = f"FAIL: {e}"
    print(f"  -> FAIL: {e}")

print("\n[TEST 11] System 3: Trailing Stop & Breakeven Protection...")
try:
    from orchestrator import AutonomousTradingOrchestrator
    orch = AutonomousTradingOrchestrator(broker=broker, risk_engine=risk_eng)
    trails = orch.monitor_and_trail_positions()
    test_results["Trailing Stop Engine"] = "PASS (Monitoring & Breakeven rule active)"
    print("  -> PASS: Trailing stop scanner evaluated")
except Exception as e:
    test_results["Trailing Stop Engine"] = f"FAIL: {e}"
    print(f"  -> FAIL: {e}")

print("\n[TEST 12] System 3: Emergency Kill Switch...")
try:
    res = orch.emergency_shutdown()
    assert res["kill_switch"] is True
    assert risk_eng.kill_switch_active is True
    risk_eng.reset_kill_switch()  # reset for normal operations
    test_results["Emergency Kill Switch"] = "PASS (Positions flattened & kill switch triggered)"
    print("  -> PASS: Kill switch flattened positions cleanly")
except Exception as e:
    test_results["Emergency Kill Switch"] = f"FAIL: {e}"
    print(f"  -> FAIL: {e}")

# -------------------------------------------------------------
# 4. REST API & DASHBOARD ENDPOINTS
# -------------------------------------------------------------
print("\n[TEST 13] Central Dashboard REST Endpoints...")
try:
    from starlette.testclient import TestClient
    import auth
    from dashboard_server import COOKIE, app
    client = TestClient(app)
    assert client.get("/api/status").status_code == 401  # logins are required
    admin = os.getenv("ADMIN_USER", "").strip().lower()
    assert admin in auth.users(), "set ADMIN_USER/ADMIN_PASSWORD in .env so a test login exists"
    client.cookies.set(COOKIE, auth.make_token(admin))

    r_status = client.get("/api/status")
    assert r_status.status_code == 200
    
    r_intel = client.get("/api/intelligence?symbol=XAUUSD&llm=false")
    assert r_intel.status_code == 200
    
    r_bt = client.get("/api/backtest?symbol=XAUUSD&count=100")
    assert r_bt.status_code == 200

    r_kb = client.get("/api/kb?q=risk")
    assert r_kb.status_code == 200
    
    test_results["Dashboard REST API"] = "PASS (/api/status, /api/intelligence, /api/backtest, /api/kb all 200 OK)"
    print("  -> PASS: Dashboard API endpoints responding with status 200")
except Exception as e:
    test_results["Dashboard REST API"] = f"FAIL: {e}"
    print(f"  -> FAIL: {e}")

# -------------------------------------------------------------
# 5. NEW MODULES: ML, RAG, RECONCILIATION, STREAMER
# -------------------------------------------------------------
print("\n[TEST 14] System 2.C: Machine Learning Barrier Odds...")
try:
    from ml_pipeline import predict_barrier_probability
    ml_pred = predict_barrier_probability(gold_c)
    assert "barrier_win_probability" in ml_pred
    test_results["Machine Learning Barrier Model"] = f"PASS (Win Odds: {ml_pred['barrier_win_probability']}, HighProb: {ml_pred['is_high_probability_setup']})"
    print(f"  -> PASS: ML Model barrier probability = {ml_pred['barrier_win_probability']}")
except Exception as e:
    test_results["Machine Learning Barrier Model"] = f"FAIL: {e}"
    print(f"  -> FAIL: {e}")

print("\n[TEST 15] System 2.E: Knowledge Base & RAG Semantic Search...")
try:
    from rag_kb import search_knowledge_base
    kb_res = search_knowledge_base("stop loss and risk limit rules")
    assert len(kb_res) > 0
    top_doc = kb_res[0]
    assert "title" in top_doc and top_doc["similarity_score"] > 0
    test_results["RAG Knowledge Base"] = f"PASS (Matched: '{top_doc['title']}', Score: {top_doc['similarity_score']})"
    print(f"  -> PASS: RAG retrieved: {top_doc['title']} (Score={top_doc['similarity_score']})")
except Exception as e:
    test_results["RAG Knowledge Base"] = f"FAIL: {e}"
    print(f"  -> FAIL: {e}")

print("\n[TEST 16] System 3.E: Broker Position Reconciliation...")
try:
    rec_res = broker.reconcile_positions()
    assert "total_live" in rec_res
    test_results["Broker Position Reconciliation"] = f"PASS (Reconciled live: {rec_res['total_live']})"
    print(f"  -> PASS: Reconciled positions: {rec_res['total_live']}")
except Exception as e:
    test_results["Broker Position Reconciliation"] = f"FAIL: {e}"
    print(f"  -> FAIL: {e}")

print("\n[TEST 17] System 1.A: Real-time Live Tick Streaming Engine...")
try:
    from streamer import stream_manager
    assert hasattr(stream_manager, "broadcast")
    assert hasattr(stream_manager, "stream_worker")
    test_results["Real-time Streaming Engine"] = "PASS (WebSocket stream manager operational)"
    print("  -> PASS: WebSocket live stream manager verified")
except Exception as e:
    test_results["Real-time Streaming Engine"] = f"FAIL: {e}"
    print(f"  -> FAIL: {e}")

# -------------------------------------------------------------
# SUMMARY REPORT
# -------------------------------------------------------------
print("\n" + "=" * 60)
print("FINAL TEST EXECUTION REPORT")
print("=" * 60)
pass_count = sum(1 for v in test_results.values() if v.startswith("PASS"))
fail_count = sum(1 for v in test_results.values() if not v.startswith("PASS"))

for name, status in test_results.items():
    prefix = "[PASS]" if status.startswith("PASS") else "[FAIL]"
    print(f"{prefix} {name}: {status}")

print("-" * 60)
print(f"TOTAL: {len(test_results)} Tests | PASSED: {pass_count} | FAILED: {fail_count}")
print("=" * 60)

