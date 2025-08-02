# Architecture Documentation / 아키텍처 문서

## 프로젝트 개요 / Project Overview

### 한국어
이 문서는 Binance Trading Bot의 시스템 아키텍처를 설명합니다. 이 시스템은 암호화폐 거래 전략을 백테스팅하고 분석하는 고성능 플랫폼입니다. FastAPI, Celery, MongoDB, Docker를 활용하여 분산형 태스크 실행과 샌드박스 환경에서의 안전한 전략 평가를 제공합니다.

### English
This document describes the system architecture of the Binance Trading Bot. This system is a high-performance platform for backtesting and analyzing cryptocurrency trading strategies. It leverages FastAPI, Celery, MongoDB, and Docker to provide distributed task execution and secure strategy evaluation in sandboxed environments.

## 시스템 아키텍처 개요 / System Architecture Overview

### 한국어
시스템은 3계층 아키텍처로 구성되어 있으며, 각 계층은 명확한 책임을 가지고 있습니다:
- **API 계층**: REST 및 GraphQL 엔드포인트 제공
- **서비스 계층**: 비즈니스 로직 오케스트레이션
- **비즈니스 로직 계층**: 샌드박스된 전략 실행

### English
The system consists of a 3-layer architecture, with each layer having clear responsibilities:
- **API Layer**: Provides REST and GraphQL endpoints
- **Service Layer**: Orchestrates business logic
- **Business Logic Layer**: Sandboxed strategy execution

```mermaid
graph TB
    subgraph "Client Layer / 클라이언트 계층"
        WEB[Web Client<br/>웹 클라이언트]
        API_CLIENT[API Client<br/>API 클라이언트]
    end
    
    subgraph "API Layer / API 계층"
        FASTAPI[FastAPI Server<br/>FastAPI 서버]
        REST[REST Endpoints<br/>REST 엔드포인트]
        GQL[GraphQL Endpoint<br/>GraphQL 엔드포인트]
        WS[WebSocket<br/>웹소켓]
    end
    
    subgraph "Service Layer / 서비스 계층"
        BACKTEST_SVC[BackTest Service<br/>백테스트 서비스]
        SYMBOL_SVC[Symbol Service<br/>심볼 서비스]
        STRATEGY_SVC[Strategy Service<br/>전략 서비스]
        ORCH_SVC[Orchestrator Service<br/>오케스트레이터 서비스]
    end
    
    subgraph "Task Queue / 태스크 큐"
        CELERY[Celery Worker<br/>Celery 워커]
        REDIS[(Redis<br/>레디스)]
    end
    
    subgraph "Business Logic Layer / 비즈니스 로직 계층"
        DOCKER[Docker Container<br/>도커 컨테이너]
        STRAT_ORCH[Strategy Orchestrator<br/>전략 오케스트레이터]
    end
    
    subgraph "Data Layer / 데이터 계층"
        MONGO_MASTER[(MongoDB Master<br/>MongoDB 마스터)]
        MONGO_SLAVE[(MongoDB Slave<br/>MongoDB 슬레이브)]
        POSTGRES[(PostgreSQL<br/>PostgreSQL)]
    end
    
    WEB --> FASTAPI
    API_CLIENT --> FASTAPI
    FASTAPI --> REST
    FASTAPI --> GQL
    FASTAPI --> WS
    
    REST --> BACKTEST_SVC
    REST --> SYMBOL_SVC
    REST --> STRATEGY_SVC
    GQL --> SYMBOL_SVC
    
    BACKTEST_SVC --> CELERY
    CELERY --> REDIS
    CELERY --> ORCH_SVC
    
    ORCH_SVC --> DOCKER
    DOCKER --> STRAT_ORCH
    
    BACKTEST_SVC --> MONGO_MASTER
    SYMBOL_SVC --> MONGO_SLAVE
    STRATEGY_SVC --> MONGO_MASTER
    STRAT_ORCH --> MONGO_SLAVE
    
    style FASTAPI fill:#e1f5fe
    style CELERY fill:#fff3e0
    style DOCKER fill:#f3e5f5
    style MONGO_MASTER fill:#ffebee
    style MONGO_SLAVE fill:#ffebee
```

## 기술 스택 / Technology Stack

