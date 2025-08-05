# 백테스트 날짜 범위 설정 문제 분석 보고서

## 문제 요약

백테스트 API에서 날짜 범위 설정(`start_date`, `end_date`)과 캔들 개수 설정(`num_iterations`)이 중복되어 있으며, 실제 구현에서는 날짜 범위가 완전히 무시되고 있습니다.

## 발견 내용

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

코드 분석 결과, `StrategyOrchestrator.py`에서는 날짜 범위를 전혀 사용하지 않습니다:

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

### 3. 사용자 경험 문제

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

#### 1. 날짜 기반 백테스트 구현

```python
# StrategyOrchestrator.py 수정안
def _fetch_candles_for_period(repo, symbol, interval, start_date, end_date, num_iterations):
    if start_date or end_date:
        # 날짜 범위로 조회
        return repo.fetch_candles_by_date_range(
            symbol, interval, 
            start_time=start_date, 
            end_time=end_date
        )
    else:
        # 기존 방식: 최근 N개
        return repo.fetch_candles(symbol, interval, num_iterations, newest_first=True)
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

## 영향도 평가

- **기능적 영향**: 낮음 (현재 기능은 정상 작동)
- **사용자 경험**: 중간 (혼란 가능성)
- **구현 복잡도**: 중간 (데이터 조회 로직 수정 필요)
- **하위 호환성**: 주의 필요 (기존 API 사용자 고려)

## 결론

현재 백테스트 시스템은 기능적으로는 작동하지만, API 설계와 실제 구현 간의 불일치로 인해 사용자에게 혼란을 줄 수 있습니다. 

**권장 사항**:
1. 즉시: 문서에 현재 제한사항 명시
2. 단기: API 응답에 경고 메시지 추가
3. 중기: 날짜 기반 백테스트 구현
4. 장기: API 인터페이스 정리 및 간소화

이를 통해 더 직관적이고 유연한 백테스트 시스템을 구축할 수 있을 것입니다.
