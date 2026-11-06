# PROJECT MASTER PROMPT: BUILD A FULL AUTONOMOUS AI TRADING SYSTEM

## 1. Project Objective

I have already developed an initial version of an AI-powered trading system. I now want to upgrade that first version into a complete, modular, intelligent and production-grade autonomous trading platform.

Your responsibility is to work as a Senior Quantitative Developer, AI/ML Engineer, Algorithmic Trading Engineer, Backend Architect and Security Engineer.

Do not blindly rebuild the application from scratch. First inspect the existing codebase, understand its architecture, identify completed functionality, find incomplete or placeholder modules, and then develop the next version using the existing implementation wherever practical.

The ultimate objective is to build an AI-powered system that can independently:

- Monitor financial markets continuously.
- Analyse live and historical market data.
- Understand candlestick patterns and market structure.
- Read financial news and economic announcements.
- Identify bullish, bearish and sideways market conditions.
- Generate and evaluate trading opportunities.
- Calculate entry prices, stop-losses and take-profits.
- Manage trading risk and portfolio exposure.
- Execute approved trades through supported broker APIs.
- Monitor open positions.
- Record every decision and trading outcome.
- Evaluate and improve its strategies using historical and new data.

The system should be designed for Forex trading initially, but its architecture should allow additional asset classes and trading providers in the future.

**Important:** A system that executes orders automatically is not necessarily an intelligent or profitable trading system. Prioritize measurable strategy performance, safety, reliability and validation over the number of automated features.

---

# 2. THE THREE CORE SYSTEMS

The application must be divided into three independent but interconnected systems.

## SYSTEM 1: MARKET INTELLIGENCE AI

### Objective

Build an intelligence layer that continuously collects, understands and analyses financial market information.

This system should behave like a financial market research analyst.

### A. Live Market Data Collection

Implement a market data collection service that supports:

- Live forex prices.
- Bid and ask prices.
- Historical price data.
- OHLCV candlestick data.
- Market depth and order book data where available.
- Trading volume where meaningful and available.
- Spread monitoring.
- Volatility monitoring.
- Multiple currency pairs.
- Multiple timeframes.

Supported timeframes should include:

- 1 minute
- 5 minutes
- 15 minutes
- 30 minutes
- 1 hour
- 4 hours
- Daily
- Weekly

The system must support continuous data updates using WebSockets or broker-supported streaming connections where available.

Handle connection interruptions, missing candles, duplicate records, timestamp inconsistencies and stale market data.

Never interpret missing or stale data as current market information.

### B. Candlestick and Technical Analysis

Develop an independent technical analysis engine.

It should analyse:

**Candlestick patterns**
- Doji.
- Hammer.
- Shooting Star.
- Engulfing.
- Morning Star.
- Evening Star.
- Pin Bar.
- Inside Bar.
- Three White Soldiers.
- Three Black Crows.

**Technical indicators**
- RSI.
- MACD.
- EMA.
- SMA.
- Bollinger Bands.
- ATR.
- ADX.
- Stochastic Oscillator.
- VWAP where meaningful.
- Fibonacci retracement.

**Market structure**
- Higher highs and higher lows.
- Lower highs and lower lows.
- Break of Structure (BOS).
- Change of Character (CHOCH).
- Support and resistance.
- Supply and demand zones.
- Liquidity sweeps.
- Fair Value Gaps.
- Order Blocks.
- Breakouts and false breakouts.
- Consolidation and ranging markets.

The system should compare multiple timeframes instead of making decisions from a single chart.

Use numerical OHLC and market data as the primary analysis input. Chart images may be used as an additional input, not as the sole source of trading decisions.

All indicators and pattern detections should have explicit definitions and testable implementations.

### C. Financial News Intelligence

Build a dedicated news intelligence module.

It should collect information from legitimate and licensed sources, including:

- Financial news.
- Central bank announcements.
- Federal Reserve decisions.
- European Central Bank decisions.
- Bank of England announcements.
- Inflation reports.
- CPI and PPI.
- Employment reports.
- GDP releases.
- Interest-rate decisions.
- Geopolitical developments.
- Major financial events.

The AI must:

1. Read incoming news.
2. Identify the relevant currencies and markets.
3. Extract important information.
4. Identify whether the event is confirmed, expected or unverified.
5. Compare actual economic figures with market expectations when available.
6. Determine possible bullish or bearish implications.
7. Identify potentially conflicting news.
8. Evaluate the information against current market conditions.
9. Record the source, publication time and event time.
10. Produce a structured analysis.

Do not treat every positive headline as bullish or every negative headline as bearish.

The system must distinguish between expected events and unexpected events, and account for the possibility that the market has already priced in an announcement.

### D. Economic Calendar Intelligence

Integrate an economic calendar.

Display:

- Event name.
- Currency affected.
- Previous value.
- Forecast value.
- Actual value.
- Event time.
- Importance level.
- Market impact.
- Related news.

Implement event-risk monitoring so the trading system can reduce exposure or avoid entering positions around selected high-impact announcements.

### E. Market Sentiment Analysis

Develop a sentiment analysis component that evaluates:

- Financial news sentiment.
- Economic announcement sentiment.
- Relevant market commentary.
- Available market positioning information.
- Volatility and price behaviour.

Sentiment must be represented using structured data with confidence, evidence and timestamps.

Do not confuse news sentiment with actual market direction.

### F. Market Regime Detection

Identify the current market environment:

- Strong bullish trend.
- Strong bearish trend.
- Weak bullish trend.
- Weak bearish trend.
- Sideways market.
- High-volatility market.
- Low-volatility market.
- Unusual or abnormal market conditions.

Use measurable features and machine learning where justified.

### SYSTEM 1 OUTPUT

The Market Intelligence AI should produce a structured market report containing:

- Instrument.
- Current market price and data timestamp.
- Market direction.
- Market regime.
- Relevant timeframe.
- Technical analysis.
- Candlestick analysis.
- Support and resistance.
- News sentiment.
- Upcoming economic events.
- Volatility condition.
- Relevant market risks.
- Confidence and supporting evidence.

This output will be consumed by System 2.

---

## SYSTEM 2: QUANTITATIVE TRADING AND DECISION ENGINE

### Objective

Build the intelligence and decision-making engine that evaluates market opportunities and determines whether a trading strategy has a valid setup.

This system must not blindly trust an LLM's prediction.

It should combine deterministic mathematical strategies, statistical models, machine learning and AI-assisted reasoning.

### A. Strategy Management

Create a modular strategy framework.

It should support multiple independently configurable strategies, including:

- Trend following.
- Moving average crossover.
- Momentum trading.
- Mean reversion.
- Breakout trading.
- Support and resistance trading.
- Price action strategies.
- Volatility-based strategies.
- News-aware strategies.

Each strategy should have:

- Unique identifier.
- Name.
- Description.
- Supported instruments.
- Supported timeframes.
- Entry conditions.
- Exit conditions.
- Risk parameters.
- Configuration.
- Backtesting results.
- Performance history.
- Active/inactive status.

Allow strategies to be independently enabled, disabled and tested.

Do not assume every strategy works in every market condition.

### B. Signal Generation

Build a signal generation engine that receives information from System 1.

It should evaluate:

- Technical indicators.
- Candlestick patterns.
- Market structure.
- Trend direction.
- Market regime.
- News conditions.
- Volatility.
- Historical strategy performance.

Possible decisions:

- BUY.
- SELL.
- HOLD.
- NO TRADE.

Every signal must include:

- Instrument.
- Direction.
- Strategy identifier.
- Timeframe.
- Proposed entry.
- Stop-loss.
- Take-profit.
- Risk/reward ratio.
- Supporting indicators.
- Supporting market evidence.
- News considerations.
- Signal timestamp.
- Expiry or invalidation conditions.
- Model or strategy version.
- Confidence score.