### 한국어
- **백엔드 프레임워크**: FastAPI (고성능 비동기 웹 프레임워크)
- **태스크 큐**: Celery + Redis (분산 태스크 처리)
- **데이터베이스**: MongoDB (마스터-슬레이브 구조), PostgreSQL
- **컨테이너화**: Docker (전략 샌드박싱)
- **API**: REST + GraphQL
- **실시간 통신**: WebSocket (진행상황 스트리밍)

### English
- **Backend Framework**: FastAPI (high-performance async web framework)
- **Task Queue**: Celery + Redis (distributed task processing)
- **Database**: MongoDB (master-slave configuration), PostgreSQL
- **Containerization**: Docker (strategy sandboxing)
- **API**: REST + GraphQL
- **Real-time Communication**: WebSocket (progress streaming)

## 데이터 흐름 / Data Flow

### 백테스트 실행 흐름 / Backtest Execution Flow

```mermaid
sequenceDiagram
    participant Client as Client<br/>클라이언트
    participant API as FastAPI<br/>FastAPI
    participant Service as BackTest Service<br/>백테스트 서비스
    participant Celery as Celery Worker<br/>Celery 워커
    participant Orch as Orchestrator<br/>오케스트레이터
    participant Docker as Docker Container<br/>도커 컨테이너
    participant Mongo as MongoDB<br/>MongoDB
    
    Client->>API: POST /backtest/submit<br/>백테스트 요청
    API->>Service: Submit backtest<br/>백테스트 제출
    Service->>Mongo: Save request<br/>요청 저장
    Service->>Celery: Queue task<br/>태스크 큐잉
    API-->>Client: Return task_id<br/>태스크 ID 반환
    
    Note over Celery: Async Processing<br/>비동기 처리
    
    Celery->>Orch: Run backtest<br/>백테스트 실행
    Orch->>Docker: Create container<br/>컨테이너 생성
    Docker->>Docker: Load strategy<br/>전략 로드
    Docker->>Mongo: Read OHLCV data<br/>OHLCV 데이터 읽기
    Docker->>Docker: Execute strategy<br/>전략 실행
    Docker-->>Orch: Return results<br/>결과 반환
    Orch-->>Celery: Complete task<br/>태스크 완료
    Celery->>Mongo: Save results<br/>결과 저장
    
    Client->>API: GET /backtest/status/{task_id}<br/>상태 확인
    API->>Celery: Check status<br/>상태 확인
    API-->>Client: Return status<br/>상태 반환
```

## 데이터베이스 아키텍처 / Database Architecture

### MongoDB 마스터-슬레이브 구조 / MongoDB Master-Slave Configuration

```mermaid
graph LR
    subgraph "Write Operations / 쓰기 작업"
        WRITE_API[API Write Requests<br/>API 쓰기 요청]
        MASTER[(MongoDB Master<br/>:27017)]
    end
    
    subgraph "Read Operations / 읽기 작업"
        READ_API[API Read Requests<br/>API 읽기 요청]
        SLAVE[(MongoDB Slave<br/>:27018)]
    end
    
    subgraph "Sandboxed Read / 샌드박스 읽기"
        DOCKER[Docker Containers<br/>도커 컨테이너]
        RO_USER[Read-Only User<br/>읽기 전용 사용자]
    end
    
    WRITE_API --> MASTER
    MASTER -.Replication<br/>복제.-> SLAVE
    READ_API --> SLAVE
    DOCKER --> RO_USER
    RO_USER --> SLAVE
    
    style MASTER fill:#ffcccc
    style SLAVE fill:#ccffcc
```

### 데이터 모델 / Data Models

```mermaid
erDiagram
    SYMBOLS {
        string symbol PK
        string name
        string type
        float market_cap
        float volume_24h
        boolean is_active
        datetime last_updated
    }
    
    CANDLES {
        string symbol FK
        string interval
        int timestamp PK
        float open
        float high
        float low
        float close
        float volume
    }
    
    STRATEGIES {
        string name PK
        string type
        string code
        object default_params
        boolean is_active
        datetime created_at
    }
    
    BACKTEST_RESULTS {
        string task_id PK
        string user_id
        string strategy_name FK
        array symbols
        object metadata
        object performance
        array trades
        datetime created_at
    }
    
    SYMBOLS ||--o{ CANDLES : has
    STRATEGIES ||--o{ BACKTEST_RESULTS : generates
```

## API 엔드포인트 구조 / API Endpoint Structure

### REST API 엔드포인트 / REST API Endpoints

