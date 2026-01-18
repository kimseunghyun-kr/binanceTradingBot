import math
import pandas as pd
import importlib

# We import orchestrator via the fixture 'orchestrator_mod' so patches are in place.

# ---- Dummy Strategy for signal generation ----
class DummyStrategy:
    signal_type = 'BUY'
    def get_required_lookback(self): return 1
    def work_units(self, symbols):   return [{'symbols': [s]} for s in symbols]
    def decide(self, window, interval, tp_ratio=2.0, sl_ratio=1.0):
        try:
            last_close = float(window.iloc[-1]['close'])
        except KeyError:
            sym0 = window.columns.levels[0][0]
            last_close = float(window[(sym0, 'close')].iloc[-1])
        sig = self.signal_type
        if sig == 'BUY':
            return {'signal': 'BUY',  'entry_price': last_close, 'tp_price': last_close*1.1, 'sl_price': last_close*0.9}
        if sig == 'SELL':
            return {'signal': 'SELL', 'entry_price': last_close, 'tp_price': last_close*0.9, 'sl_price': last_close*1.1}
        return {'signal': 'HOLD'}

# ---- Fake candle data producers ----
def _make_day_df(n_rows):
    dates = pd.date_range(end='2021-01-03', periods=max(5, n_rows), freq='D')
    times = [int(dt.timestamp() * 1000) for dt in dates]
    return pd.DataFrame({
        'open_time': times,
        'open': [100]*len(times),
        'high': [100]*len(times),
        'low' : [100]*len(times),
        'close':[100]*len(times),
        'volume':[0]*len(times),
    }).sort_values('open_time').reset_index(drop=True)

def _make_detail_df(start_time, periods=10, base=100.0, short=False, interval='15m'):
    freq = '15min' if interval == '15m' else '1H'
    start = pd.Timestamp(start_time, unit='ms') if start_time else pd.Timestamp('2021-01-01')
    times = [int(ts.timestamp() * 1000) for ts in pd.date_range(start, periods=periods, freq=freq)]
    if short:
        highs  = [base + 5] + [base + 2] * (periods - 1)
        lows   = [base - 10] + [base - 2] * (periods - 1)
        closes = [base - 10] + [base] * (periods - 1)
    else:
        highs  = [base + 2] * periods
        lows   = [base - 2] * periods
        closes = [base]     * periods
    return pd.DataFrame({
        'open_time': times,
        'open': [base]*periods,
        'high': highs,
        'low' : lows,
        'close': closes,
        'volume': [0]*periods,
    })

# ---- Test-side load_component mock ----
def _dummy_load_component(spec, builtin, base_cls, label):
    if label == 'strategy':
        # If params supplied, return instance; else return class – mirrors real behavior variants
        return DummyStrategy if not (isinstance(spec, dict) and spec.get('params') is not None) else DummyStrategy()
    if label in ('fee_model', 'slippage_model'): return (lambda ev: 0.0)
    if label == 'fill_policy':
        class _FP:
            def __init__(self, *_): pass
        return _FP
    if label == 'capacity_policy': return (lambda *args, **kwargs: True)
    if label == 'sizing_model':    return (lambda *args, **kwargs: 1.0)
    return None

# ---- CandleRepository.fetch_candles mock ----
def _fake_fetch(symbol, interval, n_rows, newest_first=False, start_time=None, for_short=False):
    if interval in {'1d', '1w'}:
        return _make_day_df(n_rows)
    # detail intervals
    return _make_detail_df(start_time, periods=10, base=100.0, short=for_short, interval=interval)

# ------------------ Tests ------------------

def _patch_infrastructure(monkeypatch, orchestrator):
    # Patch load_component
    monkeypatch.setattr(orchestrator, "load_component", _dummy_load_component, raising=True)

    # Patch CandleRepository.fetch_candles on the class inside orchestrator
    # IMPORTANT: patch the class that StrategyOrchestrator imported, not your project path
    def _fetch(self, symbol, interval, n_rows, newest_first=False, start_time=None):
        # Decide short/long data by DummyStrategy.signal_type
        short = (DummyStrategy.signal_type == 'SELL')
        return _fake_fetch(symbol, interval, n_rows, newest_first, start_time, for_short=short)

    monkeypatch.setattr(
        orchestrator.CandleRepository, "fetch_candles", _fetch, raising=True
    )


