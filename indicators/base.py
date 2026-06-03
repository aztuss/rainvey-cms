"""
indicators/base.py — Common indicator computation utilities.

Provides shared functions used across all market-class indicator modules.
All indicator modules must implement:
  - compute_indicators(df, params) → df with indicator columns
  - score_signal(df, params) → (direction, score, details)
"""

import pandas as pd
import pandas_ta as ta
import logging

logger = logging.getLogger(__name__)


def compute_ema(df, period, col="close"):
    """Compute Exponential Moving Average."""
    df[f"ema_{period}"] = ta.ema(df[col], length=period)
    return df


def compute_sma(df, period, col="close"):
    """Compute Simple Moving Average."""
    df[f"sma_{period}"] = ta.sma(df[col], length=period)
    return df


def compute_adx(df, period=14):
    """Compute Average Directional Index (ADX with +DI and -DI)."""
    adx_df = ta.adx(df["high"], df["low"], df["close"], length=period)
    if adx_df is not None and not adx_df.empty:
        df[f"adx_{period}"] = adx_df[f"ADX_{period}"]
        df[f"dmp_{period}"] = adx_df[f"DMP_{period}"]
        df[f"dmn_{period}"] = adx_df[f"DMN_{period}"]
    return df


def compute_rsi(df, period=14):
    """Compute Relative Strength Index."""
    df[f"rsi_{period}"] = ta.rsi(df["close"], length=period)
    return df


def compute_atr(df, period=14):
    """Compute Average True Range."""
    df[f"atr_{period}"] = ta.atr(df["high"], df["low"], df["close"], length=period)
    return df


def compute_macd(df, fast=12, slow=26, signal=9):
    """Compute MACD, Signal line, and Histogram."""
    macd_df = ta.macd(df["close"], fast=fast, slow=slow, signal=signal)
    if macd_df is not None and not macd_df.empty:
        df["macd"] = macd_df[f"MACD_{fast}_{slow}_{signal}"]
        df["macd_signal"] = macd_df[f"MACDs_{fast}_{slow}_{signal}"]
        df["macd_hist"] = macd_df[f"MACDh_{fast}_{slow}_{signal}"]
    return df


def compute_supertrend(df, period=10, multiplier=3.0):
    """Compute Supertrend indicator."""
    st_df = ta.supertrend(
        df["high"], df["low"], df["close"],
        length=period, multiplier=multiplier
    )
    if st_df is not None and not st_df.empty:
        # pandas_ta supertrend columns: SUPERT_period_mult, SUPERTd_period_mult, etc.
        st_col = f"SUPERT_{period}_{multiplier}"
        std_col = f"SUPERTd_{period}_{multiplier}"
        # Find the actual column names (may have float formatting differences)
        for c in st_df.columns:
            if c.startswith("SUPERT_") and "d_" not in c and "l_" not in c and "s_" not in c:
                st_col = c
            elif c.startswith("SUPERTd_"):
                std_col = c
        df["supertrend"] = st_df[st_col]
        df["supertrend_dir"] = st_df[std_col]
    return df


def compute_obv(df):
    """Compute On-Balance Volume."""
    df["obv"] = ta.obv(df["close"], df["volume"])
    return df


def compute_vwap(df):
    """
    Compute Volume-Weighted Average Price (approximation on H1 candles).
    Resets daily.
    """
    # VWAP = cumsum(typical_price * volume) / cumsum(volume)
    # We reset at each new day.
    typical_price = (df["high"] + df["low"] + df["close"]) / 3
    tp_vol = typical_price * df["volume"]

    # Group by date for daily reset
    if "datetime" in df.columns:
        dates = df["datetime"].dt.date
    else:
        dates = pd.Series(range(len(df)))

    vwap_values = []
    cum_tp_vol = 0.0
    cum_vol = 0.0
    last_date = None

    for i in range(len(df)):
        current_date = dates.iloc[i]
        if current_date != last_date:
            cum_tp_vol = 0.0
            cum_vol = 0.0
            last_date = current_date

        cum_tp_vol += tp_vol.iloc[i]
        cum_vol += df["volume"].iloc[i]

        if cum_vol > 0:
            vwap_values.append(cum_tp_vol / cum_vol)
        else:
            vwap_values.append(typical_price.iloc[i])

    df["vwap"] = vwap_values
    return df


