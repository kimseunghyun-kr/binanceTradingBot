# Binance Trading Bot Architecture Diagrams

이 문서는 Binance Trading Bot의 전체 아키텍처와 entities 폴더의 구조를 시각화한 여러 Mermaid 다이어그램을 포함합니다.

## 1. 전체 시스템 아키텍처

```mermaid
graph TB
    subgraph "Client Layer"
        Client[Web Client]
    end
    
    subgraph "API Layer"
        FastAPI[FastAPI Server<br/>KwontBot.py]
        Controllers[Controllers<br/>- BackTestController<br/>- AnalysisController<br/>- GridSearchController]
    end
    
    subgraph "Task Queue"
        Celery[Celery Worker<br/>worker.py]
        Redis[(Redis<br/>Message Broker)]
    end
    
    subgraph "Business Logic"
        Services[Services<br/>- BackTestService<br/>- AnalysisService<br/>- GridSearchService]
        Orchestrator[Strategy Orchestrator<br/>Sandboxed Execution]
    end
    
    subgraph "Data Layer"
        MongoDB[(MongoDB<br/>Candle Data)]
        PostgreSQL[(PostgreSQL<br/>Structured Data)]
        BinanceAPI[Binance API]
    end
    
    subgraph "Entities"
        Strategies[Trading Strategies]
        Portfolio[Portfolio Manager]
        TradeProposal[Trade Proposals]
    end
    
    Client --> FastAPI
    FastAPI --> Controllers
    Controllers --> Celery
    Celery --> Redis
    Redis --> Services
    Services --> Orchestrator
    Orchestrator --> Strategies
    Services --> Portfolio
    Services --> TradeProposal
    Services --> MongoDB
    Services --> PostgreSQL
    Services --> BinanceAPI
    
    style FastAPI fill:#2196F3
    style Celery fill:#4CAF50
    style Redis fill:#FF5722
    style MongoDB fill:#4DB33D
    style PostgreSQL fill:#336791
```

## 2. Entities 폴더 구조

```mermaid
graph TD
    Entities[entities/]
    
    Entities --> Strategies[strategies/]
    Entities --> Portfolio[portfolio/]
    Entities --> TradeProposal[tradeProposal/]
    
    Strategies --> BaseStrategy[BaseStrategy.py<br/>Abstract Base Class]
    Strategies --> ParametrizedStrategy[ParameterisedStrategy.py<br/>Parameter Management]
    Strategies --> ConcreteStrategies[concreteStrategies/]
    
    ConcreteStrategies --> PeakEMA[PeakEmaReversalStrategy.py]
    ConcreteStrategies --> Momentum[MomentumStrategy.py]
    ConcreteStrategies --> Ensemble[EnsembleStrategy.py]
    
    Portfolio --> BasePortfolioManager[BasePortfolioManager.py]
    Portfolio --> TradeLogEntry[TradeLogEntry.py]
    Portfolio --> Fees[fees/fees.py]
    
    TradeProposal --> TradeMeta[TradeMeta.py]
    TradeProposal --> TradeProposalClass[TradeProposal.py]
    
    style Entities fill:#E0E0E0
    style Strategies fill:#FFEB3B
    style Portfolio fill:#4CAF50
    style TradeProposal fill:#2196F3
```

## 3. Strategy 클래스 계층 구조

```mermaid
classDiagram
    class BaseStrategy {
        <<abstract>>
        +decide(df, symbol, current_time) Signal
        +filter_symbols(symbols) List~str~
        +aggregate_signals(signals) Signal
        +required_indicators() List~str~
        +fit(df, symbol)
        +set_params(params)
        +get_params() dict
        +get_required_lookback() int
        +get_indicator_periods() dict
    }
    
    class ParametrizedStrategy {
        +get_params() dict
        -_filter_internal_params(params) dict
    }
    
    class PeakEMAReversalStrategy {
        +decide(df, symbol, current_time) Signal
        +required_indicators() List~str~
        +get_required_lookback() int
        +get_indicator_periods() dict
        -_find_peaks(highs)
        -_detect_bearish_pattern(highs, lows, opens, closes)
    }
    
    class MomentumStrategy {
        +decide(df, symbol, current_time) Signal
    }
    
    class EnsembleStrategy {
        +strategies: List~BaseStrategy~
        +weights: List~float~
        +decide(df, symbol, current_time) Signal
        +required_indicators() List~str~
        +get_required_lookback() int
    }
    
    BaseStrategy <|-- ParametrizedStrategy
    BaseStrategy <|-- MomentumStrategy
    BaseStrategy <|-- EnsembleStrategy
    ParametrizedStrategy <|-- PeakEMAReversalStrategy
    EnsembleStrategy o-- BaseStrategy : contains multiple
```

