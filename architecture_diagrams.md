# Binance Trading Bot Architecture Diagrams

## 1. System Architecture Overview

```mermaid
graph TB
    subgraph "Client Layer"
        HTTP[HTTP Client]
        WS[WebSocket Client]
        GQL[GraphQL Client]
    end

    subgraph "API Layer (FastAPI)"
        subgraph "Controllers"
            BC[BacktestController]
            GC[GraphQLController]
            SC[SymbolController]
            TC[TaskController]
            AC[AnalysisController]
        end
        
        MW[Middleware<br/>- CORS<br/>- RateLimiting<br/>- Authentication]
        
        subgraph "GraphQL"
            Schema[GraphQL Schema<br/>Query/Mutation/Subscription]
            Resolvers[Resolvers<br/>- SymbolResolver<br/>- BacktestResolver<br/>- StrategyResolver]
        end
    end

    subgraph "Service Layer"
        BS[BackTestServiceV2]
        OS[OrchestratorService]
        SS[StrategyService]
        SYS[SymbolService]
        MS[MarketDataService]
        
        subgraph "Async Tasks (Celery)"
            BTT[BackTestTask]
            GST[GridSearchTask]
            AT[AnalysisTask]
        end
    end

    subgraph "Data Layer"
        subgraph "MongoDB Cluster"
            MM[(MongoDB Master<br/>:27017)]
            MS1[(MongoDB Slave<br/>:27018)]
            RO[Read-Only User<br/>backtest_readonly]
        end
        
        Redis[(Redis<br/>- Cache<br/>- Celery Broker<br/>- Rate Limiting)]
    end

    subgraph "Business Logic Layer (Sandboxed)"
        subgraph "Docker Container"
            SO[StrategyOrchestrator]
            US[User Strategy Code]
            PM[PortfolioManager]
        end
    end

    subgraph "External Services"
        BA[Binance API]
        CMC[CoinMarketCap API]
    end

    %% Client connections
    HTTP --> MW
    WS --> MW
    GQL --> MW
    
    %% Controller routing
    MW --> BC
    MW --> GC
    MW --> SC
    MW --> TC
    MW --> AC
    
    %% GraphQL flow
    GC --> Schema
    Schema --> Resolvers
    
    %% Service layer connections
    BC --> BS
    GC --> SYS
    SC --> SYS
    AC --> MS
    
    %% Async task submission
    BS --> BTT
    BS --> OS
    
    %% Celery execution
    BTT -.->|async| BS
    GST -.->|async| SS
    AT -.->|async| MS
    
    %% Database connections
    BS -->|write| MM
    BS -->|read| MS1
    Resolvers -->|read| MS1
    SYS -->|write| MM
    SYS -->|read| MS1
    
    %% Docker orchestration
    OS -->|spawn| SO
    SO -->|read-only| RO
    RO -->|query| MS1
    
    %% External API calls
    MS --> BA
    MS --> CMC
    
    %% Cache and broker
    BS <--> Redis
    BTT <--> Redis
    MW <--> Redis

    classDef api fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef service fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef data fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef sandbox fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef external fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    
    class HTTP,WS,GQL,BC,GC,SC,TC,AC,MW,Schema,Resolvers api
    class BS,OS,SS,SYS,MS,BTT,GST,AT service
    class MM,MS1,RO,Redis data
    class SO,US,PM sandbox
    class BA,CMC external
```

## 2. BacktestController Request Flow

