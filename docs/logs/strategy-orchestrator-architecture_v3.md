# Strategy Orchestrator 상세 아키텍처 문서 / Strategy Orchestrator Detailed Architecture Documentation

## 목차 / Table of Contents

1. [개요 / Overview](#개요--overview)
2. [전체 아키텍처 / Overall Architecture](#전체-아키텍처--overall-architecture)
3. [핵심 컴포넌트 상세 분석 / Core Component Detailed Analysis](#핵심-컴포넌트-상세-분석--core-component-detailed-analysis)
4. [데이터 흐름 및 처리 과정 / Data Flow and Processing](#데이터-흐름-및-처리-과정--data-flow-and-processing)
5. [클래스 다이어그램 및 관계 / Class Diagrams and Relationships](#클래스-다이어그램-및-관계--class-diagrams-and-relationships)
6. [보안 및 격리 메커니즘 / Security and Isolation Mechanisms](#보안-및-격리-메커니즘--security-and-isolation-mechanisms)
7. [성능 최적화 전략 / Performance Optimization Strategies](#성능-최적화-전략--performance-optimization-strategies)
8. [확장 포인트 및 플러그인 시스템 / Extension Points and Plugin System](#확장-포인트-및-플러그인-시스템--extension-points-and-plugin-system)

## 개요 / Overview

### 한국어
Strategy Orchestrator는 바이낸스 트레이딩 봇의 핵심 백테스팅 엔진으로, 트레이딩 전략을 안전하고 격리된 Docker 컨테이너 환경에서 실행합니다. 이 시스템은 다음과 같은 핵심 기능을 제공합니다:

- **병렬 처리 아키텍처**: ThreadPoolExecutor를 통한 멀티스레드 병렬 처리로 여러 심볼의 전략을 동시에 평가
- **2단계 실행 모델**: 병렬 제안 생성 후 순차적 WAL(Write-Ahead Log) 실행
- **플러그인 기반 확장성**: 전략, 수수료 모델, 사이징 모델 등을 동적으로 로드
- **읽기 전용 데이터 접근**: MongoDB 슬레이브 노드를 통한 안전한 데이터 접근
- **상세한 거래 추적**: 모든 거래 이벤트와 포트폴리오 변화를 정밀하게 기록

### English
The Strategy Orchestrator is the core backtesting engine of the Binance Trading Bot, executing trading strategies in secure, isolated Docker container environments. The system provides the following core features:

- **Parallel Processing Architecture**: Multi-threaded parallel processing through ThreadPoolExecutor to evaluate strategies for multiple symbols simultaneously
- **Two-Phase Execution Model**: Parallel proposal generation followed by sequential WAL (Write-Ahead Log) execution
- **Plugin-Based Extensibility**: Dynamically load strategies, fee models, sizing models, etc.
- **Read-Only Data Access**: Secure data access through MongoDB slave nodes
- **Detailed Trade Tracking**: Precisely record all trade events and portfolio changes

## 전체 아키텍처 / Overall Architecture

### 시스템 구성도 / System Architecture Diagram

```mermaid
graph TB
    subgraph "외부 시스템 / External System"
        API[FastAPI Server]
        CELERY[Celery Worker]
        DOCKER_MGR["Docker Manager<br>OrchestratorService"]
    end
    
    subgraph "Docker Container [격리된 환경 / Isolated Environment]"
        subgraph "진입점 / Entry Point"
            MAIN["StrategyOrchestrator.py<br>__main__"]
        end
        
        subgraph "핵심 오케스트레이션 / Core Orchestration"
            RUN_BT["run_backtest()<br>메인 실행 함수"]
            LOADER["LoadComponent<br>동적 컴포넌트 로더"]
        end
        
        subgraph "병렬 처리 레이어 / Parallel Processing Layer"
            THREAD_POOL["ThreadPoolExecutor<br>병렬 워커 풀"]
            WORKER1["Worker 1<br>_proposals_for_job()"]
            WORKER2["Worker 2<br>_proposals_for_job()"]
            WORKERN["Worker N<br>_proposals_for_job()"]
        end
        
        subgraph "데이터 접근 레이어 / Data Access Layer"
            CANDLE_REPO["CandleRepository<br>읽기 전용 OHLCV 데이터"]
            MONGO_SLAVE[("MongoDB Slave<br>Secondary Node")]
        end
        
        subgraph "전략 레이어 / Strategy Layer"
            BASE_STRAT["BaseStrategy<br>추상 기본 클래스"]
            PEAK_EMA[PeakEMAReversalStrategy]
            MOMENTUM[MomentumStrategy]
            ENSEMBLE[EnsembleStrategy]
        end
        
        subgraph "포트폴리오 관리 / Portfolio Management"
            BASE_PM["BasePortfolioManager<br>기본 포트폴리오 매니저"]
            PERP_PM["PerpPortfolioManager<br>선물 포트폴리오 매니저"]
            LEDGER["TransactionLedger<br>거래 원장"]
        end
        
        subgraph "거래 관리 / Trade Management"
            PROPOSAL_BUILDER["TradeProposalBuilder<br>거래 제안 생성기"]
            TRADE_PROPOSAL["TradeProposal<br>거래 제안"]
            TRADE_EVENT["TradeEvent<br>거래 이벤트"]
            FILL_POLICY["FillPolicy<br>체결 정책"]
        end
        
        subgraph "정책 및 모델 / Policies & Models"
            FEE_MODEL["EventCostModel<br>수수료 모델"]
            SLIP_MODEL["SlippageModel<br>슬리피지 모델"]
            SIZE_MODEL["SizingModel<br>포지션 사이징"]
            CAP_POLICY["CapacityPolicy<br>용량 정책"]
        end
    end
    
    %% 연결 관계
    API -->|JSON 설정| CELERY
    CELERY -->|컨테이너 생성| DOCKER_MGR
    DOCKER_MGR -->|stdin JSON| MAIN
    MAIN -->|실행| RUN_BT
    
    RUN_BT -->|컴포넌트 로드| LOADER
    LOADER -->|인스턴스화| BASE_STRAT
    LOADER -->|인스턴스화| FEE_MODEL
    LOADER -->|인스턴스화| SIZE_MODEL
    
    RUN_BT -->|병렬 실행| THREAD_POOL
    THREAD_POOL -->|작업 분배| WORKER1
    THREAD_POOL -->|작업 분배| WORKER2
    THREAD_POOL -->|작업 분배| WORKERN
    
    WORKER1 -->|데이터 조회| CANDLE_REPO
    WORKER2 -->|데이터 조회| CANDLE_REPO
    WORKERN -->|데이터 조회| CANDLE_REPO
    
    CANDLE_REPO -->|읽기 전용| MONGO_SLAVE
    
    WORKER1 -->|전략 실행| BASE_STRAT
    BASE_STRAT -->|구현| PEAK_EMA
    BASE_STRAT -->|구현| MOMENTUM
    BASE_STRAT -->|구현| ENSEMBLE
    
    WORKER1 -->|제안 생성| PROPOSAL_BUILDER
    PROPOSAL_BUILDER -->|생성| TRADE_PROPOSAL
    
    RUN_BT -->|포트폴리오 초기화| BASE_PM
    BASE_PM -->|특수화| PERP_PM
    BASE_PM -->|사용| LEDGER
    
    BASE_PM -->|실행| TRADE_PROPOSAL
    TRADE_PROPOSAL -->|이벤트 생성| TRADE_EVENT
    LEDGER -->|체결 처리| FILL_POLICY
    
    FILL_POLICY -->|비용 계산| FEE_MODEL
    FILL_POLICY -->|슬리피지| SLIP_MODEL
    BASE_PM -->|사이징| SIZE_MODEL
    BASE_PM -->|용량 체크| CAP_POLICY
    
    style DOCKER_MGR fill:#f96
    style MAIN fill:#9cf
    style RUN_BT fill:#9f9
    style THREAD_POOL fill:#ff9
    style CANDLE_REPO fill:#f9f
    style BASE_PM fill:#99f
```

## 핵심 컴포넌트 상세 분석 / Core Component Detailed Analysis

### 1. StrategyOrchestrator.py - 메인 오케스트레이터 / Main Orchestrator

#### 한국어 설명
이 파일은 전체 백테스팅 프로세스의 진입점이자 조정자 역할을 합니다. 주요 책임:

1. **설정 파싱**: stdin으로 JSON 설정을 받아 파싱
2. **컴포넌트 초기화**: LoadComponent를 통해 필요한 모든 컴포넌트 동적 로드
3. **병렬 처리 관리**: ThreadPoolExecutor로 멀티스레드 작업 분배
4. **타임라인 구성**: 모든 거래 이벤트를 시간순으로 정렬하여 실행
5. **결과 집계**: 최종 백테스트 결과 생성 및 반환

#### English Description
This file serves as the entry point and coordinator for the entire backtesting process. Key responsibilities:

1. **Configuration Parsing**: Receive and parse JSON configuration from stdin
2. **Component Initialization**: Dynamically load all necessary components through LoadComponent
3. **Parallel Processing Management**: Distribute multi-threaded tasks via ThreadPoolExecutor
4. **Timeline Construction**: Sort and execute all trade events chronologically
5. **Result Aggregation**: Generate and return final backtest results

#### 핵심 함수 분석 / Core Function Analysis

```mermaid
sequenceDiagram
    participant Main as __main__
    participant RB as run_backtest()
    participant LC as LoadComponent
    participant TP as ThreadPool
    participant W as Worker
    participant PM as PortfolioManager
    participant TL as Timeline
    
    Main->>Main: stdin.read() JSON
    Main->>RB: run_backtest(cfg)
    
    RB->>LC: load_component(fee_model)
    LC-->>RB: EventCostModel
    RB->>LC: load_component(strategy)
    LC-->>RB: BaseStrategy
    
    RB->>TP: Create ThreadPoolExecutor
    RB->>W: submit(_proposals_for_job)
    
    par 병렬 처리 / Parallel Processing
        W->>W: fetch_candles()
        W->>W: strategy.decide()
        W->>W: build proposals
    end
    
    W-->>RB: proposals list
    
    RB->>RB: Sort proposals by time
    RB->>PM: Initialize PM
    
    RB->>TL: Build timeline
    loop 각 시간대 / Each timestamp
        TL->>PM: try_execute(proposal)
        TL->>PM: on_bar(ts, prices)
    end
    
    PM-->>RB: get_results()
    RB-->>Main: JSON results
```

### 2. LoadComponent.py - 동적 컴포넌트 로더 / Dynamic Component Loader

#### 한국어 설명
LoadComponent는 플러그인 시스템의 핵심으로, 다양한 형태의 컴포넌트 사양을 받아 실제 실행 가능한 객체로 변환합니다.

**지원하는 사양 형태:**
1. **스칼라 값**: 숫자나 문자열 → 내장 맵에서 조회
2. **내장 참조**: `{"builtin": "token"}` → 내장 컴포넌트 사용
3. **동적 임포트**: `{"module": "x.y", "class": "Cls"}` → 런타임 모듈 로드

#### English Description
LoadComponent is the core of the plugin system, converting various component specifications into actual executable objects.

**Supported specification formats:**
1. **Scalar values**: Numbers or strings → lookup in built-in maps
2. **Built-in references**: `{"builtin": "token"}` → use built-in components
3. **Dynamic imports**: `{"module": "x.y", "class": "Cls"}` → runtime module loading

#### 로드 프로세스 다이어그램 / Load Process Diagram

```mermaid
flowchart TD
    START["컴포넌트 사양<br>Component Spec"] --> CHECK{"사양 타입?<br>Spec Type?"}
    
    CHECK -->|None 또는 빈 dict| DEFAULT["기본값 사용<br>Use Default"]
    CHECK -->|"스칼라 값<br>Scalar Value"| SCALAR["내장 맵 조회<br>Builtin Map Lookup"]
    CHECK -->|builtin 키| BUILTIN["내장 컴포넌트<br>Builtin Component"]
    CHECK -->|module/class| DYNAMIC["동적 임포트<br>Dynamic Import"]
    
    DEFAULT --> RESOLVE["객체 해결<br>Resolve Object"]
    SCALAR --> RESOLVE
    BUILTIN --> RESOLVE
    DYNAMIC --> IMPORT["importlib.import_module()"]
    IMPORT --> GETATTR["getattr(mod, class)"]
    GETATTR --> RESOLVE
    
    RESOLVE --> TYPE{"객체 타입?<br>Object Type?"}
    TYPE -->|"클래스<br>Class"| INSTANTIATE["인스턴스 생성<br>Instantiate"]
    TYPE -->|"호출 가능<br>Callable"| RETURN["직접 반환<br>Return Directly"]
    
    INSTANTIATE --> VALIDATE{"기본 클래스 검증<br>Base Class Check"}
    VALIDATE -->|"통과<br>Pass"| FINAL["컴포넌트 반환<br>Return Component"]
    VALIDATE -->|"실패<br>Fail"| ERROR["TypeError 발생<br>Raise TypeError"]
    
    RETURN --> FINAL
```

### 3. BaseStrategy.py - 전략 기본 클래스 / Strategy Base Class

#### 한국어 설명
모든 트레이딩 전략의 추상 기본 클래스로, 전략 개발을 위한 표준 인터페이스를 정의합니다.

**핵심 메서드:**
- `decide()`: 주어진 OHLCV 데이터로 매매 결정
- `work_units()`: 병렬 처리를 위한 작업 단위 생성
- `get_required_lookback()`: 필요한 과거 데이터 기간
- `filter_symbols()`: 전략에 맞는 심볼 필터링

#### English Description
Abstract base class for all trading strategies, defining the standard interface for strategy development.

**Core methods:**
- `decide()`: Make trading decisions based on OHLCV data
- `work_units()`: Create work units for parallel processing
- `get_required_lookback()`: Required historical data period
- `filter_symbols()`: Filter symbols suitable for the strategy

#### 전략 실행 흐름 / Strategy Execution Flow

```mermaid
stateDiagram-v2
    [*] --> Initialize: 전략 초기화<br/>Strategy Init
    
    Initialize --> WorkUnits: work_units() 호출<br/>Create work units
    
    WorkUnits --> ParallelExec: 병렬 실행 준비<br/>Prepare parallel execution
    
    ParallelExec --> FetchData: 각 워커에서<br/>In each worker
    
    FetchData --> CheckData: 데이터 검증<br/>Validate data
    CheckData --> Decision: decide() 호출<br/>Call decide()
    
    Decision --> AnalyzeMarket: 시장 분석<br/>Analyze market
    AnalyzeMarket --> GenerateSignal: 신호 생성<br/>Generate signal
    
    GenerateSignal --> BuySignal: BUY 신호<br/>BUY signal
    GenerateSignal --> NoSignal: NO 신호<br/>NO signal
    GenerateSignal --> SellSignal: SELL 신호<br/>SELL signal
    
    BuySignal --> CreateProposal: 거래 제안 생성<br/>Create proposal
    NoSignal --> NextCandle: 다음 캔들<br/>Next candle
    SellSignal --> CreateProposal
    
    CreateProposal --> [*]: 제안 반환<br/>Return proposal
    NextCandle --> CheckData
```

### 4. BasePortfolioManager.py - 포트폴리오 관리자 / Portfolio Manager

#### 한국어 설명
이벤트 기반 포트폴리오 관리자로, 거래 이벤트를 처리하고 포지션과 현금을 추적합니다.

**주요 기능:**
1. **거래 이벤트 큐 관리**: 힙 기반 우선순위 큐로 시간순 처리
2. **포지션 추적**: 각 심볼별 포지션 상태 관리
3. **현금 흐름 관리**: 거래에 따른 현금 변동 추적
4. **리스크 관리**: 용량 정책, 현금 확인 등
5. **성과 측정**: 주식 곡선, 거래 로그 생성

#### English Description
Event-driven portfolio manager that processes trade events and tracks positions and cash.

**Key features:**
1. **Trade Event Queue Management**: Time-ordered processing with heap-based priority queue
2. **Position Tracking**: Manage position state for each symbol
3. **Cash Flow Management**: Track cash changes from trades
4. **Risk Management**: Capacity policies, cash checks, etc.
5. **Performance Measurement**: Generate equity curves, trade logs

#### 포트폴리오 관리 상태 머신 / Portfolio Management State Machine

```mermaid
stateDiagram-v2
    [*] --> Idle: 초기화<br/>Initialize
    
    Idle --> ProposalReceived: try_execute() 호출<br/>try_execute() called
    
    ProposalReceived --> CheckCapacity: 용량 확인<br/>Check capacity
    CheckCapacity --> CheckCash: 현금 확인<br/>Check cash
    CheckCapacity --> Rejected: 용량 초과<br/>Over capacity
    
    CheckCash --> CheckRisk: 리스크 확인<br/>Check risk
    CheckCash --> Rejected: 현금 부족<br/>Insufficient cash
    
    CheckRisk --> ApplySizing: 사이징 적용<br/>Apply sizing
    CheckRisk --> Rejected: 리스크 초과<br/>Risk exceeded
    
    ApplySizing --> QueueEvents: 이벤트 큐 추가<br/>Queue events
    QueueEvents --> Idle
    
    Idle --> BarUpdate: on_bar() 호출<br/>on_bar() called
    
    BarUpdate --> ProcessEvents: 만기 이벤트 처리<br/>Process due events
    ProcessEvents --> UpdateLedger: 원장 업데이트<br/>Update ledger
    UpdateLedger --> UpdateCash: 현금 업데이트<br/>Update cash
    UpdateCash --> UpdateEquity: 주식 가치 계산<br/>Calculate equity
    UpdateEquity --> Idle
    
    Rejected --> Idle
```

### 5. CandleRepository.py - 캔들 데이터 저장소 / Candle Data Repository

#### 한국어 설명
읽기 전용 OHLCV 데이터 접근을 위한 저장소 패턴 구현입니다. MongoDB 슬레이브 노드에만 연결하여 데이터 무결성을 보장합니다.

**보안 특징:**
- `secondaryPreferred` 읽기 설정 강제
- 연결 타임아웃 설정
- 커넥션 풀 관리

#### English Description
Repository pattern implementation for read-only OHLCV data access. Connects only to MongoDB slave nodes to ensure data integrity.

**Security features:**
- Force `secondaryPreferred` read preference
- Connection timeout settings
- Connection pool management

### 6. TradeProposal 및 TradeProposalBuilder - 거래 제안 시스템 / Trade Proposal System

#### 한국어 설명
거래 제안은 실행할 거래 계획을 선언적으로 표현합니다. Builder 패턴을 사용하여 복잡한 거래 전략을 구성할 수 있습니다.

**특징:**
- 다중 레그 지원 (scale-in/scale-out)
- 브래킷 주문 (TP/SL)
- 유연한 가격 참조
- 이벤트 기반 실행

#### English Description
Trade proposals declaratively express trading plans to execute. Using the Builder pattern, complex trading strategies can be composed.

**Features:**
- Multi-leg support (scale-in/scale-out)
- Bracket orders (TP/SL)
- Flexible price references
- Event-based execution

#### 거래 제안 생성 프로세스 / Trade Proposal Creation Process

```mermaid
sequenceDiagram
    participant S as Strategy
    participant TPB as TradeProposalBuilder
    participant TP as TradeProposal
    participant TE as TradeEvent
    
    S->>TPB: new TradeProposalBuilder(symbol, size, direction)
    S->>TPB: scale_in(n=1, start_pct=0, step_pct=0)
    S->>TPB: bracket_exit(tp=2.0, sl=1.0)
    S->>TPB: set_entry_params(entry_price, tp_price, sl_price)
    S->>TPB: build(detail_df)
    
    TPB->>TP: Create TradeProposal
    TPB->>TP: Set meta (TradeMeta)
    TPB->>TP: Set legs (OrderLeg[])
    TPB->>TP: Set detail_df
    
    Note over TP: build_events() 호출 시<br/>When build_events() called
    
    TP->>TP: Iterate through candles
    loop 각 캔들 / Each candle
        TP->>TP: Check leg triggers
        alt 트리거 조건 충족 / Trigger met
            TP->>TE: Create TradeEvent(OPEN)
            TP->>TP: Remove filled leg
        end
    end
    
    TP->>TP: Check exit conditions
    alt TP/SL 도달 / TP/SL hit
        TP->>TE: Create TradeEvent(CLOSE)
    end
    
    TP-->>S: Return TradeEvent[]
```

### 7. TransactionLedger - 거래 원장 / Transaction Ledger

#### 한국어 설명
모든 거래의 확정적 기록을 관리하는 원장 시스템입니다. 체결 정책을 통해 거래 이벤트를 실제 체결로 변환합니다.

**핵심 기능:**
- 포지션 추적
- 현금 델타 관리
- 체결 기록 저장
- 미실현 손익 계산

#### English Description
Ledger system that manages deterministic records of all trades. Converts trade events to actual fills through fill policies.

**Core features:**
- Position tracking
- Cash delta management
- Fill record storage
- Unrealized P&L calculation

## 데이터 흐름 및 처리 과정 / Data Flow and Processing

### 전체 데이터 흐름도 / Complete Data Flow Diagram

```mermaid
graph TB
    subgraph "입력 / Input"
        CONFIG["JSON 설정<br>JSON Config"]
        SYMBOLS["심볼 리스트<br>Symbol List"]
    end
    
    subgraph "Phase 1: 병렬 제안 생성 / Parallel Proposal Generation"
        CONFIG --> WORK_UNITS["작업 단위 생성<br>Create Work Units"]
        SYMBOLS --> WORK_UNITS
        
        WORK_UNITS --> WORKERS{"병렬 워커<br>Parallel Workers"}
        
        WORKERS --> W1[Worker 1]
        WORKERS --> W2[Worker 2]
        WORKERS --> WN[Worker N]
        
        W1 --> FETCH1["데이터 조회<br>Fetch Data"]
        W2 --> FETCH2["데이터 조회<br>Fetch Data"]
        WN --> FETCHN["데이터 조회<br>Fetch Data"]
        
        FETCH1 --> MERGE1["_merge_symbol_frames()"]
        FETCH2 --> MERGE2["_merge_symbol_frames()"]
        FETCHN --> MERGEN["_merge_symbol_frames()"]
        
        MERGE1 --> DECIDE1["strategy.decide()"]
        MERGE2 --> DECIDE2["strategy.decide()"]
        MERGEN --> DECIDEN["strategy.decide()"]
        
        DECIDE1 --> PROP1[TradeProposal 생성]
        DECIDE2 --> PROP2[TradeProposal 생성]
        DECIDEN --> PROPN[TradeProposal 생성]
    end
    
    subgraph "수집 및 정렬 / Collection & Sorting"
        PROP1 --> COLLECT["제안 수집<br>Collect Proposals"]
        PROP2 --> COLLECT
        PROPN --> COLLECT
        
        COLLECT --> SORT["시간순 정렬<br>Sort by Time"]
    end
    
    subgraph "Phase 2: 순차 실행 / Sequential Execution"
        SORT --> TIMELINE["타임라인 구성<br>Build Timeline"]
        
        TIMELINE --> LOOP{"각 타임스탬프<br>Each Timestamp"}
        
        LOOP --> CHECK_PROP{"제안 있음?<br>Proposals?"}
        CHECK_PROP -->|Yes| TRY_EXEC["try_execute()"]
        CHECK_PROP -->|No| ON_BAR["on_bar()"]
        
        TRY_EXEC --> CAN_OPEN{"실행 가능?<br>Can Open?"}
        CAN_OPEN -->|Yes| QUEUE_EVENTS["이벤트 큐 추가<br>Queue Events"]
        CAN_OPEN -->|No| SKIP["건너뛰기<br>Skip"]
        
        QUEUE_EVENTS --> ON_BAR
        SKIP --> ON_BAR
        
        ON_BAR --> PROCESS_DUE["만기 이벤트 처리<br>Process Due Events"]
        PROCESS_DUE --> UPDATE_LEDGER["원장 업데이트<br>Update Ledger"]
        UPDATE_LEDGER --> UPDATE_EQUITY["주식 가치 업데이트<br>Update Equity"]
        
        UPDATE_EQUITY --> LOOP
    end
    
    subgraph "결과 / Results"
        LOOP -->|"완료<br>Complete"| FINAL["최종 결과<br>Final Results"]
        FINAL --> CASH["최종 현금<br>Final Cash"]
        FINAL --> TRADES["거래 로그<br>Trade Log"]
        FINAL --> EQUITY["주식 곡선<br>Equity Curve"]
    end
```

### 병렬 처리 상세 / Parallel Processing Details

```mermaid
flowchart LR
    subgraph "작업 분배 / Work Distribution"
        STRAT["전략<br>Strategy"] -->|"work_units()"| JOBS["작업 리스트<br>Job List"]
        
        JOBS --> J1["Job 1:<br>symbols=['BTC']"]
        JOBS --> J2["Job 2:<br>symbols=['ETH']"]
        JOBS --> JN["Job N:<br>symbols=['XRP']"]
    end
    
    subgraph "ThreadPoolExecutor"
        J1 --> T1["Thread 1"]
        J2 --> T2["Thread 2"]
        JN --> TN["Thread N"]
        
        T1 --> F1["Future 1"]
        T2 --> F2["Future 2"]
        TN --> FN["Future N"]
    end
    
    subgraph "비동기 완료 / Async Completion"
        F1 --> AS_COMP["as_completed()"]
        F2 --> AS_COMP
        FN --> AS_COMP
        
        AS_COMP --> RESULTS["결과 수집<br>Collect Results"]
    end
```

## 클래스 다이어그램 및 관계 / Class Diagrams and Relationships

### 전체 클래스 관계도 / Complete Class Relationship Diagram

```mermaid
classDiagram
    %% 핵심 클래스들 / Core Classes
    class StrategyOrchestrator {
        +run_backtest(cfg: dict) dict
        -_new_logger() Logger
        -_merge_symbol_frames() DataFrame
        -_proposals_for_job() list
    }
    
    class LoadComponent {
        +load_component(spec, builtin, base_cls, label) Callable
    }
    
    %% 전략 계층 / Strategy Layer
    class BaseStrategy {
        <<abstract>>
        +decide(df, interval, **kwargs) dict
        +work_units(symbols) list
        +get_required_lookback() int
        +filter_symbols(symbols_df) list
        +aggregate_signals(trades) Any
        +required_indicators() list
        +fit(data) void
        +reset() void
        +set_params(**params) void
        +get_params() dict
        +get_indicator_periods() list
    }
    
    class PeakEMAReversalStrategy {
        +decide(df, interval, **kwargs) dict
        -_calculate_emas(df) tuple
        -_check_peak_reversal(emas) bool
    }
    
    class MomentumStrategy {
        +decide(df, interval, **kwargs) dict
        -_calculate_momentum(df) float
    }
    
    class EnsembleStrategy {
        -strategies: list[BaseStrategy]
        +decide(df, interval, **kwargs) dict
        +add_strategy(strategy) void
    }
    
    %% 포트폴리오 관리 / Portfolio Management
    class BasePortfolioManager {
        -cash: float
        -capacity: CapacityPolicy
        -sizer: SizingModel
        -tm: TransactionLedger
        -_event_q: list[TradeEvent]
        -_trade_log: list[dict]
        -equity_curve: list[dict]
        +try_execute(proposal, now_ts) bool
        +on_bar(ts, mark_prices) void
        +can_open(proposal, now_ts, first_entry) bool
        +get_results() dict
        #_open_symbols() set
        #_open_legs() int
        #_risk_ok(meta) bool
        #_cash_ok(entry_px, size) bool
        #_log_exit(ev, exec_px) void
    }
    
    class PerpPortfolioManager {
        -funding_rates: dict
        +apply_funding(ts) void
        +calculate_margin() float
    }
    
    %% 거래 관리 / Trade Management
    class TradeProposal {
        +meta: TradeMeta
        +legs: list[OrderLeg]
        +detail_df: DataFrame
        +build_events() list[TradeEvent]
        +realize() list[TradeEvent]
        -_triggered(idx, ts, candle, cond) bool
        -_resolve_price(candle, px) float
        -_check_exit(candle, tp_px, sl_px) dict
    }
    
    class TradeProposalBuilder {
        -symbol: str
        -size: float
        -direction: str
        -_legs: list[OrderLeg]
        +scale_in(n, start_pct, step_pct, reference) self
        +bracket_exit(tp, sl, crossing_policy, exit_resolver) self
        +set_entry_params(entry_price, tp_price, sl_price, entry_ts) self
        +build(detail_df) TradeProposal
    }
    
    class TradeMeta {
        +symbol: str
        +entry_time: int
        +entry_price: float
        +tp_price: float
        +sl_price: float
        +size: float
        +direction: str
    }
    
    class TradeEvent {
        +ts: int
        +price: float
        +qty: float
        +event: TradeEventType
        +meta: dict
        +is_entry: bool
        +is_exit: bool
    }
    
    class OrderLeg {
        +qty: float
        +side: str
        +px: float|Callable
        +when: int|float|Callable
        +tif: str
        +comment: str
    }
    
    %% 원장 시스템 / Ledger System
    class TransactionLedger {
        +positions: dict[str, Position]
        -_cash_log: list[tuple]
        -_fills: list[FillRecord]
        -_fill_policy: FillPolicy
        +ingest(events) void
        +current_cash_delta() float
        +pop_cash_delta() float
        +unrealised_pnl(mark_prices) float
        +get_fills() list[FillRecord]
        -_apply_fill(fill) void
    }
    
    class Position {
        +symbol: str
        +qty: float
        +avg_px: float
        +total_cost: float
        +apply(event) void
        +mark_to_market(price) float
    }
    
    class FillRecord {
        +ts: int
        +symbol: str
        +qty: float
        +exec_price: float
        +fee_cash: float
        +event: TradeEventType
        +meta: dict
    }
    
    %% 정책 인터페이스 / Policy Interfaces
    class CapacityPolicy {
        <<interface>>
        +admit(proposal, now_ts, event_q, open_symbols) bool
    }
    
    class EventCostModel {
        <<interface>>
        +__call__(event) float
    }
    
    class SizingModel {
        <<interface>>
        +__call__(meta, action) float
    }
    
    class FillPolicy {
        <<interface>>
        +fill(event, book) list[FillRecord]
    }
    
    %% 데이터 접근 / Data Access
    class CandleRepository {
        -_client: MongoClient
        -_col: Collection
        +fetch_candles(symbol, interval, limit, start_time, newest_first) DataFrame
    }
    
    %% 관계 정의 / Relationships
    StrategyOrchestrator ..> LoadComponent : uses
    StrategyOrchestrator ..> BaseStrategy : loads
    StrategyOrchestrator ..> BasePortfolioManager : creates
    StrategyOrchestrator ..> CandleRepository : uses
    StrategyOrchestrator ..> TradeProposalBuilder : uses
    
    LoadComponent ..> BaseStrategy : instantiates
    LoadComponent ..> CapacityPolicy : instantiates
    LoadComponent ..> EventCostModel : instantiates
    LoadComponent ..> SizingModel : instantiates
    LoadComponent ..> FillPolicy : instantiates
    
    BaseStrategy <|-- PeakEMAReversalStrategy : extends
    BaseStrategy <|-- MomentumStrategy : extends
    BaseStrategy <|-- EnsembleStrategy : extends
    
    BasePortfolioManager <|-- PerpPortfolioManager : extends
    BasePortfolioManager *-- TransactionLedger : contains
    BasePortfolioManager ..> TradeProposal : executes
    BasePortfolioManager ..> CapacityPolicy : uses
    BasePortfolioManager ..> SizingModel : uses
    
    TradeProposalBuilder ..> TradeProposal : builds
    TradeProposal *-- TradeMeta : contains
    TradeProposal *-- OrderLeg : contains
    TradeProposal ..> TradeEvent : generates
    
    TransactionLedger *-- Position : manages
    TransactionLedger *-- FillRecord : stores
    TransactionLedger ..> FillPolicy : uses
    TransactionLedger ..> EventCostModel : uses
```

### 이벤트 처리 시퀀스 / Event Processing Sequence

```mermaid
sequenceDiagram
    participant PM as PortfolioManager
    participant EQ as Event Queue
    participant TL as TransactionLedger
    participant FP as FillPolicy
    participant POS as Position
    participant CASH as Cash Log
    
    Note over PM: try_execute(proposal) 호출
    
    PM->>PM: can_open() 체크
    alt 실행 가능
        PM->>PM: apply sizing
        PM->>EQ: heappush(events)
    else 실행 불가
        PM-->>PM: return False
    end
    
    Note over PM: on_bar(ts, prices) 호출
    
    loop 만기 이벤트 처리
        EQ->>PM: heappop(event)
        PM->>TL: ingest([event])
        TL->>FP: fill(event)
        FP-->>TL: FillRecord[]
        
        loop 각 FillRecord
            TL->>POS: apply(pseudo_event)
            TL->>CASH: append((ts, cash_delta))
        end
    end
    
    PM->>TL: pop_cash_delta()
    TL-->>PM: cash_delta
    PM->>PM: cash += cash_delta
    
    PM->>TL: unrealised_pnl(prices)
    TL->>POS: mark_to_market(price)
    POS-->>TL: pnl
    TL-->>PM: total_pnl
    
    PM->>PM: Update equity curve
```

## 보안 및 격리 메커니즘 / Security and Isolation Mechanisms

### 보안 아키텍처 / Security Architecture

```mermaid
graph TB
    subgraph "호스트 시스템 / Host System"
        HOST_OS[호스트 OS<br/>Host OS]
        DOCKER_ENGINE[Docker Engine]
        ORCH_SVC[OrchestratorService]
    end
    
    subgraph "격리된 컨테이너 / Isolated Container"
        subgraph "보안 설정 / Security Settings"
            READONLY[읽기 전용 파일시스템<br/>Read-only filesystem]
            NO_NET[네트워크 격리<br/>Network isolation]
            MEM_LIMIT[메모리 제한: 2GB<br/>Memory limit: 2GB]
            CPU_LIMIT[CPU 제한: 100000<br/>CPU limit: 100000]
        end
        
        subgraph "실행 환경 / Execution Environment"
            PYTHON[Python Runtime]
            STRATEGY[Strategy Code]
            ORCHESTRATOR[StrategyOrchestrator]
        end
        
        subgraph "데이터 접근 / Data Access"
            CANDLE_REPO[CandleRepository]
            MONGO_CLIENT[MongoClient<br/>secondaryPreferred]
        end
    end
    
    subgraph "데이터베이스 / Database"
        MONGO_SLAVE[(MongoDB Slave<br/>Read-only)]
    end
    
    ORCH_SVC -->|생성/관리| DOCKER_ENGINE
    DOCKER_ENGINE -->|격리 실행| READONLY
    DOCKER_ENGINE -->|리소스 제한| MEM_LIMIT
    DOCKER_ENGINE -->|리소스 제한| CPU_LIMIT
    DOCKER_ENGINE -->|네트워크 정책| NO_NET
    
    ORCHESTRATOR -->|사용| CANDLE_REPO
    CANDLE_REPO -->|읽기 전용 연결| MONGO_CLIENT
    MONGO_CLIENT -->|쿼리| MONGO_SLAVE
    
    style READONLY fill:#f99
    style NO_NET fill:#f99
    style MEM_LIMIT fill:#f99
    style CPU_LIMIT fill:#f99
    style MONGO_SLAVE fill:#9f9
```

### 격리 레벨 / Isolation Levels

#### 한국어
1. **프로세스 격리**: Docker 컨테이너로 완전한 프로세스 격리
2. **파일시스템 격리**: 읽기 전용 마운트, 임시 파일 시스템
3. **네트워크 격리**: 별도의 브리지 네트워크, 외부 접근 차단
4. **리소스 격리**: cgroups를 통한 CPU/메모리 제한
5. **데이터 격리**: 읽기 전용 데이터베이스 접근

#### English
1. **Process Isolation**: Complete process isolation with Docker containers
2. **Filesystem Isolation**: Read-only mounts, temporary filesystems
3. **Network Isolation**: Separate bridge network, external access blocked
4. **Resource Isolation**: CPU/memory limits through cgroups
5. **Data Isolation**: Read-only database access

## 성능 최적화 전략 / Performance Optimization Strategies

### 최적화 기법 / Optimization Techniques

```mermaid
graph LR
    subgraph "병렬화 / Parallelization"
        THREAD[ThreadPoolExecutor]
        WORKERS[다중 워커<br/>Multiple Workers]
        ASYNC[비동기 처리<br/>Async Processing]
    end
    
    subgraph "캐싱 / Caching"
        REDIS[Redis 캐시<br/>Redis Cache]
        RESULT_CACHE[결과 캐싱<br/>Result Caching]
        DATA_CACHE[데이터 캐싱<br/>Data Caching]
    end
    
    subgraph "데이터 최적화 / Data Optimization"
        BATCH[배치 로딩<br/>Batch Loading]
        INDEX[인덱스 활용<br/>Index Usage]
        PROJECTION[필드 프로젝션<br/>Field Projection]
    end
    
    subgraph "메모리 관리 / Memory Management"
        DF_OPT[DataFrame 최적화<br/>DataFrame Optimization]
        GC[가비지 컬렉션<br/>Garbage Collection]
        POOL[객체 풀링<br/>Object Pooling]
    end
    
    THREAD --> WORKERS
    WORKERS --> ASYNC
    
    REDIS --> RESULT_CACHE
    RESULT_CACHE --> DATA_CACHE
    
    BATCH --> INDEX
    INDEX --> PROJECTION
    
    DF_OPT --> GC
    GC --> POOL
```

### 병렬 처리 최적화 상세 / Parallel Processing Optimization Details

#### 한국어
1. **작업 분배 전략**:
   - 심볼별 균등 분배
   - 데이터 크기 기반 동적 분배
   - CPU 코어 수 고려한 워커 수 설정

2. **메모리 효율성**:
   - DataFrame 청크 처리
   - 불필요한 컬럼 제거
   - 데이터 타입 최적화

3. **I/O 최적화**:
   - 배치 데이터베이스 쿼리
   - 연결 풀링
   - 비동기 I/O

#### English
1. **Work Distribution Strategy**:
   - Equal distribution by symbol
   - Dynamic distribution based on data size
   - Worker count based on CPU cores

2. **Memory Efficiency**:
   - DataFrame chunk processing
   - Remove unnecessary columns
   - Data type optimization

3. **I/O Optimization**:
   - Batch database queries
   - Connection pooling
   - Asynchronous I/O

## 확장 포인트 및 플러그인 시스템 / Extension Points and Plugin System

### 플러그인 아키텍처 / Plugin Architecture

```mermaid
graph TB
    subgraph "설정 / Configuration"
        JSON[JSON 설정<br/>JSON Config]
        SPEC[컴포넌트 사양<br/>Component Spec]
    end
    
    subgraph "로더 / Loader"
        LOAD[LoadComponent]
        BUILTIN[내장 맵<br/>Built-in Maps]
        DYNAMIC[동적 로더<br/>Dynamic Loader]
    end
    
    subgraph "확장 포인트 / Extension Points"
        subgraph "전략 / Strategies"
            STRAT_BASE[BaseStrategy]
            CUSTOM_STRAT[사용자 전략<br/>Custom Strategy]
        end
        
        subgraph "정책 / Policies"
            CAP_BASE[CapacityPolicy]
            CUSTOM_CAP[사용자 용량 정책<br/>Custom Capacity]
        end
        
        subgraph "모델 / Models"
            FEE_BASE[EventCostModel]
            CUSTOM_FEE[사용자 수수료 모델<br/>Custom Fee Model]
        end
        
        subgraph "체결 / Execution"
            FILL_BASE[FillPolicy]
            CUSTOM_FILL[사용자 체결 정책<br/>Custom Fill Policy]
        end
    end
    
    JSON --> SPEC
    SPEC --> LOAD
    
    LOAD --> BUILTIN
    LOAD --> DYNAMIC
    
    BUILTIN --> STRAT_BASE
    DYNAMIC --> CUSTOM_STRAT
    CUSTOM_STRAT -.->|implements| STRAT_BASE
    
    BUILTIN --> CAP_BASE
    DYNAMIC --> CUSTOM_CAP
    CUSTOM_CAP -.->|implements| CAP_BASE
    
    BUILTIN --> FEE_BASE
    DYNAMIC --> CUSTOM_FEE
    CUSTOM_FEE -.->|implements| FEE_BASE
    
    BUILTIN --> FILL_BASE
    DYNAMIC --> CUSTOM_FILL
    CUSTOM_FILL -.->|implements| FILL_BASE
```

### 커스텀 컴포넌트 개발 가이드 / Custom Component Development Guide

#### 커스텀 전략 예제 / Custom Strategy Example

```python
# 커스텀 전략 구현 예제
from strategyOrchestrator.entities.strategies.BaseStrategy import BaseStrategy
import pandas as pd
from typing import Dict, Any, List

class MyCustomStrategy(BaseStrategy):
    """
    사용자 정의 트레이딩 전략
    Custom trading strategy
    """
    
    def __init__(self, **params):
        self.rsi_period = params.get('rsi_period', 14)
        self.rsi_oversold = params.get('rsi_oversold', 30)
        self.rsi_overbought = params.get('rsi_overbought', 70)
        
    def decide(self, df: pd.DataFrame, interval: str, **kwargs) -> Dict[str, Any]:
        """
        RSI 기반 매매 결정
        RSI-based trading decision
        """
        # RSI 계산
        rsi = self._calculate_rsi(df, self.rsi_period)
        
        # 매매 신호 생성
        if rsi.iloc[-1] < self.rsi_oversold:
            signal = "BUY"
            confidence = (self.rsi_oversold - rsi.iloc[-1]) / self.rsi_oversold
        elif rsi.iloc[-1] > self.rsi_overbought:
            signal = "SELL"
            confidence = (rsi.iloc[-1] - self.rsi_overbought) / (100 - self.rsi_overbought)
        else:
            signal = "NO"
            confidence = 0.0
            
        # 가격 계산
        current_price = float(df.iloc[-1]['close'])
        tp_price = current_price * (1 + kwargs.get('tp_ratio', 0.02))
        sl_price = current_price * (1 - kwargs.get('sl_ratio', 0.01))
        
        return {
            "signal": signal,
            "entry_price": current_price,
            "tp_price": tp_price,
            "sl_price": sl_price,
            "confidence": confidence,
            "meta": {
                "rsi": float(rsi.iloc[-1]),
                "strategy": "MyCustomStrategy"
            },
            "strategy_name": "MyCustomStrategy"
        }
    
    def get_required_lookback(self) -> int:
        """필요한 과거 데이터 기간"""
        return self.rsi_period + 10
    
    def _calculate_rsi(self, df: pd.DataFrame, period: int) -> pd.Series:
        """RSI 지표 계산"""
        # RSI 계산 로직
        pass
```

#### 설정 파일에서 사용 / Usage in Configuration

```json
{
    "strategy": {
        "module": "my_strategies.custom",
        "class": "MyCustomStrategy",
        "params": {
            "rsi_period": 14,
            "rsi_oversold": 25,
            "rsi_overbought": 75
        }
    }
}
```

## 디버깅 및 모니터링 / Debugging and Monitoring

### 로깅 아키텍처 / Logging Architecture

```mermaid
graph TD
    subgraph "로그 소스 / Log Sources"
        ORCH[StrategyOrchestrator]
        STRAT[Strategy]
        PM[PortfolioManager]
        REPO[CandleRepository]
    end
    
    subgraph "로거 / Loggers"
        MAIN_LOG[Main Logger<br/>Backtest_XXXX]
        STDERR[stderr Handler]
        FORMAT[Timestamp + Tag Format]
    end
    
    subgraph "로그 출력 / Log Output"
        CONSOLE[콘솔 출력<br/>Console Output]
        DOCKER[Docker Logs]
        HOST[호스트 로그<br/>Host Logs]
    end
    
    ORCH --> MAIN_LOG
    STRAT --> MAIN_LOG
    PM --> MAIN_LOG
    REPO --> MAIN_LOG
    
    MAIN_LOG --> FORMAT
    FORMAT --> STDERR
    STDERR --> CONSOLE
    CONSOLE --> DOCKER
    DOCKER --> HOST
```

### 성능 모니터링 포인트 / Performance Monitoring Points

#### 한국어
1. **병렬 처리 성능**:
   - 워커별 처리 시간
   - 작업 큐 크기
   - 스레드 풀 활용률

2. **메모리 사용량**:
   - DataFrame 메모리 사용
   - 이벤트 큐 크기
   - 포지션 맵 크기

3. **데이터베이스 성능**:
   - 쿼리 실행 시간
   - 연결 풀 상태
   - 데이터 전송량

#### English
1. **Parallel Processing Performance**:
   - Processing time per worker
   - Work queue size
   - Thread pool utilization

2. **Memory Usage**:
   - DataFrame memory usage
   - Event queue size
   - Position map size

3. **Database Performance**:
   - Query execution time
   - Connection pool status
   - Data transfer volume

## 결론 / Conclusion

### 한국어
Strategy Orchestrator는 안전성, 확장성, 성능을 모두 고려한 정교한 백테스팅 시스템입니다. Docker 기반 격리, 병렬 처리, 플러그인 아키텍처를 통해 다양한 트레이딩 전략을 효율적으로 테스트할 수 있습니다. 이 문서에서 다룬 상세한 아키텍처와 구현 세부사항은 시스템의 유지보수와 확장에 필요한 모든 정보를 제공합니다.

### English
The Strategy Orchestrator is a sophisticated backtesting system that considers safety, scalability, and performance. Through Docker-based isolation, parallel processing, and plugin architecture, various trading strategies can be efficiently tested. The detailed architecture and implementation details covered in this document provide all the information necessary for system maintenance and extension.
