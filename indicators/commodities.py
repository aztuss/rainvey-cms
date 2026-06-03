"""
indicators/commodities.py — Commodities indicator computation and scoring.

Indicators: EMA(200), ADX(14), RSI(14), ATR(14), Supertrend(10, 3.0), Bollinger Bands(20, 2.0)
"""

import pandas as pd
import logging
from indicators.base import (
    compute_ema, compute_adx, compute_rsi, compute_atr,
    compute_supertrend, compute_bollinger_bands,
    check_trend_ma, check_adx, check_rsi, check_bollinger,
    check_supertrend, check_atr_trend, determine_direction,
)

logger = logging.getLogger(__name__)


def compute_indicators(df, params):
    """
    Compute all commodities indicators on the given DataFrame.

    Args:
        df: OHLCV DataFrame
        params: Indicator parameters from config.INDICATOR_PARAMS["commodities"]

    Returns:
        DataFrame with indicator columns added.
    """
    df = df.copy()

    # Trend MA (EMA 200)
    compute_ema(df, params["trend_ma_period"])

    # ADX
    compute_adx(df, params["adx_period"])

    # RSI
    compute_rsi(df, params["rsi_period"])

    # ATR
    compute_atr(df, params["atr_period"])

    # Supertrend (10, 3.0)
    compute_supertrend(df, params["supertrend_period"], params["supertrend_multiplier"])

    # Bollinger Bands (20, 2.0)
    compute_bollinger_bands(df, params["bb_period"], params["bb_std"])

    return df


def score_signal(df, params):
    """
    Score the current signal for a commodities instrument.

    Scoring (6 indicators, 1 point each):
        1. Trend MA (EMA 200): price above/below
        2. ADX(14): above threshold (25)
        3. RSI(14): in long zone (40-65) or short zone (35-60)
        4. Bollinger Bands: price above/below middle band
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

    # 4. Bollinger Bands
    details["bollinger"] = check_bollinger(df, direction)

    # 5. Supertrend
    details["supertrend"] = check_supertrend(df, direction)

    # 6. ATR trend
    details["atr_trend"] = check_atr_trend(df, params, direction)

    score = sum(details.values())
    return direction, score, details
