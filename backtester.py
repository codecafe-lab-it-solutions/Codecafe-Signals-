"""System 2.F: Walk-Forward Backtesting Engine.
Simulates trading strategies on historical bar data with realistic
spread, commission, slippage, and position sizing.
Computes comprehensive institutional performance metrics.
"""
from dataclasses import dataclass, field
import math
from typing import Any
import numpy as np



@dataclass
class BacktestTrade:
    entry_bar: int
    exit_bar: int
    side: str
    entry_price: float
    exit_price: float
    sl: float
    tp: float
    pnl: float
    return_pct: float
    r_multiple: float
    exit_reason: str


@dataclass
class BacktestMetrics:
    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate_pct: float
    net_profit: float
    profit_factor: float
    max_drawdown_pct: float
    sharpe_ratio: float
    sortino_ratio: float
    expectancy_r: float
    avg_win: float
    avg_loss: float
    equity_curve: list[float] = field(default_factory=list)


def run_historical_backtest(
    candles: dict,
    spread_points: float = 2.0,
    commission_per_trade: float = 1.0,
    slippage_pct: float = 0.0002,
    risk_pct_per_trade: float = 1.0,
    starting_balance: float = 10000.0,
    symbol: str = "",
    timeframe: str = "H1",
    point: float = 0.0,
) -> BacktestMetrics:
    """Execute historical simulation with execution costs and risk-adjusted sizing."""
    close = np.asarray(candles["close"], dtype=float)
    high = np.asarray(candles["high"], dtype=float)
    low = np.asarray(candles["low"], dtype=float)
    open_ = np.asarray(candles["open"], dtype=float)
    n = len(close)
    point = point or float(np.median(close)) * 1e-5  # spread_points are in units of this price step

    if n < 90:  # the strategies need 80 bars of history
        return BacktestMetrics(0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, [starting_balance])

    from intelligence import technical_report  # lazy: intelligence imports heavy modules
    from strategies import StrategyManager
    strategies = StrategyManager()
    window = 80  # same bar count the live scan analyses

    balance = starting_balance
    equity_curve = [balance]
    trades: list[BacktestTrade] = []
    in_pos = False
    active_side = ""
    active_entry = 0.0
    active_sl = 0.0
    active_tp = 0.0
    active_bar = 0
    active_qty = 0.0

    for i in range(window, n):
        # 1. Manage open position
        if in_pos:
            sign = 1 if active_side == "BUY" else -1
            hit_sl = low[i] <= active_sl if active_side == "BUY" else high[i] >= active_sl
            hit_tp = high[i] >= active_tp if active_side == "BUY" else low[i] <= active_tp

            if hit_sl or hit_tp:
                exit_price = active_sl if hit_sl else active_tp
                # Apply slippage
                exit_price = exit_price * (1 - slippage_pct) if active_side == "BUY" else exit_price * (1 + slippage_pct)
                gross_pnl = (exit_price - active_entry) * active_qty * sign
                net_pnl = gross_pnl - commission_per_trade
                balance += net_pnl
                equity_curve.append(round(balance, 2))

                risk_amount = abs(active_entry - active_sl) * active_qty
                r_mult = net_pnl / (risk_amount if risk_amount > 0 else 1.0)

                trades.append(BacktestTrade(
                    entry_bar=active_bar,
                    exit_bar=i,
                    side=active_side,
                    entry_price=active_entry,
                    exit_price=exit_price,
                    sl=active_sl,
                    tp=active_tp,
                    pnl=round(net_pnl, 2),
                    return_pct=round(net_pnl / balance * 100, 2),
                    r_multiple=round(r_mult, 2),
                    exit_reason="STOP_LOSS" if hit_sl else "TAKE_PROFIT",
                ))
                in_pos = False
            continue

        # 2. Entry: the live strategies on the last `window` closed bars, as the scan sees them.
        # News is unknown in history, so it counts as NEUTRAL.
        bars = {k: np.asarray(candles[k])[i - window + 1:i + 1] for k in ("time", "open", "high", "low", "close")}
        sig = strategies.evaluate_all(technical_report(symbol, timeframe, bars, float(close[i])))
        if sig.action not in ("BUY", "SELL"):
            continue
        sign = 1 if sig.action == "BUY" else -1
        entry = close[i] * (1 + slippage_pct * sign) + spread_points * point * sign / 2
        risk_per_unit = (entry - sig.sl) * sign
        if risk_per_unit <= 0 or (sig.tp - entry) * sign < 1.49 * risk_per_unit:
            continue  # the live risk engine refuses these (SL on the wrong side, or R:R under 1.5)
        in_pos = True
        active_side = sig.action
        active_entry = entry
        active_sl = sig.sl
        active_tp = sig.tp
        active_bar = i
        active_qty = balance * (risk_pct_per_trade / 100.0) / risk_per_unit

    # Calculate metrics
    total_trades = len(trades)
    if total_trades == 0:
        return BacktestMetrics(0, 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, equity_curve)

    wins = [t.pnl for t in trades if t.pnl > 0]
    losses = [abs(t.pnl) for t in trades if t.pnl < 0]
    win_count = len(wins)
    loss_count = len(losses)
    win_rate = (win_count / total_trades) * 100.0

    total_win = sum(wins)
    total_loss = sum(losses)
    profit_factor = (total_win / total_loss) if total_loss > 0 else 99.0
    net_profit = round(balance - starting_balance, 2)

    # Drawdown
    eq_arr = np.array(equity_curve)
    peaks = np.maximum.accumulate(eq_arr)
    drawdowns = (peaks - eq_arr) / peaks * 100.0
    max_dd = float(np.max(drawdowns)) if len(drawdowns) > 0 else 0.0

    # Sharpe & Sortino
    returns = np.array([t.pnl / starting_balance for t in trades])
    mean_ret = float(returns.mean()) if len(returns) > 0 else 0.0
    std_ret = float(returns.std()) if len(returns) > 1 else 1e-6
    if math.isnan(std_ret) or std_ret == 0:
        std_ret = 1e-6

    downside_returns = returns[returns < 0]
    downside_std = float(downside_returns.std()) if len(downside_returns) > 1 else std_ret
    if math.isnan(downside_std) or downside_std == 0:
        downside_std = 1e-6

    sharpe = round(float(mean_ret / std_ret * math.sqrt(252)), 2) if not math.isnan(mean_ret) else 0.0
    sortino = round(float(mean_ret / downside_std * math.sqrt(252)), 2) if not math.isnan(mean_ret) else 0.0
    if math.isnan(sharpe):
        sharpe = 0.0
    if math.isnan(sortino):
        sortino = 0.0

    expectancy = round(float(np.mean([t.r_multiple for t in trades])), 2)
    avg_win = round(total_win / win_count, 2) if win_count else 0.0
    avg_loss = round(total_loss / loss_count, 2) if loss_count else 0.0

    return BacktestMetrics(
        total_trades=total_trades,
        winning_trades=win_count,
        losing_trades=loss_count,
        win_rate_pct=round(win_rate, 2),
        net_profit=net_profit,
        profit_factor=round(profit_factor, 2),
        max_drawdown_pct=round(max_dd, 2),
        sharpe_ratio=sharpe,
        sortino_ratio=sortino,
        expectancy_r=expectancy,
        avg_win=avg_win,
        avg_loss=avg_loss,
        equity_curve=equity_curve,
    )