```mermaid
sequenceDiagram
    participant Client
    participant FastAPI
    participant BacktestController
    participant BackTestServiceV2
    participant Celery
    participant BackTestTask
    participant OrchestratorService
    participant Docker
    participant MongoDB
    participant Redis

    Client->>FastAPI: POST /backtest/submit
    FastAPI->>BacktestController: submit_backtest(request)
    
    Note over BacktestController: Validate request & resolve symbols
    
    alt Symbol Filter Provided
        BacktestController->>MongoDB: Query symbols via GraphQL resolver
        MongoDB-->>BacktestController: Filtered symbols
    else Direct Symbols
        Note over BacktestController: Use provided symbols
    end
    
    BacktestController->>BackTestServiceV2: Prepare task payload
    BacktestController->>Celery: run_backtest_task.delay(payload)
    Celery-->>BacktestController: task_id
    
    BacktestController-->>Client: {task_id, status: "submitted", websocket_url}
    
    Note over Celery,BackTestTask: Async execution starts
    
    Celery->>BackTestTask: Execute task
    BackTestTask->>BackTestTask: Update state: PROGRESS
    
    BackTestTask->>BackTestServiceV2: run_backtest()
    
    alt Use Cache
        BackTestServiceV2->>Redis: Check cache
        Redis-->>BackTestServiceV2: Cached result (if exists)
    end
    
    BackTestServiceV2->>MongoDB: Fetch strategy code
    MongoDB-->>BackTestServiceV2: Strategy code
    
    BackTestServiceV2->>OrchestratorService: run_backtest()
    OrchestratorService->>Docker: Create container
    OrchestratorService->>Docker: Mount strategy volume
    OrchestratorService->>Docker: Send input via stdin
    
    Docker->>Docker: Execute StrategyOrchestrator
    Note over Docker: Sandboxed execution with read-only DB access
    
    Docker-->>OrchestratorService: JSON results
    OrchestratorService-->>BackTestServiceV2: Parsed results
    
    BackTestServiceV2->>Redis: Cache results
    BackTestServiceV2->>MongoDB: Save results
    
    BackTestServiceV2-->>BackTestTask: Complete results
    BackTestTask->>MongoDB: Update task status
    BackTestTask-->>Celery: Task complete
    
    alt WebSocket Connected
        BackTestTask->>Client: Stream progress via WebSocket
    end
```

## 3. GraphQL Request Flow

```mermaid
graph LR
    subgraph "Client Request"
        Query[GraphQL Query<br/>```<br/>query {<br/>  symbols(filter: {<br/>    marketCapMin: 1M<br/>  }) {<br/>    symbol<br/>    name<br/>  }<br/>}<br/>```]
    end
    
    subgraph "FastAPI Layer"
        GQLRouter[GraphQL Router<br/>Strawberry]
        Context[Context Builder<br/>- Request<br/>- User Auth]
    end
    
    subgraph "Schema Layer"
        Schema[GraphQL Schema<br/>@strawberry.type]
        QueryType[Query Type<br/>- symbols()<br/>- strategies()<br/>- backtestResults()]
        MutationType[Mutation Type<br/>- createStrategy()<br/>- updateMetadata()]
        SubType[Subscription Type<br/>- symbolUpdates()<br/>- backtestProgress()]
    end
    
    subgraph "Resolver Layer"
        SR[SymbolResolver]
        BR[BacktestResolver]
        STR[StrategyResolver]
        MR[MarketResolver]
    end
    
    subgraph "Data Access"
        MongoSlave[(MongoDB Slave<br/>Read Operations)]
        MongoMaster[(MongoDB Master<br/>Write Operations)]
        RedisCache[(Redis Cache)]
    end
    
    Query --> GQLRouter
    GQLRouter --> Context
    Context --> Schema
    Schema --> QueryType
    Schema --> MutationType
    Schema --> SubType
    
    QueryType --> SR
    QueryType --> BR
    QueryType --> STR
    QueryType --> MR
    
    MutationType --> STR
    MutationType --> SR
    
    SubType --> SR
    SubType --> BR
    
    SR -->|read| MongoSlave
    BR -->|read| MongoSlave
    STR -->|read| MongoSlave
    MR -->|read| MongoSlave
    
    SR -->|write| MongoMaster
    STR -->|write| MongoMaster
    
    SR <--> RedisCache
    BR <--> RedisCache
    
    style Query fill:#e3f2fd
    style Schema fill:#f3e5f5
    style SR fill:#e8f5e9
    style MongoSlave fill:#fff3e0
    style RedisCache fill:#ffebee
```

## 4. Database Architecture

