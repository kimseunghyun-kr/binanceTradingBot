import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import os
import glob
import re
from binance.client import Client
import mplfinance as mpf
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def parse_transactions(file_path):
    """
    Parses the transaction text file and converts it into a DataFrame.
    Also extracts the Add.Buy percentage and backtest period from the header.
    """
    transactions = []
    current_transaction = {}
    add_buy_percent = None
    backtest_start_date = None
    backtest_end_date = None
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            
            # Extract backtest period information
            if line.startswith("Start Date:"):
                backtest_start_date = line.split(":", 1)[1].strip()
                continue
            elif line.startswith("End Date:"):
                backtest_end_date = line.split(":", 1)[1].strip()
                continue
            elif line.startswith("Analysis Generated:"):
                continue  # Skip this line
            
            # Extract Add.Buy percentage from header
            if line.startswith("===") and "Add.Buy=" in line:
                match = re.search(r'Add\.Buy=(\d+\.?\d*)%', line)
                if match:
                    add_buy_percent = float(match.group(1)) / 100  # Convert to decimal
            
            if line.startswith("Symbol:"):
                if current_transaction:
                    try:
                        current_transaction['Entry Time'] = pd.to_datetime(current_transaction['Entry Time'])
                        current_transaction['Exit Time'] = pd.to_datetime(current_transaction['Exit Time'])
                    except Exception as e:
                        print(f"Date parsing error for transaction: {current_transaction}. Error: {e}")
                        current_transaction = {}
                        continue
                    transactions.append(current_transaction)
                current_transaction = {'Symbol': line.split(":")[1].strip()}
            elif ":" in line and not line.startswith("==="):
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()
                if key in ['Entry Price', 'TP Price', 'SL Price', 'Exit Price']:
                    try:
                        current_transaction[key] = float(value)
                    except ValueError:
                        current_transaction[key] = None
                elif key == 'Return':
                    try:
                        current_transaction[key] = float(value.replace('%', '')) / 100
                    except ValueError:
                        current_transaction[key] = None
                else:
                    current_transaction[key] = value
    
    if current_transaction:
        try:
            current_transaction['Entry Time'] = pd.to_datetime(current_transaction['Entry Time'])
            current_transaction['Exit Time'] = pd.to_datetime(current_transaction['Exit Time'])
            transactions.append(current_transaction)
        except Exception as e:
            print(f"Date parsing error for last transaction: {current_transaction}. Error: {e}")

    df = pd.DataFrame(transactions)
    if 'Return' not in df.columns or 'Entry Time' not in df.columns or 'Exit Time' not in df.columns:
        print("Warning: Essential columns ('Return', 'Entry Time', 'Exit Time') not found. Cannot proceed.")
        return pd.DataFrame(), add_buy_percent, None, None

    df = df.dropna(subset=['Return', 'Entry Time', 'Exit Time'])
    df = df.sort_values(by='Entry Time').reset_index(drop=True)
    
    return df, add_buy_percent, backtest_start_date, backtest_end_date


def group_positions(transactions_df):
    """
    Groups transactions by Symbol and Exit Time to identify positions.
    Each position consists of initial buy + additional buy (if any).
    """
    positions = []
    
    # Group by Symbol and Exit Time
    grouped = transactions_df.groupby(['Symbol', 'Exit Time'])
    
    for (symbol, exit_time), group in grouped:
        # Sort by entry time first, then by entry price (descending)
        # Higher price is the initial buy (additional buy happens after price drop)
        group_sorted = group.sort_values(['Entry Time', 'Entry Price'], ascending=[True, False])
        
        position = {
            'symbol': symbol,
            'exit_time': exit_time,
            'trades': group_sorted.to_dict('records'),
            'initial_entry': group_sorted.iloc[0],
            'additional_entries': group_sorted.iloc[1:].to_dict('records') if len(group_sorted) > 1 else []
        }
        positions.append(position)
    
    # Sort positions by initial entry time
    positions.sort(key=lambda x: x['initial_entry']['Entry Time'])
    
    return positions


