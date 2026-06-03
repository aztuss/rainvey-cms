"""
signals/scorer.py — Signal scoring engine.

Orchestrates multi-timeframe analysis:
  - H1 data for entry signals (indicator scoring)
  - H4 data for trend direction confirmation
  - Order Block & Liquidity analysis for market structure confirmation
  - Combines scores to determine trade action
"""

import logging
import pandas as pd

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config
from indicators import forex, crypto, indices, commodities, stocks
from indicators.base import determine_direction, is_ema_flat
from indicators import order_block

logger = logging.getLogger(__name__)

# Map market class to indicator module
INDICATOR_MODULES = {
    "forex": forex,
    "crypto": crypto,
    "indices": indices,
    "commodities": commodities,
    "stocks": stocks,
}

def check_3_candle_momentum(df, direction):
    """
    Ensure the last 3 H1 candles moved in the intended trade direction.
    """
    if len(df) < 3:
        return False
        
    last_3 = df.iloc[-3:]
    if direction == "LONG":
        return all(row["close"] > row["open"] for _, row in last_3.iterrows())
    elif direction == "SHORT":
        return all(row["close"] < row["open"] for _, row in last_3.iterrows())
        
    return False


def get_h4_trend(df_h4, market_class, symbol=None):
    """
    Determine the H4 trend direction using relaxed EMA-based logic.

    Uses price position relative to EMA200 as primary signal,
    combined with a very low slope threshold to avoid filtering
    out valid trends.

    Args:
        df_h4: H4 OHLCV DataFrame
        market_class: "forex", "crypto", "indices", "commodities", "stocks"
        symbol: Optional instrument symbol

    Returns:
        "LONG", "SHORT", or "NONE"
    """
    params = config.get_instrument_params(symbol) if symbol else config.INDICATOR_PARAMS[market_class]
    # Use EMA50 for H4 trend — Capital.com typically returns ~100 H4 bars,
    # which is not enough for EMA200. EMA50 on H4 ≈ EMA200 on H1.
    ema_period = 50

    if len(df_h4) < ema_period:
        return "NONE"

    ema = df_h4['close'].ewm(span=ema_period).mean()

    # Use last 3 H4 candles to determine slope
    if len(ema) < 4:
        return "NONE"

    slope = (ema.iloc[-1] - ema.iloc[-4]) / ema.iloc[-4] * 100
    current_price = df_h4['close'].iloc[-1]
    ema_now = ema.iloc[-1]

    # Price position relative to EMA (primary check)
    price_above = current_price > ema_now
    price_below = current_price < ema_now

    # Relaxed slope threshold: 0.01% instead of 0.1%
    if price_above and slope > 0.01:
        return "LONG"
    elif price_below and slope < -0.01:
        return "SHORT"
    elif price_above and slope > -0.05:
        return "LONG"   # Price above EMA is enough
    elif price_below and slope < 0.05:
        return "SHORT"  # Price below EMA is enough
    else:
        return "NONE"