```mermaid
graph TB
    subgraph "MongoDB Architecture"
        subgraph "Primary (Master)"
            Master[(MongoDB Master<br/>:27017<br/>Primary)]
            
            subgraph "Master Databases"
                MDB1[trading DB]
                MDB2[ohlcv DB]
                MDB3[perp DB]
            end
            
            subgraph "Collections"
                C1[symbols]
                C2[backtest_results]
                C3[strategies]
                C4[tasks]
                C5[candles]
                C6[trades]
            end
        end
        
        subgraph "Secondary (Slave)"
            Slave[(MongoDB Slave<br/>:27018<br/>Secondary)]
            
            subgraph "Slave Databases"
                SDB1[trading DB<br/>(replica)]
                SDB2[ohlcv DB<br/>(replica)]
                SDB3[perp DB<br/>(replica)]
            end
        end
        
        subgraph "Users & Permissions"
            Admin[Admin User<br/>Full Access]
            RO[backtest_readonly<br/>Read-Only User]
            App[App User<br/>Read/Write]
        end
    end
    
    subgraph "Connection Management"
        MCC[MongoDBConfig Class]
        
        subgraph "Connection Pools"
            MASync[Master Async<br/>Motor Client]
            MSync[Master Sync<br/>PyMongo Client]
            SSync[Slave Sync<br/>Secondary Preferred]
        end
        
        subgraph "URIs"
            MURI[Master URI<br/>mongodb://localhost:27017]
            SURI[Slave URI<br/>mongodb://localhost:27018]
            ROURI[Read-Only URI<br/>mongodb://backtest_readonly@...]
        end
    end
    
    subgraph "Access Patterns"
        Write[Write Operations<br/>- Create backtest<br/>- Save results<br/>- Update symbols]
        Read[Read Operations<br/>- Query symbols<br/>- Fetch strategies<br/>- Get results]
        Sandbox[Sandboxed Read<br/>- Strategy execution<br/>- Market data fetch]
    end
    
    Master --> MDB1
    Master --> MDB2
    Master --> MDB3
    
    MDB1 --> C1
    MDB1 --> C2
    MDB1 --> C3
    MDB1 --> C4
    MDB2 --> C5
    MDB1 --> C6
    
    Master -.->|Replication| Slave
    Slave --> SDB1
    Slave --> SDB2
    Slave --> SDB3
    
    Admin --> Master
    App --> Master
    App --> Slave
    RO --> Slave
    
    MCC --> MASync
    MCC --> MSync
    MCC --> SSync
    
    MASync --> MURI
    MSync --> MURI
    SSync --> SURI
    RO --> ROURI
    
    Write --> Master
    Read --> Slave
    Sandbox --> RO
    
    classDef primary fill:#bbdefb,stroke:#1565c0,stroke-width:2px
    classDef secondary fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px
    classDef config fill:#fff9c4,stroke:#f57f17,stroke-width:2px
    classDef access fill:#ffccbc,stroke:#d84315,stroke-width:2px
    
    class Master,MDB1,MDB2,MDB3,C1,C2,C3,C4,C5,C6 primary
    class Slave,SDB1,SDB2,SDB3 secondary
    class MCC,MASync,MSync,SSync,MURI,SURI,ROURI config
    class Write,Read,Sandbox access
```

## 5. Celery Task Flow

```mermaid
stateDiagram-v2
    [*] --> TaskSubmitted: API Request
    
    TaskSubmitted --> CeleryQueue: run_backtest_task.delay()
    
    state CeleryQueue {
        Pending --> Claimed: Worker picks up
        Claimed --> Executing: Task starts
    }
    
    state Executing {
        Initialize --> ValidateInputs
        ValidateInputs --> CheckCache
        
        state CheckCache {
            CacheHit --> ReturnCached
            CacheMiss --> FetchStrategy
        }
        
        FetchStrategy --> PrepareConfig
        PrepareConfig --> CallService
        
        state CallService {
            BackTestService --> OrchestratorService
            OrchestratorService --> DockerExecution
            DockerExecution --> ParseResults
        }
        
        ParseResults --> SaveResults
        
        state SaveResults {
            SaveMongoDB --> SaveRedis
            SaveRedis --> UpdateTaskDoc
        }
    }
    
    Executing --> Progress: Update Progress
    Progress --> Executing: Continue
    
    Executing --> Success: Complete
    Executing --> Failure: Error
    
    Success --> [*]
    Failure --> [*]

```