Confidence scores must be calibrated and evaluated against actual outcomes. Do not present arbitrary LLM-generated percentages as statistically reliable probabilities.

### C. Machine Learning Models

Build a separate ML infrastructure.

Investigate and implement appropriate models such as:

- XGBoost.
- LightGBM.
- Random Forest.
- PyTorch-based models.
- Time-series forecasting models.
- Classification models.
- Anomaly detection models.
- Market regime classification models.

Possible applications:

1. Identify market regimes.
2. Classify market conditions.
3. Detect historical patterns.
4. Estimate volatility.
5. Estimate the probability of reaching predefined price barriers.
6. Identify unusual market movements.
7. Evaluate the historical performance of strategy conditions.

Use feature engineering and proper chronological dataset splitting.

Prevent look-ahead bias, data leakage and overfitting.

Do not train models using future information that would not have been available at the time of the simulated trade.

### D. LLM Integration

Use an LLM for tasks where language understanding and contextual reasoning are useful.

Examples:

- Understanding financial news.
- Summarising economic reports.
- Explaining technical signals.
- Comparing multiple market hypotheses.
- Identifying conflicting evidence.
- Producing human-readable trade explanations.
- Retrieving relevant information from the trading knowledge base.

The LLM must return structured outputs validated against strict schemas.

It must never directly submit orders to a broker.

It must not override risk limits or bypass the execution engine.

### E. Knowledge Base and RAG

Create a trading knowledge base where I can provide:

- Forex trading books.
- Trading strategy documentation.
- Research papers.
- Technical analysis material.
- Economic and financial documentation.
- Strategy-specific notes.
- Internal trading rules.
- Historical research.

Implement Retrieval-Augmented Generation (RAG) so the AI can retrieve relevant knowledge when analysing markets.

Possible technologies:

- pgvector.
- PostgreSQL.
- Embedding models.
- Document processing.
- Vector search.

Keep the knowledge base separate from the actual strategy implementation.

A document describing a strategy must not automatically make that strategy active.

### F. Backtesting Engine

This is a mandatory component.

Build a proper historical strategy testing environment.

Features:

- Historical market data loading.
- Multiple instruments.
- Multiple timeframes.
- Strategy configuration.
- Entry and exit simulation.
- Spread modelling.
- Commission modelling.
- Slippage modelling.
- Swap and financing cost modelling where applicable.
- Position sizing.
- Stop-loss and take-profit simulation.
- Equity curve.
- Drawdown calculation.
- Trade history.

Performance metrics must include:

- Total return.
- Net profit/loss.
- Win rate.
- Average win.
- Average loss.
- Profit factor.
- Maximum drawdown.
- Sharpe ratio.
- Sortino ratio.
- Expectancy.
- Risk/reward ratio.
- Number of trades.
- Average holding duration.

Implement walk-forward validation and out-of-sample testing.

Avoid unrealistic assumptions about execution prices and order fills.

### G. Strategy Evaluation

Create a strategy comparison system.

Compare:

- Strategy performance.
- Performance across different market regimes.
- Performance across instruments.
- Performance across timeframes.
- Risk-adjusted returns.
- Drawdowns.
- Consistency.
- Trading costs.

The system should identify strategies that are underperforming and flag them for review.

It must not automatically change live trading parameters simply because a recent strategy performed poorly.

### H. Learning and Feedback

Record every trading decision and its eventual result.

The system should learn from:

- Successful trades.
- Failed trades.
- Missed opportunities.
- False signals.
- Unexpected volatility.
- News-driven market movements.
- Changes in market regimes.

Build a controlled model improvement pipeline.

Model training and validation must be separate from live inference.

New models must pass evaluation before promotion.

Keep model versions, training datasets, evaluation metrics and rollback capability.

### SYSTEM 2 OUTPUT

Produce a structured trading decision containing:

