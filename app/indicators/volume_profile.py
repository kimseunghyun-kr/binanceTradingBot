# app/indicators/volume_profile.py
import numpy as np
import pandas as pd

def volume_profile(df: pd.DataFrame, bins: int = 20, value_area_pct: float = 0.7):
    """
    Calculate volume profile for the price range in df and return volume distribution and value area.
    Returns a dict with:
      - 'histogram': list of (price_level, volume) tuples for each bin
      - 'poc': price level with highest volume (Point of Control)
      - 'value_area': (low_price, high_price) covering `value_area_pct` of volume
    """
    if df.empty:
        return {"histogram": [], "poc": None, "value_area": None}
    highs = df["high"].to_numpy()
    lows = df["low"].to_numpy()
    volumes = df["volume"].to_numpy()
    total_vol = volumes.sum()
    price_min = lows.min()
    price_max = highs.max()
    # Define price bins
    hist_bins = np.linspace(price_min, price_max, bins+1)
    volume_hist = np.zeros(bins)
    # Accumulate volume into bins
    for high, low, vol in zip(highs, lows, volumes):
        # Distribute candle's volume across the bins that intersect its range
        # Determine which bins this candle spans
        candle_range = high - low if high > low else 0
        if candle_range <= 0 or vol == 0:
            # Treat as all volume at one price (use mid price)
            mid_price = (high + low) / 2.0
            # Find bin index for mid_price
            idx = np.searchsorted(hist_bins, mid_price) - 1
            if 0 <= idx < bins:
                volume_hist[idx] += vol
            continue
        # Spread volume linearly across price range
        # (Alternatively, allocate proportionally per overlapping segment)
        # Here, we'll sample a number of points (e.g., 10) in the range for simplicity
        parts = 10
        part_vol = vol / parts
        prices = np.linspace(low, high, parts+1)
        for p in prices:
            idx = np.searchsorted(hist_bins, p) - 1
            if 0 <= idx < bins:
                volume_hist[idx] += part_vol
    # Prepare output histogram data (using bin midpoints as price level)
    hist_data = []
    for i in range(bins):
        if volume_hist[i] > 0:
            price_level = (hist_bins[i] + hist_bins[i+1]) / 2.0
            hist_data.append((price_level, volume_hist[i]))
    if not hist_data:
        return {"histogram": [], "poc": None, "value_area": None}
    # Point of Control (max volume bin)
    poc_index = int(np.argmax(volume_hist))
    poc_price = (hist_bins[poc_index] + hist_bins[poc_index+1]) / 2.0
    # Calculate Value Area
    target_volume = total_vol * value_area_pct
    # Start from POC and include bins outward until target_volume is reached
    vol_sum = volume_hist[poc_index]
    left_idx = poc_index
    right_idx = poc_index
    while vol_sum < target_volume:
        # Decide whether to expand left or right next
        left_vol = volume_hist[left_idx-1] if left_idx > 0 else 0
        right_vol = volume_hist[right_idx+1] if right_idx < bins-1 else 0
        if left_vol >= right_vol and left_idx > 0:
            left_idx -= 1
            vol_sum += volume_hist[left_idx]
        elif right_idx < bins-1:
            right_idx += 1
            vol_sum += volume_hist[right_idx]
        else:
            break  # no more bins to expand
    value_area_low = hist_bins[left_idx]
    value_area_high = hist_bins[right_idx+1]
    return {
        "histogram": hist_data,
        "poc": poc_price,
        "value_area": (value_area_low, value_area_high)
    }