def compute_bollinger_bands(df, period=20, std=2.0):
    """Compute Bollinger Bands."""
    bb_df = ta.bbands(df["close"], length=period, std=std)
    if bb_df is not None and not bb_df.empty:
        # Columns: BBL, BBM, BBU, BBB, BBP
        for c in bb_df.columns:
            if c.startswith("BBL_"):
                df["bb_lower"] = bb_df[c]
            elif c.startswith("BBM_"):
                df["bb_middle"] = bb_df[c]
            elif c.startswith("BBU_"):
                df["bb_upper"] = bb_df[c]
            elif c.startswith("BBB_"):
                df["bb_bandwidth"] = bb_df[c]
            elif c.startswith("BBP_"):
                df["bb_pctb"] = bb_df[c]
    return df


def get_trend_ma(df, params):
    """Get the trend MA column name and compute it."""
    ma_type = params["trend_ma_type"]
    period = params["trend_ma_period"]
    col_name = f"{ma_type.lower()}_{period}"

    if col_name not in df.columns:
        if ma_type == "EMA":
            compute_ema(df, period)
        else:
            compute_sma(df, period)

    return col_name


def check_trend_ma(df, params, direction):
    """
    Check if price is above/below the trend MA.

    Returns:
        1 if confirms direction, 0 otherwise.
    """
    col = get_trend_ma(df, params)
    if col not in df.columns:
        return 0

    last = df.iloc[-1]
    if pd.isna(last[col]):
        return 0

    if direction == "LONG":
        return 1 if last["close"] > last[col] else 0
    elif direction == "SHORT":
        return 1 if last["close"] < last[col] else 0
    return 0


def check_adx(df, params):
    """
    Check if ADX is above threshold (trend is strong enough).

    Returns:
        1 if ADX > threshold, 0 otherwise.
    """
    period = params["adx_period"]
    threshold = params["adx_threshold"]
    col = f"adx_{period}"

    if col not in df.columns:
        return 0

    last = df.iloc[-1]
    if pd.isna(last[col]):
        return 0

    # Volume confirmation: current volume > 20-period average volume
    vol_confirm = True
    if "volume" in df.columns and len(df) >= 20:
        vol_sma = df["volume"].rolling(20).mean().iloc[-1]
        if pd.notna(last["volume"]) and pd.notna(vol_sma) and vol_sma > 0:
            vol_confirm = last["volume"] > vol_sma

    adx_pass = last[col] > threshold
    return 1 if (adx_pass and vol_confirm) else 0


def check_rsi(df, params, direction):
    """
    Check if RSI is in the valid zone for the given direction.

    Returns:
        1 if RSI is in zone, 0 otherwise.
    """
    period = params["rsi_period"]
    col = f"rsi_{period}"

    if col not in df.columns:
        return 0

    last = df.iloc[-1]
    if pd.isna(last[col]):
        return 0

    rsi_val = last[col]
    if direction == "LONG":
        lo, hi = params["rsi_long_zone"]
        return 1 if lo <= rsi_val <= hi else 0
    elif direction == "SHORT":
        lo, hi = params["rsi_short_zone"]
        return 1 if lo <= rsi_val <= hi else 0
    return 0


def check_macd(df, direction):
    """
    Check MACD histogram direction.

    Returns:
        1 if histogram confirms direction, 0 otherwise.
    """
    if "macd_hist" not in df.columns:
        return 0

    last = df.iloc[-1]
    if pd.isna(last["macd_hist"]):
        return 0

    if direction == "LONG":
        return 1 if last["macd_hist"] > 0 else 0
    elif direction == "SHORT":
        return 1 if last["macd_hist"] < 0 else 0
    return 0


def check_supertrend(df, direction):
    """
    Check Supertrend direction.
    supertrend_dir: 1 = bullish (price above ST), -1 = bearish.

    Returns:
        1 if confirms direction, 0 otherwise.
    """
    if "supertrend_dir" not in df.columns:
        return 0

    last = df.iloc[-1]
    if pd.isna(last["supertrend_dir"]):
        return 0

    if direction == "LONG":
        return 1 if last["supertrend_dir"] == 1 else 0
    elif direction == "SHORT":
        return 1 if last["supertrend_dir"] == -1 else 0
    return 0


def check_obv(df, direction):
    """
    Check OBV trend (rising = bullish, falling = bearish).
    Uses a 20-period SMA of OBV as reference.

    Returns:
        1 if OBV confirms direction, 0 otherwise.
    """
    if "obv" not in df.columns:
        return 0

    if len(df) < 20:
        return 0

    last = df.iloc[-1]
    obv_sma = df["obv"].rolling(20).mean().iloc[-1]

    if pd.isna(last["obv"]) or pd.isna(obv_sma):
        return 0

    if direction == "LONG":
        return 1 if last["obv"] > obv_sma else 0
    elif direction == "SHORT":
        return 1 if last["obv"] < obv_sma else 0
    return 0


