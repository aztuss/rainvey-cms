"""
indicators/indices.py — Indices indicator computation and scoring.

Indicators: SMA(200), ADX(14), RSI(10), ATR(10), Supertrend(7, 3.0), VWAP
"""

import pandas as pd
import logging
from indicators.base import (
    compute_sma, compute_adx, compute_rsi, compute_atr,
    compute_supertrend, compute_vwap,
    check_trend_ma, check_adx, check_rsi, check_vwap,
    check_supertrend, check_atr_trend, determine_direction,
)

logger = logging.getLogger(__name__)


def compute_indicators(df, params):
    """
    Compute all indices indicators on the given DataFrame.

    Args:
        df: OHLCV DataFrame
        params: Indicator parameters from config.INDICATOR_PARAMS["indices"]

    Returns:
        DataFrame with indicator columns added.
    """
    df = df.copy()

    # Trend MA (SMA 200)
    compute_sma(df, params["trend_ma_period"])

    # ADX
    compute_adx(df, params["adx_period"])

    # RSI (10-period for indices)
    compute_rsi(df, params["rsi_period"])

    # ATR (10-period for indices)
    compute_atr(df, params["atr_period"])

    # Supertrend (7, 3.0)
    compute_supertrend(df, params["supertrend_period"], params["supertrend_multiplier"])

    # VWAP
    compute_vwap(df)

    return df


def score_signal(df, params):
    """
    Score the current signal for an indices instrument.

    Scoring (6 indicators, 1 point each):
        1. Trend MA (SMA 200): price above/below
        2. ADX(14): above threshold (20)
        3. RSI(10): in long zone (45-65) or short zone (35-55)
        4. VWAP: price above/below
        5. Supertrend: bullish/bearish
        6. ATR trend: volatility expanding

    Args:
        df: DataFrame with indicators computed
        params: Indicator parameters

    Returns:
        (direction, score, details) tuple
    """
    direction = determine_direction(df, params)
    if direction == "NONE":
        return "NONE", 0, {"reason": "No clear direction"}

    details = {}

    # 1. Trend MA
    details["trend_ma"] = check_trend_ma(df, params, direction)

    # 2. ADX
    details["adx"] = check_adx(df, params)

    # 3. RSI
    details["rsi"] = check_rsi(df, params, direction)

    # 4. VWAP
    details["vwap"] = check_vwap(df, direction)

    # 5. Supertrend
    details["supertrend"] = check_supertrend(df, direction)

    # 6. ATR trend
    details["atr_trend"] = check_atr_trend(df, params, direction)

    score = sum(details.values())
    return direction, score, details