```mermaid
graph TB
    subgraph "Backtest Endpoints / 백테스트 엔드포인트"
        BT1["POST /backtest/submit<br/>백테스트 제출"]
        BT2["GET /backtest/status/{task_id}<br/>상태 확인"]
        BT3["GET /backtest/results/{task_id}<br/>결과 조회"]
        BT4["WS /backtest/stream/{task_id}<br/>실시간 스트리밍"]
    end
    
    subgraph "Symbol Endpoints / 심볼 엔드포인트"
        SYM1["GET /symbol/list<br/>심볼 목록"]
        SYM2["GET /symbol/{symbol}<br/>심볼 상세"]
        SYM3["POST /symbol/filter<br/>심볼 필터링"]
    end
    
    subgraph "Strategy Endpoints / 전략 엔드포인트"
        STR1["GET /strategy/list<br/>전략 목록"]
        STR2["POST /strategy/create<br/>전략 생성"]
        STR3["PUT /strategy/{name}<br/>전략 수정"]
    end
    
    subgraph "Analysis Endpoints / 분석 엔드포인트"
        AN1["POST /analysis/portfolio<br/>포트폴리오 분석"]
        AN2["GET /analysis/performance<br/>성과 분석"]
    end
    
    subgraph "GraphQL Endpoint / GraphQL 엔드포인트"
        GQL["POST /graphql<br/>GraphQL 쿼리"]
    end
```

## Celery 태스크 워크플로우 / Celery Task Workflow

```mermaid
stateDiagram-v2
    [*] --> PENDING: Task Submitted<br/>태스크 제출됨
    PENDING --> STARTED: Worker Picks Up<br/>워커가 처리 시작
    STARTED --> PROGRESS: Processing<br/>처리 중
    PROGRESS --> PROGRESS: Update Progress<br/>진행상황 업데이트
    PROGRESS --> SUCCESS: Completed<br/>완료
    PROGRESS --> FAILURE: Error<br/>오류
    SUCCESS --> [*]
    FAILURE --> RETRY: Retry Logic<br/>재시도 로직
    RETRY --> STARTED: Retry Attempt<br/>재시도
    FAILURE --> [*]: Max Retries<br/>최대 재시도 초과
```

## Docker 샌드박싱 아키텍처 / Docker Sandboxing Architecture

### 한국어
전략 실행은 보안과 격리를 위해 Docker 컨테이너 내에서 이루어집니다. 각 백테스트는 독립된 컨테이너에서 실행되며, 읽기 전용 데이터베이스 접근만 허용됩니다.

### English
Strategy execution occurs within Docker containers for security and isolation. Each backtest runs in an independent container with read-only database access.

```mermaid
graph TB
    subgraph "Host System / 호스트 시스템"
        CELERY["Celery Worker<br/>Celery 워커"]
        DOCKER_ENGINE["Docker Engine<br/>도커 엔진"]
        SOCKET["/var/run/docker.sock"]
    end
    
    subgraph "Container Environment / 컨테이너 환경"
        subgraph "Container 1"
            ORCH1[Strategy Orchestrator<br/>전략 오케스트레이터]
            STRAT1[User Strategy<br/>사용자 전략]
        end
        
        subgraph "Container 2"
            ORCH2[Strategy Orchestrator<br/>전략 오케스트레이터]
            STRAT2[User Strategy<br/>사용자 전략]
        end
    end
    
    subgraph "Network / 네트워크"
        BRIDGE[Docker Bridge Network<br/>도커 브리지 네트워크]
        MONGO_NET[MongoDB Access<br/>MongoDB 접근]
    end
    
    CELERY --> DOCKER_ENGINE
    DOCKER_ENGINE --> SOCKET
    DOCKER_ENGINE --> ORCH1
    DOCKER_ENGINE --> ORCH2
    
    ORCH1 --> BRIDGE
    ORCH2 --> BRIDGE
    BRIDGE --> MONGO_NET
    
    style ORCH1 fill:#e8f5e9
    style ORCH2 fill:#e8f5e9
```

## 전략 실행 흐름 / Strategy Execution Flow