def check_vwap(df, direction):
    """
    Check price vs VWAP.
    LONG: price above VWAP, SHORT: price below VWAP.

    Returns:
        1 if confirms direction, 0 otherwise.
    """
    if "vwap" not in df.columns:
        return 0

    last = df.iloc[-1]
    if pd.isna(last["vwap"]):
        return 0

    if direction == "LONG":
        return 1 if last["close"] > last["vwap"] else 0
    elif direction == "SHORT":
        return 1 if last["close"] < last["vwap"] else 0
    return 0


def check_bollinger(df, direction):
    """
    Check Bollinger Bands for mean-reversion / breakout signal.
    LONG: price near lower band (bb_pctb < 0.2) or bouncing from it.
    SHORT: price near upper band (bb_pctb > 0.8) or rejecting from it.

    For trend-following context, we check:
    LONG: price above middle band (bullish momentum)
    SHORT: price below middle band (bearish momentum)

    Returns:
        1 if confirms direction, 0 otherwise.
    """
    if "bb_middle" not in df.columns:
        return 0

    last = df.iloc[-1]
    if pd.isna(last["bb_middle"]):
        return 0

    if direction == "LONG":
        return 1 if last["close"] > last["bb_middle"] else 0
    elif direction == "SHORT":
        return 1 if last["close"] < last["bb_middle"] else 0
    return 0


def check_atr_trend(df, params, direction):
    """
    ATR-based volatility confirmation.
    Confirms trade if ATR is above its 20-period SMA (volatility is expanding).
    This isn't direction-specific — it confirms that the market is moving.

    Returns:
        1 if ATR > ATR_SMA (volatility is enough), 0 otherwise.
    """
    period = params["atr_period"]
    col = f"atr_{period}"

    if col not in df.columns:
        return 0

    if len(df) < 20:
        return 1  # Not enough data, give benefit of doubt

    atr_sma = df[col].rolling(20).mean().iloc[-1]
    last_atr = df.iloc[-1][col]

    if pd.isna(last_atr) or pd.isna(atr_sma):
        return 0

    return 1 if last_atr > atr_sma else 0


def is_ema_flat(df, params, lookback=5, threshold=0.0001):
    """
    Check if the EMA slope is flat over the lookback period.
    Default threshold is 0.01% (0.0001) change over 5 bars.
    Returns True if flat, False if clearly trending.
    """
    ma_col = get_trend_ma(df, params)
    if ma_col not in df.columns or len(df) < lookback + 1:
        return True
    
    current_ema = df.iloc[-1][ma_col]
    past_ema = df.iloc[-(lookback+1)][ma_col]
    
    if pd.isna(current_ema) or pd.isna(past_ema) or past_ema == 0:
        return True
        
    pct_change = abs((current_ema - past_ema) / past_ema)
    return pct_change < threshold


def determine_direction(df, params):
    """
    Determine the primary signal direction based on key indicators.
    Uses trend MA + Supertrend + ADX (+DI vs -DI) for direction.

    Returns:
        "LONG", "SHORT", or "NONE"
    """
    last = df.iloc[-1]

    # Check trend MA direction
    ma_col = get_trend_ma(df, params)
    if ma_col not in df.columns or pd.isna(last.get(ma_col)):
        return "NONE"

    above_ma = last["close"] > last[ma_col]

    # Check Supertrend direction
    st_bullish = False
    st_bearish = False
    if "supertrend_dir" in df.columns and not pd.isna(last.get("supertrend_dir")):
        st_bullish = last["supertrend_dir"] == 1
        st_bearish = last["supertrend_dir"] == -1

    # Check DI direction
    adx_period = params["adx_period"]
    dmp_col = f"dmp_{adx_period}"
    dmn_col = f"dmn_{adx_period}"
    di_long = False
    di_short = False
    if dmp_col in df.columns and dmn_col in df.columns:
        if not pd.isna(last.get(dmp_col)) and not pd.isna(last.get(dmn_col)):
            di_long = last[dmp_col] > last[dmn_col]
            di_short = last[dmn_col] > last[dmp_col]

    # Decision: at least 2 of 3 indicators must agree
    long_votes = sum([above_ma, st_bullish, di_long])
    short_votes = sum([not above_ma, st_bearish, di_short])

    if long_votes >= 2:
        return "LONG"
    elif short_votes >= 2:
        return "SHORT"
    return "NONE"
