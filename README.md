# CodeCafe Signals (prototype)

A forex assistant that runs inside Claude Code. It reads MT5 market data, finds signals automatically, and places trades only after you approve them. It works on a demo account only.

## Files
- `signals.py`: strategy v2. An EMA20/EMA50 cross filtered by RSI(14), taken only in the direction of a rising or falling EMA200 and only during London/New York hours. SL is 2×ATR(14) and TP is 3×SL. Each signal is BUY, SELL or WAIT, with reasons and an invalidation level. The file also holds the backtester and lot sizing.
- `research.py`: the variant search that picked v2. Run `uv run python research.py <data dir> grid`, then `... validate <kind> <session 0|1> <sl> <rr>`. The data dir holds `<SYMBOL>_<TF>.npy` files saved from MT5 with `copy_rates_from_pos`.
- `bybit.py`: a small Bybit V5 client (standard library only). Market data comes from real mainnet prices; trading goes only to Demo Trading or the testnet.
- `crypto_server.py`: the `yo-crypto` MCP server for Bybit **Demo Trading spot** (or testnet via `BYBIT_NET=testnet`), long-only. Tools: `account`, `price`, `scan`, `backtest`, `positions`, `suggest_size`, `place_order` (market buy with SL and TP attached) and `close_position`. Limits: 1% risk, at most 1000 USDT per order, 3% daily loss, 3 coins.
- `paper.py`: the paper broker. It trades fake money at real prices on any symbol, with no account or API key: crypto `BTCUSDT`, forex `EURUSD`, US stocks `AAPL`, Indian stocks `RELIANCE.NS`. Balances start at 10,000 USD and 10,00,000 INR. Real candles settle SL and TP. Any one trade can risk at most 2% of the balance. The `yo-omni` tools are `omni_execute_trade(platform="paper", ...)`, `omni_paper_positions` and `omni_paper_close`.
- `dashboard_server.py` and `web/`: the **hosted dashboard** (login, live quotes, scans, backtests, paper trading and the Screen Coach). Run it locally with `uv run python dashboard_server.py` or `Run_CodeCafe_Signals.bat`.
  - `auth.py` handles logins. The admin creates client logins, and clients change their own password. The shared `demo` login can't change its password.
  - `store.py` keeps logins and per-user paper accounts in Supabase Postgres when `DATABASE_URL` is set, otherwise in `./data`.
  - `coach.py` is the Screen Coach. It reads a shared screen frame with Gemini (`GEMINI_API_KEY`, free tier). Without that key it falls back to Claude (`ANTHROPIC_API_KEY`), and without either it gives a free plan from live data when you type a symbol.
  - The site places paper trades only. You place real orders yourself.
- `server.py`: an MCP server with the tools `account`, `price`, `candles`, `scan`, `backtest`, `positions`, `place_order` and `close_position`.
- `omni_server.py`: the unified `yo-omni` MCP server. Scrapes any market (Forex, Crypto, Stocks, Indices), renders ASCII/SVG charts, detects candlestick patterns and S/R levels, scans live news sentiment, runs `day-trader-skill` modules (ORB, Time Machine 10,000 replays), and executes trades via API or Screen UI with safety confirmations.
- `universal_data.py`: zero-dependency market data fetcher (Yahoo Finance, Bybit, MT5) and standalone ASCII & SVG candlestick chart generator.
- `chart_vision.py`: technical price action & candlestick pattern analyzer (Pin bars, Engulfing, Doji, S/R pivots, SL/TP levels).
- `news_scraper.py`: real-time financial RSS headlines scraper, sentiment scoring, and macro event risk flags (FOMC, CPI, NFP, SEC).
- `executor.py`: universal hybrid trade execution engine (MT5, Bybit, Paper Broker, or Windows Screen UI automation).

## Free cloud deploy (Render + Supabase)
1. **Database.** On supabase.com, create a free project.
   - Open **Connect**, then **Session pooler**, and copy the URI. It must be the pooler URI, because the direct connection is IPv6-only.
   - Put your database password into the URI. This full URI is `DATABASE_URL`.
