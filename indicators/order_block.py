"""
indicators/order_block.py — Smart Money Concept: Order Block & Liquidity Analysis

Real SMC Logic:
  1. Bullish Order Block  = Last BEARISH candle before a strong up-move
                           (institutional buy orders trapped there)
  2. Bearish Order Block  = Last BULLISH candle before a strong down-move
                           (institutional sell orders trapped there)
  3. Liquidity Sweep      = Price sweeps a swing high/low then reverses
                           (stops triggered → institutional entry)
  4. MSS (Market Structure Shift) = Break of structure confirming new direction
  5. FVG (Fair Value Gap) = 3-candle imbalance — price tends to fill it

SL/TP Strategy:
  LONG:  SL below Bullish OB low,  TP at nearest liquidity above
  SHORT: SL above Bearish OB high, TP at nearest liquidity below

Flow:
  Swing High/Low → Liquidity Sweep → MSS → OB identified → Entry at OB
"""

import pandas as pd
import numpy as np
import logging

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# 1. SWING HIGHS / LOWS
# ─────────────────────────────────────────────────────────────────────────────

def find_swing_levels(df, lookback=168, swing_strength=2):
    """
    Find swing highs and lows — price structures that attract liquidity.

    A swing high: candle high is higher than N candles on each side.
    A swing low:  candle low  is lower  than N candles on each side.

    Args:
        df: OHLCV DataFrame
        lookback: Number of candles to analyze (default 168 = 7 days H1)
        swing_strength: Candles on each side to confirm swing (default 2)

    Returns:
        dict with:
            'highs': list of {'price': float, 'idx': int, 'touched': int}
            'lows':  list of {'price': float, 'idx': int, 'touched': int}
    """
    if len(df) < (swing_strength * 2 + 3):
        return {"highs": [], "lows": []}

    df_an = df.iloc[-lookback:].copy().reset_index(drop=True)
    n = len(df_an)
    s = swing_strength

    swing_highs = []
    swing_lows  = []

    for i in range(s, n - s):
        high = df_an.iloc[i]['high']
        low  = df_an.iloc[i]['low']

        # Swing High: higher than all surrounding candles
        left_highs  = [df_an.iloc[j]['high'] for j in range(i - s, i)]
        right_highs = [df_an.iloc[j]['high'] for j in range(i + 1, i + s + 1)]

        if all(high > h for h in left_highs) and all(high > h for h in right_highs):
            swing_highs.append({
                "price": round(high, 5),
                "idx":   i,
                "type":  "high"
            })

        # Swing Low: lower than all surrounding candles
        left_lows  = [df_an.iloc[j]['low'] for j in range(i - s, i)]
        right_lows = [df_an.iloc[j]['low'] for j in range(i + 1, i + s + 1)]

        if all(low < l for l in left_lows) and all(low < l for l in right_lows):
            swing_lows.append({
                "price": round(low, 5),
                "idx":   i,
                "type":  "low"
            })

    return {
        "highs": swing_highs,
        "lows":  swing_lows,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 2. ORDER BLOCKS (Real SMC Definition)
# ─────────────────────────────────────────────────────────────────────────────

def find_order_blocks(df, lookback=168, min_move_multiplier=1.5):
    """
    Identify REAL Order Blocks using Smart Money Concept definition.

    Bullish OB = Last BEARISH (red) candle immediately before a strong
                 bullish impulse. Price often returns to this zone.
                 → SL goes BELOW the OB low.

    Bearish OB = Last BULLISH (green) candle immediately before a strong
                 bearish impulse. Price often returns to this zone.
                 → SL goes ABOVE the OB high.

    Detection method:
      1. Calculate average candle body size
      2. Find candles with bodies > min_move_multiplier × avg (strong moves)
      3. The last opposing-color candle before the strong move = Order Block
      4. OB must NOT have been violated (mitigated) since formation

    Args:
        df: OHLCV DataFrame
        lookback: Number of candles to analyze
        min_move_multiplier: Impulse must be N × avg body to qualify

    Returns:
        dict:
            'bullish_ob': list of OB dicts (most recent last)
            'bearish_ob': list of OB dicts (most recent last)
        Each OB dict:
            zone_high, zone_low: OB price range
            ob_open, ob_close:   Actual open/close of the OB candle
            formed_at_idx:       Index in df where OB was formed
            strength:            Impulse strength score 0-1
            mitigated:           Whether price has already entered the OB
            distance_pips:       Distance from current price to OB zone
            has_fvg:             True if the impulse created a Fair Value Gap
    """
    if len(df) < 20:
        return {"bullish_ob": [], "bearish_ob": []}

    df_an = df.iloc[-lookback:].copy().reset_index(drop=True)
    n = len(df_an)

    # Average body size (for impulse detection)
    bodies = abs(df_an['close'] - df_an['open'])
    avg_body = bodies.mean()
    if avg_body == 0:
        return {"bullish_ob": [], "bearish_ob": []}

    current_price = df_an['close'].iloc[-1]

    bullish_obs = []
    bearish_obs = []

    for i in range(3, n - 2):
        body  = df_an.iloc[i]['close'] - df_an.iloc[i]['open']
        is_bull = body > 0
        is_bear = body < 0

        # ── Bullish OB: Find last bearish candle before bullish impulse ──
        if is_bull and abs(body) > avg_body * min_move_multiplier:
            # Search backward for last bearish candle
            for j in range(i - 1, max(i - 6, 0), -1):
                prev_body = df_an.iloc[j]['close'] - df_an.iloc[j]['open']
                if prev_body < 0:  # Bearish candle found
                    ob_high = df_an.iloc[j]['high']
                    ob_low  = df_an.iloc[j]['low']
                    ob_open = df_an.iloc[j]['open']
                    ob_close= df_an.iloc[j]['close']

                    # Check if OB has been mitigated (price re-entered zone)
                    future_data = df_an.iloc[j+1:]
                    mitigated = any(
                        row['low'] <= ob_high and row['high'] >= ob_low
                        for _, row in future_data.iterrows()
                    )

                    # Impulse strength: how strong was the breakout
                    impulse_size = abs(body)
                    strength = min(1.0, impulse_size / (avg_body * 3))

                    # Distance from current price to OB
                    distance = current_price - ob_high  # positive = price above OB
                    distance_pips = round(distance * 10000, 1)  # in pips

                    # FVG (Fair Value Gap) Check
                    # Is candle i the center of a bullish FVG? (High of i-1 < Low of i+1)
                    has_fvg = False
                    if i + 1 < n:
                        prev_high = df_an.iloc[i-1]['high']
                        next_low  = df_an.iloc[i+1]['low']
                        if prev_high < next_low:
                            has_fvg = True
                            # Boost strength if FVG exists
                            strength = min(1.0, strength * 1.5)

                    bullish_obs.append({
                        "zone_high":     round(ob_high, 5),
                        "zone_low":      round(ob_low, 5),
                        "ob_open":       round(ob_open, 5),
                        "ob_close":      round(ob_close, 5),
                        "formed_at_idx": j,
                        "strength":      round(strength, 2),
                        "mitigated":     mitigated,
                        "distance_pips": distance_pips,
                        "has_fvg":       has_fvg,
                        "type":          "bullish_ob"
                    })
                    break  # Only last bearish candle before impulse

        # ── Bearish OB: Find last bullish candle before bearish impulse ──
        elif is_bear and abs(body) > avg_body * min_move_multiplier:
            # Search backward for last bullish candle
            for j in range(i - 1, max(i - 6, 0), -1):
                prev_body = df_an.iloc[j]['close'] - df_an.iloc[j]['open']
                if prev_body > 0:  # Bullish candle found
                    ob_high = df_an.iloc[j]['high']
                    ob_low  = df_an.iloc[j]['low']
                    ob_open = df_an.iloc[j]['open']
                    ob_close= df_an.iloc[j]['close']

                    # Check if OB has been mitigated
                    future_data = df_an.iloc[j+1:]
                    mitigated = any(
                        row['low'] <= ob_high and row['high'] >= ob_low
                        for _, row in future_data.iterrows()
                    )

                    impulse_size = abs(body)
                    strength = min(1.0, impulse_size / (avg_body * 3))

                    distance = ob_low - current_price  # positive = price below OB
                    distance_pips = round(distance * 10000, 1)

                    # FVG (Fair Value Gap) Check
                    # Is candle i the center of a bearish FVG? (Low of i-1 > High of i+1)
                    has_fvg = False
                    if i + 1 < n:
                        prev_low  = df_an.iloc[i-1]['low']
                        next_high = df_an.iloc[i+1]['high']
                        if prev_low > next_high:
                            has_fvg = True
                            # Boost strength if FVG exists
                            strength = min(1.0, strength * 1.5)

                    bearish_obs.append({
                        "zone_high":     round(ob_high, 5),
                        "zone_low":      round(ob_low, 5),
                        "ob_open":       round(ob_open, 5),
                        "ob_close":      round(ob_close, 5),
                        "formed_at_idx": j,
                        "strength":      round(strength, 2),
                        "mitigated":     mitigated,
                        "distance_pips": distance_pips,
                        "has_fvg":       has_fvg,
                        "type":          "bearish_ob"
                    })
                    break

    # Filter: prefer un-mitigated OBs, especially those with FVGs
    def best_obs(obs_list, direction):
        fresh = [ob for ob in obs_list if not ob['mitigated']]
        if not fresh:
            fresh = obs_list
            
        # Strongly prioritize OBs with an FVG
        fvg_obs = [ob for ob in fresh if ob.get('has_fvg')]
        if fvg_obs:
            fresh = fvg_obs

        if direction == 'bull':
            valid = [ob for ob in fresh if ob['zone_high'] < current_price]
            return sorted(valid, key=lambda x: current_price - x['zone_high'])[:3]
        else:
            valid = [ob for ob in fresh if ob['zone_low'] > current_price]
            return sorted(valid, key=lambda x: x['zone_low'] - current_price)[:3]

    return {
        "bullish_ob": best_obs(bullish_obs, 'bull'),
        "bearish_ob": best_obs(bearish_obs, 'bear'),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 3. LIQUIDITY ZONES (Swing High/Low clusters = Stop hunt targets)
# ─────────────────────────────────────────────────────────────────────────────

def find_liquidity_zones(df, lookback=168, touch_threshold=2):
    """
    Find liquidity zones: price levels where many stops are likely clustered.

    These are areas where price has:
    - Multiple swing highs at similar levels (buy-stop liquidity above)
    - Multiple swing lows at similar levels (sell-stop liquidity below)

    Institutions sweep these levels to fill large orders.

    Args:
        df: OHLCV DataFrame
        lookback: Number of candles
        touch_threshold: Min swing touches to form a zone

    Returns:
        dict:
            'above_price': [{'level', 'zone_high', 'zone_low', 'touches', 'strength'}]
            'below_price': [{'level', 'zone_high', 'zone_low', 'touches', 'strength'}]
    """
    if len(df) < 10:
        return {"above_price": [], "below_price": []}

    df_an = df.iloc[-lookback:].copy().reset_index(drop=True)
    current_price = df_an['close'].iloc[-1]

    # Get all swing levels
    swings = find_swing_levels(df_an, lookback=len(df_an), swing_strength=2)

    # Price range for clustering
    price_range = df_an['high'].max() - df_an['low'].min()
    if price_range == 0:
        return {"above_price": [], "below_price": []}

    # Cluster tolerance: 0.1% of price (≈10 pips for EURUSD)
    cluster_tol = current_price * 0.001

    # Cluster swing highs → buy-stop pools above price
    def cluster_levels(levels, tol):
        if not levels:
            return []
        sorted_levels = sorted(levels, key=lambda x: x['price'])
        clusters = []
        current_cluster = [sorted_levels[0]]

        for level in sorted_levels[1:]:
            if level['price'] - current_cluster[-1]['price'] <= tol:
                current_cluster.append(level)
            else:
                clusters.append(current_cluster)
                current_cluster = [level]
        clusters.append(current_cluster)

        result = []
        for cluster in clusters:
            if len(cluster) >= touch_threshold:
                prices = [c['price'] for c in cluster]
                avg_price = sum(prices) / len(prices)
                touches = len(cluster)
                result.append({
                    "level":     round(avg_price, 5),
                    "zone_high": round(max(prices) + cluster_tol, 5),
                    "zone_low":  round(min(prices) - cluster_tol, 5),
                    "touches":   touches,
                    "strength":  min(1.0, touches / 5.0)
                })
        return result

    high_clusters = cluster_levels(swings['highs'], cluster_tol)
    low_clusters  = cluster_levels(swings['lows'],  cluster_tol)

    # Also add single strong swing highs/lows if they're prominent
    # (even 1-touch levels matter if they're recent)
    if swings['highs']:
        most_recent_high = max(swings['highs'], key=lambda x: x['idx'])
        if most_recent_high['price'] > current_price:
            if not any(abs(z['level'] - most_recent_high['price']) < cluster_tol
                       for z in high_clusters):
                high_clusters.append({
                    "level":     round(most_recent_high['price'], 5),
                    "zone_high": round(most_recent_high['price'] + cluster_tol, 5),
                    "zone_low":  round(most_recent_high['price'] - cluster_tol, 5),
                    "touches":   1,
                    "strength":  0.3
                })

    if swings['lows']:
        most_recent_low = min(swings['lows'], key=lambda x: x['price'])
        if most_recent_low['price'] < current_price:
            if not any(abs(z['level'] - most_recent_low['price']) < cluster_tol
                       for z in low_clusters):
                low_clusters.append({
                    "level":     round(most_recent_low['price'], 5),
                    "zone_high": round(most_recent_low['price'] + cluster_tol, 5),
                    "zone_low":  round(most_recent_low['price'] - cluster_tol, 5),
                    "touches":   1,
                    "strength":  0.3
                })

    above = sorted(
        [z for z in high_clusters if z['level'] > current_price],
        key=lambda x: x['level']
    )
    below = sorted(
        [z for z in low_clusters if z['level'] < current_price],
        key=lambda x: x['level'], reverse=True
    )

    return {
        "above_price": above[:4],
        "below_price": below[:4],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 4. LIQUIDITY SWEEP DETECTION
# ─────────────────────────────────────────────────────────────────────────────

def check_liquidity_sweep(df, direction, lookback=50):
    """
    Detect if price recently SWEPT liquidity and reversed — the key SMC entry signal.

    A sweep happens when:
    - Price briefly breaks a swing high/low (triggering stops)
    - Then quickly reverses back (institutions collected their fill)
    - Confirmation: candle closes BACK inside the range (wick beyond level)

    This is the MOST reliable SMC entry signal:
    Price dips below swing low → wicks below → candle closes above → LONG signal

    Args:
        df: OHLCV DataFrame
        direction: "LONG" (swept lows) or "SHORT" (swept highs)
        lookback: Recent candles to check for sweep

    Returns:
        dict:
            'swept': bool — was a sweep detected?
            'sweep_level': float — price level that was swept
            'candles_ago': int — how many candles ago
            'strength': float 0-1 — strength of the sweep signal
    """
    if len(df) < 10:
        return {"swept": False, "sweep_level": None, "candles_ago": None, "strength": 0}

    df_an = df.iloc[-lookback:].copy().reset_index(drop=True)
    n = len(df_an)

    # Get swing levels from a longer lookback for reference
    swings = find_swing_levels(df, lookback=min(len(df), 168), swing_strength=2)

    if direction == "LONG":
        # We want to see: wick below swing low + close above it
        if not swings['lows']:
            return {"swept": False, "sweep_level": None, "candles_ago": None, "strength": 0}

        # Check last 5 candles for a sweep
        for i in range(max(0, n - 5), n):
            candle = df_an.iloc[i]
            candle_low   = candle['low']
            candle_close = candle['close']
            candle_open  = candle['open']

            for swing in swings['lows']:
                level = swing['price']
                # Price wicked below the swing low but closed above it
                if candle_low < level and candle_close > level:
                    # Confirm bullish close (close > open)
                    if candle_close > candle_open:
                        wick_size = level - candle_low
                        body_size = abs(candle_close - candle_open)
                        # Wick should be noticeable
                        if wick_size > 0:
                            strength = min(1.0, wick_size / (body_size + wick_size + 1e-10))
                            return {
                                "swept":       True,
                                "sweep_level": round(level, 5),
                                "candles_ago": n - 1 - i,
                                "strength":    round(strength, 2)
                            }

    elif direction == "SHORT":
        # We want to see: wick above swing high + close below it
        if not swings['highs']:
            return {"swept": False, "sweep_level": None, "candles_ago": None, "strength": 0}

        for i in range(max(0, n - 5), n):
            candle = df_an.iloc[i]
            candle_high  = candle['high']
            candle_close = candle['close']
            candle_open  = candle['open']

            for swing in swings['highs']:
                level = swing['price']
                # Price wicked above the swing high but closed below it
                if candle_high > level and candle_close < level:
                    # Confirm bearish close (close < open)
                    if candle_close < candle_open:
                        wick_size = candle_high - level
                        body_size = abs(candle_close - candle_open)
                        if wick_size > 0:
                            strength = min(1.0, wick_size / (body_size + wick_size + 1e-10))
                            return {
                                "swept":       True,
                                "sweep_level": round(level, 5),
                                "candles_ago": n - 1 - i,
                                "strength":    round(strength, 2)
                            }

    return {"swept": False, "sweep_level": None, "candles_ago": None, "strength": 0}


# ─────────────────────────────────────────────────────────────────────────────
# 5. MARKET STRUCTURE SHIFT (MSS)
# ─────────────────────────────────────────────────────────────────────────────

def detect_mss(df, direction, lookback=50):
    """
    Detect Market Structure Shift — price breaks a prior swing in the
    intended direction, confirming trend change.

    Bullish MSS: Price breaks above a recent swing high (Higher High formed)
    Bearish MSS: Price breaks below a recent swing low (Lower Low formed)

    This confirms the sweep was genuine and price is ready to move.

    Args:
        df: OHLCV DataFrame
        direction: "LONG" or "SHORT"
        lookback: Candles to analyze

    Returns:
        dict:
            'confirmed': bool
            'break_level': float (the level that was broken)
            'candles_ago': int
    """
    if len(df) < 10:
        return {"confirmed": False, "break_level": None, "candles_ago": None}

    df_an = df.iloc[-lookback:].copy().reset_index(drop=True)
    n = len(df_an)

    # Find swing levels in the first half of the lookback period
    mid = n // 2
    if mid < 5:
        return {"confirmed": False, "break_level": None, "candles_ago": None}

    df_past = df_an.iloc[:mid]
    swings_past = find_swing_levels(df_past, lookback=mid, swing_strength=2)

    current_close = df_an['close'].iloc[-1]

    if direction == "LONG":
        # Bullish MSS: recent close broke above a past swing high
        if not swings_past['highs']:
            return {"confirmed": False, "break_level": None, "candles_ago": None}

        for i in range(mid, n):
            close = df_an.iloc[i]['close']
            for swing in swings_past['highs']:
                if close > swing['price']:
                    return {
                        "confirmed":   True,
                        "break_level": round(swing['price'], 5),
                        "candles_ago": n - 1 - i
                    }

    elif direction == "SHORT":
        # Bearish MSS: recent close broke below a past swing low
        if not swings_past['lows']:
            return {"confirmed": False, "break_level": None, "candles_ago": None}

        for i in range(mid, n):
            close = df_an.iloc[i]['close']
            for swing in swings_past['lows']:
                if close < swing['price']:
                    return {
                        "confirmed":   True,
                        "break_level": round(swing['price'], 5),
                        "candles_ago": n - 1 - i
                    }

    return {"confirmed": False, "break_level": None, "candles_ago": None}


# ─────────────────────────────────────────────────────────────────────────────
# 6. SL/TP CALCULATION BASED ON ORDER BLOCKS
# ─────────────────────────────────────────────────────────────────────────────

def calculate_ob_sl_tp(entry_price, direction, order_blocks, liquidity_zones,
                        atr_value=None, min_rr=1.5):
    """
    Calculate precise SL and TP levels using Order Block and Liquidity zones.

    SL Logic:
        LONG:  SL = just below the nearest Bullish OB zone_low
               (If no OB: use 1.5× ATR below entry)
        SHORT: SL = just above the nearest Bearish OB zone_high
               (If no OB: use 1.5× ATR above entry)

    TP Logic:
        TP1 = nearest liquidity zone in target direction (1:1 to 1:2 RR)
        TP2 = second liquidity zone or 2× SL distance

    Args:
        entry_price: Trade entry price
        direction: "LONG" or "SHORT"
        order_blocks: dict from find_order_blocks()
        liquidity_zones: dict from find_liquidity_zones()
        atr_value: ATR for fallback calculations
        min_rr: Minimum risk:reward ratio required

    Returns:
        dict:
            'sl': Stop loss price
            'tp1': Take profit 1 (partial close)
            'tp2': Take profit 2 (final target)
            'sl_distance': Distance in price units
            'tp1_distance': Distance in price units
            'risk_reward': TP1/SL distance ratio
            'ob_used': bool — was an OB used for SL?
            'liq_used': bool — was liquidity zone used for TP?
            'valid': bool — is this a valid setup (meets min RR)?
    """
    # ATR fallback
    atr = atr_value if atr_value else (entry_price * 0.002)  # 0.2% fallback
    buffer = atr * 0.1  # Small buffer below/above OB

    sl_price    = None
    tp1_price   = None
    tp2_price   = None
    ob_used     = False
    liq_used    = False

    if direction == "LONG":
        # ── SL: Below the best Bullish OB ──
        bullish_obs = order_blocks.get("bullish_ob", [])
        if bullish_obs:
            # Use closest OB (first in list, already sorted by proximity)
            best_ob = bullish_obs[0]
            sl_price = round(best_ob["zone_low"] - buffer, 5)
            ob_used = True
            logger.debug(f"SL from Bullish OB: {best_ob['zone_low']:.5f} → SL={sl_price:.5f}")
        else:
            # Fallback: 1.5× ATR below entry
            sl_price = round(entry_price - atr * 1.5, 5)
            logger.debug(f"SL from ATR fallback: {sl_price:.5f}")

        sl_distance = entry_price - sl_price

        # ── TP: Next liquidity zone above ──
        liq_above = liquidity_zones.get("above_price", [])
        if liq_above:
            tp1_price = round(liq_above[0]["level"], 5)
            liq_used = True
            if len(liq_above) > 1:
                tp2_price = round(liq_above[1]["level"], 5)
            else:
                tp2_price = round(entry_price + sl_distance * 2.0, 5)
            logger.debug(f"TP1 from liquidity: {tp1_price:.5f}")
        else:
            tp1_price = round(entry_price + sl_distance * 1.5, 5)
            tp2_price = round(entry_price + sl_distance * 2.5, 5)

    else:  # SHORT
        # ── SL: Above the best Bearish OB ──
        bearish_obs = order_blocks.get("bearish_ob", [])
        if bearish_obs:
            best_ob = bearish_obs[0]
            sl_price = round(best_ob["zone_high"] + buffer, 5)
            ob_used = True
            logger.debug(f"SL from Bearish OB: {best_ob['zone_high']:.5f} → SL={sl_price:.5f}")
        else:
            sl_price = round(entry_price + atr * 1.5, 5)
            logger.debug(f"SL from ATR fallback: {sl_price:.5f}")

        sl_distance = sl_price - entry_price

        # ── TP: Next liquidity zone below ──
        liq_below = liquidity_zones.get("below_price", [])
        if liq_below:
            tp1_price = round(liq_below[0]["level"], 5)
            liq_used = True
            if len(liq_below) > 1:
                tp2_price = round(liq_below[1]["level"], 5)
            else:
                tp2_price = round(entry_price - sl_distance * 2.0, 5)
            logger.debug(f"TP1 from liquidity: {tp1_price:.5f}")
        else:
            tp1_price = round(entry_price - sl_distance * 1.5, 5)
            tp2_price = round(entry_price - sl_distance * 2.5, 5)

    # Calculate actual distances
    if direction == "LONG":
        sl_distance  = round(entry_price - sl_price, 5)
        tp1_distance = round(tp1_price - entry_price, 5)
        tp2_distance = round(tp2_price - entry_price, 5)
    else:
        sl_distance  = round(sl_price - entry_price, 5)
        tp1_distance = round(entry_price - tp1_price, 5)
        tp2_distance = round(entry_price - tp2_price, 5)

    # Validate: TP must be in the right direction
    sl_distance  = max(sl_distance,  atr * 0.5)
    tp1_distance = max(tp1_distance, sl_distance * min_rr)
    tp2_distance = max(tp2_distance, sl_distance * (min_rr + 0.5))

    risk_reward = round(tp1_distance / sl_distance, 2) if sl_distance > 0 else 0

    # Recalculate final prices with validated distances
    if direction == "LONG":
        sl_price  = round(entry_price - sl_distance,  5)
        tp1_price = round(entry_price + tp1_distance, 5)
        tp2_price = round(entry_price + tp2_distance, 5)
    else:
        sl_price  = round(entry_price + sl_distance,  5)
        tp1_price = round(entry_price - tp1_distance, 5)
        tp2_price = round(entry_price - tp2_distance, 5)

    is_valid = risk_reward >= min_rr

    return {
        "sl":           sl_price,
        "tp1":          tp1_price,
        "tp2":          tp2_price,
        "sl_distance":  sl_distance,
        "tp1_distance": tp1_distance,
        "tp2_distance": tp2_distance,
        "risk_reward":  risk_reward,
        "ob_used":      ob_used,
        "liq_used":     liq_used,
        "valid":        is_valid,
    }


# ─────────────────────────────────────────────────────────────────────────────
# 7. ROAD MAP — Market Overview (Treyder'in "haritası")
# ─────────────────────────────────────────────────────────────────────────────

def build_market_map(df, lookback=168):
    """
    Build a full market map — what an experienced trader sees at a glance.

    Returns a structured view of:
    - Key resistance levels above (where price might struggle)
    - Key support levels below (where price might bounce)
    - Order blocks (institutional zones)
    - Current bias (bullish / bearish / neutral)

    This is the "xəritə" (map) concept — before entering, know the landscape.

    Args:
        df: OHLCV DataFrame
        lookback: Number of candles to analyze

    Returns:
        dict with market overview
    """
    if len(df) < 20:
        return {"bias": "NEUTRAL", "key_levels": [], "order_blocks": {}, "liquidity": {}}

    df_an = df.iloc[-lookback:].copy().reset_index(drop=True)
    current_price = df_an['close'].iloc[-1]

    swings    = find_swing_levels(df_an, lookback=len(df_an))
    obs       = find_order_blocks(df_an, lookback=len(df_an))
    liquidity = find_liquidity_zones(df_an, lookback=len(df_an))

    # Determine bias: more structure above = bearish, more below = bullish
    highs_above = [h for h in swings['highs'] if h['price'] > current_price]
    lows_below  = [l for l in swings['lows']  if l['price'] < current_price]

    # Recent trend: compare first and last portion
    if len(df_an) > 20:
        first_close = df_an['close'].iloc[:10].mean()
        last_close  = df_an['close'].iloc[-10:].mean()
        if last_close > first_close * 1.001:
            bias = "BULLISH"
        elif last_close < first_close * 0.999:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"
    else:
        bias = "NEUTRAL"

    # Build key levels list for display
    key_levels = []
    for z in liquidity['above_price']:
        key_levels.append({
            "level": z['level'],
            "type": "RESISTANCE",
            "touches": z['touches'],
            "strength": z['strength'],
            "above_current": True
        })
    for z in liquidity['below_price']:
        key_levels.append({
            "level": z['level'],
            "type": "SUPPORT",
            "touches": z['touches'],
            "strength": z['strength'],
            "above_current": False
        })

    # Sort by distance from current price
    key_levels = sorted(key_levels, key=lambda x: abs(x['level'] - current_price))

    return {
        "current_price": round(current_price, 5),
        "bias":          bias,
        "key_levels":    key_levels[:8],   # Top 8 nearest levels
        "order_blocks":  obs,
        "liquidity":     liquidity,
        "swing_highs":   [h['price'] for h in highs_above[:3]],
        "swing_lows":    [l['price'] for l in lows_below[:3]],
    }


# ─────────────────────────────────────────────────────────────────────────────
# 8. MAIN ANALYSIS FUNCTION (Used by scorer.py)
# ─────────────────────────────────────────────────────────────────────────────

def analyze_market_structure(df, direction, atr_value=None, lookback=168):
    """
    Full SMC analysis for trade entry confirmation.

    Pipeline:
        1. Find swing levels (liquidity pools)
        2. Find Order Blocks (institutional zones)
        3. Find liquidity zones (stop clusters)
        4. Check for liquidity sweep (key entry trigger)
        5. Check MSS (market structure shift)
        6. Calculate OB-based SL/TP
        7. Score entry strength

    Args:
        df: OHLCV DataFrame (H1 recommended)
        direction: "LONG" or "SHORT"
        atr_value: Current ATR value (for fallback SL sizing)
        lookback: Candles to analyze (default 168 = 7 days H1)

    Returns:
        dict:
            swing_levels:   Swing highs/lows
            order_blocks:   Bullish/Bearish OBs
            liquidity_zones: Above/below price zones
            liquidity_sweep: Sweep detection result
            mss:            Market structure shift
            sl_tp:          Calculated SL/TP levels
            entry_strength: 0.0 to 1.0 score
            recommendation: "STRONG_BUY"|"BUY"|"NEUTRAL"|"WEAK"
            current_price:  Latest close
    """
    swings    = find_swing_levels(df, lookback)
    obs       = find_order_blocks(df, lookback)
    liquidity = find_liquidity_zones(df, lookback)
    sweep     = check_liquidity_sweep(df, direction, lookback=min(50, lookback))
    mss       = detect_mss(df, direction, lookback=min(50, lookback))

    current_price = df['close'].iloc[-1]

    # Calculate SL/TP using OB + Liquidity
    entry_price = current_price
    sl_tp = calculate_ob_sl_tp(
        entry_price=entry_price,
        direction=direction,
        order_blocks=obs,
        liquidity_zones=liquidity,
        atr_value=atr_value,
        min_rr=1.5
    )

    # ── Entry Strength Scoring ──
    strength = 0.0

    # Order Block present and valid
    if direction == "LONG":
        if obs.get("bullish_ob"):
            best_ob = obs["bullish_ob"][0]
            ob_score = best_ob["strength"] * 0.35
            strength += ob_score
            # Extra bonus if price is near the OB (returning to it)
            if best_ob["distance_pips"] < 20:
                strength += 0.1
    else:
        if obs.get("bearish_ob"):
            best_ob = obs["bearish_ob"][0]
            ob_score = best_ob["strength"] * 0.35
            strength += ob_score
            if best_ob["distance_pips"] < 20:
                strength += 0.1

    # Liquidity sweep (most important SMC signal)
    if sweep["swept"]:
        strength += 0.30
        # Recency bonus: sweep in last 1-2 candles is stronger
        if sweep.get("candles_ago") is not None and sweep["candles_ago"] <= 2:
            strength += 0.05

    # MSS confirmation
    if mss["confirmed"]:
        strength += 0.20

    # Good Risk:Reward ratio
    if sl_tp.get("risk_reward", 0) >= 2.0:
        strength += 0.10
    elif sl_tp.get("risk_reward", 0) >= 1.5:
        strength += 0.05

    # Liquidity zone as TP target exists
    if sl_tp.get("liq_used"):
        strength += 0.05

    strength = round(min(1.0, strength), 2)

    # Recommendation thresholds
    if strength >= 0.75:
        recommendation = "STRONG_BUY" if direction == "LONG" else "STRONG_SELL"
    elif strength >= 0.55:
        recommendation = "BUY" if direction == "LONG" else "SELL"
    elif strength >= 0.35:
        recommendation = "NEUTRAL"
    else:
        recommendation = "WEAK"

    logger.debug(
        f"SMC Analysis [{direction}]: OB={'✓' if obs.get(direction.lower()[:4]+'ish_ob') else '✗'} "
        f"| Sweep={'✓' if sweep['swept'] else '✗'} "
        f"| MSS={'✓' if mss['confirmed'] else '✗'} "
        f"| RR={sl_tp.get('risk_reward', 0)} "
        f"| Strength={strength} → {recommendation}"
    )

    return {
        "swing_levels":    swings,
        "order_blocks":    obs,
        "liquidity_zones": liquidity,
        "liquidity_sweep": sweep,
        "mss":             mss,
        "sl_tp":           sl_tp,
        "entry_strength":  strength,
        "recommendation":  recommendation,
        "current_price":   round(current_price, 5),
    }
