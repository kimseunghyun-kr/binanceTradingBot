# Strategy Orchestrator Architecture Documentation / 전략 오케스트레이터 아키텍처 문서

## 개요 / Overview

### 한국어
Strategy Orchestrator는 바이낸스 트레이딩 봇의 핵심 구성 요소로, 트레이딩 전략을 안전하고 격리된 환경에서 실행하는 시스템입니다. 이 시스템은 Docker 컨테이너를 활용하여 각 백테스트를 샌드박스 환경에서 실행하며, 읽기 전용 MongoDB 접근을 통해 시스템 보안을 보장합니다.

주요 특징:
- 병렬 처리를 통한 고성능 백테스팅
- Docker 컨테이너 기반 격리 실행
- 읽기 전용 데이터베이스 접근으로 데이터 무결성 보장
- 유연한 전략 플러그인 시스템

### English
The Strategy Orchestrator is a core component of the Binance Trading Bot that executes trading strategies in a secure, isolated environment. The system leverages Docker containers to run each backtest in a sandboxed environment and ensures system security through read-only MongoDB access.

Key features:
- High-performance backtesting through parallel processing
- Docker container-based isolated execution
- Data integrity guaranteed through read-only database access
- Flexible strategy plugin system

## 시스템 아키텍처 / System Architecture

### 상위 수준 아키텍처 / High-Level Architecture

```mermaid
graph TB
    subgraph "메인 시스템 / Main System"
        API[FastAPI<br/>API Layer]
        CELERY[Celery Worker<br/>비동기 작업 처리]
        ORCH_SVC[OrchestratorService<br/>컨테이너 관리]
        REDIS[(Redis<br/>캐시 & 큐)]
        MONGO_M[(MongoDB Master<br/>쓰기)]
    end
    
    subgraph "샌드박스 환경 / Sandbox Environment"
        DOCKER[Docker Container<br/>격리된 실행 환경]
        STRAT_ORCH[StrategyOrchestrator<br/>전략 실행 엔진]
        MONGO_S[(MongoDB Slave<br/>읽기 전용)]
    end
    
    API -->|백테스트 요청| CELERY
    CELERY -->|실행 위임| ORCH_SVC
    ORCH_SVC -->|컨테이너 생성| DOCKER
    DOCKER -->|내부 실행| STRAT_ORCH
    STRAT_ORCH -->|데이터 조회| MONGO_S
    ORCH_SVC -->|결과 캐싱| REDIS
    CELERY -->|결과 저장| MONGO_M
    
    style DOCKER fill:#f9f,stroke:#333,stroke-width:4px
    style STRAT_ORCH fill:#bbf,stroke:#333,stroke-width:2px
```

### 컴포넌트 관계도 / Component Relationships

```mermaid
classDiagram
    class StrategyOrchestrator {
        +run_backtest(config: dict) dict
        -_proposals_for_job(job: dict) list
        -_merge_symbol_frames() DataFrame
    }
    
    class BaseStrategy {
        <<abstract>>
        +decide(df: DataFrame) dict
        +get_required_lookback() int
        +work_units(symbols: list) list
    }
    
    class BasePortfolioManager {
        -cash: float
        -positions: dict
        +try_execute(proposal) bool
        +on_bar(ts, prices) void
        +get_results() dict
    }
    
    class CandleRepository {
        -mongo_client: MongoClient
        +fetch_candles(symbol, interval) DataFrame
    }
    
    class TradeProposal {
        +symbol: str
        +direction: str
        +size: float
        +build_events() list[TradeEvent]
    }
    
    class LoadComponent {
        +load_component(spec, builtin, base_cls) Callable
    }
    
    StrategyOrchestrator --> BaseStrategy : uses
    StrategyOrchestrator --> BasePortfolioManager : manages
    StrategyOrchestrator --> CandleRepository : fetches data
    StrategyOrchestrator --> LoadComponent : loads components
    BasePortfolioManager --> TradeProposal : executes
    BaseStrategy <|-- PeakEMAReversalStrategy : implements
    BaseStrategy <|-- MomentumStrategy : implements
```

## 핵심 워크플로우 / Core Workflows

### 백테스트 실행 프로세스 / Backtest Execution Process