2. **AI key (free).** On aistudio.google.com, choose **Get API key** and copy it. This is `GEMINI_API_KEY`. Free-tier prompts may be used by Google to improve its models.
3. **Render.** On render.com, sign up with GitHub. Choose **New**, then **Blueprint**, and pick this repo. `render.yaml` sets up a free Docker web service with auto-deploy on every push to `main`.
4. **Secrets.** Render asks for each `sync: false` value: `DATABASE_URL`, `GEMINI_API_KEY`, `GROQ_API_KEY`, `ADMIN_USER`/`ADMIN_PASSWORD` and `DEMO_USER`/`DEMO_PASSWORD`. `SECRET_KEY` is generated automatically. Use new passwords, not your local ones; `.env.cloud` (gitignored) holds a ready set.
5. When the deploy is live, open `https://codecafe-signals.onrender.com` (or the URL Render shows) and log in as admin. Click **Clients** to create a login for each client.

Free-tier limits:
- 512 MB RAM. The service sleeps after about 15 minutes without visitors, and the first visit then takes 30-60 seconds.
- MT5 doesn't run in the cloud, so the cloud version uses paper trading only.

## Backtest results (MetaQuotes-Demo history, typical spread included, 1R = amount risked per trade)
- **v1 (EMA cross + RSI only):** roughly breakeven (profit factor 0.94–1.09) with drawdowns of 21–47R. It lost −131R on the most recent 30% of history.
- **v2:** chosen from 32 variants using only the first 70% of history, 8 pairs × H1/H4. On the unseen last 30% it made +107R over 445 trades (profit factor 1.35, win rate 31%), with 12 of 16 markets positive. Over the full H1 history it made EURUSD +16R, USDJPY +38R and XAUUSD +25R.
- This is still a backtest, not proof. 32 variants were tried, so some of the gain may be luck. Paper-trade it on demo before trusting it. **Don't use real money.**
- `test_core.py`: offline checks. Run them with `uv run python test_core.py`.

## Crypto results (Bybit spot, long-only, 0.2% fees, London/NY hours in UTC)
v2 was built for forex and **mostly loses on crypto**. On H1, the last 30% of history went: BTC +8.4R (19 trades), ETH −14.5R, SOL −13.0R and XRP −14.1R. Removing the session filter did not help. H4 had too few trades to judge. Treat crypto signals as untested until a crypto-specific strategy passes the same in-sample/out-of-sample check.

## Bybit Demo Trading setup
Bybit's testnet blocks Indian accounts with error 10024, so we use Demo Trading inside a normal bybit.com account instead.
1. On bybit.com, open the profile menu, choose Demo Trading, and create an API key while in demo mode. Tick only SPOT > Trade and leave withdrawals off.
2. Set the key yourself: `setx BYBIT_KEY ...` and `setx BYBIT_SECRET ...`. Then restart Claude Code.
3. Add `"yo-crypto"` to `enabledMcpjsonServers`. Add `mcp__yo-crypto__place_order` and `mcp__yo-crypto__close_position` to `ask` in `.claude/settings.json`.

## Hard limits (top of `server.py`)
Each trade risks 1% of the balance, with at most 0.10 lots. Every trade needs a stop-loss. New trades stop once today's loss reaches 3%. At most 3 positions can be open, and a live account is refused.

## Setup
1. Install MetaTrader 5 from metatrader5.com and open a free **demo** account in it.
2. In MT5, enable Tools > Options > Expert Advisors > "Allow algorithmic trading".
3. Keep the MT5 terminal open and logged in.
4. If your broker uses symbol suffixes such as `EURUSDm`, set the `YO_SYMBOLS` environment variable, for example `EURUSDm,GBPUSDm`.
5. Create `.claude/settings.json` with the content below, so Claude Code always asks you before a trade:

```json
{
  "enabledMcpjsonServers": ["yo-signals"],
  "permissions": {
    "allow": ["mcp__yo-signals__account", "mcp__yo-signals__price", "mcp__yo-signals__candles",
              "mcp__yo-signals__scan", "mcp__yo-signals__positions"],
    "ask": ["mcp__yo-signals__place_order", "mcp__yo-signals__close_position"]
  }
}
```

6. Restart Claude Code in this folder. Then ask it to "scan for signals" or "analyze EURUSD".
