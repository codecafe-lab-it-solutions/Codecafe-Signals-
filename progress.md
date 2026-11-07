# CodeCafe Signals & CodeCafe Omni — Project Progress & Quickstart Guide

This document summarizes the entire codebase, architecture, verified live test results, and instructions so that any developer or AI assistant can immediately understand and build upon this project without reading the whole repository.

---

## 1. What Is This Project?

**CodeCafe Signals** is an autonomous multi-asset algorithmic trading assistant, web platform, and Model Context Protocol (MCP) server suite. It connects to live market feeds, analyzes price action and news sentiment, calculates mathematical risk-controlled lot sizing, and executes trades autonomously or via user confirmation on **demo/paper accounts only**.

### Supported Execution Platforms
1. **Multi-Tenant Paper Broker**: Native paper trading with real live prices across Forex, Commodities, Indices, US/Indian stocks, and Crypto (`paper.py`, `broker.py`).
2. **Forex & Commodities**: MetaTrader 5 (MT5) via official Python API (`MetaTrader5`).
3. **Cryptocurrency Spot**: Bybit Demo Trading / Testnet via standard-library V5 REST client (`bybit.py`).
4. **Interactive Multimodal Screen Coach**: Reads real-time broker charts via browser screen share and generates verified plans (`coach.py` via Gemini 3.5 / Claude / Local fallbacks).
5. **Desktop Screen UI Fallback**: Native Windows `ctypes` UI targeting for platforms without direct APIs (`click_agent.py`).

---

## 2. Codebase Map & Responsibilities

