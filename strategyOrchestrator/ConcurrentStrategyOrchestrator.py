"""
ConcurrentStrategyOrchestrator.py
──────────────────────────────────────────────────────────────────────────
Enhanced orchestrator with concurrency support for efficient backtesting.
Ensures deterministic results while maximizing performance.
"""

import asyncio
import hashlib
import json
import logging
import sys
import time
import traceback
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple, Callable

import numpy as np
import pandas as pd
from numba import jit, prange

from entities.perpetuals.portfolio.PerpPortfolioManager import PerpPortfolioManager
from entities.portfolio.BasePortfolioManager import BasePortfolioManager
from entities.portfolio.fees.fees import (
    static_fee_model,
    per_symbol_fee_model,
    random_slippage_model,
)
from entities.strategies.BaseStrategy import BaseStrategy
from entities.tradeManager.FillPolicy import FillPolicy, AggressiveMarketPolicy
from entities.tradeManager.TradeProposal import TradeProposal
from strategyOrchestrator.repository.candleRepository import CandleRepository


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


@dataclass
class BacktestConfig:
    """Configuration for backtest execution."""
    symbols: List[str]
    interval: str
    num_iterations: int
    initial_capital: float = 10000.0
    position_size_pct: float = 5.0
    max_positions: int = 10
    tp_ratio: float = 0.1
    sl_ratio: float = 0.05
    use_perpetuals: bool = False
    fee_model: Dict[str, Any] = None
    slippage_model: Dict[str, Any] = None
    fill_policy: Dict[str, Any] = None
    strategy_config: Dict[str, Any] = None
    parallel_symbols: int = 4  # Number of symbols to process in parallel
    chunk_size: int = 1000  # Candles to process per chunk


