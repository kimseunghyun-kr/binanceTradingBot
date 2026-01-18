# Orchestrator Tests

This directory contains all tests related to the Strategy Orchestrator module.

## Test Files

### Pure Function Implementation Tests

#### `test_pure_orchestrator.py` (Unit Tests)
Comprehensive unit tests for the pure function orchestrator implementation.

**Requirements:** `pytest`, `pandas`, `pydantic`

**Test Classes:**
- `TestPrefetchedDataSource` - Tests in-memory data source
- `TestDataPrefetchService` - Tests data prefetch service
- `TestPureOrchestrator` - Tests pure orchestrator execution
- `TestOrchestratorInputDTO` - Tests DTO modifications
- `TestIntegration` - Basic integration tests

**Run:**
```bash
pytest tests/orchestrator/test_pure_orchestrator.py -v
```

---

#### `test_integration_pure_orchestrator.py` (Integration Tests)
End-to-end integration tests for the pure function orchestrator.

**Requirements:** `pytest`, Docker, MongoDB (full environment)

**Test Classes:**
- `TestOrchestratorServiceIntegration` - Full backtest flow tests
- `TestPureFunctionProperties` - Verify determinism and no side effects

**Run:**
```bash
pytest tests/orchestrator/test_integration_pure_orchestrator.py -v
```

**Note:** Most tests are marked with `@pytest.mark.skip` as they require a full environment setup.

---

#### `test_pure_function_basic.py` (Basic Tests)
Simple tests that can run without pytest or external dependencies.

**Requirements:** `python3` only

**Tests:**
- `test_prefetched_data_source()` - Basic PrefetchedDataSource test
- `test_orchestrator_input_dto()` - DTO serialization test
- `test_json_serialization()` - JSON encode/decode test (✅ passes)
- `test_container_config_pure()` - Container config verification

**Run:**
```bash
python3 tests/orchestrator/test_pure_function_basic.py
```

---

### Legacy Tests

#### `test_strategy_orchestrator.py`
Existing tests for the strategy orchestrator (before pure function refactor).

**Run:**
```bash
pytest tests/orchestrator/test_strategy_orchestrator.py -v
```

---

## Running All Tests

```bash
# Run all orchestrator tests
pytest tests/orchestrator/ -v

# Run only pure function tests
pytest tests/orchestrator/test_pure*.py -v

# Run with coverage
pytest tests/orchestrator/ --cov=app.services.orchestrator --cov=strategyOrchestrator -v

# Run basic tests (no dependencies)
python3 tests/orchestrator/test_pure_function_basic.py
```

---

## Test Organization

```
tests/orchestrator/
├── __init__.py                              # Package init
├── README.md                                # This file
├── test_pure_orchestrator.py               # Unit tests for pure function
├── test_integration_pure_orchestrator.py   # Integration tests for pure function
├── test_pure_function_basic.py             # Basic tests (no deps)
└── test_strategy_orchestrator.py           # Legacy orchestrator tests
```

---

## Related Documentation

- **Main Documentation:** `/PURE_ORCHESTRATOR_REFACTOR.md`
- **Source Code:**
  - `app/services/orchestrator/OrchestratorService.py`
  - `app/services/orchestrator/DataPrefetchService.py`
  - `strategyOrchestrator/StrategyOrchestrator.py`
  - `app/dto/orchestrator/OrchestratorInput.py`

---

## Key Concepts Tested

### Pure Function Properties
- ✅ **Determinism**: Same input → Same output
- ✅ **No Side Effects**: No database writes, no network calls
- ✅ **Isolation**: Container has `network_mode: none`
- ✅ **Security**: No credentials in container environment

### Data Flow
1. Host pre-fetches OHLCV data from MongoDB
2. Data passed to container via stdin
3. Container runs pure computation (no I/O)
4. Results returned via stdout

---

## Contributing

When adding new orchestrator tests:
1. Place them in `tests/orchestrator/`
2. Follow naming convention: `test_*.py`
3. Use appropriate test class naming
4. Mark integration tests with `@pytest.mark.skip(reason="...")`
5. Update this README with new test descriptions
