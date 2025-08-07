# Windows에서 Binance Trading Bot 실행 가이드

## 목차
1. [필수 사전 준비 사항](#필수-사전-준비-사항)
2. [프로젝트 설정](#프로젝트-설정)
3. [실행 방법](#실행-방법)
4. [문제 해결](#문제-해결)
5. [개발 환경 설정](#개발-환경-설정)

## 필수 사전 준비 사항

### 1. Python 설치 (3.10 이상)
- [Python 공식 사이트](https://www.python.org/downloads/)에서 Windows용 Python 다운로드
- 설치 시 **"Add Python to PATH"** 옵션 반드시 체크
- 설치 확인:
```cmd
python --version
pip --version
```

### 2. Docker Desktop 설치
- [Docker Desktop for Windows](https://www.docker.com/products/docker-desktop/) 다운로드 및 설치
- WSL2 백엔드 사용 권장 (설치 중 선택)
- 설치 후 Docker Desktop 실행
- 설치 확인:
```cmd
docker --version
docker compose version
```

### 3. Git 설치
- [Git for Windows](https://git-scm.com/download/win) 다운로드 및 설치
- 설치 확인:
```cmd
git --version
```

## 프로젝트 설정

### 1. 프로젝트 클론
```cmd
git clone <repository-url>
cd binanceTradingBot
```

### 2. Python 가상환경 생성 및 활성화
```cmd
# 가상환경 생성
python -m venv venv

# 가상환경 활성화
venv\Scripts\activate

# (가상환경 비활성화는: deactivate)
```

### 3. 의존성 패키지 설치
```cmd
# 가상환경이 활성화된 상태에서
pip install -r requirements.txt
```

### 4. 환경 변수 설정
프로젝트 루트에 `.env` 파일 생성:
```env
# MongoDB 설정
MONGO_URI_MASTER=mongodb://localhost:27017
MONGO_URI_SLAVE=mongodb://localhost:27018
MONGO_DB=trading

# Redis 설정
REDIS_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Binance API (선택사항 - 실제 거래 시 필요)
BINANCE_API_KEY=your-binance-api-key
BINANCE_API_SECRET=your-binance-api-secret

# CoinMarketCap API (선택사항)
COINMARKETCAP_API_KEY=your-cmc-api-key

# 보안 키
SECRET_KEY=your-secret-key-here

# Rate Limiting
RATE_LIMIT_PER_MINUTE=100
```

## 실행 방법

### 방법 1: Docker Compose로 전체 실행 (권장) ⭐

가장 간단하고 권장되는 방법입니다. 모든 서비스를 한 번에 시작합니다:

```cmd
# 프로젝트 루트에서
start_with_docker_compose_windows.bat
```

이 명령은 다음을 자동으로 실행합니다:
- MongoDB 마스터/슬레이브 (레플리카 셋)
- Redis
- PostgreSQL
- FastAPI 애플리케이션
- Celery Worker
- Nginx 프록시
- mongo_init.sh를 통한 레플리카 셋 초기화

서비스 중지:
```cmd
stop_docker_compose_windows.bat
```

### 방법 2: 로컬 개발 모드 (Python 직접 실행)

Docker로 DB만 실행하고 Python 앱은 로컬에서 실행:

#### 1단계: 데이터베이스 서비스만 시작
```cmd
# DB 서비스만 시작 (profile: db)
docker compose --profile db up -d

# 서비스 상태 확인
docker ps
```

#### 2단계: Celery Worker 시작 (새 터미널)
```cmd
# 새 명령 프롬프트 창
cd binanceTradingBot
venv\Scripts\activate
python worker.py
```

#### 3단계: FastAPI 애플리케이션 시작
```cmd
# 다른 터미널에서
cd binanceTradingBot
venv\Scripts\activate
python run_local.py
# 또는
python KwontBot.py
```

### 방법 3: 기존 스크립트 사용 (레거시)

이전 버전과의 호환성을 위한 방법:
```cmd
# 기본 실행
run_local_windows.bat

# 디버그 모드
run_local_debug_windows.bat

# Worker 시작
start_worker_windows.bat
```

## 서비스 접속

### API 문서 및 테스트
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- GraphQL Playground: http://localhost:8000/graphql

### Health Check
```cmd
curl http://localhost:8000/health
```

PowerShell에서:
```powershell
Invoke-WebRequest -Uri http://localhost:8000/health | Select-Object -ExpandProperty Content
```

### GraphQL 테스트
PowerShell:
```powershell
$query = '{"query": "{ symbols(limit: 5) { symbol name } }"}'
$response = Invoke-WebRequest -Uri http://localhost:8000/graphql -Method POST -ContentType "application/json" -Body $query
$response.Content
```

## 문제 해결

### 1. Docker 관련 문제

#### Docker Desktop이 실행되지 않음
- Windows 기능에서 "Hyper-V" 및 "Windows Subsystem for Linux" 활성화 필요
- 관리자 권한으로 PowerShell 실행:
```powershell
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -All
Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux
```

#### 컨테이너가 시작되지 않음
```cmd
# 모든 컨테이너 중지 및 제거
docker compose down

# 볼륨 정리 (주의: 데이터 삭제됨)
docker volume prune

# 다시 시작
docker compose up -d
```

### 2. Python 관련 문제

#### pip 패키지 설치 실패
```cmd
# pip 업그레이드
python -m pip install --upgrade pip

# 캐시 삭제 후 재설치
pip cache purge
pip install -r requirements.txt
```

#### 가상환경 활성화 실패
- PowerShell 실행 정책 변경 필요:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### 3. 포트 충돌 문제

#### 포트 사용 중 확인
```cmd
# 특정 포트 확인 (예: 8000)
netstat -ano | findstr :8000

# 프로세스 종료 (PID를 위 명령에서 확인)
taskkill /PID <PID> /F
```

사용 중인 포트:
- 8000: FastAPI
- 27017: MongoDB Primary
- 27018: MongoDB Secondary (디버그 모드)
- 5432: PostgreSQL
- 6379: Redis

### 4. Celery Worker 문제

#### Worker가 작업을 받지 못함
```cmd
# Redis 연결 테스트
docker exec -it binancetradingbot-redis-1 redis-cli ping
# 응답: PONG

# Celery 상태 확인
celery -A app.core.celery_app inspect active
```

## 개발 환경 설정

### Visual Studio Code
1. 확장 프로그램 설치:
   - Python
   - Pylance
   - Docker
   - Thunder Client (API 테스트용)

2. 설정 (`.vscode/settings.json`):
```json
{
    "python.defaultInterpreterPath": "./venv/Scripts/python.exe",
    "python.linting.enabled": true,
    "python.linting.pylintEnabled": false,
    "python.linting.flake8Enabled": true,
    "python.formatting.provider": "black"
}
```

3. 디버그 설정 (`.vscode/launch.json`):
```json
{
    "version": "0.2.0",
    "configurations": [
        {
            "name": "FastAPI",
            "type": "python",
            "request": "launch",
            "module": "uvicorn",
            "args": [
                "KwontBot:app",
                "--reload",
                "--port", "8000"
            ],
            "jinja": true
        },
        {
            "name": "Celery Worker",
            "type": "python",
            "request": "launch",
            "module": "celery",
            "args": [
                "-A", "app.core.celery_app",
                "worker",
                "--loglevel=info"
            ]
        }
    ]
}
```

### PyCharm
1. 프로젝트 인터프리터 설정:
   - File → Settings → Project → Python Interpreter
   - 가상환경 선택: `venv\Scripts\python.exe`

2. Run Configuration 추가:
   - FastAPI: Python 스크립트로 `run_local.py` 실행
   - Celery: Python 스크립트로 `worker.py` 실행

## 유용한 명령어 모음

### Docker Compose 명령어 (권장)
```cmd
# Profile을 사용한 서비스 관리
docker compose --profile db --profile app up -d --build  # 전체 시작
docker compose --profile db up -d                        # DB만 시작
docker compose --profile app up -d                       # 앱만 시작
docker compose --profile db --profile app down           # 전체 중지

# 서비스 상태 확인
docker compose ps
docker compose --profile db --profile app ps

# 로그 보기
docker compose logs -f                    # 전체 로그
docker compose logs -f app               # FastAPI 로그
docker compose logs -f worker            # Celery 로그
docker compose logs -f mongo1 mongo2     # MongoDB 로그
```

### Docker 일반 명령어
```cmd
# 실행 중인 컨테이너 보기
docker ps

# 컨테이너 로그 보기
docker logs tradingbot_app
docker logs tradingbot_worker
docker logs tradingbot_mongo1

# 컨테이너 내부 접속
docker exec -it tradingbot_mongo1 mongosh
docker exec -it tradingbot_redis redis-cli

# 서비스 재시작
docker restart tradingbot_app
```

### 테스트 명령어
```cmd
# 아키텍처 테스트
python test_architecture.py

# 유닛 테스트 (있을 경우)
pytest

# 코드 포맷팅
black .

# 코드 린팅
flake8

# 타입 체크
mypy .
```

## 추가 팁

### 성능 최적화
1. Windows Defender 예외 추가:
   - 프로젝트 폴더
   - Python 실행 파일
   - Docker Desktop 폴더

2. Docker Desktop 메모리 할당:
   - Settings → Resources → Advanced
   - Memory: 최소 4GB 권장
   - CPUs: 가용 CPU의 50% 이상

### 로그 확인
- FastAPI 로그: 콘솔 출력
- Celery 로그: `logs/worker.log` 또는 콘솔
- Docker 로그: `docker logs <container-name>`

### 백업
정기적으로 다음 항목 백업:
- `.env` 파일
- MongoDB 데이터: `docker exec binancetradingbot-mongo-1 mongodump`
- 커스텀 전략 파일들

## 지원 및 문의

문제가 지속되면:
1. 에러 메시지와 로그 수집
2. `docker compose logs > docker_logs.txt`
3. GitHub Issues에 보고

---

**참고**: 이 가이드는 Windows 10/11 환경을 기준으로 작성되었습니다.