class ConcurrentOrchestrator:
    """
    Concurrent backtest orchestrator with deterministic execution.
    
    Key features:
    - Parallel symbol processing with proper synchronization
    - Chunked data processing for memory efficiency
    - Deterministic results despite parallelization
    - Real-time progress updates
    """
    
    def __init__(self, config: BacktestConfig):
        self.config = config
        self.progress = 0
        self.results = {}
        self.errors = []
        
        # Initialize executors
        self.thread_executor = ThreadPoolExecutor(max_workers=config.parallel_symbols)
        self.process_executor = ProcessPoolExecutor(max_workers=2)
    
    async def run_backtest(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run concurrent backtest with progress tracking.
        """
        start_time = time.time()
        
        try:
            # Parse input configuration
            self._parse_input(input_data)
            
            # Initialize strategy
            strategy = self._initialize_strategy()
            
            # Prepare symbol data
            symbol_data = self._prepare_symbol_data(input_data.get('symbol_data', {}))
            
            # Create global timeline
            global_timeline = self._create_global_timeline(symbol_data)
            
            # Initialize portfolio
            portfolio = self._initialize_portfolio()
            
            # Run backtest with concurrency
            results = await self._run_concurrent_backtest(
                strategy, portfolio, symbol_data, global_timeline
            )
            
            # Calculate final metrics
            final_metrics = self._calculate_final_metrics(results, portfolio)
            
            # Prepare output
            output = self._prepare_output(final_metrics, start_time)
            
            return output
            
        except Exception as e:
            logger.error(f"Backtest failed: {str(e)}\n{traceback.format_exc()}")
            return {
                "status": "failed",
                "error": str(e),
                "traceback": traceback.format_exc(),
                "duration_seconds": time.time() - start_time
            }
        finally:
            # Cleanup
            self.thread_executor.shutdown(wait=True)
            self.process_executor.shutdown(wait=True)
    
    def _parse_input(self, input_data: Dict[str, Any]):
        """Parse and validate input configuration."""
        self.config.symbols = input_data.get('symbols', self.config.symbols)
        self.config.interval = input_data.get('interval', self.config.interval)
        self.config.num_iterations = input_data.get('num_iterations', self.config.num_iterations)
        self.config.strategy_config = input_data.get('strategy_config', {})
        
        # Update other parameters
        for key in ['initial_capital', 'position_size_pct', 'max_positions', 
                    'tp_ratio', 'sl_ratio', 'use_perpetuals']:
            if key in input_data:
                setattr(self.config, key, input_data[key])
    
    def _initialize_strategy(self) -> BaseStrategy:
        """Initialize strategy from configuration or code."""
        # Load strategy module dynamically
        strategy_name = self.config.strategy_config.get('name')
        
        # Try to load from user_strategies first
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                "user_strategy", 
                "/orchestrator/user_strategies/user_strategy.py"
            )
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Find strategy class
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and 
                        issubclass(attr, BaseStrategy) and 
                        attr != BaseStrategy):
                        return attr(**self.config.strategy_config.get('params', {}))
        except:
            pass
        
        # Fallback to built-in strategies
        from entities.strategies.concreteStrategies.PeakEmaReversalStrategy import PeakEMAReversalStrategy
        
        strategy_map = {
            "PeakEMAReversalStrategy": PeakEMAReversalStrategy,
        }
        
        strategy_class = strategy_map.get(strategy_name)
        if not strategy_class:
            raise ValueError(f"Unknown strategy: {strategy_name}")
        
        return strategy_class(**self.config.strategy_config.get('params', {}))
    
    def _prepare_symbol_data(self, raw_data: Dict[str, str]) -> Dict[str, pd.DataFrame]:
        """Prepare symbol data from JSON strings."""
        symbol_data = {}
        
        for symbol, json_data in raw_data.items():
            if symbol in self.config.symbols:
                df = pd.read_json(json_data, orient='split')
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                df.set_index('timestamp', inplace=True)
                symbol_data[symbol] = df
        
        return symbol_data
    
    def _create_global_timeline(self, symbol_data: Dict[str, pd.DataFrame]) -> pd.DatetimeIndex:
        """Create unified timeline across all symbols."""
        all_timestamps = []
        
        for df in symbol_data.values():
            all_timestamps.extend(df.index.tolist())
        
        # Create unique sorted timeline
        global_timeline = pd.DatetimeIndex(sorted(set(all_timestamps)))
        
        # Limit to num_iterations
        if len(global_timeline) > self.config.num_iterations:
            global_timeline = global_timeline[-self.config.num_iterations:]
        
        return global_timeline
    
    def _initialize_portfolio(self):
        """Initialize portfolio manager."""
        if self.config.use_perpetuals:
            return PerpPortfolioManager(
                initial_capital=self.config.initial_capital,
                position_size_pct=self.config.position_size_pct,
                max_positions=self.config.max_positions
            )
        else:
            return BasePortfolioManager(
                initial_capital=self.config.initial_capital,
                position_size_pct=self.config.position_size_pct,
                max_positions=self.config.max_positions
            )
    
    async def _run_concurrent_backtest(
        self,
        strategy: BaseStrategy,
        portfolio,
        symbol_data: Dict[str, pd.DataFrame],
        global_timeline: pd.DatetimeIndex
    ) -> Dict[str, Any]:
        """
        Run backtest with concurrent symbol processing.
        
        Key approach:
        1. Process timeline in chunks for memory efficiency
        2. Process multiple symbols in parallel per timestamp
        3. Maintain deterministic order for portfolio updates
        """
        results = {
            'trades': [],
            'equity_curve': [],
            'symbol_metrics': {}
        }
        
        # Process in chunks
        chunk_size = min(self.config.chunk_size, len(global_timeline))
        num_chunks = (len(global_timeline) + chunk_size - 1) // chunk_size
        
        for chunk_idx in range(num_chunks):
            start_idx = chunk_idx * chunk_size
            end_idx = min((chunk_idx + 1) * chunk_size, len(global_timeline))
            chunk_timeline = global_timeline[start_idx:end_idx]
            
            # Process chunk
            chunk_results = await self._process_chunk(
                strategy, portfolio, symbol_data, chunk_timeline
            )
            
            # Merge results
            results['trades'].extend(chunk_results['trades'])
            results['equity_curve'].extend(chunk_results['equity_curve'])
            
            # Update progress
            self.progress = (end_idx / len(global_timeline)) * 100
            self._report_progress()
        
        return results
    
    async def _process_chunk(
        self,
        strategy: BaseStrategy,
        portfolio,
        symbol_data: Dict[str, pd.DataFrame],
        chunk_timeline: pd.DatetimeIndex
    ) -> Dict[str, Any]:
        """Process a chunk of the timeline."""
        chunk_results = {
            'trades': [],
            'equity_curve': []
        }
        
        for timestamp in chunk_timeline:
            # Get data for all symbols at this timestamp
            timestamp_data = {}
            for symbol, df in symbol_data.items():
                if timestamp in df.index:
                    timestamp_data[symbol] = df.loc[timestamp]
            
            if not timestamp_data:
                continue
            
            # Generate signals for all symbols in parallel
            signals = await self._generate_signals_parallel(
                strategy, timestamp_data, symbol_data, timestamp
            )
            
            # Process signals sequentially to maintain determinism
            for symbol, signal in sorted(signals.items()):
                if signal != 0:
                    # Create trade proposal
                    proposal = self._create_trade_proposal(
                        symbol, signal, timestamp_data[symbol], timestamp
                    )
                    
                    # Execute trade
                    if proposal:
                        trade = portfolio.execute_trade(proposal)
                        if trade:
                            chunk_results['trades'].append(trade)
            
            # Update portfolio state
            portfolio.update_positions(timestamp_data, timestamp)
            
            # Record equity
            chunk_results['equity_curve'].append({
                'timestamp': timestamp,
                'equity': portfolio.get_total_equity(),
                'cash': portfolio.cash,
                'positions': len(portfolio.open_positions)
            })
        
        return chunk_results
    
    async def _generate_signals_parallel(
        self,
        strategy: BaseStrategy,
        timestamp_data: Dict[str, Any],
        symbol_data: Dict[str, pd.DataFrame],
        timestamp: pd.Timestamp
    ) -> Dict[str, int]:
        """Generate signals for multiple symbols in parallel."""
        loop = asyncio.get_event_loop()
        
        # Create tasks for each symbol
        tasks = []
        for symbol, candle in timestamp_data.items():
            # Get historical data for the symbol
            hist_data = symbol_data[symbol].loc[:timestamp]
            
            # Run signal generation in thread pool
            task = loop.run_in_executor(
                self.thread_executor,
                self._generate_signal_for_symbol,
                strategy, symbol, hist_data, candle
            )
            tasks.append((symbol, task))
        
        # Wait for all signals
        signals = {}
        for symbol, task in tasks:
            try:
                signal = await task
                signals[symbol] = signal
            except Exception as e:
                logger.error(f"Signal generation failed for {symbol}: {e}")
                signals[symbol] = 0
        
        return signals
    
    def _generate_signal_for_symbol(
        self,
        strategy: BaseStrategy,
        symbol: str,
        hist_data: pd.DataFrame,
        current_candle: pd.Series
    ) -> int:
        """Generate signal for a single symbol."""
        try:
            # Prepare data in format expected by strategy
            signal = strategy.generate_signal(symbol, hist_data, current_candle)
            return signal
        except Exception as e:
            logger.error(f"Failed to generate signal for {symbol}: {e}")
            return 0
    
    def _create_trade_proposal(
        self,
        symbol: str,
        signal: int,
        candle: pd.Series,
        timestamp: pd.Timestamp
    ) -> Optional[TradeProposal]:
        """Create trade proposal from signal."""
        if signal == 0:
            return None
        
        side = "buy" if signal > 0 else "sell"
        
        return TradeProposal(
            symbol=symbol,
            side=side,
            quantity=abs(signal),
            price=candle['close'],
            timestamp=timestamp,
            sl_price=candle['close'] * (1 - self.config.sl_ratio) if side == "buy" else candle['close'] * (1 + self.config.sl_ratio),
            tp_price=candle['close'] * (1 + self.config.tp_ratio) if side == "buy" else candle['close'] * (1 - self.config.tp_ratio)
        )
    
    def _calculate_final_metrics(
        self,
        results: Dict[str, Any],
        portfolio
    ) -> Dict[str, Any]:
        """Calculate final performance metrics."""
        equity_curve = pd.DataFrame(results['equity_curve'])
        
        if equity_curve.empty:
            return self._empty_metrics()
        
        # Calculate returns
        equity_curve['returns'] = equity_curve['equity'].pct_change()
        
        # Calculate metrics
        total_return = (equity_curve['equity'].iloc[-1] / self.config.initial_capital - 1) * 100
        
        # Sharpe ratio (annualized)
        sharpe_ratio = self._calculate_sharpe_ratio(equity_curve['returns'])
        
        # Max drawdown
        max_drawdown = self._calculate_max_drawdown(equity_curve['equity'])
        
        # Win rate
        trades = results['trades']
        winning_trades = [t for t in trades if t.get('pnl', 0) > 0]
        win_rate = len(winning_trades) / len(trades) * 100 if trades else 0
        
        return {
            'total_return': total_return,
            'sharpe_ratio': sharpe_ratio,
            'max_drawdown': max_drawdown,
            'win_rate': win_rate,
            'total_trades': len(trades),
            'winning_trades': len(winning_trades),
            'losing_trades': len(trades) - len(winning_trades),
            'final_equity': equity_curve['equity'].iloc[-1],
            'equity_curve': equity_curve.to_dict('records'),
            'trades': trades
        }
    
    @staticmethod
    @jit(nopython=True)
    def _calculate_sharpe_ratio_numba(returns: np.ndarray) -> float:
        """Calculate Sharpe ratio using Numba for speed."""
        if len(returns) < 2:
            return 0.0
        
        # Remove NaN values
        valid_returns = returns[~np.isnan(returns)]
        if len(valid_returns) < 2:
            return 0.0
        
        mean_return = np.mean(valid_returns)
        std_return = np.std(valid_returns)
        
        if std_return == 0:
            return 0.0
        
        # Annualize (assuming daily returns)
        sharpe = (mean_return / std_return) * np.sqrt(252)
        
        return sharpe
    
    def _calculate_sharpe_ratio(self, returns: pd.Series) -> float:
        """Calculate Sharpe ratio."""
        return float(self._calculate_sharpe_ratio_numba(returns.values))
    
    @staticmethod
    @jit(nopython=True)
    def _calculate_max_drawdown_numba(equity: np.ndarray) -> float:
        """Calculate maximum drawdown using Numba."""
        if len(equity) < 2:
            return 0.0
        
        peak = equity[0]
        max_dd = 0.0
        
        for i in range(1, len(equity)):
            if equity[i] > peak:
                peak = equity[i]
            
            drawdown = (peak - equity[i]) / peak * 100
            if drawdown > max_dd:
                max_dd = drawdown
        
        return max_dd
    
    def _calculate_max_drawdown(self, equity: pd.Series) -> float:
        """Calculate maximum drawdown."""
        return float(self._calculate_max_drawdown_numba(equity.values))
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics structure."""
        return {
            'total_return': 0,
            'sharpe_ratio': 0,
            'max_drawdown': 0,
            'win_rate': 0,
            'total_trades': 0,
            'winning_trades': 0,
            'losing_trades': 0,
            'final_equity': self.config.initial_capital,
            'equity_curve': [],
            'trades': []
        }
    
    def _prepare_output(self, metrics: Dict[str, Any], start_time: float) -> Dict[str, Any]:
        """Prepare final output."""
        return {
            'status': 'success',
            'run_id': self._generate_run_id(),
            'start_time': datetime.fromtimestamp(start_time).isoformat(),
            'end_time': datetime.utcnow().isoformat(),
            'duration_seconds': time.time() - start_time,
            'portfolio_metrics': metrics,
            'symbol_metrics': self._calculate_symbol_metrics(metrics['trades']),
            'trades': metrics['trades'],
            'total_return': metrics['total_return'],
            'sharpe_ratio': metrics['sharpe_ratio'],
            'max_drawdown': metrics['max_drawdown'],
            'win_rate': metrics['win_rate'],
            'errors': self.errors,
            'warnings': [],
            'config': {
                'symbols': self.config.symbols,
                'interval': self.config.interval,
                'num_iterations': self.config.num_iterations,
                'initial_capital': self.config.initial_capital
            }
        }
    
    def _calculate_symbol_metrics(self, trades: List[Dict]) -> Dict[str, Dict[str, Any]]:
        """Calculate per-symbol metrics."""
        symbol_metrics = {}
        
        for trade in trades:
            symbol = trade['symbol']
            if symbol not in symbol_metrics:
                symbol_metrics[symbol] = {
                    'total_trades': 0,
                    'winning_trades': 0,
                    'total_pnl': 0,
                    'win_rate': 0
                }
            
            symbol_metrics[symbol]['total_trades'] += 1
            if trade.get('pnl', 0) > 0:
                symbol_metrics[symbol]['winning_trades'] += 1
            symbol_metrics[symbol]['total_pnl'] += trade.get('pnl', 0)
        
        # Calculate win rates
        for symbol, metrics in symbol_metrics.items():
            if metrics['total_trades'] > 0:
                metrics['win_rate'] = metrics['winning_trades'] / metrics['total_trades'] * 100
        
        return symbol_metrics
    
    def _generate_run_id(self) -> str:
        """Generate unique run ID."""
        data = {
            'symbols': self.config.symbols,
            'timestamp': time.time()
        }
        return hashlib.sha256(
            json.dumps(data, sort_keys=True).encode()
        ).hexdigest()[:16]
    
    def _report_progress(self):
        """Report progress to stderr."""
        progress_msg = {
            'type': 'progress',
            'progress': self.progress,
            'timestamp': datetime.utcnow().isoformat()
        }
        print(json.dumps(progress_msg), file=sys.stderr)


async def main():
    """Main entry point for orchestrator."""
    # Read input from stdin
    input_json = sys.stdin.read()
    
    try:
        input_data = json.loads(input_json)
    except json.JSONDecodeError as e:
        error_output = {
            'status': 'failed',
            'error': f'Invalid JSON input: {str(e)}'
        }
        print(json.dumps(error_output))
        sys.exit(1)
    
    # Create default configuration
    config = BacktestConfig(
        symbols=input_data.get('symbols', []),
        interval=input_data.get('interval', '1h'),
        num_iterations=input_data.get('num_iterations', 100)
    )
    
    # Create and run orchestrator
    orchestrator = ConcurrentOrchestrator(config)
    result = await orchestrator.run_backtest(input_data)
    
    # Output result as JSON
    print(json.dumps(result, default=str))


if __name__ == "__main__":
    asyncio.run(main())