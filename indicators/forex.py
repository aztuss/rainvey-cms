"""
indicators/forex.py — Forex indicator computation and scoring.

Indicators: EMA(200), ADX(14), RSI(14), ATR(14), MACD(12,26,9), Supertrend(10, 3.0)
"""

import pandas as pd
import logging
from indicators.base import (
    compute_ema, compute_adx, compute_rsi, compute_atr,
    compute_macd, compute_supertrend,
    check_trend_ma, check_adx, check_rsi, check_macd,
    check_supertrend, check_atr_trend, determine_direction,
    get_trend_ma,
)

logger = logging.getLogger(__name__)


def compute_indicators(df, params):
    """
    Compute all forex indicators on the given DataFrame.

    Args:
        df: OHLCV DataFrame
        params: Indicator parameters from config.INDICATOR_PARAMS["forex"]

    Returns:
        DataFrame with indicator columns added.
    """
    df = df.copy()

    # Trend MA
    compute_ema(df, params["trend_ma_period"])

    # ADX
    compute_adx(df, params["adx_period"])

    # RSI
    compute_rsi(df, params["rsi_period"])

    # ATR
    compute_atr(df, params["atr_period"])

    # MACD
    compute_macd(df, params["macd_fast"], params["macd_slow"], params["macd_signal"])

    # Supertrend
    compute_supertrend(df, params["supertrend_period"], params["supertrend_multiplier"])

    return df


def score_signal(df, params):
    """
    Score the current signal for a forex instrument.

    Scoring (6 indicators, 1 point each):
        1. Trend MA (EMA 200): price above/below
        2. ADX(14): above threshold (25)
        3. RSI(14): in long zone (45-65) or short zone (35-55)
        4. MACD histogram: positive/negative
        5. Supertrend: bullish/bearish
        6. ATR trend: volatility expanding

    Args:
        df: DataFrame with indicators computed
        params: Indicator parameters

    Returns:
        (direction, score, details) tuple
        direction: "LONG", "SHORT", or "NONE"
        score: 0-6
        details: dict with per-indicator results
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

    # 4. MACD histogram
    details["macd"] = check_macd(df, direction)

    # 5. Supertrend
    details["supertrend"] = check_supertrend(df, direction)

    # 6. ATR trend
    details["atr_trend"] = check_atr_trend(df, params, direction)

    score = sum(details.values())
    return direction, score, details
