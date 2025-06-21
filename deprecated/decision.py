import pandas as pd
from typing import Optional
from indicators.indicators import compute_ema_series

def kwon_strategy_decision(df: pd.DataFrame, interval: str,
                           tp_ratio: float = 0.1, sl_ratio: float = 0.05) -> dict:
    """
    1. Get initial signal
    2. Generate trade signal with TP/SL if initial signal is positive
    """
    initial_signal = check_upper_section(df, interval)
    final = generate_trade_signal(df, initial_signal, tp_ratio, sl_ratio)
    if final['signal'] == 'BUY':
        final['decision'] = f"YES_{final['ema_period']}"
    else:
        final['decision'] = 'NO'
    return final