- BUY, SELL, HOLD or NO TRADE.
- Selected strategy.
- Instrument.
- Timeframe.
- Entry price.
- Stop-loss.
- Take-profit.
- Position sizing recommendation.
- Risk/reward ratio.
- Supporting evidence.
- Model evaluation.
- Confidence or calibrated probability where available.
- Reasons for rejecting a trade.
- Signal validity period.

Send this output to System 3 for independent validation.

---

## SYSTEM 3: EXECUTION, PORTFOLIO AND RISK MANAGEMENT ENGINE

### Objective

Build a secure execution system that can communicate with supported trading platforms and manage the complete lifecycle of a trade.

This system is responsible for protecting the account.

The execution engine must not blindly execute signals received from System 2.

### A. Broker and Platform Connectivity

Design a modular broker adapter architecture.

Investigate integrations with:

- MetaTrader 5.
- MetaTrader 4 where practical.
- cTrader.
- Other brokers offering documented and permitted trading APIs.

Keep cryptocurrency exchange adapters separate from forex broker adapters.

Potential future integrations:

- Binance.
- Bybit.
- CoinDCX.

Do not assume that crypto exchanges are forex brokers.

Each adapter should support the operations available through its provider:

- Authentication.
- Account information.
- Live prices.
- Market data.
- Available instruments.
- Account balance.
- Open positions.
- Pending orders.
- Order placement.
- Order modification.
- Order cancellation.
- Position closing.
- Trade history.

Use official, supported APIs wherever possible.

Do not make browser automation or mouse clicking the primary trading mechanism.

If a provider does not offer an appropriate API, keep it unsupported until a reliable and permitted integration is established.

### B. Order Execution

Implement a dedicated order management service.

It must handle:

- Market orders.
- Limit orders.
- Stop orders.
- Buy orders.
- Sell orders.
- Position modification.
- Stop-loss placement.
- Take-profit placement.
- Order cancellation.
- Partial fills.
- Rejected orders.
- Duplicate requests.
- Execution timeouts.

Every order must have a unique internal identifier and idempotency protection where supported.

Never assume that submitting an order means that it has been executed.

Verify broker responses and reconcile actual account positions with internal records.

### C. Independent Risk Management

This is one of the most important components.

Create a risk management service independent of the AI and strategy engines.

It must validate every proposed trade before execution.

Implement configurable controls for:

- Maximum risk per trade.
- Maximum daily loss.
- Maximum weekly loss.
- Maximum account drawdown.
- Maximum simultaneous open positions.
- Maximum exposure per instrument.
- Maximum total portfolio exposure.
- Maximum leverage.
- Minimum risk/reward ratio.
- Maximum spread.
- Maximum permitted slippage.
- Minimum available margin.
- High-impact news restrictions.

Implement position sizing based on account equity, stop-loss distance, instrument specifications and account currency.

Never use a fixed lot size as a universal position-sizing rule.

### D. Emergency Protection

Build an emergency stop system.

It should support:

- Disable all new orders.
- Stop the trading engine.
- Cancel pending orders.
- Close positions when explicitly configured and authorized.
- Disable a specific strategy.
- Disable a specific broker connection.
- Pause trading during abnormal market conditions.
- Alert the operator when the system becomes disconnected.

An emergency stop must be independent of the AI model.

Do not automatically close positions merely because the application restarts or loses connectivity.

### E. Portfolio Management

Monitor:

- Account balance.
- Equity.
- Available margin.
- Used margin.
- Floating profit/loss.
- Realised profit/loss.
- Open positions.
- Pending orders.
- Exposure by instrument.
- Daily trading performance.
- Drawdown.
- Trading costs.

Reconcile portfolio data with the actual broker account.

### F. Execution Audit Trail

Record every important event:

- Incoming signal.
- Market data used.
- Risk validation result.
- Rejected trade and reason.
- Order submission.
- Broker response.
- Order fill.
- Position modification.
- Stop-loss activation.
- Take-profit activation.
- Position closure.
- Final profit/loss.