def simulate_portfolio_with_positions(positions, initial_capital=1.0, position_size=0.25, risk_free_rate_annual=0.0, backtest_start_date=None, backtest_end_date=None):
    """
    Simulates portfolio performance with the new position management rules:
    - Initial buy: 25% of initial capital (fixed)
    - Additional buy: 25% of initial capital (fixed)
    - Maximum position size: 50% per position
    - Total portfolio allocation cannot exceed 100%
    """
    current_portfolio_value = initial_capital
    current_allocations = {}  # Track current allocations by position
    portfolio_timeline = []
    taken_positions = []
    
    # Fixed capital amounts based on initial capital
    fixed_position_capital = initial_capital * position_size  # Always 0.25
    
    # Add initial point
    min_entry_time = min(pos['initial_entry']['Entry Time'] for pos in positions)
    portfolio_timeline.append({
        'time': min_entry_time - pd.Timedelta(seconds=1), 
        'capital': current_portfolio_value,
        'total_allocation': 0.0
    })
    
    # Create a list of all events (entries and exits)
    events = []
    
    for pos_idx, position in enumerate(positions):
        # Initial entry event
        events.append({
            'time': position['initial_entry']['Entry Time'],
            'type': 'entry',
            'subtype': 'initial',
            'position_idx': pos_idx,
            'trade': position['initial_entry']
        })
        
        # Additional entry events
        for add_trade in position['additional_entries']:
            events.append({
                'time': add_trade['Entry Time'],
                'type': 'entry',
                'subtype': 'additional',
                'position_idx': pos_idx,
                'trade': add_trade
            })
        
        # Exit event
        events.append({
            'time': position['exit_time'],
            'type': 'exit',
            'position_idx': pos_idx
        })
    
    # Sort events by time
    events.sort(key=lambda x: x['time'])
    
    # Process events chronologically
    active_positions = {}  # position_idx -> position data
    
    for event in events:
        current_time = event['time']
        
        if event['type'] == 'entry':
            pos_idx = event['position_idx']
            position = positions[pos_idx]
            
            # Calculate current total allocation
            total_allocation = sum(pos['allocation'] for pos in active_positions.values())
            
            if event['subtype'] == 'initial':
                # Check if we can allocate 25% for initial buy
                if total_allocation + position_size <= 1.0 + 1e-9:
                    # Take the position with fixed capital amount
                    capital_for_trade = fixed_position_capital  # Use fixed amount
                    
                    active_positions[pos_idx] = {
                        'position': position,
                        'allocation': position_size,
                        'initial_capital': capital_for_trade,
                        'initial_price': event['trade']['Entry Price'],
                        'trades_taken': [event['trade']],
                        'total_capital_invested': capital_for_trade
                    }
                    
                    taken_positions.append({
                        'position_idx': pos_idx,
                        'position': position,
                        'trades_taken': [event['trade']]
                    })
                    
            elif event['subtype'] == 'additional':
                # Check if this position exists and we can add 25% more
                if pos_idx in active_positions and total_allocation + position_size <= 1.0 + 1e-9:
                    # Add to existing position with fixed capital amount
                    additional_capital = fixed_position_capital  # Use fixed amount
                    active_positions[pos_idx]['allocation'] += position_size
                    active_positions[pos_idx]['total_capital_invested'] += additional_capital
                    active_positions[pos_idx]['trades_taken'].append(event['trade'])
                    
                    # Update taken_positions
                    for taken_pos in taken_positions:
                        if taken_pos['position_idx'] == pos_idx:
                            taken_pos['trades_taken'].append(event['trade'])
                            break
        
        elif event['type'] == 'exit':
            pos_idx = event['position_idx']
            
            if pos_idx in active_positions:
                active_pos = active_positions[pos_idx]
                position = active_pos['position']
                
                # Calculate returns for the position
                total_return = 0.0
                for trade in active_pos['trades_taken']:
                    # Each trade's capital weight in the position
                    trade_weight = position_size / active_pos['allocation']
                    total_return += trade['Return'] * trade_weight
                
                # Calculate profit/loss
                profit_loss = active_pos['total_capital_invested'] * total_return
                current_portfolio_value += profit_loss
                
                # Remove from active positions
                del active_positions[pos_idx]
                
                # Record portfolio value at exit
                portfolio_timeline.append({
                    'time': current_time,
                    'capital': current_portfolio_value,
                    'total_allocation': sum(pos['allocation'] for pos in active_positions.values())
                })
    
    # Create DataFrame from portfolio timeline
    pnl_df = pd.DataFrame(portfolio_timeline)
    if not pnl_df.empty:
        pnl_df = pnl_df.sort_values(by='time').drop_duplicates(subset=['time'], keep='last')
        pnl_df.reset_index(drop=True, inplace=True)
    
    # Calculate metrics
    if len(pnl_df) < 2:
        return np.nan, np.nan, np.nan, 0, pnl_df, taken_positions
    
    # Calculate performance metrics
    metrics = calculate_performance_metrics(pnl_df, risk_free_rate_annual, backtest_start_date, backtest_end_date)
    
    return metrics['annual_return'], metrics['sharpe_ratio'], metrics['mdd'], metrics['turnover'], pnl_df, taken_positions