def score_instrument(symbol, df_h1, df_h4):
    """
    Full signal scoring for one instrument.

    Process:
        1. Get H4 trend direction
        2. Compute H1 indicators and score
        3. Check H4/H1 alignment
        4. Analyze market structure (Order Blocks, Liquidity)
        5. Determine lot size based on score

    Args:
        symbol: Instrument symbol (e.g., "EURUSD")
        df_h1: H1 OHLCV DataFrame (with enough history for indicators)
        df_h4: H4 OHLCV DataFrame

    Returns:
        dict with keys:
            symbol: str
            direction: "LONG" | "SHORT" | "NONE"
            score: int (0-6)
            confidence: float (0-100)
            lot_size: float ($15, $10, or 0)
            action: "FULL_LOT" | "REDUCED_LOT" | "SKIP"
            h4_trend: str
            h1_direction: str
            indicator_details: dict
            market_structure: dict (Order Block analysis)
            skip_reason: str or None
    """
    instrument_config = config.INSTRUMENTS[symbol]
    market_class = instrument_config["class"]
    params = config.get_instrument_params(symbol)
    module = INDICATOR_MODULES[market_class]

    result = {
        "symbol": symbol,
        "direction": "NONE",
        "score": 0,
        "confidence": 0.0,
        "lot_size": 0.0,
        "action": "SKIP",
        "h4_trend": "NONE",
        "h1_direction": "NONE",
        "indicator_details": {},
        "market_structure": {},
        "skip_reason": None,
    }

    # --- Step 1: H4 trend ---
    if df_h4 is None or df_h4.empty or len(df_h4) < 50:
        result["skip_reason"] = "Insufficient H4 data"
        logger.info(f"[{symbol}] SKIP — insufficient H4 data")
        return result

    h4_trend = get_h4_trend(df_h4, market_class, symbol)
    result["h4_trend"] = h4_trend

    if h4_trend == "NONE":
        result["skip_reason"] = "H4 trend unclear"
        logger.info(f"[{symbol}] SKIP — H4 trend unclear")
        return result

    # --- Step 2: H1 indicators and scoring ---
    if df_h1 is None or df_h1.empty or len(df_h1) < 200:
        result["skip_reason"] = "Insufficient H1 data"
        logger.info(f"[{symbol}] SKIP — insufficient H1 data")
        return result

    df_h1 = module.compute_indicators(df_h1, params)
    h1_direction, score, details = module.score_signal(df_h1, params)
    result["h1_direction"] = h1_direction
    result["indicator_details"] = details

    if h1_direction == "NONE":
        result["skip_reason"] = "H1 signal unclear"
        logger.info(f"[{symbol}] SKIP — H1 signal unclear")
        return result

    # --- Step 3: H4/H1 alignment check ---
    if h4_trend != h1_direction:
        result["score"] = score
        result["skip_reason"] = f"H4 trend ({h4_trend}) opposes H1 signal ({h1_direction})"
        logger.info(
            f"[{symbol}] SKIP — H4={h4_trend} vs H1={h1_direction} (misaligned)"
        )
        return result

    # --- Step 3.5: 3-Candle Momentum Filter (RELAXED) ---
    # Only log for info, do not block trades based on this
    if not check_3_candle_momentum(df_h1, h1_direction):
        logger.debug(f"[{symbol}] NOTE — 3-candle momentum not confirmed (continuing anyway)")

    # --- Step 4: Market Structure Analysis (Order Blocks + Liquidity + Sweep + MSS) ---
    atr_value = get_atr_value(df_h1, market_class)
    try:
        structure = order_block.analyze_market_structure(
            df_h1,
            h1_direction,
            atr_value=atr_value,
            lookback=168  # 7 days of H1
        )
        result["market_structure"] = structure

        # Log detailed SMC analysis
        sweep  = structure.get("liquidity_sweep", {})
        mss    = structure.get("mss", {})
        sl_tp  = structure.get("sl_tp", {})
        obs    = structure.get("order_blocks", {})

        ob_key = "bullish_ob" if h1_direction == "LONG" else "bearish_ob"
        ob_count = len(obs.get(ob_key, []))

        logger.info(
            f"[{symbol}] SMC -> OBs={ob_count} "
            f"| Sweep={'Y ({} ago)'.format(sweep.get('candles_ago', '?')) if sweep.get('swept') else 'N'} "
            f"| MSS={'Y' if mss.get('confirmed') else 'N'} "
            f"| RR={sl_tp.get('risk_reward', 0):.1f} "
            f"| Strength={structure['entry_strength']} [{structure['recommendation']}]"
        )
        if sl_tp.get('sl'):
            logger.info(
                f"[{symbol}] OB Levels -> SL={sl_tp.get('sl')} "
                f"TP1={sl_tp.get('tp1')} TP2={sl_tp.get('tp2')} "
                f"[OB={'Y' if sl_tp.get('ob_used') else 'N'} "
                f"Liq={'Y' if sl_tp.get('liq_used') else 'N'}]"
            )
    except Exception as e:
        logger.warning(f"[{symbol}] Market structure analysis failed: {e}")
        result["market_structure"] = {}

    # --- Step 5: Market Structure Validation ---
    # SMC threshold: 0.35 minimum (at least OB or Sweep must be present)
    market_struct  = result.get("market_structure", {})
    entry_strength = market_struct.get("entry_strength", 0.0)

    if entry_strength < 0.35:
        result["skip_reason"] = (
            f"Weak SMC structure (strength={entry_strength}) — "
            f"No OB + No Sweep detected"
        )
        logger.info(
            f"[{symbol}] SKIP — SMC strength too low ({entry_strength}) "
            f"(need OB or Liquidity Sweep to enter)"
        )
        return result

    # --- Step 6: Score-based action ---
    result["direction"] = h1_direction
    result["score"] = score
    result["confidence"] = round((score / 6) * 100, 1)

    if score >= config.SCORE_FULL_LOT:
        result["action"] = "FULL_LOT"
        logger.info(
            f"[{symbol}] {h1_direction} — Score {score}/6 "
            f"({result['confidence']}%) [Structure: {entry_strength}] -> FULL_LOT action"
        )
    elif score >= config.SCORE_REDUCED_LOT:
        result["action"] = "REDUCED_LOT"
        logger.info(
            f"[{symbol}] {h1_direction} — Score {score}/6 "
            f"({result['confidence']}%) [Structure: {entry_strength}] -> REDUCED_LOT action"
        )
    else:
        result["action"] = "SKIP"
        result["skip_reason"] = f"Score too low ({score}/6)"
        logger.info(
            f"[{symbol}] SKIP — Score {score}/6 ({result['confidence']}%) below threshold"
        )

    return result


def get_atr_value(df_h1, market_class):
    """
    Extract the latest ATR value from an H1 DataFrame with indicators computed.

    Args:
        df_h1: H1 DataFrame (indicators already computed)
        market_class: Market class string

    Returns:
        float ATR value, or None if unavailable
    """
    params = config.INDICATOR_PARAMS.get(market_class, config.INDICATOR_PARAMS["forex"])
    atr_col = f"atr_{params['atr_period']}"

    if atr_col not in df_h1.columns:
        return None

    val = df_h1.iloc[-1][atr_col]
    if pd.isna(val):
        return None
    return float(val)
