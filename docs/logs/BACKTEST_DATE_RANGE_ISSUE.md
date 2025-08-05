# 백테스트 날짜 범위 설정 문제 분석 보고서

## 문제 요약

백테스트 API에서 날짜 범위 설정(`start_date`, `end_date`)과 캔들 개수 설정(`num_iterations`)이 중복되어 있으며, 실제 구현에서는 날짜 범위가 완전히 무시되고 있습니다.

## 발견 내용 (업데이트: 추가 코드 분석 완료)

### 1. API 인터페이스의 혼란

현재 백테스트 요청 시 사용자는 다음 파라미터들을 제공할 수 있습니다:

```python
# app/dto/BackTestRequest.py
class BacktestRequest(BaseModel):
    timeframe: str = "1d"
    num_iterations: int = 100
    start_date: Optional[str] = None
    # ...

# app/dto/orchestrator/OrchestratorInput.py
class OrchestratorInput(BaseModel):
    interval: str
    num_iterations: int = 100
    start_date: datetime | None = None
    end_date: datetime | None = None
```

**문제점**: 논리적으로 `interval`과 날짜 범위가 정해지면 캔들 개수는 자동으로 계산되어야 합니다. 예를 들어:
- `interval: "1d"`, `start_date: "2024-01-01"`, `end_date: "2024-01-31"` → 31개 캔들
- 사용자가 `num_iterations: 100`도 함께 지정하면 어떤 것을 따라야 할지 모호합니다.

### 2. 실제 구현의 문제

코드 분석 결과, `StrategyOrchestrator.py`에서는 날짜 범위를 전혀 사용하지 않습니다.

**추가 발견사항**:
- `OrchestratorInput.to_container_payload()`는 `start_date`와 `end_date`를 **전달하고 있습니다** (exclude 리스트에 없음)
- 하지만 `StrategyOrchestrator.py`의 `run_backtest()`에서는 이 날짜들을 **전혀 사용하지 않습니다**

이는 더욱 문제가 심각함을 시사합니다:

```python
# strategyOrchestrator/StrategyOrchestrator.py
def run_backtest(cfg: dict[str, Any]) -> dict[str, Any]:
    iterations: int = cfg.get("num_iterations", 60)
    # start_date, end_date는 전혀 참조되지 않음

def _proposals_for_job(...):
    # 최근 데이터에서 num_iter 개수만큼만 가져옴
    merged = _merge_symbol_frames(repo, symbols, interval, num_iter + lookback + 20, lookback)
    
    # 가장 최근부터 과거로 num_iter개만 처리
    first_idx = max(lookback, len(merged) - num_iter)
    for i in range(last_idx, first_idx - 1, -1):
        # ...
```

**결과**:
- 항상 가장 최근 데이터에서부터 `num_iterations`개의 캔들만 백테스트
- 특정 과거 기간(예: 2023년 1월~3월) 백테스트 불가능
- 사용자가 날짜를 지정해도 완전히 무시됨

### 3. 날짜 처리 인프라는 존재하지만 사용되지 않음

추가 조사 결과, 날짜 기반 데이터 처리를 위한 인프라는 이미 구축되어 있습니다:

1. **BinanceProvider**:
   - `fetch_ohlcv()` 메서드는 `start` 파라미터를 받아 처리
   - 날짜를 캔들 경계에 맞춰 정렬하는 로직 포함

2. **CandleRepository**:
   - `fetch_candles()` 메서드는 `start_time` 파라미터 지원
   - MongoDB 쿼리에서 날짜 필터링 가능

3. **DataService**:
   - `ensure_ohlcv()` 메서드는 `start`와 `end` 날짜 범위 지원
   - 날짜 범위의 gap을 찾아 필요한 데이터만 가져오는 효율적인 로직

**문제는 StrategyOrchestrator가 이 기능들을 활용하지 않는다는 것입니다.**

### 4. 사용자 경험 문제

USER_GUIDE.md의 예시들을 보면:
```json
{
  "symbols": ["BTCUSDT"],
  "interval": "1d",
  "num_iterations": 365  // 1년치 데이터
}
```

날짜 범위 파라미터는 존재하지만 실제로 작동하지 않으므로:
- 사용자가 날짜 범위를 지정해도 예상과 다른 결과
- API 문서와 실제 동작의 불일치
- 특정 역사적 기간 백테스트 불가능

## 제안사항

### 단기 개선안 (즉시 적용 가능)