```mermaid
flowchart TB
    subgraph "Input / 입력"
        CONFIG[Strategy Config<br/>전략 설정]
        SYMBOLS[Symbol List<br/>심볼 목록]
        PARAMS[Parameters<br/>파라미터]
    end
    
    subgraph "Initialization / 초기화"
        LOAD[Load Strategy<br/>전략 로드]
        REPO[Initialize Repository<br/>저장소 초기화]
        PM[Create Portfolio Manager<br/>포트폴리오 매니저 생성]
    end
    
    subgraph "Parallel Processing / 병렬 처리"
        SPLIT[Split Work Units<br/>작업 단위 분할]
        WORKER1[Worker Thread 1<br/>워커 스레드 1]
        WORKER2[Worker Thread 2<br/>워커 스레드 2]
        WORKERN[Worker Thread N<br/>워커 스레드 N]
        MERGE[Merge Proposals<br/>제안 병합]
    end
    
    subgraph "Sequential Execution / 순차 실행"
        TIMELINE[Build Timeline<br/>타임라인 구성]
        EXECUTE[Execute Trades<br/>거래 실행]
        UPDATE[Update Portfolio<br/>포트폴리오 업데이트]
    end
    
    subgraph "Output / 출력"
        RESULTS[Generate Results<br/>결과 생성]
        METRICS[Calculate Metrics<br/>지표 계산]
        JSON[JSON Output<br/>JSON 출력]
    end
    
    CONFIG --> LOAD
    SYMBOLS --> LOAD
    PARAMS --> LOAD
    
    LOAD --> REPO
    REPO --> PM
    PM --> SPLIT
    
    SPLIT --> WORKER1
    SPLIT --> WORKER2
    SPLIT --> WORKERN
    
    WORKER1 --> MERGE
    WORKER2 --> MERGE
    WORKERN --> MERGE
    
    MERGE --> TIMELINE
    TIMELINE --> EXECUTE
    EXECUTE --> UPDATE
    UPDATE --> EXECUTE
    
    UPDATE --> RESULTS
    RESULTS --> METRICS
    METRICS --> JSON
```

## 보안 고려사항 / Security Considerations

### 한국어
1. **샌드박스 실행**: 모든 사용자 전략은 격리된 Docker 컨테이너에서 실행
2. **읽기 전용 접근**: 전략은 데이터베이스에 대해 읽기 권한만 보유
3. **리소스 제한**: 컨테이너는 메모리와 CPU 제한 설정
4. **네트워크 격리**: 컨테이너는 제한된 네트워크 접근만 허용
5. **JWT 인증**: API 접근에 JWT 토큰 기반 인증 사용 가능

### English
1. **Sandboxed Execution**: All user strategies run in isolated Docker containers
2. **Read-Only Access**: Strategies only have read permissions to the database
3. **Resource Limits**: Containers have memory and CPU limits
4. **Network Isolation**: Containers have restricted network access
5. **JWT Authentication**: JWT token-based authentication available for API access

```mermaid
graph TB
    subgraph "Security Layers / 보안 계층"
        AUTH[Authentication<br/>인증]
        AUTHZ[Authorization<br/>인가]
        SANDBOX[Sandboxing<br/>샌드박싱]
        LIMIT[Resource Limits<br/>리소스 제한]
    end
    
    subgraph "Protection Mechanisms / 보호 메커니즘"
        JWT[JWT Tokens<br/>JWT 토큰]
        RBAC[Role-Based Access<br/>역할 기반 접근]
        DOCKER_ISO[Docker Isolation<br/>도커 격리]
        RATE[Rate Limiting<br/>속도 제한]
    end
    
    AUTH --> JWT
    AUTHZ --> RBAC
    SANDBOX --> DOCKER_ISO
    LIMIT --> RATE
    
    style AUTH fill:#ffecb3
    style SANDBOX fill:#c5e1a5
```

## 배포 아키텍처 / Deployment Architecture

### 한국어
시스템은 Docker Compose를 사용하여 모든 서비스를 오케스트레이션합니다. 개발 환경과 프로덕션 환경 모두를 지원하며, 수평 확장이 가능합니다.

### English
The system uses Docker Compose to orchestrate all services. It supports both development and production environments with horizontal scaling capabilities.

