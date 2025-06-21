import os
import sys
import subprocess
import platform
import logging
import schedule
import yaml
import questionary

from marketDataApi.apiconfig.config import ANALYSIS_SYMBOLS
from marketDataApi.loader import initialize_symbols, initialize_symbols_from_config
from runEnvironment.BackTestEnvironment import backtest_timeframe_cached, backtest_timeframe
from strategies.concreteStrategies.EnsembleStrategy import EnsembleStrategy
from strategies.concreteStrategies.MomentumStrategy import MomentumStrategy
from strategies.concreteStrategies.PeakEmaReversalStrategy import PeakEMAReversalStrategy

YAML_CONFIG_FILE = "./inputconfig/config.yml"

def load_config(config_path=YAML_CONFIG_FILE):
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    return config

def create_strategy_from_config(cfg):
    # Simple single-strategy support
    strat_name = cfg['name']
    params = cfg.get('params', {})
    if strat_name == 'peak_ema_reversal':
        return PeakEMAReversalStrategy(**params)
    elif strat_name == 'momentum':
        return MomentumStrategy(**params)
    else:
        raise ValueError(f"Unknown strategy: {strat_name}")

def create_ensemble_from_config(cfg):
    strategies = []
    weights = []
    for strat_cfg in cfg['strategies']:
        strat = create_strategy_from_config(strat_cfg)
        weight = strat_cfg.get('weight', 1.0)
        strategies.append(strat)
        weights.append(weight)
    total = sum(weights)
    weights = [w/total for w in weights]
    return EnsembleStrategy(strategies, weights=weights)

def open_new_terminal_and_rerun():
    system = platform.system()
    script = sys.argv[0]
    args = sys.argv[1:]
    command = [sys.executable, script] + args
    print("Attempting to launch a new terminal window for interactive input...")
    try:
        if system == "Windows":
            # Uses start to launch new terminal (cmd)
            subprocess.Popen(["start", "cmd", "/K"] + command, shell=True)
        elif system == "Darwin":  # macOS
            subprocess.Popen(["open", "-a", "Terminal.app"] + command)
        elif system == "Linux":
            # Try common terminals
            for term in ["gnome-terminal", "x-terminal-emulator", "konsole", "xterm"]:
                try:
                    subprocess.Popen([term, "-e"] + command)
                    break
                except FileNotFoundError:
                    continue
        else:
            print("Unknown OS. Please rerun this script from a terminal.")
    except Exception as e:
        print(f"Could not launch a new terminal: {e}")
    sys.exit(0)

def get_config_or_interactive():
    import sys
    if not sys.stdin.isatty():
        print("Detected non-interactive environment.")
        if os.path.exists(YAML_CONFIG_FILE):
            print("Config file found. Automatically using config mode.")
            cfg = load_config(YAML_CONFIG_FILE)
            return "config", cfg
        else:
            print("No config file found. Trying to open a new terminal for interactive input...")
            open_new_terminal_and_rerun()
            # Will exit above. If failed, return exit
            print("Failed to open a terminal. Exiting.")
            sys.exit(1)
    else:
        if os.path.exists(YAML_CONFIG_FILE):
            mode = questionary.select(
                "Choose input mode:",
                choices=[
                    "config file",
                    "interactive"
                ]
            ).ask()
            if mode == "config file":
                cfg = load_config(YAML_CONFIG_FILE)
                return "config", cfg
            else:
                return "interactive", None
        else:
            return "interactive", None


def safe_float(prompt, default=None):
    while True:
        ans = questionary.text(prompt).ask()
        if ans == "" and default is not None:
            return default
        try:
            return float(ans)
        except Exception:
            print("Invalid input, enter a number.")