```mermaid
sequenceDiagram
    participant User as 사용자/User
    participant API as API Layer
    participant Celery as Celery Worker
    participant OrchSvc as OrchestratorService
    participant Docker as Docker Container
    participant StratOrch as StrategyOrchestrator
    participant MongoDB as MongoDB Slave
    
    User->>API: 백테스트 요청<br/>Submit backtest request
    API->>Celery: 비동기 작업 생성<br/>Create async task
    Celery->>OrchSvc: 백테스트 실행<br/>Execute backtest
    
    OrchSvc->>Docker: 컨테이너 생성<br/>Create container
    OrchSvc->>Docker: 전략 코드 업로드<br/>Upload strategy code
    OrchSvc->>Docker: JSON 설정 전송<br/>Send JSON config
    
    Docker->>StratOrch: 프로세스 시작<br/>Start process
    StratOrch->>MongoDB: 캔들 데이터 조회<br/>Fetch candle data
    
    loop 각 심볼에 대해 / For each symbol
        StratOrch->>StratOrch: 전략 실행<br/>Execute strategy
        StratOrch->>StratOrch: 거래 제안 생성<br/>Generate proposals
    end
    
    StratOrch->>StratOrch: 포트폴리오 시뮬레이션<br/>Simulate portfolio
    StratOrch-->>Docker: 결과 반환<br/>Return results
    Docker-->>OrchSvc: 로그 & 결과<br/>Logs & results
    OrchSvc-->>Celery: 백테스트 결과<br/>Backtest results
    Celery-->>API: 완료 통지<br/>Completion notice
    API-->>User: 결과 표시<br/>Display results
```

### 전략 실행 상세 플로우 / Strategy Execution Detail Flow

```mermaid
graph LR
    subgraph "병렬 처리 단계 / Parallel Processing Phase"
        A[심볼 리스트<br/>Symbol List] --> B[작업 단위 생성<br/>Create Work Units]
        B --> C1[Worker 1]
        B --> C2[Worker 2]  
        B --> C3[Worker N]
        
        C1 --> D1[데이터 조회<br/>Fetch Data]
        C2 --> D2[데이터 조회<br/>Fetch Data]
        C3 --> D3[데이터 조회<br/>Fetch Data]
        
        D1 --> E1[전략 실행<br/>Run Strategy]
        D2 --> E2[전략 실행<br/>Run Strategy]
        D3 --> E3[전략 실행<br/>Run Strategy]
        
        E1 --> F[거래 제안 수집<br/>Collect Proposals]
        E2 --> F
        E3 --> F
    end
    
    subgraph "순차 처리 단계 / Sequential Processing Phase"
        F --> G[시간순 정렬<br/>Sort by Time]
        G --> H[포트폴리오 매니저<br/>Portfolio Manager]
        H --> I[WAL 실행<br/>WAL Execution]
        I --> J[결과 생성<br/>Generate Results]
    end
```

## 기술적 상세 구현 / Technical Implementation Details

### 컴포넌트 로딩 시스템 / Component Loading System

```mermaid
graph TD
    A[컴포넌트 사양<br/>Component Spec] --> B{사양 타입<br/>Spec Type}
    
    B -->|스칼라 값<br/>Scalar Value| C[내장 조회<br/>Builtin Lookup]
    B -->|builtin 키<br/>builtin key| D[내장 맵<br/>Builtin Map]
    B -->|module/class| E[동적 임포트<br/>Dynamic Import]
    
    C --> F[객체 해결<br/>Resolve Object]
    D --> F
    E --> F
    
    F --> G{객체 타입<br/>Object Type}
    G -->|클래스<br/>Class| H[인스턴스화<br/>Instantiate]
    G -->|호출 가능<br/>Callable| I[직접 반환<br/>Return Directly]
    
    H --> J[컴포넌트 반환<br/>Return Component]
    I --> J
```

### 데이터 접근 패턴 / Data Access Pattern

```mermaid
graph LR
    subgraph "샌드박스 환경 / Sandbox Environment"
        A[StrategyOrchestrator] --> B[CandleRepository]
        B --> C{읽기 전용<br/>Read-Only}
        C --> D[(MongoDB Slave<br/>Secondary Node)]
    end
    
    subgraph "보안 설정 / Security Settings"
        E[secondaryPreferred]
        F[읽기 전용 URI<br/>Read-Only URI]
        G[격리된 네트워크<br/>Isolated Network]
    end
    
    C -.-> E
    C -.-> F
    C -.-> G
```

## 주요 디자인 결정 / Key Design Decisions

### 샌드박싱 전략 / Sandboxing Strategy