Include timestamps, strategy versions and correlation identifiers.

Maintain an immutable or tamper-evident audit trail where practical.

### SYSTEM 3 OUTPUT

Provide:

- Order status.
- Broker response.
- Actual execution price.
- Actual position size.
- Open position information.
- Realised and unrealised P&L.
- Risk validation result.
- Execution errors.
- Account status.
- Trade lifecycle history.

---

# 3. CENTRAL DASHBOARD

Develop a professional trading dashboard that provides complete visibility into all three systems.

Use the existing frontend architecture if it is already functional.

### Dashboard modules

**1. Overview**
- Account balance.
- Equity.
- Daily P&L.
- Total P&L.
- Active positions.
- Active strategies.
- System health.
- Market status.

**2. Live Markets**
- Currency pairs.
- Live prices.
- Candlestick charts.
- Technical indicators.
- Multiple timeframe selection.
- Spread and volatility.

**3. AI Market Intelligence**
- Market analysis.
- News feed.
- Economic calendar.
- Sentiment.
- Market regime.
- AI-generated reports.

**4. Trading Signals**
- Buy/sell/hold signals.
- Signal history.
- Entry and exit levels.
- Signal confidence.
- Supporting evidence.
- Rejected signals.

**5. Strategies**
- Strategy library.
- Enable/disable controls.
- Strategy configurations.
- Performance comparison.
- Backtesting results.

**6. ML Models**
- Model registry.
- Model versions.
- Training status.
- Evaluation results.
- Prediction history.
- Model drift monitoring.

**7. Backtesting**
- Historical date selection.
- Instrument selection.
- Strategy selection.
- Configuration.
- Equity curve.
- Performance metrics.
- Trade-by-trade analysis.

**8. Execution**
- Broker connections.
- Account information.
- Open positions.
- Pending orders.
- Order history.
- Execution logs.

**9. Risk Management**
- Risk limits.
- Account exposure.
- Daily loss limits.
- Maximum drawdown.
- Margin monitoring.
- Emergency stop.

**10. Knowledge Base**
- Upload trading books.
- Upload PDFs and documents.
- Manage trading rules.
- Search knowledge.
- View indexed documents.

**11. System Monitoring**
- Service status.
- Data feed status.
- Broker connection status.
- AI model status.
- API errors.
- Background jobs.
- Logs and alerts.

Use a professional financial trading interface. Avoid unnecessary decorative elements and excessive animations. Prioritize readability, accurate data and operational clarity.

---

# 4. OPERATING MODES

The system must support separate operating modes.

### Mode 1: Research Mode

- Historical market analysis.
- News analysis.
- Strategy development.
- Model experiments.
- No trade execution.

### Mode 2: Backtesting Mode

- Historical data.
- Simulated orders.
- Historical performance evaluation.
- No broker orders.

### Mode 3: Paper Trading Mode

- Live market data.
- Simulated account balance.
- Simulated orders and fills.
- Full signal and execution pipeline.
- No real-money orders.

### Mode 4: Demo Broker Mode

- Connect to an explicitly configured broker demo account.
- Test actual broker connectivity.
- Test order submission and modification.
- Verify order responses and reconciliation.

### Mode 5: Live Trading Mode

- Explicit operator authorization.
- Supported and legally permitted broker connection.
- Independent risk validation.
- Strict account-level limits.
- Continuous monitoring.
- Emergency shutdown.

**Mandatory default:** Research or Paper Trading mode.

Live trading must remain disabled unless explicitly configured and authorized. Do not expose real trading functionality merely because a broker API credential is present.

---

# 5. SYSTEM ARCHITECTURE AND TECHNOLOGY

First inspect the existing repository and preserve working technologies wherever practical.

Potential technology stack:

### Backend
- Python.
- FastAPI.
- Pydantic.
- Async processing.

### Data Processing
- Pandas.
- NumPy.
- TA-Lib.
- Scikit-learn.