```mermaid
graph TB
    subgraph "Load Balancer / 로드 밸런서"
        NGINX[Nginx<br/>Nginx]
    end
    
    subgraph "Application Tier / 애플리케이션 계층"
        APP1[FastAPI Instance 1<br/>FastAPI 인스턴스 1]
        APP2[FastAPI Instance 2<br/>FastAPI 인스턴스 2]
    end
    
    subgraph "Worker Tier / 워커 계층"
        WORKER1[Celery Worker 1<br/>Celery 워커 1]
        WORKER2[Celery Worker 2<br/>Celery 워커 2]
        WORKERN[Celery Worker N<br/>Celery 워커 N]
    end
    
    subgraph "Data Tier / 데이터 계층"
        REDIS_CLUSTER[Redis Cluster<br/>Redis 클러스터]
        MONGO_RS[MongoDB ReplicaSet<br/>MongoDB 레플리카셋]
        PG_MASTER[PostgreSQL Master<br/>PostgreSQL 마스터]
    end
    
    NGINX --> APP1
    NGINX --> APP2
    
    APP1 --> REDIS_CLUSTER
    APP2 --> REDIS_CLUSTER
    
    REDIS_CLUSTER --> WORKER1
    REDIS_CLUSTER --> WORKER2
    REDIS_CLUSTER --> WORKERN
    
    WORKER1 --> MONGO_RS
    WORKER2 --> MONGO_RS
    WORKERN --> MONGO_RS
    
    APP1 --> MONGO_RS
    APP2 --> MONGO_RS
    APP1 --> PG_MASTER
    APP2 --> PG_MASTER
    
    style NGINX fill:#b3e5fc
    style REDIS_CLUSTER fill:#ffccbc
    style MONGO_RS fill:#dcedc8
```

## 주요 설계 결정사항 / Key Design Decisions

### 한국어
1. **Celery 비동기 처리**: 장시간 실행되는 백테스트를 블로킹 없이 처리
2. **MongoDB 마스터-슬레이브**: 읽기/쓰기 분리로 확장성 향상
3. **Docker 샌드박싱**: 전략 실행의 보안성 보장
4. **GraphQL 지원**: 유연한 쿼리 기능 제공
5. **Pydantic 설정 관리**: 타입 안전한 설정 관리

### English
1. **Celery for Async**: Handles long-running backtests without blocking
2. **MongoDB Master-Slave**: Separates read/write concerns for scalability
3. **Docker Sandboxing**: Ensures security for strategy execution
4. **GraphQL Support**: Provides flexible querying capabilities
5. **Pydantic Settings**: Type-safe configuration management

## 일반적인 워크플로우 / Common Workflows

### 백테스트 워크플로우 / Backtesting Workflow

```mermaid
stateDiagram-v2
    [*] --> StrategySelection: User Selects Strategy<br/>사용자가 전략 선택
    StrategySelection --> SymbolFilter: Apply Symbol Filters<br/>심볼 필터 적용
    SymbolFilter --> ParameterConfig: Configure Parameters<br/>파라미터 설정
    ParameterConfig --> SubmitBacktest: Submit Backtest<br/>백테스트 제출
    SubmitBacktest --> QueuedTask: Task Queued<br/>태스크 대기열
    QueuedTask --> Processing: Worker Processing<br/>워커 처리
    Processing --> ContainerExecution: Execute in Container<br/>컨테이너에서 실행
    ContainerExecution --> ResultGeneration: Generate Results<br/>결과 생성
    ResultGeneration --> SaveResults: Save to Database<br/>데이터베이스 저장
    SaveResults --> NotifyUser: Notify User<br/>사용자 알림
    NotifyUser --> [*]
```

## 향후 고려사항 / Future Considerations

### 한국어
1. **실시간 거래**: 백테스트 결과를 기반으로 한 실시간 거래 기능
2. **머신러닝 통합**: AI/ML 기반 전략 최적화
3. **멀티 익스체인지 지원**: 여러 거래소 데이터 통합
4. **고급 시각화**: 대시보드 및 차트 기능 강화
5. **클라우드 네이티브**: Kubernetes 기반 배포

### English
1. **Live Trading**: Real-time trading based on backtest results
2. **Machine Learning Integration**: AI/ML-based strategy optimization
3. **Multi-Exchange Support**: Integration with multiple exchange data
4. **Advanced Visualization**: Enhanced dashboard and charting features
5. **Cloud Native**: Kubernetes-based deployment

## 결론 / Conclusion

### 한국어
Binance Trading Bot은 확장 가능하고 안전한 암호화폐 거래 전략 백테스팅 플랫폼입니다. 마이크로서비스 아키텍처와 컨테이너 기반 격리를 통해 높은 성능과 보안성을 제공합니다.

### English
The Binance Trading Bot is a scalable and secure cryptocurrency trading strategy backtesting platform. It provides high performance and security through microservices architecture and container-based isolation.
