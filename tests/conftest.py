# tests/conftest.py
import os
import sys
import types
import importlib
import pytest

# 1) Keep pytest hermetic: don't auto-load random global plugins
os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")

# 2) Mock MongoDB modules early to prevent connection attempts during import
def _mock_pymongo():
    """Mock pymongo to prevent actual database connections during tests."""
    class FakeCollection:
        def find(self, *args, **kwargs):
            return iter([])  # Return empty iterator
        def find_one(self, *args, **kwargs):
            return None

    class FakeDatabase:
        def __getitem__(self, name):
            return FakeCollection()

    class FakeMongoClient:
        def __init__(self, *args, **kwargs):
            pass
        def __getitem__(self, name):
            return FakeDatabase()

    # Patch pymongo.MongoClient early
    import pymongo
    pymongo.MongoClient = FakeMongoClient

# Apply MongoDB mocking immediately
_mock_pymongo()


# ---- Strategy A: Patch get_settings() to a light dummy object ----
class _DummySettings:
    # Minimal surface used by the orchestrator path:
    mongo_slave_uri = "mongodb://localhost:27017"
    MONGO_URI_SLAVE = "mongodb://localhost:27017"
    MONGO_URI_MASTER = "mongodb://localhost:27017"
    MONGO_DB_OHLCV = "TEST_DB"
    MONGO_DB_PERP = "TEST_DB"


def _install_fake_get_settings(monkeypatch):
    """
    Install a fake app.core.pydanticConfig.settings.get_settings that
    returns a _DummySettings() instance. This avoids Pydantic validation entirely.
    """
    # If the settings module is already imported, patch its attr.
    try:
        mod = importlib.import_module("app.core.pydanticConfig.settings")
        monkeypatch.setattr(mod, "get_settings", lambda: _DummySettings(), raising=False)
        return
    except Exception:
        # Not imported yet; register a stub module in sys.modules so the later import hits our stub.
        fake_settings_mod = types.ModuleType("app.core.pydanticConfig.settings")
        fake_settings_mod.get_settings = lambda: _DummySettings()
        sys.modules["app.core.pydanticConfig.settings"] = fake_settings_mod


# ---- Strategy B: Patch env so real Settings() can be constructed (optional) ----
def _install_env_for_pydantic(monkeypatch):
    """
    If you prefer the real Settings model to be constructed, set minimal env vars here.
    Adjust keys to match your actual Settings model if needed.
    """
    env_defaults = {
        "MONGO_USER": "dummy",
        "MONGO_USER_PW": "dummy",
        "MONGO_HOST": "localhost",
        "MONGO_PORT": "27017",
        "MONGO_DB_OHLCV": "TEST_DB",
        # If your Settings expects a composed URI, add it too:
        "MONGO_SLAVE_URI": "mongodb://localhost:27017",
    }
    for k, v in env_defaults.items():
        monkeypatch.setenv(k, v)


@pytest.fixture(scope="session")
def orchestrator_import_strategy():
    """
    Choose how to neutralize Settings during import:
    - return 'get_settings' to stub get_settings()
    - return 'env' to set environment vars for a real Settings()
    """
    return "get_settings"  # change to "env" if you prefer env-based approach


@pytest.fixture
def orchestrator_mod(monkeypatch, orchestrator_import_strategy):
    """
    Import the orchestrator only AFTER we apply our chosen patching strategy.
    This ensures that deep imports (PerpPortfolioManager -> perp_specs -> settings)
    don't trigger real env validation or DB connections.
    """
    # Clear any prior import to force a clean import with our patches
    for name in list(sys.modules):
        if name.startswith("strategyOrchestrator"):
            sys.modules.pop(name)

    if orchestrator_import_strategy == "get_settings":
        _install_fake_get_settings(monkeypatch)
    else:
        _install_env_for_pydantic(monkeypatch)

    # Mock perp_specs to avoid MongoDB connection
    fake_perp_specs = types.ModuleType("strategyOrchestrator.entities.perpetuals.contracts.perp_specs")
    fake_perp_specs.PERP_SPECS = {}  # Empty dict for testing
    sys.modules["strategyOrchestrator.entities.perpetuals.contracts.perp_specs"] = fake_perp_specs

    # Mock funding_provider to avoid MongoDB connection
    class FakeFundingProvider:
        def get_funding_rate(self, symbol, timestamp):
            return 0.0
    fake_funding_repo = types.ModuleType("strategyOrchestrator.entities.perpetuals.portfolio.Funding_repository")
    fake_funding_repo.funding_provider = FakeFundingProvider()
    sys.modules["strategyOrchestrator.entities.perpetuals.portfolio.Funding_repository"] = fake_funding_repo

    # Now import the orchestrator module safely
    mod = importlib.import_module("strategyOrchestrator.StrategyOrchestrator")
    return mod


# Optional helper: quick fake repo you can use in tests if you want to avoid
# monkeypatching CandleRepository.fetch_candles per test. You can still monkeypatch.
class FakeRepo:
    def __init__(self, day_frame_fn, detail_frame_fn):
        self._day_frame_fn = day_frame_fn
        self._detail_frame_fn = detail_frame_fn

    def fetch_candles(self, symbol, interval, n_rows, newest_first=False, start_time=None):
        if interval in {"1d", "1w"}:
            return self._day_frame_fn(symbol, interval, n_rows, newest_first, start_time)
        return self._detail_frame_fn(symbol, interval, n_rows, newest_first, start_time)