### Machine Learning
- XGBoost.
- LightGBM.
- PyTorch.
- Hugging Face models where appropriate.

### Database
- PostgreSQL.
- TimescaleDB for time-series data.
- pgvector for knowledge retrieval.

### Caching and Messaging
- Redis.
- Celery or an appropriate background job system.
- WebSockets.

### Trading Infrastructure
- MetaTrader 5 Python integration.
- LEAN.
- NautilusTrader.
- Official broker APIs.

Do not integrate all these frameworks unnecessarily. Evaluate which one fits the existing system and select a clear primary trading engine.

### Frontend
- Preserve existing React or Next.js implementation.
- TypeScript.
- Trading charts.
- WebSocket-based live updates.

### Deployment
- Docker.
- Docker Compose.
- Environment-based configuration.
- Structured application logging.
- Automated backups.
- Health checks.

---

# 6. SECURITY AND FINANCIAL SAFETY

Implement security as a core architectural requirement.

- Store API credentials in environment variables or a secure secrets manager.
- Never hardcode broker passwords or API keys.
- Never expose trading credentials to frontend code.
- Restrict API permissions to the minimum required.
- Avoid withdrawal permissions on trading API keys.
- Use encrypted communication.
- Implement authentication and role-based authorization.
- Protect all execution endpoints.
- Maintain an audit trail.
- Implement rate limits.
- Validate incoming external data.
- Protect against duplicate order submissions.
- Implement safe failure behaviour.
- Separate demo and live credentials.
- Require explicit authorization for live trading.
- Implement account and system kill switches.

For Indian deployment, investigate the applicable RBI, FEMA, SEBI and exchange requirements for the exact instruments, broker and trading arrangement before enabling live trading. Do not assume an overseas forex broker is legally available simply because its API works.

---

# 7. TESTING AND VALIDATION

Create a complete testing framework.

### Unit testing
- Indicator calculations.
- Candlestick detection.
- Strategy conditions.
- Position sizing.
- Risk validation.
- Order validation.

### Integration testing
- Database connectivity.
- Market data ingestion.
- News processing.
- Broker adapters.
- Execution responses.
- Portfolio reconciliation.

### Simulation testing
- Historical market scenarios.
- High-volatility scenarios.
- Market gaps.
- Spread widening.
- Network failures.
- Broker disconnections.
- Rejected and partially filled orders.

### Strategy testing
- In-sample performance.
- Out-of-sample performance.
- Walk-forward testing.
- Transaction costs.
- Slippage.
- Drawdown.
- Different market regimes.

### Operational testing
- Service restarts.
- Duplicate events.
- Database failures.
- Feed interruptions.
- Emergency shutdown.
- Recovery and reconciliation.

Never claim that a strategy is profitable merely because it produced positive results in a backtest.

---

# 8. DEVELOPMENT WORKFLOW

Follow this exact implementation workflow.

## Phase 1: Existing Project Audit

Before changing code:

1. Inspect the complete repository.
2. Understand the frontend and backend architecture.
3. Identify all existing modules.
4. Identify completed functionality.
5. Identify incomplete functionality.
6. Find mock data and placeholder implementations.
7. Identify existing integrations.
8. Inspect database schemas and migrations.
9. Inspect environment variables and deployment configuration.
10. Identify security and performance problems.

Produce an audit report containing:

- Existing architecture.
- Completed modules.
- Incomplete modules.
- Broken functionality.
- Missing integrations.
- Technical debt.
- Security risks.
- Recommended improvements.

Do not delete existing working functionality without a clear reason.

## Phase 2: Architecture Design

Create:

- System architecture diagram.
- Service dependency diagram.
- Database schema.
- API endpoint documentation.
- Data flow documentation.
- Broker integration design.
- AI model architecture.
- Risk management specification.

Identify which existing components can be reused.

## Phase 3: Development Planning

Break implementation into small, testable milestones.

For each milestone specify:

- Objective.
- Files to create or modify.
- Dependencies.
- Expected output.
- Acceptance criteria.
- Tests required.

