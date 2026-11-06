# CodeCafe Signals & CodeCafe Omni — Project Progress & Quickstart Guide

This document summarizes the entire codebase, architecture, verified live test results, and instructions so that any developer or AI assistant can immediately understand and build upon this project without reading the whole repository.

---

## 1. What Is This Project?

**CodeCafe Signals** is a multi-asset algorithmic trading assistant and Model Context Protocol (MCP) server suite. It connects to live market feeds, analyzes price action and news sentiment, calculates risk-controlled lot sizing, and executes trades autonomously or via user confirmation on **demo/paper accounts only**.

### Supported Execution Platforms
1. **Forex & Commodities**: MetaTrader 5 (MT5) via official Python API (`MetaTrader5`).
2. **Cryptocurrency Spot**: Bybit Demo Trading / Testnet via standard-library V5 REST client (`bybit.py`).
3. **US Equities / Stocks**: Paper broker integration via Alpaca & Jake Schincariol's `day-trader-skill` toolkit.
4. **Desktop Screen UI Fallback**: Native Windows `ctypes` UI targeting for platforms without direct APIs.

---

## 2. Codebase Map & Responsibilities

| File | Primary Job | Key Functions / Tools |
| :--- | :--- | :--- |
| [`auto_trader.py`](file:///o:/Projects/CodeCafe%20Signals/auto_trader.py) | **Autonomous Trading Loop Daemon** | `run_single_cycle()`, `monitor_open_positions()`, `scan_for_opportunities()`. Automatically manages positions, trails SL to breakeven, takes profit at $\ge \$100$, and logs lessons. Run with `--loop`. |
| [`omni_server.py`](file:///o:/Projects/CodeCafe%20Signals/omni_server.py) | **Unified MCP Server (`yo-omni`)** | Tools: `omni_scrape_data`, `omni_chart`, `omni_analyze_chart`, `omni_news`, `omni_daytrader`, `omni_plan_trade`, `omni_execute_trade`. |
| [`universal_data.py`](file:///o:/Projects/CodeCafe%20Signals/universal_data.py) | **Universal Market Data & Charting** | Scrapes candles from Yahoo Finance, Bybit, or MT5 with zero extra dependencies. Generates terminal ASCII charts and standalone SVG candlestick files. |
| [`chart_vision.py`](file:///o:/Projects/CodeCafe%20Signals/chart_vision.py) | **Technical Price Action & S/R Analyzer** | Identifies Support/Resistance pivot clusters, candlestick patterns (Hammer, Pin Bar, Engulfing, Doji), and generates exact SL/TP levels. Formats vision prompts for multimodal LLMs. |
| [`news_scraper.py`](file:///o:/Projects/CodeCafe%20Signals/news_scraper.py) | **Real-Time News & Sentiment Engine** | Scrapes RSS headlines (Yahoo + Google News) with zero API keys. Scores net sentiment and flags high-impact macro events (FOMC, CPI, NFP, SEC). |
| [`executor.py`](file:///o:/Projects/CodeCafe%20Signals/executor.py) | **Universal Hybrid Trade Executor** | Routes orders to MT5, Bybit, Paper broker, or Windows UI focus. Enforces strict safety gates (`confirm=True`, mandatory SL). |
| [`signals.py`](file:///o:/Projects/CodeCafe%20Signals/signals.py) | **Strategy v2 Math & Backtester** | Offline indicator formulas (EMA, RSI, ATR), strategy logic, bar-by-bar backtester with spreads/costs, and lot size calculations. |
| [`server.py`](file:///o:/Projects/CodeCafe%20Signals/server.py) | **MT5 Forex MCP Server (`yo-signals`)** | Exposes tools: `account`, `price`, `candles`, `scan`, `backtest`, `positions`, `place_order`, `close_position`. |
| [`crypto_server.py`](file:///o:/Projects/CodeCafe%20Signals/crypto_server.py) | **Bybit Crypto MCP Server (`yo-crypto`)** | Exposes tools for Bybit spot demo trading (long-only). |
| [`vendor/day-trader-skill/`](file:///o:/Projects/CodeCafe%20Signals/vendor/day-trader-skill) | **11-Skill Day Trading Pack** | ORB breakout scanner, 10,000-replay Time Machine, SEC filings, budget, and risk limits. |
| [`trade_journal.json`](file:///o:/Projects/CodeCafe%20Signals/trade_journal.json) | **Live Trade Journal & Learning Ledger** | Tracks account starting balance, placed trades, active tickets, closed deal outcomes, and learned lessons. |
| [`.mcp.json`](file:///o:/Projects/CodeCafe%20Signals/.mcp.json) | **MCP Server Configuration** | Declares `yo-omni`, `yo-signals`, and `yo-crypto` for Claude Code / Antigravity. |

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

## 4. Hard Safety Rules & Risk Caps

All automated and manual executions strictly adhere to these immutable rules:
- **Demo-Only Enforcement**: Real-money trading is blocked in code (`DEMO_ONLY = True` on MT5; Bybit routes strictly to demo/testnet).
- **Position Sizing**: 1% risk per trade. MT5 lots capped at `0.10 lots` max; Bybit capped at `1000 USDT` notional.
- **Max Open Positions**: Capped at `3` concurrent positions to preserve margin.
- **Mandatory Stop-Loss**: Every order must carry a positive stop-loss.
- **Daily Drawdown Circuit Breaker**: New trades halt for the day if realized daily loss reaches **3.0%**.
- **Trailing Stop Protection**: When a trade reaches +1.5R profit, SL moves to entry price (breakeven) to eliminate downside risk.

---

## 5. How to Run & Test

### Run Offline Unit Tests
```powershell
uv run python test_core.py
uv run python test_omni.py
```
*Both suites must pass with zero errors.*

### Start Autonomous Trading Daemon (MT5)
Make sure MetaTrader 5 is open and logged into a demo account, with "Allow algorithmic trading" enabled:
```powershell
uv run python -u auto_trader.py --loop
```
*The daemon will monitor every 20 seconds, trail stops, bank profits at $\ge \$100$, record lessons, and scan for new setups.*

### Query Live Account & Positions via CLI
```powershell
uv run python -c "from server import account, positions; import pprint; pprint.pprint(account()); pprint.pprint(positions())"
```

### Scrape Market Data & Render ASCII Chart
```powershell
uv run python -c "from universal_data import fetch_universal_candles, render_ascii_chart; print(render_ascii_chart(fetch_universal_candles('BTC-USD', 'H1', 25)))"
```

### Scrape Breaking News & Macro Sentiment
```powershell
uv run python -c "from news_scraper import get_market_news_brief; import pprint; pprint.pprint(get_market_news_brief('TSLA'))"
```

### Generate Full Trade Plan (Chart + Patterns + S/R + Macro)
```powershell
uv run python -c "from omni_server import omni_plan_trade; import json; print(json.dumps(omni_plan_trade('EURUSD', 'M15'), indent=2))"
```

---

## 6. Next Recommended Enhancements

For future developers or next iterations:
1. **Crypto-Specific Strategy**: Strategy v2 was built for Forex; backtests show negative R on Crypto spot. Research and backtest a crypto momentum or mean-reversion strategy in `signals.py`.
2. **US Stock Market Hours Automation**: Connect `omni_daytrader` ORB scans to run automatically during NYSE market open (09:30 - 10:15 ET).
3. **Browser Automation**: If binary options or unsupported brokers are required, integrate Playwright in headless mode to read DOM prices and trigger web buttons.
4. **Interactive Dashboard**: Build a lightweight web view (FastAPI or Streamlit) reading `trade_journal.json` to visualize real-time equity curves and win rates.