#### 1. 문서화 개선
USER_GUIDE.md에 다음 내용 추가:
```markdown
### ⚠️ 현재 버전 제한사항
- `start_date`와 `end_date` 파라미터는 아직 구현되지 않았습니다
- 백테스트는 항상 최신 데이터에서부터 `num_iterations`개의 캔들만 처리합니다
- 특정 과거 기간 백테스트는 다음 버전에서 지원 예정입니다
```

#### 2. API 응답 개선
```python
# BackTestService.py에 추가
if start_date or end_date:
    logger.warning("Date range parameters are not yet implemented. Using num_iterations only.")
    # 응답에 경고 포함
    result["warnings"] = ["Date range filtering is not yet supported. Used latest {num_iterations} candles."]
```

### 중장기 개선안

#### 1. 날짜 기반 백테스트 구현 (인프라는 이미 준비됨)

```python
# StrategyOrchestrator.py 수정안
def run_backtest(cfg: dict[str, Any]) -> dict[str, Any]:
    # 기존 코드
    iterations: int = cfg.get("num_iterations", 60)
    
    # 추가할 코드
    start_date = cfg.get("start_date")  # ISO-8601 string
    end_date = cfg.get("end_date")      # ISO-8601 string
    
    # ...

def _merge_symbol_frames(
    repo: CandleRepository,
    symbols: Sequence[str],
    interval: str,
    n_rows: int,
    lookback: int,
    start_date: str | None = None,  # 추가
    end_date: str | None = None,     # 추가
) -> pd.DataFrame | None:
    """Fetch and horizontally merge OHLCV frames for the given basket."""
    frames: list[pd.DataFrame] = []
    for sym in symbols:
        if start_date:
            # 날짜 기반 조회 (이미 CandleRepository에 구현되어 있음!)
            start_ms = int(datetime.fromisoformat(start_date).timestamp() * 1000)
            df = repo.fetch_candles(sym, interval, n_rows, start_time=start_ms)
        else:
            # 기존 방식: 최근 N개
            df = repo.fetch_candles(sym, interval, n_rows, newest_first=True)
        # ...
```

#### 2. 파라미터 우선순위 명확화

```python
class OrchestratorInput(BaseModel):
    # ...
    
    @validator('num_iterations')
    def validate_iterations(cls, v, values):
        if values.get('start_date') or values.get('end_date'):
            # 날짜 범위가 있으면 num_iterations 무시
            logger.info("Date range provided, ignoring num_iterations")
            return None
        return v
```

#### 3. 점진적 마이그레이션

- **Phase 1** (현재): 문서화 및 경고 추가
- **Phase 2**: 날짜 범위 지원 추가 (backward compatible)
  ```python
  # 두 방식 모두 지원
  if request.start_date or request.end_date:
      # 새로운 날짜 기반 로직
  else:
      # 기존 num_iterations 로직
  ```
- **Phase 3**: `num_iterations` deprecated 공지
- **Phase 4**: `num_iterations` 제거, 날짜 범위만 사용

## 영향도 평가 (업데이트)

- **기능적 영향**: 낮음 (현재 기능은 정상 작동)
- **사용자 경험**: 높음 (날짜 파라미터가 무시되는 것은 심각한 UX 문제)
- **구현 복잡도**: **낮음** (인프라가 이미 구축되어 있어 StrategyOrchestrator만 수정하면 됨)
- **하위 호환성**: 주의 필요 (기존 API 사용자 고려)

## 결론

현재 백테스트 시스템은 기능적으로는 작동하지만, API 설계와 실제 구현 간의 불일치로 인해 사용자에게 혼란을 줄 수 있습니다.

**중요한 발견**: 날짜 기반 백테스트를 위한 모든 인프라(BinanceProvider, CandleRepository, DataService)는 이미 구축되어 있으며, 단지 StrategyOrchestrator에서 이를 활용하지 않고 있을 뿐입니다.

**권장 사항**:
1. 즉시: 문서에 현재 제한사항 명시
2. 단기: API 응답에 경고 메시지 추가
3. **중기: 날짜 기반 백테스트 구현 (예상보다 구현이 쉬움)**
   - StrategyOrchestrator에서 날짜 파라미터를 받아 CandleRepository에 전달하기만 하면 됨
   - 예상 작업량: 50-100줄 미만의 코드 수정
4. 장기: API 인터페이스 정리 및 간소화

이를 통해 더 직관적이고 유연한 백테스트 시스템을 구축할 수 있을 것입니다.