## 4. 트레이딩 플로우 시퀀스 다이어그램

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant Celery
    participant BackTestService
    participant Strategy
    participant TradeProposal
    participant PortfolioManager
    participant MongoDB
    
    Client->>FastAPI: POST /backtest
    FastAPI->>Celery: Submit backtest task
    Celery->>BackTestService: Execute backtest
    BackTestService->>MongoDB: Fetch candle data
    MongoDB-->>BackTestService: Return data
    
    loop For each time period
        BackTestService->>Strategy: decide(df, symbol, time)
        Strategy-->>BackTestService: Return Signal
        
        alt Signal is BUY/SELL
            BackTestService->>TradeProposal: Create proposal
            BackTestService->>PortfolioManager: try_execute(proposal)
            PortfolioManager->>PortfolioManager: TransactionLedger check
            
            alt Can open position
                PortfolioManager->>TradeProposal: realize()
                TradeProposal-->>PortfolioManager: Return execution result
                PortfolioManager->>PortfolioManager: Update positions
                PortfolioManager->>PortfolioManager: Log trade
            end
        end
    end
    
    BackTestService-->>Celery: Return results
    Celery-->>FastAPI: Task complete
    FastAPI-->>Client: Return task ID
```

## 5. Portfolio Manager 상태 관리

```mermaid
stateDiagram-v2
    [*] --> Initialized: Create Portfolio
    
    Initialized --> HasCash: Initial capital
    
    HasCash --> PositionOpen: Open position
    HasCash --> HasCash: Reject trade (insufficient funds)
    
    PositionOpen --> PositionOpen: Add position (pyramid)
    PositionOpen --> PositionClosed: Close position
    PositionOpen --> PositionOpen: Mark to market
    
    PositionClosed --> HasCash: Return capital + PnL
    
    state PositionOpen {
        [*] --> Active
        Active --> ProfitTarget: Price hits TP
        Active --> StopLoss: Price hits SL
        Active --> ManualClose: Close signal
        ProfitTarget --> [*]
        StopLoss --> [*]
        ManualClose --> [*]
    }
```

## 6. Trade Proposal 실행 플로우

```mermaid
graph LR
    A[Trade Signal] --> B{Signal Type}
    B -->|BUY/SELL| C[Create TradeMeta]
    B -->|NO/CLOSE| D[No Action/Close Position]
    
    C --> E[Create TradeProposal]
    E --> F{Portfolio Check}
    F -->|Can Open| G[Reserve Capital]
    F -->|Cannot Open| H[Reject Trade]
    
    G --> I[Lazy Execution]
    I --> J{Market Movement}
    J -->|Hit TP| K[Take Profit Exit]
    J -->|Hit SL| L[Stop Loss Exit]
    J -->|Time Limit| M[Close at Market]
    
    K --> N[Calculate PnL]
    L --> N
    M --> N
    
    N --> O[Update Portfolio]
    O --> P[Log Trade]
    
    style A fill:#FFEB3B
    style N fill:#4CAF50
    style L fill:#F44336
