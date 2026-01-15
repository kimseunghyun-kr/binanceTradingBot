# Binance Trading Bot - Complete Documentation

## Table of Contents
1. [Introduction](#introduction)
2. [What is This Project?](#what-is-this-project)
3. [Key Trading Concepts Explained](#key-trading-concepts-explained)
4. [Project Architecture](#project-architecture)
5. [Trading Strategies](#trading-strategies)
6. [Technical Indicators](#technical-indicators)
7. [How Backtesting Works](#how-backtesting-works)
8. [Getting Started](#getting-started)
9. [API Usage](#api-usage)
10. [Advanced Features](#advanced-features)

---

## Introduction

Welcome! This document will help you understand the Binance Trading Bot project, even if you're not familiar with financial trading or programming concepts. We'll explain everything in simple terms.

## What is This Project?

This is an **automated trading bot** that can test trading strategies against historical cryptocurrency market data. Think of it like a time machine for trading - it lets you see how a trading strategy would have performed in the past before you risk real money.

### What Does It Do?

1. **Collects Market Data**: Downloads historical price information for cryptocurrencies from Binance (like Bitcoin, Ethereum, etc.)
2. **Runs Trading Strategies**: Tests different approaches to buying and selling based on price patterns
3. **Simulates Trading**: Pretends to buy and sell based on your strategy rules, tracking how much money you would have made or lost
4. **Provides Results**: Shows you detailed reports of the trades, profits, losses, and overall performance

### Why Is This Useful?

- **Test Before You Invest**: See if your trading idea works before using real money
- **Learn from History**: Understand how markets behave in different conditions
- **Optimize Strategies**: Find the best settings for your trading approach
- **Avoid Costly Mistakes**: Discover problems with your strategy in a safe environment

---

## Key Trading Concepts Explained

Let's break down the financial trading terms you'll encounter:

### Basic Trading Terms

#### 1. **Cryptocurrency / Coin**
Digital money like Bitcoin (BTC) or Ethereum (ETH). In this project, we trade these against USDT (a stable coin worth $1).

#### 2. **Trading Pair**
A combination of two currencies, like "BTCUSDT" means trading Bitcoin against US Dollar Tether. When you see this, it means "How many USDT does one Bitcoin cost?"

#### 3. **Buy Signal / Sell Signal**
- **Buy Signal**: The bot decides it's a good time to purchase a cryptocurrency
- **Sell Signal**: The bot decides it's time to sell what you own

#### 4. **Long Position**
Buying a cryptocurrency hoping its price will go up so you can sell it later for profit. This is the most common type of trading.

#### 5. **Short Position** (Advanced)
Betting that a price will go down. You borrow and sell cryptocurrency, then buy it back cheaper later. This project supports futures/perpetuals for shorting.

### Price and Charts

#### 6. **OHLCV Data**
The fundamental price information for any time period:
- **O**pen: Price at the start of the period
- **H**igh: Highest price during the period
- **L**ow: Lowest price during the period
- **C**lose: Price at the end of the period
- **V**olume: How much was traded during this time

Example: If you look at a "1 day" candle for Bitcoin:
- Open: $50,000 (price at midnight)
- High: $52,000 (highest point that day)
- Low: $49,500 (lowest point that day)
- Close: $51,500 (price at end of day)
- Volume: 1,200 BTC traded

#### 7. **Candlestick / Candle**
A visual way to show OHLCV data. Each "candle" represents one time period:
- Green/white candle = price went up (close > open)
- Red/black candle = price went down (close < open)

#### 8. **Time Interval**
How long each candle represents:
- `1m` = 1 minute
- `15m` = 15 minutes
- `1h` = 1 hour
- `4h` = 4 hours
- `1d` = 1 day
- `1w` = 1 week

### Risk Management

#### 9. **Take Profit (TP)**
The price level where you automatically sell to lock in profits.

Example: You buy Bitcoin at $50,000. You set TP at $55,000. When price reaches $55,000, you automatically sell and take your $5,000 profit.

#### 10. **Stop Loss (SL)**
The price level where you automatically sell to prevent bigger losses.

Example: You buy at $50,000. You set SL at $48,000. If price drops to $48,000, you automatically sell to limit your loss to $2,000 instead of potentially losing more.

#### 11. **Risk-Reward Ratio**
The relationship between your potential profit and potential loss.

Example:
- Buy at: $50,000
- Take Profit: $55,000 (potential gain: $5,000)
- Stop Loss: $48,000 (potential loss: $2,000)
- Risk-Reward Ratio: 5,000 / 2,000 = 2.5 (you risk $1 to potentially make $2.50)

Good traders often look for ratios of 2:1 or better.

#### 12. **Portfolio**
The collection of all your investments. If you own Bitcoin, Ethereum, and some USDT cash, that's your portfolio.

#### 13. **Position Size**
How much money you put into each trade. Instead of investing all your money in one trade, you might use only 10% per trade to spread risk.

### Performance Metrics

#### 14. **Profit and Loss (PnL)**
- **Realized PnL**: Actual profit/loss from closed trades (you've sold)
- **Unrealized PnL**: Potential profit/loss from open trades (you still hold)

#### 15. **Equity Curve**
A line graph showing how your total account value changes over time. Going up = making money, going down = losing money.

#### 16. **Drawdown**
How much your account drops from its highest point.

Example: Your account grows from $10,000 to $15,000, then drops to $12,000. Your drawdown is $3,000 or 20% from the peak. This measures how much pain you might feel during losing streaks.

#### 17. **Sharpe Ratio**
A number that measures risk-adjusted returns. Higher is better:
- Below 1: Not great
- 1-2: Good
- Above 2: Excellent

It tells you if your profits are worth the volatility (price swings) you had to endure.

### Market Dynamics

#### 18. **Volume**
How much trading activity happens. High volume = lots of people buying/selling. Low volume = fewer trades.

High volume often makes prices more reliable and easier to trade.

#### 19. **Liquidity**
How easily you can buy or sell without affecting the price. Major coins like Bitcoin have high liquidity (easy to trade), while small coins might have low liquidity (hard to trade without moving the price).

#### 20. **Slippage**
The difference between the price you expect and the price you actually get. In fast-moving markets, you might want to buy at $50,000 but actually buy at $50,100 because the price moved.

#### 21. **Fees**
The cost of making trades. Binance charges a small percentage (typically 0.1%) per trade. These add up over time and affect your profitability.

### Trading Concepts

#### 22. **Trend**
The general direction of price movement:
- **Uptrend**: Prices generally moving up (higher highs and higher lows)
- **Downtrend**: Prices generally moving down (lower highs and lower lows)
- **Sideways**: Prices moving in a range without clear direction

#### 23. **Momentum**
How fast and strong a price is moving. Strong momentum = rapid price changes. Weak momentum = slow, gradual changes.

#### 24. **Reversal**
When a trend changes direction. For example, an uptrend suddenly becoming a downtrend.

#### 25. **Support and Resistance**
- **Support**: A price level where falling prices tend to stop falling (buyers step in)
- **Resistance**: A price level where rising prices tend to stop rising (sellers step in)

Think of support as a floor and resistance as a ceiling.

#### 26. **Breakout**
When price moves beyond a support or resistance level, potentially starting a new trend.

---

## Project Architecture

### How the System Works (Big Picture)

Think of this project like a restaurant with different stations:

```
┌─────────────────────────────────────────────────────────────┐
│                        You (User)                           │
│                            │                                 │
│                            ▼                                 │
│               ┌─────────────────────────┐                    │
│               │   FastAPI Web Server    │                    │
│               │  (Takes Your Orders)    │                    │
│               └──────────┬──────────────┘                    │
│                          │                                   │
│                          ▼                                   │
│               ┌─────────────────────────┐                    │
│               │    Task Queue (Celery)  │                    │
│               │   (Order Management)    │                    │
│               └──────────┬──────────────┘                    │
│                          │                                   │
│                          ▼                                   │
│               ┌─────────────────────────┐                    │
│               │    Worker Processes     │                    │
│               │   (Kitchen Staff)       │                    │
│               └──────────┬──────────────┘                    │
│                          │                                   │
│                          ▼                                   │
│         ┌─────────────────────────────────────┐              │
│         │   Sandboxed Strategy Container      │              │
│         │     (Isolated Test Kitchen)         │              │
│         │   - Runs trading strategies          │              │
│         │   - Simulates trades                │              │
│         │   - Calculates results              │              │
│         └─────────────────┬───────────────────┘              │
│                          │                                   │
│                          ▼                                   │
│         ┌────────────────────────────────────┐               │
│         │        Databases                   │               │
│         │  - MongoDB (Market Data)           │               │
│         │  - Redis (Fast Cache)              │               │
│         │  - PostgreSQL (Optional)           │               │
│         └────────────────────────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

### Components Explained

#### 1. **FastAPI Web Server** (`KwontBot.py`)
- The front door of the application
- Provides a web interface (like a website) where you can:
  - Submit backtest requests
  - Check status of running tests
  - Retrieve results
  - Manage strategies
- Accessible at `http://localhost:8000` with interactive documentation at `/docs`

#### 2. **Celery Task Queue** (`worker.py`)
- Manages long-running tasks in the background
- Like a job scheduler - takes your requests and processes them one by one
- Lets you submit multiple tests without waiting for each to finish
- Uses Redis to keep track of tasks

#### 3. **Strategy Orchestrator** (`strategyOrchestrator/`)
- The brain of the backtesting operation
- Runs in an isolated Docker container (like a secure sandbox)
- Reads historical market data
- Executes your trading strategy rules
- Simulates buying and selling
- Calculates all the results

#### 4. **MongoDB Database**
- Stores all historical price data (OHLCV candles)
- Saves backtest results
- Keeps track of tasks
- Uses a "replica set" (two copies) for reliability and performance

#### 5. **Redis Cache**
- Super-fast temporary storage
- Stores recent results so you don't have to re-run tests
- Acts as message broker for Celery tasks

### Data Flow

When you request a backtest:

1. **You send a request** → FastAPI receives it (e.g., "Test strategy X on Bitcoin for last year")

2. **FastAPI validates** → Checks if your request makes sense and has all required info

3. **Task created** → Request is packaged as a task and sent to Celery queue

4. **Worker picks up task** → A worker process starts processing your request

5. **Data preparation** → Worker fetches required historical price data from MongoDB

6. **Container spawned** → A secure Docker container is created for testing

7. **Strategy execution** → Inside container:
   - Load trading strategy code
   - Process historical data day by day
   - Generate buy/sell signals
   - Simulate executing trades
   - Track portfolio value over time

8. **Results compiled** → Container outputs:
   - List of all trades made
   - Profit/loss for each trade
   - Overall performance metrics
   - Equity curve data

9. **Results stored** → Saved to MongoDB and cached in Redis

10. **You retrieve results** → Access via API endpoints or web interface

---

## Trading Strategies

A **trading strategy** is a set of rules that decide when to buy and when to sell. This project currently implements one main strategy with room for more.

### Available Strategies

#### 1. PeakEMAReversalStrategy (Main Strategy)

**What it does in simple terms:**

This strategy looks for moments when a cryptocurrency's price has peaked (gone very high), started falling, and is now crossing below a special average price line. This often signals that the upward trend is over and the price might continue falling.

**How it works:**

1. **Find a Peak**
   - Looks at recent price history (last 7 days for daily charts)
   - Identifies if there was one clear peak (the highest point)
   - Example: Bitcoin went from $48k → $52k (peak) → $49k

2. **Check for Bearish Pattern**
   - After the peak, are prices mostly falling?
   - Looks at the candles - are they mostly red (closing lower than opening)?
   - Needs at least 5 out of 6 candles to be bearish

3. **EMA Crossover**
   - EMA = Exponential Moving Average (a smoothed average price line)
   - Strategy uses two EMAs: 15-period and 33-period
   - Waits for the low price to drop below the EMA line
   - This confirms the downward momentum

4. **Generate Buy Signal**
   - When all three conditions are met, the strategy says "BUY"
   - But wait - why buy if price is falling?
   - This is a **reversal strategy** - it bets that after falling to the EMA, the price will bounce back up
   - Like catching a falling ball when it reaches the floor

**Strategy Parameters:**

- `ema_window`: Which EMA to use (15 or 33) - smaller reacts faster, larger is smoother
- `tp_ratio`: Take Profit ratio (e.g., 1.1 = sell when price goes up 10%)
- `sl_ratio`: Stop Loss ratio (e.g., 0.95 = sell if price drops 5%)
- `use_trailing_stop`: Should the stop loss move up as price increases?

**Example Trade:**

```
Day 1-5: Bitcoin rises from $48,000 to $52,000 (peak identified)
Day 6-11: Bitcoin falls with red candles: $51k → $50k → $49.5k → $49k → $48.5k → $48k
Day 11: Price ($48k) crosses below EMA-15 ($48.5k)

Strategy generates BUY signal at $48,000
Take Profit set at $52,800 (10% up, tp_ratio=1.1)
Stop Loss set at $45,600 (5% down, sl_ratio=0.95)

Outcome A: Price rebounds to $52,800 → Take Profit hit → +10% profit
Outcome B: Price drops to $45,600 → Stop Loss hit → -5% loss
Outcome C: Price stagnates → Position held until trend changes
```

#### 2. MomentumStrategy (Placeholder)

This is a template for future development. Momentum strategies typically buy when prices are rising strongly and sell when momentum weakens.

#### 3. EnsembleStrategy (Advanced)

Combines signals from multiple strategies. For example:
- Strategy A says "BUY"
- Strategy B says "HOLD"
- Strategy C says "BUY"

Ensemble might generate a BUY signal if 2 out of 3 agree, giving you more confident trades.

### Creating Your Own Strategy

You can create custom strategies by:

1. **Inheriting from BaseStrategy** - Use the provided template
2. **Implementing `decide()` method** - Your logic for generating signals
3. **Defining parameters** - What settings can users adjust?
4. **Testing** - Run backtests to see if it works

---

## Technical Indicators

Technical indicators are mathematical calculations based on price and volume data. They help identify patterns and potential trading opportunities.

### 1. EMA (Exponential Moving Average)

**What it is:**
A line that smooths out price data to show the average price over a period, giving more weight to recent prices.

**Why it's useful:**
- Shows the trend direction (line going up = uptrend, down = downtrend)
- Acts as support/resistance (prices often bounce off the EMA)
- Crossovers can signal trend changes

**Example:**
15-period EMA on a daily chart = average of last 15 days, but yesterday counts more than 15 days ago

**Used in:**
PeakEMAReversalStrategy uses both EMA-15 and EMA-33

**How to read it:**
```
If price is above EMA → Bullish (uptrend likely)
If price is below EMA → Bearish (downtrend likely)
If price crosses above EMA → Potential buy signal
If price crosses below EMA → Potential sell signal
```

### 2. Volume Profile

**What it is:**
Shows how much trading happened at different price levels during a time period.

**Why it's useful:**
- Identifies price levels where lots of trading occurred (high interest zones)
- POC (Point of Control) = price with most volume (often acts as magnet)
- Value Area = range where 70% of volume occurred

**Example:**
Bitcoin traded between $45k-$55k last month
- $50k had the most volume (POC) - price keeps returning here
- $48k-$52k is the value area (70% of trades)
- $45k and $55k had little volume (weak zones)

**How traders use it:**
- POC often acts as support or resistance
- High volume areas = strong support/resistance
- Low volume areas = price might move through quickly

### 3. Fibonacci Retracement

**What it is:**
Draws horizontal lines at key percentages (23.6%, 38.2%, 50%, 61.8%, 78.6%) between a high and low point.

**Why it's useful:**
After a big price move, retracements often happen at these "magic" levels before the trend continues.

**Example:**
Bitcoin rallied from $40k to $60k (+$20k move)
Fibonacci levels:
- 23.6%: $55,280 (retraced 23.6% of the $20k move)
- 38.2%: $52,360
- 50%: $50,000 (halfway back)
- 61.8%: $47,640 (the "golden ratio")
- 78.6%: $44,280

If Bitcoin drops to $47,640 and bounces, that's a classic Fibonacci retracement trade.

**How traders use it:**
- Wait for price to retrace to a Fib level
- Look for reversal signals at these levels
- Use as entry points to join the main trend

### Other Indicators (Available via `ta` library)

The project includes the `ta` library with 100+ indicators:

**RSI (Relative Strength Index)**
- Measures if something is "overbought" (too expensive, might fall) or "oversold" (too cheap, might rise)
- Scale: 0-100
- Above 70 = overbought, below 30 = oversold

**MACD (Moving Average Convergence Divergence)**
- Shows momentum and trend changes
- Crossovers signal potential buy/sell points

**Bollinger Bands**
- Three lines showing volatility
- Price touching outer bands = extreme levels

**ATR (Average True Range)**
- Measures volatility/price movement
- High ATR = big price swings, low ATR = quiet market

You can add any of these to your custom strategies!

---

## How Backtesting Works

Backtesting is like running a simulation - you pretend it's the past and see how your strategy would have performed.

### The Backtesting Process

#### Step 1: Data Collection

```
Request: "Test PeakEMAReversalStrategy on BTCUSDT from Jan 1, 2024 to Dec 31, 2024"
         ↓
System checks MongoDB for historical data
         ↓
If data exists → Load it
If data missing → Download from Binance API and store it
         ↓
Data ready: 365 daily candles for Bitcoin
```

#### Step 2: Strategy Initialization

```
Load strategy code
Set parameters:
  - ema_window: 15
  - tp_ratio: 1.10 (10% take profit)
  - sl_ratio: 0.95 (5% stop loss)

Initialize portfolio:
  - Starting cash: $10,000
  - Position size: 10% per trade ($1,000 per trade)
  - Max open positions: 5
```

#### Step 3: Historical Simulation (Timeline Execution)

The system steps through time, one day at a time:

```
Day 1 (Jan 1, 2024):
  ├─ Get OHLCV data: Open=$42,000, High=$43,000, Low=$41,500, Close=$42,800
  ├─ Strategy analyzes last 7 days
  ├─ Decision: No signal (not enough history yet)
  └─ Portfolio: $10,000 cash, 0 positions

Day 7 (Jan 7, 2024):
  ├─ Now have 7 days of data
  ├─ Strategy looks for peak + bearish pattern + EMA cross
  ├─ Decision: No signal (conditions not met)
  └─ Portfolio: Still $10,000 cash, 0 positions

Day 15 (Jan 15, 2024):
  ├─ Peak found on Day 10 at $45,000
  ├─ Days 11-15 were bearish (red candles)
  ├─ Price ($43,200) just crossed below EMA-15 ($43,500)
  ├─ Decision: BUY SIGNAL!
  ├─ Execute: Buy $1,000 worth at $43,200 = 0.02315 BTC
  ├─ Set Take Profit: $47,520 (10% up)
  ├─ Set Stop Loss: $41,040 (5% down)
  └─ Portfolio: $9,000 cash, 1 position (0.02315 BTC)

Day 16-25 (Jan 16-25, 2024):
  ├─ Monitor open position
  ├─ Update unrealized P&L as price changes
  ├─ Day 20: Price at $41,000 → Stop Loss triggered!
  ├─ Sell 0.02315 BTC at $41,040 = $950
  ├─ Trade result: Loss of $50 (-5%)
  └─ Portfolio: $9,950 cash, 0 positions

... continues for all 365 days ...

Day 365 (Dec 31, 2024):
  ├─ Close all remaining positions
  ├─ Final calculation
  └─ Results: See below
```

#### Step 4: Performance Calculation

After simulating the entire year, the system calculates:

**Trade Statistics:**
```
Total trades: 43
Winning trades: 28 (65% win rate)
Losing trades: 15 (35% loss rate)
Average win: +8.2%
Average loss: -4.8%
Largest win: +15.3% ($153 on one trade)
Largest loss: -5.0% ($50 on one trade)
```

**Portfolio Performance:**
```
Starting value: $10,000
Ending value: $12,450
Total return: +24.5%
Buy and hold return: +18.2% (if you just bought and held Bitcoin)
Outperformance: +6.3%

Max drawdown: -8.3% (worst peak-to-valley drop)
Sharpe ratio: 1.85 (good risk-adjusted returns)
```

**Equity Curve:**
```
Jan: $10,000
Feb: $10,250
Mar: $10,180 (small drawdown)
Apr: $10,520
May: $10,890
Jun: $11,200
Jul: $11,050
Aug: $11,400
Sep: $11,250
Oct: $11,650
Nov: $12,100
Dec: $12,450
```

### Two-Phase Execution Architecture

The system uses a clever approach to make backtesting fast:

#### Phase 1: Parallel Proposal Generation (Fast)

```
Split symbols into groups:
  Group 1: BTCUSDT, ETHUSDT, BNBUSDT
  Group 2: ADAUSDT, DOGEUSDT, SOLUSDT
  Group 3: XRPUSDT, DOTUSDT, MATICUSDT

Process in parallel (simultaneously):
  Thread 1 → Analyzes Group 1 → Generates buy/sell proposals
  Thread 2 → Analyzes Group 2 → Generates buy/sell proposals
  Thread 3 → Analyzes Group 3 → Generates buy/sell proposals

Result: List of all potential trades with entry/exit prices
Example:
  - Buy BTCUSDT at $43,200 on Jan 15
  - Buy ETHUSDT at $2,250 on Jan 18
  - Buy BNBUSDT at $305 on Jan 22
  ...
```

#### Phase 2: Serial Timeline Execution (Accurate)

```
Now simulate executing these trades in time order:

Timeline: Jan 1 → Dec 31

For each day:
  1. Check if any trades should enter (buy signals)
  2. Check if any trades should exit (take profit or stop loss hit)
  3. Update portfolio cash (add profits, subtract losses)
  4. Calculate unrealized P&L for open positions
  5. Record portfolio value (equity curve point)
  6. Enforce risk rules (e.g., max 5 open positions, must have cash available)

This ensures:
  - Trades happen in correct time order
  - You can't trade more money than you have
  - Risk limits are respected
  - Accurate reflection of how trading would actually work
```

**Why This Approach?**

- **Phase 1 (Parallel)**: Fast because each symbol is analyzed independently
- **Phase 2 (Serial)**: Accurate because portfolio effects are properly simulated in time order
- **Result**: Best of both worlds - speed AND accuracy

---

## Getting Started

### Prerequisites

Before running this project, you need:

1. **Python 3.10 or newer**
   - Download from python.org
   - Check version: `python --version`

2. **Docker Desktop**
   - Used for running databases and strategy containers
   - Download from docker.com

3. **Basic Terminal Knowledge**
   - You'll run commands in Terminal (Mac/Linux) or Command Prompt (Windows)

### Installation Steps

#### 1. Clone the Repository

```bash
# Download the project
git clone <repository-url>
cd binanceTradingBot
```

#### 2. Install Python Dependencies

```bash
# Install all required Python packages
pip install -r requirements.txt
```

This installs:
- FastAPI (web framework)
- Celery (task queue)
- MongoDB drivers (database)
- Pandas (data processing)
- Technical analysis libraries
- And 50+ other packages

#### 3. Start the Databases

```bash
# Start MongoDB, Redis, and PostgreSQL
docker-compose --profile db up -d
```

This command:
- `-d` = run in background (detached mode)
- `--profile db` = only start database services

Wait about 30 seconds for databases to initialize.

#### 4. Configure Environment

Create a `.env` file with your settings:

```bash
# Copy example file
cp .env.example .env

# Edit with your settings
nano .env
```

Key settings:
```
PROFILE=development
BINANCE_API_KEY=your_binance_api_key
BINANCE_API_SECRET=your_binance_secret
COINMARKETCAP_API_KEY=your_cmc_key
```

**Note:** Get API keys from:
- Binance: binance.com → Account → API Management
- CoinMarketCap: coinmarketcap.com/api

#### 5. Start the API Server

```bash
# Start FastAPI server
python run_local.py
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete
```

Open browser to: http://localhost:8000/docs

#### 6. Start the Worker

In a new terminal window:

```bash
# Start Celery worker
python worker.py
```

You should see:
```
[INFO/MainProcess] Connected to redis://localhost:6379//
[INFO/MainProcess] celery@hostname ready.
```

### Verify Installation

1. Open http://localhost:8000/docs in your browser
2. You should see the Swagger UI with available endpoints
3. Try the `/health` endpoint - it should return `{"status": "healthy"}`

---

## API Usage

The API provides several endpoints for interacting with the trading bot.

### Swagger UI (Interactive Documentation)

Visit http://localhost:8000/docs for interactive API documentation where you can:
- See all available endpoints
- Read parameter descriptions
- Test endpoints directly from your browser
- View example requests and responses

### Common Endpoints

#### 1. Submit a Backtest

**Endpoint:** `POST /backtest/submit`

**Purpose:** Start a new backtest job

**Request Body:**
```json
{
  "strategy_name": "PeakEMAReversalStrategy",
  "strategy_params": {
    "ema_window": 15,
    "tp_ratio": 1.10,
    "sl_ratio": 0.95
  },
  "symbols": ["BTCUSDT", "ETHUSDT", "BNBUSDT"],
  "interval": "1d",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31",
  "initial_capital": 10000,
  "position_size_pct": 0.10
}
```

**Response:**
```json
{
  "task_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "status": "submitted",
  "message": "Backtest task submitted successfully"
}
```

Save the `task_id` - you'll need it to check results!

#### 2. Check Task Status

**Endpoint:** `GET /task/status/{task_id}`

**Purpose:** See if your backtest is done

**Response (Running):**
```json
{
  "task_id": "a1b2c3d4...",
  "status": "PROGRESS",
  "progress": 45,
  "message": "Processing 12 of 27 symbols"
}
```

**Response (Complete):**
```json
{
  "task_id": "a1b2c3d4...",
  "status": "SUCCESS",
  "completed_at": "2024-01-15T14:32:10Z"
}
```

#### 3. Get Backtest Results

**Endpoint:** `GET /backtest/results/{task_id}`

**Purpose:** Retrieve full backtest results

**Response:**
```json
{
  "task_id": "a1b2c3d4...",
  "strategy": "PeakEMAReversalStrategy",
  "parameters": {...},
  "performance": {
    "total_return": 0.245,
    "total_trades": 43,
    "winning_trades": 28,
    "losing_trades": 15,
    "win_rate": 0.651,
    "max_drawdown": -0.083,
    "sharpe_ratio": 1.85
  },
  "trades": [
    {
      "symbol": "BTCUSDT",
      "entry_time": "2024-01-15T00:00:00Z",
      "entry_price": 43200,
      "exit_time": "2024-01-20T00:00:00Z",
      "exit_price": 41040,
      "pnl": -50,
      "pnl_pct": -0.05,
      "reason": "stop_loss"
    },
    ...
  ],
  "equity_curve": [
    {"date": "2024-01-01", "value": 10000},
    {"date": "2024-01-02", "value": 10000},
    ...
  ]
}
```

#### 4. List Available Symbols

**Endpoint:** `GET /symbols`

**Purpose:** See which cryptocurrencies you can backtest

**Response:**
```json
{
  "symbols": [
    {
      "symbol": "BTCUSDT",
      "base": "BTC",
      "quote": "USDT",
      "status": "TRADING"
    },
    {
      "symbol": "ETHUSDT",
      "base": "ETH",
      "quote": "USDT",
      "status": "TRADING"
    },
    ...
  ],
  "count": 145
}
```

#### 5. Get Symbol Data

**Endpoint:** `GET /symbols/{symbol}/data?interval=1d&start=2024-01-01&end=2024-12-31`

**Purpose:** Download historical price data for a symbol

**Response:**
```json
{
  "symbol": "BTCUSDT",
  "interval": "1d",
  "data": [
    {
      "timestamp": "2024-01-01T00:00:00Z",
      "open": 42000,
      "high": 43000,
      "low": 41500,
      "close": 42800,
      "volume": 1250.5
    },
    ...
  ]
}
```

### Example Workflow (Python)

Here's how to use the API from Python:

```python
import requests
import time

BASE_URL = "http://localhost:8000"

# 1. Submit backtest
response = requests.post(f"{BASE_URL}/backtest/submit", json={
    "strategy_name": "PeakEMAReversalStrategy",
    "strategy_params": {
        "ema_window": 15,
        "tp_ratio": 1.10,
        "sl_ratio": 0.95
    },
    "symbols": ["BTCUSDT", "ETHUSDT"],
    "interval": "1d",
    "start_date": "2024-01-01",
    "end_date": "2024-12-31",
    "initial_capital": 10000
})

task_id = response.json()["task_id"]
print(f"Task submitted: {task_id}")

# 2. Poll for completion
while True:
    status_response = requests.get(f"{BASE_URL}/task/status/{task_id}")
    status = status_response.json()["status"]

    print(f"Status: {status}")

    if status == "SUCCESS":
        break
    elif status == "FAILURE":
        print("Backtest failed!")
        exit(1)

    time.sleep(5)  # Check every 5 seconds

# 3. Get results
results = requests.get(f"{BASE_URL}/backtest/results/{task_id}")
performance = results.json()["performance"]

print(f"Total Return: {performance['total_return']*100:.2f}%")
print(f"Win Rate: {performance['win_rate']*100:.2f}%")
print(f"Sharpe Ratio: {performance['sharpe_ratio']:.2f}")
```

---

## Advanced Features

### 1. Grid Search (Parameter Optimization)

**What it does:**
Tests multiple parameter combinations to find the best settings.

**Example:**
```json
{
  "strategy_name": "PeakEMAReversalStrategy",
  "param_grid": {
    "ema_window": [10, 15, 20, 33],
    "tp_ratio": [1.05, 1.10, 1.15, 1.20],
    "sl_ratio": [0.93, 0.95, 0.97]
  },
  "symbols": ["BTCUSDT"],
  "interval": "1d",
  "start_date": "2024-01-01",
  "end_date": "2024-12-31"
}
```

This tests: 4 × 4 × 3 = 48 different combinations!

Results show which combination performed best.

### 2. Custom Strategies

You can upload your own strategy code:

**Endpoint:** `POST /strategy/create`

**Request:**
```json
{
  "name": "MyCustomStrategy",
  "code": "base64_encoded_python_code",
  "description": "My awesome trading strategy"
}
```

The system will:
1. Validate your code
2. Store it in the database
3. Make it available for backtesting

**Requirements:**
- Must inherit from `BaseStrategy`
- Must implement `decide()` method
- Must return valid signals (BUY, SELL, or NO_SIGNAL)

### 3. Market Data Management

**Ensure Data Availability:**

The system automatically downloads missing data, but you can pre-fetch:

```bash
# Via API
POST /data/ensure
{
  "symbols": ["BTCUSDT", "ETHUSDT"],
  "interval": "1d",
  "start_date": "2020-01-01",
  "end_date": "2024-12-31"
}
```

This is useful before running many backtests.

**Data Intervals Available:**
- `1m`, `3m`, `5m`, `15m`, `30m` (minute intervals)
- `1h`, `2h`, `4h`, `6h`, `12h` (hourly intervals)
- `1d`, `3d` (daily intervals)
- `1w` (weekly)
- `1M` (monthly)

### 4. Futures/Perpetuals Trading

The system supports futures (leveraged) trading:

```json
{
  "strategy_name": "PeakEMAReversalStrategy",
  "market_type": "perpetual",
  "leverage": 3,
  "margin_mode": "isolated",
  ...
}
```

**Warning:** Futures trading is more complex and risky. Only use if you understand leverage.

### 5. Portfolio Constraints

Control risk with constraints:

```json
{
  "capacity_config": {
    "max_legs": 5,
    "max_symbols": 3,
    "max_position_size": 1000
  },
  "sizing_model": "fixed_fraction",
  "sizing_params": {
    "fraction": 0.10
  }
}
```

This ensures:
- Never more than 5 open positions
- Never more than 3 different symbols at once
- Each position max $1,000
- Each trade is 10% of available capital

### 6. Fee and Slippage Models

Make backtests more realistic:

```json
{
  "fee_model": "per_symbol",
  "fee_params": {
    "BTCUSDT": 0.001,
    "ETHUSDT": 0.001,
    "default": 0.001
  },
  "slippage_model": "random",
  "slippage_params": {
    "mean": 0.0005,
    "std": 0.0002
  }
}
```

- Fees: 0.1% per trade (typical Binance rate)
- Slippage: Random, averaging 0.05% with some variance

### 7. Analysis Tools

**GraphQL API:**

More flexible queries via GraphQL endpoint at `/graphql`

Example query:
```graphql
query {
  backtestResults(
    strategyName: "PeakEMAReversalStrategy",
    minReturn: 0.15,
    orderBy: "sharpe_ratio"
  ) {
    taskId
    performance {
      totalReturn
      sharpeRatio
      maxDrawdown
    }
    createdAt
  }
}
```

**Export Results:**

Export trades to CSV:
```
GET /backtest/results/{task_id}/export?format=csv
```

### 8. Caching

Results are cached for 2 hours. If you run the exact same backtest twice, the second request returns instantly.

Cache key includes:
- Strategy name and all parameters
- Symbol list
- Date range
- Interval
- All configuration options

### 9. WebSocket Support

Real-time updates while backtest runs:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/backtest/{task_id}');

ws.onmessage = (event) => {
  const update = JSON.parse(event.data);
  console.log(`Progress: ${update.progress}%`);
};
```

---

## Tips for Success

### 1. Start Simple
- Begin with one symbol (BTCUSDT)
- Use shorter date ranges (1 month) for testing
- Increase complexity gradually

### 2. Understand Risk Management
- Never risk more than 1-2% of capital per trade
- Always use stop losses
- Diversify across multiple symbols

### 3. Avoid Overfitting
- Don't optimize parameters on the same data you'll trade
- Test on "out-of-sample" data (dates not used for optimization)
- Simpler strategies often work better than complex ones

### 4. Consider Transaction Costs
- Fees add up quickly with many trades
- Include realistic slippage in backtests
- High-frequency strategies need careful cost analysis

### 5. Monitor Drawdowns
- Max drawdown shows worst-case scenario
- Can you stomach a 20% drop?
- Lower drawdown = easier to stick with the strategy

### 6. Be Skeptical of Great Results
- If backtest shows 200% returns, be cautious
- Past performance doesn't guarantee future results
- Market conditions change

### 7. Paper Trade First
- After backtesting, try "paper trading" (fake money, real-time)
- Test on current market conditions
- Build confidence before risking real capital

---

## Common Questions

### Q: Do I need to understand programming?

**A:** Basic knowledge helps, but not required for using existing strategies. The API and Swagger UI let you run backtests without coding. To create custom strategies, you'll need Python knowledge.

### Q: Is this safe for real trading?

**A:** This project is for backtesting only. It doesn't execute real trades. Before live trading:
1. Thoroughly backtest
2. Paper trade for weeks/months
3. Start with small amounts
4. Never risk money you can't afford to lose

### Q: How accurate are backtests?

**A:** Backtests are estimates. Real trading has:
- Execution delays
- Slippage (worse prices than backtested)
- Emotional decisions
- Unexpected market events

Include fees and slippage in backtests for more realism.

### Q: Why does my strategy work in backtest but fail in real trading?

**A:** Common reasons:
- **Overfitting**: Optimized too much for past data
- **Look-ahead bias**: Used information not available at the time
- **Changed market conditions**: Market behavior shifted
- **Transaction costs**: Fees eat profits
- **Execution differences**: Can't always get the exact prices from backtest

### Q: What's a good win rate?

**A:** Win rate alone doesn't matter! A strategy with 40% win rate can be profitable if wins are much larger than losses. Focus on:
- Risk-reward ratio
- Total return
- Sharpe ratio
- Max drawdown

### Q: How much data do I need?

**A:** More is better:
- Minimum: 1 year
- Better: 2-3 years
- Best: 5+ years across different market conditions (bull, bear, sideways)

This shows how strategy performs in various scenarios.

### Q: Can I trade multiple strategies simultaneously?

**A:** Yes! Using different strategies can diversify risk. The EnsembleStrategy feature supports this. Just ensure total risk stays within your limits.

### Q: What's the difference between spot and futures trading?

**A:**
- **Spot**: Buy and own the actual cryptocurrency. Lower risk.
- **Futures/Perpetuals**: Trade contracts with leverage. Can profit from falling prices (shorting) but much riskier.

Start with spot trading.

---

## Troubleshooting

### Problem: Worker not starting

**Solutions:**
1. Check Redis is running: `docker ps` (should see redis container)
2. Check for port conflicts: Redis uses port 6379
3. Look at worker logs: `python worker.py` should show connection messages
4. Restart Redis: `docker-compose restart redis`

### Problem: Task stays in PENDING forever

**Solutions:**
1. Ensure worker is running
2. Check worker logs for errors
3. Verify MongoDB is accessible
4. Try restarting worker

### Problem: Backtest fails with "Data not available"

**Solutions:**
1. Check date range - Binance has limited history for some symbols
2. Verify symbol exists and is trading
3. Try ensuring data first: `/data/ensure` endpoint
4. Check Binance API key is valid

### Problem: Results seem unrealistic

**Solutions:**
1. Enable fee model (0.1% is typical)
2. Add slippage model
3. Check for look-ahead bias in custom strategies
4. Verify position sizing isn't too aggressive
5. Review individual trades for anomalies

### Problem: Docker containers not starting

**Solutions:**
1. Ensure Docker Desktop is running
2. Check for port conflicts (27017, 27018, 6379, 5432)
3. Try: `docker-compose down` then `docker-compose --profile db up -d`
4. Check disk space (MongoDB needs storage)

### Problem: API returns 500 error

**Solutions:**
1. Check API server logs
2. Verify database connections
3. Check .env file has required settings
4. Try restarting API server

---

## Next Steps

Now that you understand the project:

1. **Run Your First Backtest**
   - Start with PeakEMAReversalStrategy on BTCUSDT
   - Use last 6 months of data
   - Review the results

2. **Experiment with Parameters**
   - Try different ema_window values (10, 15, 20, 33)
   - Adjust tp_ratio and sl_ratio
   - Use grid search to find optimal settings

3. **Test on Multiple Symbols**
   - Add ETHUSDT, BNBUSDT to your tests
   - Compare which coins work best
   - Consider diversification benefits

4. **Learn About Indicators**
   - Study how EMA works
   - Explore other indicators in the `ta` library
   - Understand when each indicator is useful

5. **Create a Custom Strategy**
   - Start with a simple idea (e.g., "buy when RSI < 30")
   - Implement using the BaseStrategy template
   - Backtest thoroughly
   - Iterate and improve

6. **Join the Community**
   - Share your results (be honest about what works and doesn't)
   - Learn from others' strategies
   - Contribute improvements to the project

---

## Resources for Learning More

### Trading Concepts
- Investopedia.com - Excellent explanations of financial terms
- TradingView.com - Charts and technical analysis tools
- BabyPips.com - Beginner-friendly trading education

### Technical Analysis
- "Technical Analysis of Financial Markets" by John Murphy
- "Japanese Candlestick Charting Techniques" by Steve Nison
- TradingView Education section

### Python & Programming
- Python.org documentation
- Real Python (realpython.com) tutorials
- FastAPI documentation

### Risk Management
- "The New Trading for a Living" by Dr. Alexander Elder
- "Trading in the Zone" by Mark Douglas
- Position sizing calculators online

### Backtesting Best Practices
- QuantConnect blog
- Quantopian forums (archived)
- Papers on SSRN about trading system validation

---

## Glossary of Terms

**API (Application Programming Interface)**: A way for programs to talk to each other. This project's API lets you send requests and get results.

**Async/Asynchronous**: Running tasks without waiting for each to finish. Like cooking multiple dishes at once instead of one at a time.

**Backtest**: Testing a trading strategy on historical data to see how it would have performed.

**Bullish**: Expecting prices to rise. Bulls attack upward with their horns.

**Bearish**: Expecting prices to fall. Bears swipe downward with their paws.

**Candle/Candlestick**: Visual representation of price action for a time period.

**Celery**: A Python library for running tasks in the background.

**Container**: An isolated environment for running code (like a virtual computer).

**Docker**: Software for creating and managing containers.

**EMA (Exponential Moving Average)**: A smoothed average price giving more weight to recent data.

**Equity Curve**: Graph showing account value over time.

**FastAPI**: A modern Python web framework for building APIs.

**Leverage**: Borrowing money to trade larger positions (increases both gains and losses).

**Long**: Buying an asset hoping it increases in value.

**MongoDB**: A database for storing large amounts of data.

**OHLCV**: Open, High, Low, Close, Volume - the fundamental price data.

**P&L (Profit and Loss)**: How much money you made or lost.

**Position**: An open trade you're currently holding.

**Redis**: A super-fast in-memory database used for caching and queues.

**Short**: Betting an asset will decrease in value.

**Signal**: A notification from a strategy to buy, sell, or hold.

**Slippage**: Difference between expected price and actual execution price.

**Strategy**: A set of rules for when to buy and sell.

**Swagger UI**: Interactive documentation for APIs.

**Symbol**: Trading pair like BTCUSDT (Bitcoin vs Tether).

**Technical Indicator**: Mathematical calculation based on price/volume to identify patterns.

**Volume**: Amount of trading activity (how much was bought and sold).

---

## Conclusion

Congratulations on making it through this comprehensive guide! You now understand:

- What this trading bot does and why it's useful
- Key financial and trading concepts
- How the system architecture works
- What strategies and indicators are available
- How backtesting simulates historical trading
- How to get started and use the API
- Advanced features for optimization
- Common pitfalls and how to avoid them

Remember: **Backtesting is a tool for learning and testing ideas, not a crystal ball**. Use it wisely, manage your risk, and never stop learning.

Happy backtesting!

---

## Project Information

**Status**: Early development (pre-alpha)
**License**: [Check repository]
**Contributors**: [Check repository]
**Issues/Support**: [GitHub Issues](https://github.com/your-repo/issues)

**Version**: 1.0.0 (Documentation)
**Last Updated**: 2026-01-15