```mermaid
sequenceDiagram
    participant API
    participant Redis as Redis Broker
    participant Worker as Celery Worker
    participant Task as BackTestTask
    participant Service as BackTestServiceV2
    participant MongoDB
    participant Docker

    API->>Redis: Submit task to queue
    Note over Redis: Task queued with ID
    
    Worker->>Redis: Poll for tasks
    Redis-->>Worker: Deliver task
    
    Worker->>Task: Execute run_backtest_task()
    
    Task->>Task: Update state: PROGRESS (0%)
    Task->>MongoDB: Check cache
    
    alt Cache Hit
        MongoDB-->>Task: Return cached result
        Task->>Task: Update state: SUCCESS
        Task-->>Worker: Return result
    else Cache Miss
        Task->>Service: run_backtest()
        Service->>MongoDB: Fetch strategy code
        MongoDB-->>Service: Strategy code
        
        Service->>Docker: Execute in container
        
        loop Progress Updates
            Docker-->>Service: Progress event
            Service-->>Task: Progress update
            Task->>Task: Update state: PROGRESS (n%)
            Task->>MongoDB: Save progress
        end
        
        Docker-->>Service: Final results
        Service->>MongoDB: Save results
        Service->>Redis: Cache results
        Service-->>Task: Return results
        
        Task->>MongoDB: Update task document
        Task->>Task: Update state: SUCCESS
        Task-->>Worker: Complete
    end
    
    Worker->>Redis: Mark task complete
    Worker->>API: Result available
```

## 6. Docker Sandboxing Architecture

```mermaid
graph TB
    subgraph "Host System"
        subgraph "OrchestratorService"
            OS[OrchestratorService]
            TP[Thread Pool<br/>max_workers=5]
            TC[Temp Directory<br/>Strategy Code]
        end
        
        subgraph "Docker Daemon"
            DM[Docker Manager]
            IMG[Orchestrator Image<br/>tradingbot_orchestrator:latest]
        end
    end
    
    subgraph "Sandboxed Container"
        subgraph "Container Config"
            ENV[Environment<br/>- MONGO_URI (read-only)<br/>- RUN_ID<br/>- PYTHONUNBUFFERED=1]
            RES[Resources<br/>- Memory: 2GB<br/>- CPU: 100%<br/>- Auto-remove: true]
            VOL[Volume Mount<br/>user_strategy.py (read-only)]
        end
        
        subgraph "Execution Environment"
            SO[StrategyOrchestrator.py]
            US[User Strategy Code]
            PM[PortfolioManager]
            DM2[DataManager]
        end
        
        subgraph "Permissions"
            RO[Read-Only DB Access<br/>backtest_readonly user]
            NW[No Network<br/>(except MongoDB)]
            FS[No Host Filesystem<br/>(except mounted strategy)]
        end
    end
    
    subgraph "Data Flow"
        Input[Input Config<br/>(via stdin)]
        Output[JSON Results<br/>(via stdout)]
        Logs[Logs<br/>(stdout/stderr)]
    end
    
    OS --> TP
    TP --> TC
    TC --> |Create strategy.py| VOL
    
    OS --> DM
    DM --> IMG
    IMG --> |Create container| ENV
    
    ENV --> SO
    VOL --> US
    SO --> US
    SO --> PM
    SO --> DM2
    
    DM2 --> RO
    RO --> |Query only| MongoDB[(MongoDB Slave)]
    
    OS --> |Send config| Input
    Input --> SO
    SO --> Output
    SO --> Logs
    Output --> OS
    Logs --> OS
    
    style OS fill:#e1f5fe
    style SO fill:#fff3e0
    style RO fill:#ffcdd2
    style MongoDB fill:#c8e6c9
    
    classDef host fill:#e3f2fd,stroke:#1565c0,stroke-width:2px
    classDef sandbox fill:#fff3e0,stroke:#ef6c00,stroke-width:2px
    classDef security fill:#ffebee,stroke:#c62828,stroke-width:2px
    
    class OS,TP,TC,DM,IMG host
    class ENV,RES,VOL,SO,US,PM,DM2 sandbox
    class RO,NW,FS security
```

## 7. Component Interaction Diagram