def test_proposal_generation_timestamp(monkeypatch, orchestrator_mod):
    orchestrator = orchestrator_mod
    _patch_infrastructure(monkeypatch, orchestrator)

    DummyStrategy.signal_type = 'BUY'
    cfg = {'symbols': ['TEST'], 'interval': '1d', 'num_iterations': 5, 'initial_cash': 100000}
    res = orchestrator.run_backtest(cfg)
    assert len(res['trade_log']) > 0
    assert res['trade_log'][0]['entry_time'] > 10**9  # ms epoch, not a tiny index


def test_short_trade_execution(monkeypatch, orchestrator_mod):
    orchestrator = orchestrator_mod
    _patch_infrastructure(monkeypatch, orchestrator)

    DummyStrategy.signal_type = 'SELL'
    cfg = {'symbols': ['TEST'], 'interval': '1d', 'num_iterations': 1, 'initial_cash': 100000}
    res = orchestrator.run_backtest(cfg)
    assert len(res['trade_log']) == 1
    trade = res['trade_log'][0]
    assert trade['direction'] == 'SHORT'
    assert trade['exit_type'] in ('TP', 'FINAL')  # depending on your builder/exit logic
    assert res['final_cash'] >= 100000  # profit or flat


def test_final_position_close_out(monkeypatch, orchestrator_mod):
    orchestrator = orchestrator_mod
    _patch_infrastructure(monkeypatch, orchestrator)

    DummyStrategy.signal_type = 'BUY'
    cfg = {'symbols': ['TEST'], 'interval': '1d', 'num_iterations': 1, 'initial_cash': 100000}
    res = orchestrator.run_backtest(cfg)
    assert len(res['trade_log']) == 1
    assert res['trade_log'][0]['exit_type'] in ('FINAL', 'TP', 'SL')  # FINAL expected in flat detail


def test_load_component_params_instantiation(monkeypatch, orchestrator_mod):
    orchestrator = orchestrator_mod
    _patch_infrastructure(monkeypatch, orchestrator)

    DummyStrategy.signal_type = 'BUY'
    cfg = {'symbols': ['TEST'], 'interval': '1d', 'strategy': {'module': 'x', 'class': 'Y', 'params': {} }}
    res = orchestrator.run_backtest(cfg)
    assert isinstance(res, dict)  # ran without TypeError


def test_sizing_model_application(monkeypatch, orchestrator_mod):
    orchestrator = orchestrator_mod

    # Patch load_component, but return a sizing model that scales to 0.5
    def _load_component_sized(spec, builtin, base_cls, label):
        if label == 'strategy':
            return DummyStrategy
        if label == 'sizing_model':
            return (lambda meta, act: 0.5)
        if label in ('fee_model', 'slippage_model'): return (lambda ev: 0.0)
        if label == 'fill_policy':
            class _FP:
                def __init__(self, *_): pass
            return _FP
        if label == 'capacity_policy': return (lambda *args, **kwargs: True)
        return None

    monkeypatch.setattr(orchestrator, "load_component", _load_component_sized, raising=True)

    # Patch CandleRepository.fetch_candles
    def _fetch(self, symbol, interval, n_rows, newest_first=False, start_time=None):
        short = True  # force profit scenario
        return _fake_fetch(symbol, interval, n_rows, newest_first, start_time, for_short=short)
    monkeypatch.setattr(orchestrator.CandleRepository, "fetch_candles", _fetch, raising=True)

    DummyStrategy.signal_type = 'SELL'
    cfg = {'symbols': ['TEST'], 'interval': '1d', 'num_iterations': 1, 'initial_cash': 100000}
    res = orchestrator.run_backtest(cfg)
    t = res['trade_log'][0]
    assert math.isclose(t['size'], 0.5, rel_tol=1e-6)
    assert res['final_cash'] >= 100000  # profit scaled to 0.5 position


def test_initial_cash_config(monkeypatch, orchestrator_mod):
    orchestrator = orchestrator_mod
    _patch_infrastructure(monkeypatch, orchestrator)

    DummyStrategy.signal_type = 'HOLD'
    cfg = {'symbols': ['TEST'], 'interval': '1d', 'num_iterations': 1, 'initial_cash': 50000}
    res = orchestrator.run_backtest(cfg)
    assert math.isclose(res['final_cash'], 50000, rel_tol=1e-6)