| File | Primary Job | Key Functions / Tools |
| :--- | :--- | :--- |
| [`dashboard_server.py`](file:///o:/Projects/CodeCafe%20Signals/dashboard_server.py) | **Central Web Platform & API Server** | Starlette ASGI server with WebSockets, live tick feeds, JWT/cookie auth, rate limiting, and security headers. |
| [`web/index.html`](file:///o:/Projects/CodeCafe%20Signals/web/index.html) | **Single-Page Dashboard UI** | Zero-dependency high-performance UI: active symbol tabs, TradingView-style charts, live scan alerts, positions, and history. |
| [`auth.py`](file:///o:/Projects/CodeCafe%20Signals/auth.py) | **Multi-Tenant Authentication** | Scrypt password hashing, HMAC signed session cookies, instant session revocation via `iat` checks, role-based access (`admin`, `client`, `demo`). |
| [`paper.py`](file:///o:/Projects/CodeCafe%20Signals/paper.py) | **Isolated Paper Execution Engine** | Per-user balance and position tracking, multi-tenant state persistence, automated SL/TP hit detection. |
| [`broker.py`](file:///o:/Projects/CodeCafe%20Signals/broker.py) | **QuantConnect LEAN Broker Abstraction** | Unified interface (`PaperBroker`, `MT5Broker`, `BybitBroker`) with user-isolated ticket namespacing. |
| [`risk_engine.py`](file:///o:/Projects/CodeCafe%20Signals/risk_engine.py) | **Independent Mathematical Risk Gate** | Enforces 1% risk rule, maximum daily drawdown, max open position cap, minimum 1.50 R:R, and per-user emergency kill switch. |
| [`orchestrator.py`](file:///o:/Projects/CodeCafe%20Signals/orchestrator.py) | **Autonomous Trading Pipeline** | End-to-end integration: System 1 (Intel) $\to$ System 2 (Strategy) $\to$ System 3 (Risk) $\to$ Execution. |
| [`coach.py`](file:///o:/Projects/CodeCafe%20Signals/coach.py) | **Multimodal Screen AI Coach** | Inspects trading screens via Gemini 3.5 Flash / Claude Opus 5.5 / Local technical plan fallbacks with schema enforcement. |
| [`ml_pipeline.py`](file:///o:/Projects/CodeCafe%20Signals/ml_pipeline.py) | **Triple Barrier Odds Classifier** | HistGradientBoosting barrier touch probability predictor without lookahead bias. |
| [`rag_kb.py`](file:///o:/Projects/CodeCafe%20Signals/rag_kb.py) | **Trading Rules Knowledge Base & RAG** | SQLite-backed strategy documentation retrieval using TF-IDF vector search and cosine similarity. |
| [`universal_data.py`](file:///o:/Projects/CodeCafe%20Signals/universal_data.py) | **Universal Market Data & Charting** | Scrapes candles from Yahoo Finance, Bybit, or MT5 with zero extra dependencies. Generates ASCII & SVG candle charts. |
| [`chart_vision.py`](file:///o:/Projects/CodeCafe%20Signals/chart_vision.py) | **Technical Price Action & S/R Analyzer** | Identifies Support/Resistance pivot clusters, candlestick patterns (Hammer, Pin Bar, Engulfing, Doji), and generates SL/TP levels. |
| [`news_scraper.py`](file:///o:/Projects/CodeCafe%20Signals/news_scraper.py) | **Real-Time News & Sentiment Engine** | Scrapes RSS headlines with zero API keys. Scores net sentiment and flags high-impact macro events (FOMC, CPI, NFP). |
| [`economic_calendar.py`](file:///o:/Projects/CodeCafe%20Signals/economic_calendar.py) | **Macro Event Risk Engine** | High-impact economic calendar monitoring with local caching and trade blackout warnings. |
| [`store.py`](file:///o:/Projects/CodeCafe%20Signals/store.py) | **Key-Value Persistence Layer** | Transparently toggles between cloud PostgreSQL (Supabase) and local atomic JSON files. |
| [`db.py`](file:///o:/Projects/CodeCafe%20Signals/db.py) | **Local SQLite Database & Audit Trail** | Thread-safe logging for signals, orders, market intelligence, and audit trails. |
| [`render.yaml`](file:///o:/Projects/CodeCafe%20Signals/render.yaml) & [`Dockerfile`](file:///o:/Projects/CodeCafe%20Signals/Dockerfile) | **Production Cloud Blueprint** | Docker runtime running as non-root user `app` with auto-deploy on Render. |

---

## 3. Verified Live Trading Proof of Concept (Session: 2026-11-04)

The autonomous trader was tested live on a **MetaTrader 5 MetaQuotes-Demo** account:
- **Starting Balance**: `$100,000.00 USD`
- **Ending Balance**: **`$100,138.07 USD`**
- **Net Realized Profit**: **`+$138.07 USD`**
- **Win Rate**: **75%** (3 Wins, 1 Loss)
- **Active Open Positions After Stop**: 0 (Flattened cleanly)

### Trade Breakdown
1. **`XAUUSD` (Gold)**: BUY 0.1 lots @ 4033.43 $\to$ Closed @ 4046.66 $\to$ **+$132.30 Net Profit** (Auto-banked at $\ge \$100$ rule).
2. **`AUDUSD`**: BUY 0.1 lots @ 0.69998 $\to$ Closed @ 0.70083 $\to$ **+$8.50 Net Profit**.
3. **`EURUSD`**: BUY 0.1 lots @ 1.12381 $\to$ Closed @ 1.12426 $\to$ **+$4.50 Net Profit**.
4. **`USDCAD`**: SELL 0.1 lots @ 1.39547 $\to$ Closed @ 1.39648 $\to$ **-$7.23 Loss**.

---

## 4. Hard Safety Rules, Security Controls & Risk Caps

All automated and manual executions strictly adhere to these immutable rules:
- **Enforced Execution Gates**: Manual trades via `/api/execute` must pass `risk.validate_trade()` (SL mandatory, RR $\ge 1.50$, directional sanity, drawdown limit).
- **Multi-Tenant Isolation**: Paper tickets are namespaced per user (`username-id`) to eliminate SQLite collision and cross-user PnL leaks.
- **Session Revocation**: Password changes immediately invalidate all existing session cookies via token `iat` vs `changed` timestamp comparison.
- **Brute-Force & Abuse Protection**: Login endpoints enforce in-memory IP rate limiting (5 attempts/min); screen coach endpoints cap input payloads at 10MB.
- **HTTP Security Headers**: Strict CSP, `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, and `Referrer-Policy: strict-origin-when-cross-origin`.
- **Per-User Kill Switch**: Engaging the emergency stop flattens positions and blocks new orders strictly for the requesting user, leaving other users unaffected.
- **Demo-Only Enforcement**: Real-money trading is blocked in code (`DEMO_ONLY = True` on MT5; Bybit routes strictly to demo/testnet).
- **Position Sizing**: 1% risk per trade. MT5 lots capped at `0.10 lots` max; Bybit capped at `1000 USDT` notional.
- **Daily Drawdown Circuit Breaker**: New trades halt for the day if realized daily loss reaches **3.0%**.

---

## 5. Automated Test Suites & How to Run

The repository contains 6 comprehensive automated test suites covering unit math, security, architecture, and full-system workflows:

### 1. Run Complete Test Suite
```powershell
uv run python test_security_and_fixes.py
uv run python test_core.py
uv run python test_auth.py
uv run python test_omni.py
uv run python test_prototype.py
uv run python test_full_system.py
```

### Suite Breakdown
- [`test_security_and_fixes.py`](file:///o:/Projects/CodeCafe%20Signals/test_security_and_fixes.py): TDD suite testing security headers, session revocation, login rate limiting, `/api/execute` risk validation, and multi-tenant ticket isolation.
- [`test_core.py`](file:///o:/Projects/CodeCafe%20Signals/test_core.py): Technical indicators (RSI boundary checks, ADX 0–100 scale normalization, ATR).
- [`test_auth.py`](file:///o:/Projects/CodeCafe%20Signals/test_auth.py): Scrypt password hashing, HMAC cookies, expired/tampered token rejection.
- [`test_omni.py`](file:///o:/Projects/CodeCafe%20Signals/test_omni.py): Candlestick patterns, pivot clustering, SVG/ASCII charting, market structure.
- [`test_prototype.py`](file:///o:/Projects/CodeCafe%20Signals/test_prototype.py): SQLite DB audit trail, LEAN PaperBroker, live data feeds, Groq LLM news.
- [`test_full_system.py`](file:///o:/Projects/CodeCafe%20Signals/test_full_system.py): Masterprompt 17-point end-to-end integration and REST endpoint validation.

---

## 6. How to Launch Locally or Deploy

### Run Desktop Dashboard Locally
```powershell
# Double click Run_CodeCafe_Signals.bat, or run from shell:
uv run python dashboard_server.py
```
Open `http://127.0.0.1:8765` in your browser.

### Cloud Deploy (Render + Supabase)
1. Push repository to GitHub.
2. In Render, select **New $\to$ Blueprint** and select this repo (`render.yaml`).
3. Set environment secrets: `DATABASE_URL`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `ADMIN_USER`, `ADMIN_PASSWORD`, `DEMO_USER`, `DEMO_PASSWORD`.
4. Render builds the Docker container and deploys with auto-healing `/healthz` healthchecks.