#### 한국어
1. **컨테이너 격리**: 각 백테스트는 독립적인 Docker 컨테이너에서 실행되어 호스트 시스템과 완전히 격리됩니다.
2. **읽기 전용 데이터 접근**: MongoDB slave 노드에만 접근하여 데이터 무결성을 보장합니다.
3. **리소스 제한**: 메모리(2GB)와 CPU 할당량을 제한하여 시스템 안정성을 유지합니다.
4. **자동 정리**: 컨테이너는 실행 후 자동으로 제거되어 리소스 누수를 방지합니다.

#### English
1. **Container Isolation**: Each backtest runs in an independent Docker container, completely isolated from the host system.
2. **Read-Only Data Access**: Access only to MongoDB slave nodes ensures data integrity.
3. **Resource Limits**: Memory (2GB) and CPU quotas maintain system stability.
4. **Automatic Cleanup**: Containers are automatically removed after execution to prevent resource leaks.

### 병렬 처리 아키텍처 / Parallel Processing Architecture

```mermaid
graph TB
    subgraph "Phase 1: 병렬 제안 생성 / Parallel Proposal Generation"
        A[ThreadPoolExecutor] --> B[Worker 1]
        A --> C[Worker 2]
        A --> D[Worker N]
        
        B --> E[심볼 A 처리<br/>Process Symbol A]
        C --> F[심볼 B 처리<br/>Process Symbol B]  
        D --> G[심볼 N 처리<br/>Process Symbol N]
    end
    
    subgraph "Phase 2: 순차 WAL 실행 / Sequential WAL Execution"
        H[정렬된 제안<br/>Sorted Proposals] --> I[타임라인 구성<br/>Build Timeline]
        I --> J[순차 실행<br/>Sequential Execution]
        J --> K[포트폴리오 업데이트<br/>Portfolio Updates]
    end
    
    E --> H
    F --> H
    G --> H
```

## 보안 고려사항 / Security Considerations

### 보안 계층 / Security Layers

```mermaid
graph TD
    subgraph "네트워크 격리 / Network Isolation"
        A[Docker Network<br/>격리된 브리지 네트워크]
    end
    
    subgraph "데이터 접근 제어 / Data Access Control"
        B[읽기 전용 MongoDB URI]
        C[Secondary Node 전용]
        D[인증 활성화 옵션]
    end
    
    subgraph "리소스 제한 / Resource Limits"
        E[메모리 제한: 2GB]
        F[CPU 할당량: 100000]
        G[로그 크기 제한]
    end
    
    subgraph "코드 격리 / Code Isolation"
        H[사용자 전략 격리 디렉토리]
        I[Python 샌드박스 환경]
    end
```

## 사용자를 위한 가이드 / User Guide

### 퀀트 투자자를 위한 설명 / For Quantitative Investors

#### 한국어
Strategy Orchestrator는 여러분의 트레이딩 전략을 안전하게 테스트할 수 있는 백테스팅 엔진입니다. 

**작동 방식:**
1. 전략 정의: 매수/매도 조건을 Python 코드로 작성
2. 데이터 준비: 시스템이 자동으로 과거 가격 데이터를 로드
3. 시뮬레이션: 실제 시장과 동일한 조건에서 전략 실행
4. 결과 분석: 수익률, 거래 횟수, 승률 등 상세 지표 제공

**주요 이점:**
- 실제 자금 위험 없이 전략 검증
- 다양한 시장 조건에서 전략 성능 평가
- 병렬 처리로 빠른 백테스트 실행
- 전략 코드가 시스템에 영향을 주지 않는 안전한 실행

#### English
The Strategy Orchestrator is a backtesting engine that allows you to safely test your trading strategies.

**How it works:**
1. Define Strategy: Write buy/sell conditions in Python code
2. Data Preparation: System automatically loads historical price data
3. Simulation: Execute strategy under real market conditions
4. Result Analysis: Provides detailed metrics like returns, trade count, win rate

**Key Benefits:**
- Validate strategies without real capital risk
- Evaluate strategy performance under various market conditions
- Fast backtesting through parallel processing
- Safe execution where strategy code cannot affect the system

### 프로그래머를 위한 구현 세부사항 / Implementation Details for Programmers

#### 전략 개발 가이드 / Strategy Development Guide

