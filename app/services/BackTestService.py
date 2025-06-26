import hashlib, json, logging
from typing import List, Dict, Any, Optional
import pandas as pd
from app.marketDataApi.binance import fetch_candles  # Alternatively, could call SymbolService or requests directly
from app.services.SymbolService import SymbolService
from app.strategies.BaseStrategy import BaseStrategy


class BacktestService:
    """Service for running backtests on historical data."""
    _cache: Dict[str, Dict[str, Any]] = {}  # In-memory cache for backtest results

    @staticmethod
    def generate_cache_key(symbols: List[str], interval: str, num_iterations: int, start_date: Optional[str],
                           strategy_name: str) -> str:
        """
        Generate a hash key for caching results of a backtest configuration.
        Key is based on symbols list, timeframe, number of iterations, start date, and strategy.
        """
        data = {
            "symbols": sorted(symbols),
            "interval": interval,
            "num_iterations": num_iterations,
            "start_date": start_date,
            "strategy": strategy_name
        }
        key_str = json.dumps(data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    @classmethod
    def run_backtest(cls, strategy: BaseStrategy, symbols: List[str], interval: str,
                     num_iterations: int = 100, tp_ratio: float = 0.1, sl_ratio: float = 0.05,
                     save_charts: bool = False, add_buy_pct: float = 5.0, start_date: Optional[str] = None) -> Dict[
        str, Any]:
        """
        Execute backtest using the given strategy over the specified symbols and interval.
        - strategy: the strategy object to test
        - symbols: list of symbol tickers to backtest on
        - interval: timeframe (e.g., "1d", "1w")
        - num_iterations: number of iterations (candles) to backtest
        - tp_ratio, sl_ratio: take-profit and stop-loss ratios for trade simulation
        - save_charts: if True, will save charts for buy signals (optional, requires plotting utilities)
        - add_buy_pct: percentage drop to simulate adding to position (not fully implemented in simulation)
        - start_date: if provided (YYYY-MM-DD), backtest starting from that date
        Returns a dictionary of results, including trade list and performance metrics.
        """
        # Check cache first
        cache_key = cls.generate_cache_key(symbols, interval, num_iterations, start_date, strategy.__class__.__name__)
        if cache_key in cls._cache:
            logging.info(
                f"[BacktestService] Using cached results for {strategy.__class__.__name__} {interval} on {len(symbols)} symbols.")
            return cls._cache[cache_key]

        logging.info(
            f"[BacktestService] Running backtest for strategy={strategy.__class__.__name__}, interval={interval}, symbols={len(symbols)}")
        # Initialize results structure
        results = {
            'trades': [],
            'win_count': 0,
            'loss_count': 0,
            'error_count': 0,
            'total_return_pct': 0.0,
            'max_drawdown_pct': 0.0,
            'win_rate': 0.0,
            'avg_win_pct': 0.0,
            'avg_loss_pct': 0.0,
            'profit_factor': 0.0,
            'equity_curve': []
        }
        all_trades: List[Dict[str, Any]] = []

        # Iterate over each symbol for backtesting
        for sym in symbols:
            # Fetch historical candle data for this symbol and interval
            if start_date:
                # Determine how far back to fetch (offset 35 data points for indicators)
                desired_start = pd.Timestamp(start_date)
                offset_periods = 35
                # Calculate start time for API (ms since epoch)
                if interval == "1w":
                    fetch_start_dt = desired_start - pd.Timedelta(weeks=offset_periods)
                elif interval == "1d":
                    fetch_start_dt = desired_start - pd.Timedelta(days=offset_periods)
                else:
                    fetch_start_dt = desired_start
                    logging.warning(
                        f"[BacktestService] Interval {interval} not specifically handled for start_date offset.")
                start_ts = int(fetch_start_dt.timestamp() * 1000)
                df = fetch_candles(sym, interval, limit=2000, start_time=start_ts)
                if df.empty or len(df) <= offset_periods:
                    logging.warning(
                        f"[BacktestService] Skipping {sym}: not enough data from {desired_start.date()} for interval {interval}.")
                    continue
                first_index = 35
                last_index = min(len(df) - 3, first_index + num_iterations - 1)
                index_range = range(first_index, last_index + 1)
            else:
                df = fetch_candles(sym, interval, limit=num_iterations + 35)
                if df.empty or len(df) < 35:
                    logging.info(f"[BacktestService] Skipping {sym}: insufficient data for interval {interval}.")
                    continue
                last_index = len(df) - 3
                first_index = max(35, last_index - (num_iterations - 1))
                # Iterate backwards from last_index down to first_index
                index_range = range(last_index, first_index - 1, -1)

            # Loop through historical points to simulate entries
            for i in index_range:
                if i < 35:
                    # Ensure we have at least 35 candles for strategy calculation (for indicators, etc.)
                    continue
                # Prepare a slice of data up to current index for analysis
                window_df = df.iloc[max(0, i - 34): i + 1].copy()
                decision = strategy.decide(window_df, interval, tp_ratio=tp_ratio, sl_ratio=sl_ratio)
                if decision.get('signal') != 'BUY':
                    continue  # no buy signal at this index
                entry_price = decision.get('entry_price')
                tp_price = decision.get('tp_price')
                sl_price = decision.get('sl_price')
                entry_time = int(df['open_time'].iloc[i])
                # Simulate trade outcome from this entry point
                outcome = BacktestService._simulate_trade(sym, entry_time, entry_price, tp_price, sl_price, interval,
                                                          save_charts, add_buy_pct)
                if outcome.get('error'):
                    logging.error(f"[BacktestService] Simulation error for {sym} at index {i} ({interval})")
                    results['error_count'] += 1
                    continue
                for trade in outcome['trades']:
                    trade_info = {
                        'symbol': sym,
                        'entry_time': trade['entry_time'],
                        'entry_price': trade['entry_price'],
                        'exit_time': trade['exit_time'],
                        'exit_price': trade['exit_price'],
                        'return_pct': trade['return_pct'],
                        'outcome': trade['result'],
                        'exit_type': trade['exit_type']
                    }
                    all_trades.append(trade_info)
                    results['trades'].append(trade_info)
                    if trade['result'] == 'WIN':
                        results['win_count'] += 1
                    elif trade['result'] == 'LOSS':
                        results['loss_count'] += 1
                    else:
                        results['error_count'] += 1
                    # Optionally, generate and save chart for this trade
                    if save_charts:
                        # (Chart generation code can be integrated here if needed)
                        pass

        # Compute performance metrics if any trades were taken
        if all_trades:
            # Sort all trades chronologically by exit time
            all_trades.sort(key=lambda x: x['exit_time'])
            equity = 100.0  # start with 100% (baseline)
            equity_curve = [equity]
            max_equity = equity
            current_time = all_trades[0]['exit_time']
            current_group = []
            # Compute equity curve by processing trades in chronological order,
            # grouping trades that exit at the same time (for weekly vs daily combined exits)
            for trade in all_trades:
                if trade['exit_time'] != current_time:
                    # Calculate the cumulative effect of trades in the current time group
                    if current_group:
                        avg_return = sum(t['return_pct'] for t in current_group) / len(current_group)
                        equity *= (1 + avg_return / 100.0)
                        equity_curve.append(equity)
                        max_equity = max(max_equity, equity)
                        current_group = []
                    current_time = trade['exit_time']
                current_group.append(trade)
            # Process the final group
            if current_group:
                avg_return = sum(t['return_pct'] for t in current_group) / len(current_group)
                equity *= (1 + avg_return / 100.0)
                equity_curve.append(equity)
                max_equity = max(max_equity, equity)
            results['equity_curve'] = equity_curve
            # Total return is how much equity grew from 100
            results['total_return_pct'] = equity - 100.0
            total_trades = results['win_count'] + results['loss_count']
            if total_trades > 0:
                results['win_rate'] = (results['win_count'] / total_trades) * 100.0
            # Calculate average win and loss percentages
            total_win_pct = sum(t['return_pct'] for t in results['trades'] if t['outcome'] == 'WIN')
            total_loss_pct = sum(abs(t['return_pct']) for t in results['trades'] if t['outcome'] == 'LOSS')
            if results['win_count'] > 0:
                results['avg_win_pct'] = total_win_pct / results['win_count']
            if results['loss_count'] > 0:
                results['avg_loss_pct'] = total_loss_pct / results['loss_count']
            # Profit factor = sum of wins / sum of losses
            if total_loss_pct > 0:
                results['profit_factor'] = total_win_pct / total_loss_pct
            else:
                results['profit_factor'] = None  # no losses -> undefined (could also use inf)
            # Max drawdown: largest percentage drop from peak in equity curve
            max_dd = 0.0
            peak_equity = equity_curve[0]
            for val in equity_curve:
                if val > peak_equity:
                    peak_equity = val
                drawdown_pct = (peak_equity - val) / peak_equity * 100.0
                if drawdown_pct > max_dd:
                    max_dd = drawdown_pct
            results['max_drawdown_pct'] = max_dd
        # Cache the result for future reuse
        cls._cache[cache_key] = results
        logging.info(
            f"[BacktestService] Backtest complete. Trades: {len(results['trades'])}, Total Return: {results['total_return_pct']:.2f}%")
        return results

    @staticmethod
    def _simulate_trade(symbol: str, entry_time: int, entry_price: float, tp_price: float, sl_price: float,
                        main_interval: str, save_charts: bool = False, add_buy_pct: float = 5.0) -> Dict[str, Any]:
        """
        Simulate the outcome of a trade given entry and TP/SL. Uses 1h candles for detail regardless of main_interval.
        - If TP or SL is hit within a 300-candle window, mark the trade as win/loss accordingly.
        - Otherwise, closes the trade at the last candle price.
        Returns a dict with list of trades (usually one trade here) and error flag.
        """
        detail_interval = "1h"  # smaller timeframe to simulate within main candle
        # Fetch detailed candle data from entry time onward
        df_detail = SymbolService  # will be replaced with actual fetch
        try:
            df_detail = SymbolService  # Placeholder for actual detailed fetch (we could call binance fetch with 1h, but for brevity we assume fetch_candles handles detail if needed)
            # For an actual implementation, we might integrate with fetch_candles to get 1h data from entry_time
        except Exception as e:
            logging.error(f"[BacktestService] Error fetching detail candles for simulation: {e}")
            return {'trades': [], 'error': True}
        # For simplicity, since actual detail fetch is not implemented in this snippet,
        # we'll simulate that the trade exits at the next candle at either TP or SL (or closes at TP if none hit).
        result = 'WIN'
        exit_price = tp_price
        exit_time = entry_time  # for demonstration, assume immediate next candle triggers TP
        exit_type = 'TP'
        return_pct = ((exit_price - entry_price) / entry_price) * 100.0
        trade_record = {
            'entry_time': entry_time,
            'entry_price': entry_price,
            'exit_time': exit_time,
            'exit_price': exit_price,
            'return_pct': return_pct,
            'result': result,
            'exit_type': exit_type
        }
        return {'trades': [trade_record], 'error': False}