Do not attempt to implement every module in a single uncontrolled code change.

## Phase 4: Incremental Implementation

Implement in this order:

1. Core backend infrastructure.
2. Market data collection.
3. Technical analysis.
4. News intelligence.
5. Economic calendar.
6. Market intelligence reports.
7. Strategy framework.
8. Signal generation.
9. Backtesting.
10. ML model infrastructure.
11. Knowledge base and RAG.
12. Independent risk engine.
13. Paper execution engine.
14. Broker adapters.
15. Portfolio management.
16. Dashboard integration.
17. Monitoring and audit logs.
18. Demo account testing.
19. Live execution safeguards.

The ordering can be adjusted when the existing codebase already has working components.

## Phase 5: Validation

After every milestone:

- Run tests.
- Check logs.
- Verify database operations.
- Verify API responses.
- Check frontend integration.
- Validate failure scenarios.
- Document known issues.

Never mark a module complete simply because its UI exists.

A module is complete only when its underlying functionality works.

---

# 9. STRICT DEVELOPMENT RULES

Follow these rules throughout the project:

1. Do not rebuild everything from scratch without first auditing the existing implementation.
2. Do not replace existing technologies without explaining the benefit.
3. Do not introduce unnecessary dependencies.
4. Do not use mock data in production workflows.
5. Clearly identify simulated, historical and live data.
6. Do not generate fake trading signals to make the dashboard look active.
7. Do not hardcode market prices, balances or trading results.
8. Do not allow an LLM to bypass risk controls.
9. Do not allow the AI to directly execute trades.
10. Do not enable live trading by default.
11. Do not assume API order submission equals successful execution.
12. Do not use future data in historical backtesting.
13. Do not claim a model is profitable without rigorous evidence.
14. Do not silently ignore errors.
15. Do not expose credentials.
16. Do not break existing production functionality.
17. Maintain proper documentation and database migrations.
18. Keep all trading operations traceable.
19. Prefer reliable, deterministic components for financial calculations.
20. Every major component must be independently testable.

---

# 10. REQUIRED DELIVERABLES

At the end of development, provide:

1. Complete upgraded application.
2. Updated system architecture.
3. Functional Market Intelligence AI.
4. Functional Quantitative Trading Engine.
5. Functional Execution and Risk Engine.
6. Broker integration framework.
7. Working paper trading environment.
8. Historical backtesting framework.
9. ML training and evaluation pipeline.
10. Knowledge base and RAG integration.
11. Central trading dashboard.
12. Database schema and migrations.
13. API documentation.
14. Docker deployment configuration.
15. Environment variable documentation.
16. Automated tests.
17. Security documentation.
18. Installation and setup guide.
19. Operations and monitoring guide.
20. Known limitations and future development roadmap.

---

# 11. FIRST TASK: START WITH THE EXISTING PROJECT

Do not immediately start coding.

First inspect the existing application and answer the following:

1. What have I already built?
2. Which of the three core systems are implemented?
3. Which components are functional and which are only UI or placeholders?
4. Which modules can be reused?
5. Which modules need improvement?
6. Which modules need to be developed from scratch?
7. What is the current technical architecture?
8. What are the biggest security and reliability risks?
9. Which trading framework and broker integration would best fit this project?
10. What is the most practical implementation roadmap?

Produce a detailed gap analysis and development plan.

Then begin implementation milestone by milestone.

**Do not stop after producing the audit report.** Once the audit and architecture plan are complete, proceed with the first safe implementation milestone, unless a critical missing decision or external dependency requires my approval.

The final objective is not just an AI that predicts market direction. It is a complete, explainable, testable and risk-controlled autonomous trading platform in which:

- System 1 understands the market.
- System 2 evaluates opportunities and makes trading decisions.
- System 3 validates risk and manages execution.

All three systems must work together while remaining independently testable and independently controllable.

Build it as a serious financial software system, not a trading-bot demonstration.