```

## 7. Strategy Orchestrator 샌드박싱

```mermaid
graph TB
    subgraph "Main Application"
        BackTestService[BackTest Service]
        Orchestrator[Strategy Orchestrator]
    end
    
    subgraph "Sandboxed Environment"
        subgraph "Docker Container 1"
            Strategy1[Strategy Instance]
            Runtime1[Isolated Runtime]
        end
        
        subgraph "Docker Container 2"
            Strategy2[Strategy Instance]
            Runtime2[Isolated Runtime]
        end
    end
    
    BackTestService --> Orchestrator
    Orchestrator -->|stdin/stdout| Strategy1
    Orchestrator -->|stdin/stdout| Strategy2
    
    Strategy1 -.->|No file access| FS1[File System]
    Strategy2 -.->|No network access| NET1[Network]
    
    style Strategy1 fill:#4CAF50
    style Strategy2 fill:#4CAF50
    style FS1 fill:#F44336
    style NET1 fill:#F44336
```

## 8. 데이터 플로우와 캐싱

```mermaid
graph TD
    A[Binance API Request] --> B{Redis Cache}
    B -->|Cache Hit| C[Return Cached Data]
    B -->|Cache Miss| D[Fetch from Binance]
    
    D --> E[Store in Redis]
    E --> F[Store in MongoDB]
    F --> C
    
    subgraph "Data Processing"
        C --> G[Add Technical Indicators]
        G --> H[Strategy Processing]
    end
    
    subgraph "Caching Layers"
        Redis[Redis<br/>- Short-term cache<br/>- 5min TTL]
        MongoDB[MongoDB<br/>- Long-term storage<br/>- Historical data]
    end
    
    style Redis fill:#FF5722
    style MongoDB fill:#4DB33D
```

## 9. Grid Search 파라미터 최적화

```mermaid
graph TD
    A[Grid Search Request] --> B[Parameter Grid Generation]
    B --> C[Create Parameter Combinations]
    
    C --> D[Parallel Execution]
    
    subgraph "Parallel Backtests"
        D --> E1[Backtest 1<br/>Params: {a:1, b:2}]
        D --> E2[Backtest 2<br/>Params: {a:1, b:3}]
        D --> E3[Backtest 3<br/>Params: {a:2, b:2}]
        D --> EN[Backtest N<br/>Params: {a:n, b:m}]
    end
    
    E1 --> F[Results Collection]
    E2 --> F
    E3 --> F
    EN --> F
    
    F --> G[Performance Comparison]
    G --> H[Best Parameters]
    
    style D fill:#FFC107
    style H fill:#4CAF50
```

## 10. 신호 생성 상세 플로우 (PeakEMAReversalStrategy)

```mermaid
flowchart TD
    A[Start: decide()] --> B[Get Recent Data]
    B --> C{Find Peak<br/>in last N bars}
    
    C -->|No Peak| D[Return 'NO' Signal]
    C -->|Peak Found| E[Check Bearish Pattern<br/>After Peak]
    
    E -->|No Pattern| D
    E -->|Pattern Found| F[Calculate EMAs]
    
    F --> G{Price < Fast EMA<br/>< Slow EMA?}
    
    G -->|No| D
    G -->|Yes| H[Generate BUY Signal]
    
    H --> I[Set Entry Price]
    I --> J[Calculate TP<br/>Entry × (1 + tp_pct)]
    J --> K[Calculate SL<br/>Entry × (1 - sl_pct)]
    K --> L[Return Signal with<br/>TradeMeta]
    
    style A fill:#2196F3
    style H fill:#4CAF50
    style L fill:#4CAF50
    style D fill:#F44336
```

## 주요 특징

1. **모듈화된 구조**: 각 컴포넌트가 명확히 분리되어 있어 유지보수와 확장이 용이
2. **비동기 처리**: Celery를 통한 백그라운드 작업 처리로 시스템 응답성 향상
3. **샌드박싱**: Docker 컨테이너를 통한 전략 실행 격리로 보안성 강화
4. **확장 가능한 전략 시스템**: 추상 클래스를 통한 새로운 전략 추가 용이
5. **다층 캐싱**: Redis와 MongoDB를 활용한 효율적인 데이터 관리
6. **리스크 관리**: Portfolio Manager를 통한 포지션 크기 및 자금 관리