def interactive_input():
    print("Which strategy? (peak_ema_reversal/momentum/ensemble)")
    strategy_name = questionary.select(
        "Strategy:",
        choices=["peak_ema_reversal", "momentum", "ensemble"]
    ).ask()

    if strategy_name == "ensemble":
        # Example: support 2 strategies in ensemble
        print("For ensemble, you will configure two strategies and weights.")
        s1 = questionary.select("First strategy:", choices=["peak_ema_reversal", "momentum"]).ask()
        w1 = safe_float("Weight for first strategy? (e.g. 0.5)")
        s2 = questionary.select("Second strategy:", choices=["peak_ema_reversal", "momentum"]).ask()
        w2 = safe_float("Weight for second strategy? (e.g. 0.5)")
        strat_cfgs = [{"name": s1, "weight": w1}, {"name": s2, "weight": w2}]
        strat_cfg = {"use": True, "strategies": strat_cfgs}
        strategy = create_ensemble_from_config(strat_cfg)
    else:
        params = {}
        if strategy_name == "peak_ema_reversal":
            params['tp_ratio'] = safe_float("TP ratio? (e.g. 0.1)")
            params['sl_ratio'] = safe_float("SL ratio? (e.g. 0.05)")
            strategy = PeakEMAReversalStrategy(**params)
        elif strategy_name == "momentum":
            params['window'] = int(safe_float("Momentum window (e.g. 20)"))
            strategy = MomentumStrategy(**params)

    tf = questionary.select("Which timeframe?", choices=["1w", "1d"]).ask()
    save_charts = questionary.confirm("Save charts?").ask()
    add_buy_pct = safe_float("Add-buy pct (e.g. 5.0)")
    tp_ratio = safe_float("TP ratio (e.g. 0.1)")
    sl_ratio = safe_float("SL ratio (e.g. 0.05)")
    use_cache = questionary.confirm("Use signal cache?").ask()
    start_date = questionary.text("Start date (YYYY-MM-DD, leave blank for default):").ask()
    if start_date == "":
        start_date = None
    return {
        "strategy": strategy,
        "tf": tf,
        "tp_ratio": tp_ratio,
        "sl_ratio": sl_ratio,
        "save_charts": save_charts,
        "add_buy_pct": add_buy_pct,
        "use_cache": use_cache,
        "start_date": start_date,
    }

def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logging.info("Starting Backtest Bot (hybrid mode)...")

    mode, config = get_config_or_interactive()
    # After loading config:
    if "symbols" in config:
        ANALYSIS_SYMBOLS = initialize_symbols_from_config(config["symbols"])
    else:
        ANALYSIS_SYMBOLS = initialize_symbols()  # Fallback to old interactive version

    if not ANALYSIS_SYMBOLS:
        logging.info("No symbols available for analysis. Exiting.")
        return

    if mode == "config":
        cfg = config
        if cfg.get('ensemble', {}).get('use', False):
            strategy = create_ensemble_from_config(cfg['ensemble'])
        else:
            strategy = create_strategy_from_config(cfg['strategy'])
        backtest_cfg = cfg['backtest']
        # Backtest (cache optional)
        use_cache = backtest_cfg.get('use_cache', False)
        backtest_func = backtest_timeframe_cached if use_cache else backtest_timeframe
        results = backtest_func(
            strategy,
            ANALYSIS_SYMBOLS,
            backtest_cfg['timeframe'],
            num_iterations=backtest_cfg.get('num_iterations', 100),
            tp_ratio=backtest_cfg['tp_ratios'][0],
            sl_ratio=backtest_cfg['sl_ratios'][0],
            save_charts=backtest_cfg.get('save_charts', False),
            add_buy_pct=backtest_cfg.get('add_buy_pcts', [5.0])[0],
            start_date=backtest_cfg.get('start_date', None)
        )
    else:
        params = interactive_input()
        # Backtest (cache optional)
        backtest_func = backtest_timeframe_cached if params['use_cache'] else backtest_timeframe
        results = backtest_func(
            params['strategy'],
            ANALYSIS_SYMBOLS,
            params['tf'],
            num_iterations=100,
            tp_ratio=params['tp_ratio'],
            sl_ratio=params['sl_ratio'],
            save_charts=params['save_charts'],
            add_buy_pct=params['add_buy_pct'],
            start_date=params['start_date']
        )
    logging.info("Backtest complete.")

if __name__ == "__main__":
    main()