```mermaid
graph TB
    subgraph "Entry Points"
        REST[REST API<br/>FastAPI]
        GQL[GraphQL API<br/>Strawberry]
        WS[WebSocket<br/>Real-time updates]
    end
    
    subgraph "Controllers"
        BC[BacktestController<br/>- submit<br/>- status<br/>- results]
        GC[GraphQLController<br/>- query<br/>- mutation<br/>- subscription]
        SC[SymbolController<br/>- list<br/>- filter<br/>- update]
        TC[TaskController<br/>- status<br/>- cancel<br/>- list]
    end
    
    subgraph "Services"
        BS[BackTestServiceV2<br/>- run_backtest<br/>- cache_management<br/>- result_enrichment]
        OS[OrchestratorService<br/>- docker_management<br/>- sandbox_execution<br/>- result_parsing]
        SS[SymbolService<br/>- symbol_filtering<br/>- metadata_update<br/>- market_data]
        MS[MarketDataService<br/>- binance_integration<br/>- cmc_integration<br/>- data_aggregation]
    end
    
    subgraph "Infrastructure"
        subgraph "Async Processing"
            CeleryApp[Celery App<br/>- task_queue<br/>- result_backend<br/>- worker_pool]
            Tasks[Tasks<br/>- BackTestTask<br/>- GridSearchTask<br/>- AnalysisTask]
        end
        
        subgraph "Data Storage"
            MongoConfig[MongoDBConfig<br/>- connection_pools<br/>- master/slave<br/>- read_only_user]
            RedisCache[Redis<br/>- result_cache<br/>- rate_limiting<br/>- celery_broker]
        end
        
        subgraph "Security"
            Auth[Authentication<br/>- JWT tokens<br/>- user_context]
            RateLimit[Rate Limiting<br/>- per_user<br/>- per_endpoint]
        end
    end
    
    subgraph "Business Logic"
        Strategies[Strategies<br/>- BaseStrategy<br/>- Concrete Impls<br/>- Custom Code]
        Portfolio[Portfolio<br/>- position_mgmt<br/>- risk_mgmt<br/>- fee_models]
        Orchestrator[Orchestrator<br/>- strategy_exec<br/>- data_loading<br/>- result_agg]
    end
    
    %% Entry point connections
    REST --> BC
    REST --> SC
    REST --> TC
    GQL --> GC
    WS --> BC
    
    %% Controller to Service
    BC --> BS
    GC --> SS
    GC --> BS
    SC --> SS
    TC --> CeleryApp
    
    %% Service interactions
    BS --> OS
    BS --> Tasks
    SS --> MS
    MS --> MongoConfig
    
    %% Infrastructure usage
    BS --> MongoConfig
    BS --> RedisCache
    OS --> MongoConfig
    Tasks --> CeleryApp
    
    %% Security integration
    REST --> Auth
    REST --> RateLimit
    GQL --> Auth
    Auth --> GC
    RateLimit --> RedisCache
    
    %% Business logic execution
    OS --> Orchestrator
    Orchestrator --> Strategies
    Orchestrator --> Portfolio
    Strategies --> MongoConfig
    
    classDef entry fill:#e1f5fe,stroke:#01579b,stroke-width:2px
    classDef controller fill:#f3e5f5,stroke:#4a148c,stroke-width:2px
    classDef service fill:#e8f5e9,stroke:#1b5e20,stroke-width:2px
    classDef infra fill:#fff3e0,stroke:#e65100,stroke-width:2px
    classDef business fill:#fce4ec,stroke:#880e4f,stroke-width:2px
    
    class REST,GQL,WS entry
    class BC,GC,SC,TC controller
    class BS,OS,SS,MS service
    class CeleryApp,Tasks,MongoConfig,RedisCache,Auth,RateLimit infra
    class Strategies,Portfolio,Orchestrator business
```

## Key Architectural Patterns

### 1. **Three-Layer Architecture**
- **API Layer**: FastAPI controllers handle HTTP/WebSocket/GraphQL requests
- **Service Layer**: Business logic orchestration, async task management
- **Business Logic Layer**: Sandboxed strategy execution in Docker containers

### 2. **Async Processing**
- Celery for long-running backtests
- Progress tracking via task state updates
- WebSocket streaming for real-time updates

### 3. **Data Access Patterns**
- **Master MongoDB**: All write operations
- **Slave MongoDB**: Read operations (secondary preferred)
- **Read-Only User**: Sandboxed containers get limited access
- **Redis Cache**: Result caching with TTL

### 4. **Security Boundaries**
- Docker containers with resource limits (2GB RAM, 100% CPU)
- Read-only database access for strategies
- No network access except MongoDB
- Volume mount for strategy code (read-only)

### 5. **Scalability Features**
- Connection pooling for MongoDB
- Thread pool for concurrent Docker executions
- Distributed task queue with Celery
- Master-slave database separation

### 6. **GraphQL Integration**
- Flexible querying with Strawberry
- Resolvers use slave MongoDB for reads
- Subscriptions for real-time updates
- Type-safe schema with Pydantic models

This architecture ensures security through sandboxing, scalability through distributed processing, and flexibility through GraphQL and pluggable strategies.