# analytics.py
import numpy as np

def compute_sharpe(equity_curve, risk_free_rate=0.0, freq_per_year=365*24):
    """Equity_curve is a list of dicts with 'equity' and 'time' keys. freq_per_year=8760 for hourly."""
    equities = np.array([pt['equity'] for pt in equity_curve])
    returns = np.diff(equities) / equities[:-1]
    if len(returns) == 0 or np.std(returns) == 0:
        return 0.0
    excess_ret = returns - (risk_free_rate / freq_per_year)
    return np.mean(excess_ret) / np.std(excess_ret) * np.sqrt(freq_per_year)

def compute_max_drawdown(equity_curve):
    equities = np.array([pt['equity'] for pt in equity_curve])
    if len(equities) == 0:
        return 0.0
    running_max = np.maximum.accumulate(equities)
    drawdowns = (equities - running_max) / running_max
    return float(drawdowns.min())

def compute_cagr(equity_curve):
    equities = np.array([pt['equity'] for pt in equity_curve])
    if len(equities) < 2:
        return 0.0
    t0, t1 = equity_curve[0]['time'], equity_curve[-1]['time']
    years = (t1 - t0) / (365*24*60*60*1000)  # if ms timestamp; adjust if sec
    return (equities[-1]/equities[0])**(1/years) - 1 if years > 0 else 0.0

# Usage:
# analytics.compute_sharpe(results['equity_curve'])
# analytics.compute_max_drawdown(results['equity_curve'])