def calculate_performance_metrics(pnl_df, risk_free_rate_annual=0.0, backtest_start_date=None, backtest_end_date=None):
    """
    Calculates performance metrics from the P&L DataFrame.
    Uses actual backtest period if provided, otherwise infers from data.
    """
    if pnl_df.empty or len(pnl_df) < 2:
        return {
            'annual_return': np.nan,
            'sharpe_ratio': np.nan,
            'mdd': 0.0,
            'turnover': 0
        }
    
    cumulative_pnl_series = pnl_df['capital']
    time_series = pnl_df['time']
    
    # Use provided backtest period or infer from data
    if backtest_start_date and backtest_end_date:
        start_date = pd.to_datetime(backtest_start_date)
        end_date = pd.to_datetime(backtest_end_date)
        print(f"Using actual backtest period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    else:
        start_date = time_series.min()
        end_date = time_series.max()
        print(f"Using inferred period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    # Duration calculation
    total_duration_days = (end_date - start_date).days
    total_years = max(total_duration_days / 365.25, 1/365.25)
    
    # Annual Return (Simple/Arithmetic Average)
    initial_value = cumulative_pnl_series.iloc[0]
    final_value = cumulative_pnl_series.iloc[-1]
    
    if total_years > 0 and initial_value > 0:
        total_return = (final_value - initial_value) / initial_value
        annual_return = total_return / total_years  # Simple arithmetic average
    else:
        annual_return = 0.0
    
    # Maximum Drawdown
    roll_max = cumulative_pnl_series.cummax()
    drawdown = cumulative_pnl_series / roll_max - 1.0
    mdd = drawdown.min()
    
    # Sharpe Ratio
    sharpe_ratio = np.nan
    if len(pnl_df) >= 2:
        # Resample to daily returns
        pnl_daily = pnl_df.set_index('time')['capital'].resample('D').last().ffill()
        if len(pnl_daily) >= 2:
            daily_returns = pnl_daily.pct_change().dropna()
            if not daily_returns.empty and daily_returns.std() != 0:
                # Use already calculated CAGR for more accuracy
                # Sharpe = (CAGR - Risk Free Rate) / Annualized Volatility
                annualized_volatility = daily_returns.std() * np.sqrt(365)
                sharpe_ratio = (annual_return - risk_free_rate_annual) / annualized_volatility
    
    # Turnover (number of positions closed per year)
    num_exits = len(pnl_df[pnl_df['time'] > pnl_df['time'].min()])
    turnover = num_exits / total_years if total_years > 0 else num_exits
    
    return {
        'annual_return': annual_return,
        'sharpe_ratio': sharpe_ratio,
        'mdd': mdd,
        'turnover': turnover
    }


def analyze_yearly_performance(pnl_df, taken_positions, year, risk_free_rate_annual=0.0, backtest_start_date=None, backtest_end_date=None):
    """
    Analyzes performance for a specific year.
    Uses actual backtest period if provided.
    """
    if pnl_df.empty:
        return np.nan, np.nan, np.nan, 0
    
    year_start = pd.Timestamp(f'{year}-01-01')
    year_end = pd.Timestamp(f'{year}-12-31 23:59:59')
    
    # Adjust year boundaries based on actual backtest period
    if backtest_start_date:
        actual_start = pd.to_datetime(backtest_start_date)
        if year_start < actual_start:
            year_start = actual_start
    
    if backtest_end_date:
        actual_end = pd.to_datetime(backtest_end_date)
        if year_end > actual_end:
            year_end = actual_end
    
    # Get PnL before year start
    pnl_before = pnl_df[pnl_df['time'] < year_start]
    start_capital = pnl_before['capital'].iloc[-1] if not pnl_before.empty else 1.0
    
    # Get PnL for the year
    year_pnl = pnl_df[(pnl_df['time'] >= year_start) & (pnl_df['time'] <= year_end)].copy()
    
    if year_pnl.empty:
        # No activity in this year
        return 0.0, np.nan, 0.0, 0
    
    # Prepend start capital
    start_row = pd.DataFrame([{'time': year_start - pd.Timedelta(seconds=1), 'capital': start_capital}])
    year_pnl_metrics = pd.concat([start_row, year_pnl], ignore_index=True)
    year_pnl_metrics = year_pnl_metrics.sort_values(by='time').reset_index(drop=True)
    
    # Calculate yearly metrics with proper period
    year_start_str = year_start.strftime('%Y-%m-%d')
    year_end_str = year_end.strftime('%Y-%m-%d')
    metrics = calculate_performance_metrics(year_pnl_metrics, risk_free_rate_annual, year_start_str, year_end_str)
    
    # Count positions closed in this year
    positions_closed = 0
    for taken_pos in taken_positions:
        if taken_pos['position']['exit_time'].year == year:
            positions_closed += 1
    
    return metrics['annual_return'], metrics['sharpe_ratio'], metrics['mdd'], positions_closed


def plot_pnl(pnl_df, output_directory, title="Portfolio Performance"):
    """
    Plots the cumulative PnL chart.
    """
    plt.figure(figsize=(12, 6))
    plt.plot(pnl_df['time'], pnl_df['capital'], marker='.', linestyle='-', linewidth=2)
    plt.title(title, fontsize=14)
    plt.xlabel('Date', fontsize=12)
    plt.ylabel('Portfolio Value (Initial = 1.0)', fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    
    # Add horizontal line at 1.0
    plt.axhline(y=1.0, color='r', linestyle='--', alpha=0.5)
    
    plt.tight_layout()
    
    # Save plot
    plot_path = os.path.join(output_directory, "portfolio_performance.png")
    plt.savefig(plot_path, dpi=150, bbox_inches='tight')
    print(f"Portfolio performance chart saved to {plot_path}")
    plt.close()


def write_true_transactions(taken_positions, output_path):
    """
    Writes the true transactions (actually taken trades) to a file.
    """
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write("=== True Transactions (Actually Taken Trades) ===\n\n")
        
        position_count = 0
        for taken_pos in taken_positions:
            position = taken_pos['position']
            trades = taken_pos['trades_taken']
            
            position_count += 1
            f.write(f"Position #{position_count}\n")
            f.write(f"Symbol: {position['symbol']}\n")
            f.write(f"Number of trades in position: {len(trades)}\n")
            f.write(f"Exit Time: {position['exit_time']}\n")
            f.write("-" * 50 + "\n")
            
            for i, trade in enumerate(trades):
                trade_type = "Initial Buy" if i == 0 else f"Additional Buy #{i}"
                f.write(f"\n{trade_type}:\n")
                f.write(f"Entry Time: {trade['Entry Time']}\n")
                f.write(f"Entry Price: {trade['Entry Price']:.8f}\n")
                f.write(f"Exit Price: {trade['Exit Price']:.8f}\n")
                f.write(f"Return: {trade['Return']*100:.2f}%\n")
                f.write(f"Outcome: {trade['Outcome']}\n")
            
            f.write("\n" + "="*50 + "\n\n")
    
    print(f"True transactions saved to {output_path}")


def create_position_charts(taken_positions, output_directory, add_buy_percent):
    """
    Creates candlestick charts for each position using Binance API.
    """
    # Initialize Binance client
    api_key = os.getenv('BINANCE_API_KEY')
    api_secret = os.getenv('BINANCE_API_SECRET')
    
    if not api_key or not api_secret:
        print("Error: Binance API credentials not found in .env file")
        return
    
    try:
        client = Client(api_key, api_secret)
    except Exception as e:
        print(f"Error initializing Binance client: {e}")
        return
    
    # Create charts directory
    charts_dir = os.path.join(output_directory, "position_charts")
    os.makedirs(charts_dir, exist_ok=True)
    
    for pos_idx, taken_pos in enumerate(taken_positions):
        position = taken_pos['position']
        trades = taken_pos['trades_taken']
        symbol = position['symbol']
        
        try:
            # Get time range
            earliest_entry = min(trade['Entry Time'] for trade in trades)
            exit_time = position['exit_time']
            
            # Calculate time range for klines
            start_time = earliest_entry - timedelta(weeks=20)
            end_time = min(exit_time + timedelta(weeks=2), pd.Timestamp.now())
            
            # Convert to milliseconds
            start_ms = int(start_time.timestamp() * 1000)
            end_ms = int(end_time.timestamp() * 1000)
            
            # Fetch weekly klines
            print(f"Fetching data for {symbol} position #{pos_idx+1}...")
            klines = client.get_historical_klines(
                symbol=symbol,
                interval=Client.KLINE_INTERVAL_1WEEK,
                start_str=start_ms,
                end_str=end_ms
            )
            
            if not klines:
                print(f"No data available for {symbol}")
                continue
            
            # Convert to DataFrame
            df = pd.DataFrame(klines, columns=[
                'timestamp', 'open', 'high', 'low', 'close', 'volume',
                'close_time', 'quote_asset_volume', 'number_of_trades',
                'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
            ])
            
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            
            # Convert to float
            for col in ['open', 'high', 'low', 'close', 'volume']:
                df[col] = df[col].astype(float)
            
            # Create the chart
            fig, axes = mpf.plot(
                df[['open', 'high', 'low', 'close', 'volume']],
                type='candle',
                style='yahoo',
                volume=True,
                returnfig=True,
                figsize=(14, 8),
                title=dict(title=f"{symbol} Position #{pos_idx+1}", fontsize=16),
                panel_ratios=(3,1)
            )
            
            ax_price = axes[0]
            
            # Plot entry and exit points
            for i, trade in enumerate(trades):
                # Find nearest candle indices
                entry_time = trade['Entry Time']
                entry_idx = df.index.get_indexer([entry_time], method='nearest')[0]
                exit_idx = df.index.get_indexer([exit_time], method='nearest')[0]
                
                # Entry marker
                entry_color = 'green' if i == 0 else 'blue'
                entry_label = "Initial Buy" if i == 0 else f"Add Buy (-{add_buy_percent*100:.1f}%)"
                ax_price.scatter(entry_idx, trade['Entry Price'], color=entry_color, s=150, 
                               marker='^', label=entry_label, zorder=5)
                ax_price.text(entry_idx, trade['Entry Price'], f"{trade['Entry Price']:.2f}", 
                             ha='center', va='bottom', fontsize=9)
                
                # Exit marker - always red
                ax_price.scatter(exit_idx, trade['Exit Price'], color='red', s=150, 
                               marker='v', zorder=5)
                
                # Connect entry and exit
                ax_price.plot([entry_idx, exit_idx], [trade['Entry Price'], trade['Exit Price']], 
                             'k--', alpha=0.5, linewidth=1)
            
            # Add exit price text (only once)
            ax_price.text(exit_idx, trades[0]['Exit Price'], f"{trades[0]['Exit Price']:.2f}", 
                         ha='center', va='top', fontsize=9)
            
            # Calculate position return
            position_return = sum(trade['Return'] for trade in trades) / len(trades)
            
            # Add position info
            info_text = f"Position Return: {position_return*100:.2f}%\n"
            info_text += f"Trades: {len(trades)} ({'Initial' if len(trades) == 1 else 'Initial + Add'})\n"
            info_text += f"Exit: {exit_time.strftime('%Y-%m-%d')}"
            
            ax_price.text(0.02, 0.98, info_text, transform=ax_price.transAxes,
                         bbox=dict(boxstyle='round', facecolor='white', alpha=0.8),
                         verticalalignment='top', fontsize=10)
            
            # Add legend
            if len(trades) > 1:
                ax_price.legend(loc='upper right')
            
            # Save chart
            filename = f"position_{pos_idx+1:03d}_{symbol}_{exit_time.strftime('%Y%m%d')}.png"
            filepath = os.path.join(charts_dir, filename)
            plt.savefig(filepath, dpi=150, bbox_inches='tight')
            plt.close()
            
            print(f"Chart saved: {filepath}")
            
        except Exception as e:
            print(f"Error creating chart for position #{pos_idx+1} ({symbol}): {e}")
            plt.close()
            continue
    
    print(f"\nChart generation complete. Charts saved in {charts_dir}")


def analyze_single_add_buy_folder(target_directory, create_charts=True):
    """Analyze a single add_buy folder"""
    transaction_files = glob.glob(os.path.join(target_directory, "backtest_transactions*.txt"))
    
    if not transaction_files:
        print(f"Error: No transaction file found in {target_directory}")
        return False
    
    file_path = transaction_files[0]
    if len(transaction_files) > 1:
        print(f"Warning: Multiple transaction files found. Using: {file_path}")
    
    print(f"\nAnalyzing file: {file_path}")
    
    # Parse transactions
    transactions_df, add_buy_percent, backtest_start_date, backtest_end_date = parse_transactions(file_path)
    
    if transactions_df.empty:
        print("Error: Could not parse transactions.")
        return False
    
    print(f"Successfully parsed {len(transactions_df)} transactions")
    print(f"Additional buy trigger: {add_buy_percent*100:.1f}% drop")
    if backtest_start_date and backtest_end_date:
        print(f"Backtest period: {backtest_start_date} to {backtest_end_date}")
    print()
    
    # Group into positions
    positions = group_positions(transactions_df)
    print(f"Identified {len(positions)} potential positions")
    
    # Simulate portfolio
    print("\nSimulating portfolio with position-based strategy...")
    print("- Initial buy: 25% of initial capital (fixed)")
    print("- Additional buy: 25% of initial capital (fixed)")
    print("- Maximum allocation: 100% of portfolio\n")
    
    (annual_return, sharpe_ratio, mdd, turnover, 
     pnl_df, taken_positions) = simulate_portfolio_with_positions(positions, backtest_start_date=backtest_start_date, backtest_end_date=backtest_end_date)
    
    if pnl_df.empty or pd.isna(annual_return):
        print("Error: Could not simulate portfolio")
        return False
    
    # Display results
    print("=== PORTFOLIO PERFORMANCE ===")
    print(f"Positions taken: {len(taken_positions)} / {len(positions)} potential")
    print(f"Annualized Return: {annual_return:.2%}")
    print(f"Annualized Sharpe Ratio: {sharpe_ratio:.2f}")
    print(f"Maximum Drawdown: {mdd:.2%}")
    print(f"Turnover (positions/year): {turnover:.2f}")
    
    # Save detailed results
    results_path = os.path.join(target_directory, "portfolio_analysis_results.txt")
    with open(results_path, 'w', encoding='utf-8') as f:
        f.write("=== PORTFOLIO ANALYSIS RESULTS ===\n")
        f.write(f"Analysis Date: {datetime.now()}\n")
        f.write(f"Source File: {file_path}\n")
        if backtest_start_date and backtest_end_date:
            f.write(f"Backtest Period: {backtest_start_date} to {backtest_end_date}\n")
        f.write(f"Strategy: 25% of initial capital + 25% of initial capital on {add_buy_percent*100:.1f}% drop\n")
        f.write("Note: All position sizes are fixed at 25% of initial capital (0.25)\n\n")
        
        f.write("Overall Performance:\n")
        f.write(f"  Positions taken: {len(taken_positions)} / {len(positions)} potential\n")
        f.write(f"  Annualized Return: {annual_return:.2%}\n")
        f.write(f"  Annualized Sharpe Ratio: {sharpe_ratio:.2f}\n")
        f.write(f"  Maximum Drawdown: {mdd:.2%}\n")
        f.write(f"  Turnover: {turnover:.2f} positions/year\n\n")
        
        # Yearly analysis
        f.write("Yearly Performance:\n")
        years = [2021, 2022, 2023, 2024, 2025]
        for year in years:
            y_return, y_sharpe, y_mdd, y_positions = analyze_yearly_performance(
                pnl_df, taken_positions, year, backtest_start_date=backtest_start_date, backtest_end_date=backtest_end_date
            )
            f.write(f"  {year}:\n")
            f.write(f"    Return: {y_return:.2%}\n")
            f.write(f"    Sharpe: {y_sharpe:.2f}\n")
            f.write(f"    MDD: {y_mdd:.2%}\n")
            f.write(f"    Positions closed: {y_positions}\n")
    
    print(f"\nDetailed results saved to {results_path}")
    
    # Generate portfolio performance chart
    plot_pnl(pnl_df, target_directory)
    
    # Write true transactions
    true_tx_path = os.path.join(target_directory, "true_transactions.txt")
    write_true_transactions(taken_positions, true_tx_path)
    
    # Create position charts (optional)
    if taken_positions and create_charts:
        print("\nGenerating position charts...")
        create_position_charts(taken_positions, target_directory, add_buy_percent)
    elif taken_positions and not create_charts:
        print("\nSkipping position charts generation (disabled by user)")
    
    return True


def analyze_all_add_buy_folders(timeframe, tp_percent, sl_percent):
    """Analyze all add_buy folders within a TP/SL combination"""
    tp_folder = f"{tp_percent:.1f}%"
    sl_folder = f"{sl_percent:.1f}%"
    
    base_directory = os.path.join("backtest_results", timeframe, tp_folder, sl_folder)
    
    if not os.path.isdir(base_directory):
        print(f"Error: Directory not found: {base_directory}")
        print("Please ensure the backtest results exist.")
        return
    
    # Find all add_buy folders
    add_buy_folders = [f for f in os.listdir(base_directory) 
                      if os.path.isdir(os.path.join(base_directory, f)) and f.startswith("add_buy_")]
    
    if not add_buy_folders:
        print(f"No add_buy folders found in {base_directory}")
        return
    
    # Sort folders by add_buy percentage
    add_buy_folders.sort(key=lambda x: float(x.replace("add_buy_", "").replace("pct", "")))
    
    print(f"\nFound {len(add_buy_folders)} add_buy folders to analyze:")
    for folder in add_buy_folders:
        print(f"  - {folder}")
    
    # Analyze each folder
    for folder in add_buy_folders:
        print(f"\n{'='*60}")
        print(f"Analyzing: {folder}")
        print(f"{'='*60}")
        
        target_directory = os.path.join(base_directory, folder)
        success = analyze_single_add_buy_folder(target_directory)
        
        if success:
            print(f"\n✓ Analysis complete for {folder}")
        else:
            print(f"\n✗ Analysis failed for {folder}")
    
    print(f"\n{'='*60}")
    print(f"All analyses complete!")
    print(f"{'='*60}")


def get_user_inputs():
    """Gets and validates user inputs for timeframe, TP, and SL."""
    while True:
        timeframe = input("Enter timeframe (1d or 1w): ").strip().lower()
        if timeframe in ['1d', '1w']:
            break
        print("Invalid timeframe. Please enter '1d' or '1w'.")

    while True:
        try:
            tp_percent = float(input("Enter Take Profit percentage (e.g., 11.0): ").strip())
            if tp_percent > 0:
                break
            print("Take Profit percentage must be positive.")
        except ValueError:
            print("Invalid input. Please enter a numeric value for TP percentage.")

    while True:
        try:
            sl_percent = float(input("Enter Stop Loss percentage (e.g., 12.5): ").strip())
            if sl_percent > 0:
                break
            print("Stop Loss percentage must be positive.")
        except ValueError:
            print("Invalid input. Please enter a numeric value for SL percentage.")
    
    while True:
        analyze_all = input("Analyze all add_buy folders? (y/n): ").strip().lower()
        if analyze_all in ['y', 'n']:
            break
        print("Please enter 'y' for yes or 'n' for no.")
            
    return timeframe, tp_percent, sl_percent, analyze_all == 'y'


# Main execution
if __name__ == "__main__":
    timeframe, tp_percent, sl_percent, analyze_all = get_user_inputs()
    
    if analyze_all:
        # Analyze all add_buy folders within the TP/SL combination
        analyze_all_add_buy_folders(timeframe, tp_percent, sl_percent)
    else:
        # Original single folder analysis
        while True:
            try:
                add_buy_percent = float(input("Enter Additional Buy percentage (e.g., 5.0): ").strip())
                if add_buy_percent > 0:
                    break
                print("Additional Buy percentage must be positive.")
            except ValueError:
                print("Invalid input. Please enter a numeric value for Additional Buy percentage.")
        
        tp_folder = f"{tp_percent:.1f}%"
        sl_folder = f"{sl_percent:.1f}%"
        add_buy_folder = f"add_buy_{add_buy_percent:.1f}pct"
        
        target_directory = os.path.join("backtest_results", timeframe, f"{tp_folder}_{sl_folder}", add_buy_folder)
        
        if not os.path.isdir(target_directory):
            print(f"Error: Directory not found: {target_directory}")
            print("Please ensure the backtest results exist.")
        else:
            success = analyze_single_add_buy_folder(target_directory)
            if success:
                print("\nAnalysis complete!")