```python
# 커스텀 전략 예제 / Custom Strategy Example
from strategyOrchestrator.entities.strategies.BaseStrategy import BaseStrategy

class MyCustomStrategy(BaseStrategy):
    def decide(self, df: pd.DataFrame, interval: str, **kwargs) -> Dict[str, Any]:
        """
        전략 로직 구현 / Implement strategy logic
        
        Args:
            df: OHLCV 데이터프레임 / OHLCV dataframe
            interval: 시간 간격 (예: '1h', '1d') / Time interval
            
        Returns:
            거래 신호 딕셔너리 / Trade signal dictionary
        """
        # 전략 로직 구현
        signal = self._analyze_market(df)
        
        return {
            "signal": signal,  # "BUY", "SELL", or "NO"
            "entry_price": entry_price,
            "tp_price": take_profit_price,
            "sl_price": stop_loss_price,
            "confidence": confidence_score,
            "meta": {"custom_data": value}
        }
```

#### 플러그인 시스템 활용 / Using the Plugin System

```mermaid
graph LR
    A[전략 설정<br/>Strategy Config] --> B[LoadComponent]
    
    B --> C{설정 타입}
    C -->|내장 전략| D[STRAT_MAP<br/>내장 전략 맵]
    C -->|커스텀 모듈| E[동적 임포트<br/>Dynamic Import]
    
    D --> F[전략 인스턴스<br/>Strategy Instance]
    E --> F
    
    F --> G[StrategyOrchestrator<br/>실행 엔진]
```

## 성능 최적화 / Performance Optimization

### 병렬 처리 최적화 / Parallel Processing Optimization

```mermaid
graph TD
    subgraph "리소스 할당 / Resource Allocation"
        A[parallel_symbols 파라미터] --> B[ThreadPoolExecutor 크기]
        B --> C[동시 실행 워커 수]
    end
    
    subgraph "캐싱 전략 / Caching Strategy"
        D[Redis 캐시] --> E[백테스트 결과]
        F[SHA256 해시] --> G[캐시 키 생성]
    end
    
    subgraph "데이터 최적화 / Data Optimization"
        H[배치 데이터 로드]
        I[인덱싱된 MongoDB 쿼리]
        J[메모리 효율적 DataFrame 처리]
    end
```

## 확장성 고려사항 / Scalability Considerations

### 미래 확장 가능성 / Future Extensibility

#### 한국어
1. **전략 마켓플레이스**: 사용자가 전략을 공유하고 거래할 수 있는 생태계
2. **실시간 거래 통합**: 백테스트에서 검증된 전략을 실거래로 연결
3. **ML 모델 지원**: 머신러닝 기반 전략 실행을 위한 프레임워크
4. **분산 백테스팅**: 여러 노드에서 대규모 백테스트 실행

#### English
1. **Strategy Marketplace**: Ecosystem for users to share and trade strategies
2. **Live Trading Integration**: Connect validated strategies from backtests to live trading
3. **ML Model Support**: Framework for executing machine learning-based strategies
4. **Distributed Backtesting**: Large-scale backtesting across multiple nodes

## 문제 해결 가이드 / Troubleshooting Guide

### 일반적인 문제와 해결책 / Common Issues and Solutions

```mermaid
graph TD
    A[문제 발생<br/>Issue Occurs] --> B{문제 유형<br/>Issue Type}
    
    B -->|컨테이너 오류| C[Docker 로그 확인<br/>Check Docker Logs]
    B -->|데이터 없음| D[MongoDB 연결 확인<br/>Verify MongoDB Connection]
    B -->|전략 오류| E[전략 코드 검증<br/>Validate Strategy Code]
    B -->|성능 문제| F[리소스 할당 조정<br/>Adjust Resource Allocation]
    
    C --> G[해결책 적용<br/>Apply Solution]
    D --> G
    E --> G
    F --> G
```

## 결론 / Conclusion

### 한국어
Strategy Orchestrator는 안전하고 효율적인 백테스팅을 위한 강력한 시스템입니다. Docker 기반 격리, 읽기 전용 데이터 접근, 병렬 처리를 통해 대규모 전략 테스트를 안정적으로 수행할 수 있습니다. 이 아키텍처는 확장성과 보안성을 모두 고려하여 설계되었으며, 향후 실시간 거래 시스템으로의 전환도 용이합니다.

### English
The Strategy Orchestrator is a powerful system for safe and efficient backtesting. Through Docker-based isolation, read-only data access, and parallel processing, it can reliably perform large-scale strategy testing. This architecture is designed with both scalability and security in mind, making it easy to transition to real-time trading systems in the future.
