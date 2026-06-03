"""
data/fetcher.py — OHLCV data download and caching.

Downloads candle data from Capital.com API, converts to pandas DataFrames,
and caches locally as CSV files to avoid redundant API calls.
"""

import os
import logging
import pandas as pd
from datetime import datetime, timedelta, timezone

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger(__name__)

# Cache directory
CACHE_DIR = os.path.join(os.path.dirname(__file__), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)


def _resolution_to_str(resolution):
    """Convert Capital.com resolution to a filename-friendly string."""
    return resolution.replace("_", "").lower()


def _parse_candles(raw_prices):
    """
    Parse Capital.com price response into a pandas DataFrame.

    Capital.com returns candles with bid/ask OHLC.
    We use the mid-price: (bid + ask) / 2.

    Args:
        raw_prices: List of candle dicts from Capital.com API.

    Returns:
        pd.DataFrame with columns: datetime, open, high, low, close, volume
    """
    rows = []
    for candle in raw_prices:
        try:
            dt = candle["snapshotTime"]  # ISO format string
            bid = candle.get("openPrice", candle.get("bidPrice", {}))
            ask = candle.get("closePrice", candle.get("askPrice", {}))

            # Capital.com format: each price level has bid/ask sub-objects
            if "openPrice" in candle and isinstance(candle["openPrice"], dict):
                o = (candle["openPrice"]["bid"] + candle["openPrice"]["ask"]) / 2
                h = (candle["highPrice"]["bid"] + candle["highPrice"]["ask"]) / 2
                l = (candle["lowPrice"]["bid"] + candle["lowPrice"]["ask"]) / 2
                c = (candle["closePrice"]["bid"] + candle["closePrice"]["ask"]) / 2
            else:
                # Flat format fallback
                o = float(candle.get("openPrice", 0))
                h = float(candle.get("highPrice", 0))
                l = float(candle.get("lowPrice", 0))
                c = float(candle.get("closePrice", 0))

            v = float(candle.get("lastTradedVolume", 0))

            rows.append({
                "datetime": pd.to_datetime(dt),
                "open": o,
                "high": h,
                "low": l,
                "close": c,
                "volume": v,
            })
        except (KeyError, TypeError, ValueError) as e:
            logger.warning(f"Skipping malformed candle: {e}")
            continue

    if not rows:
        return pd.DataFrame(columns=["datetime", "open", "high", "low", "close", "volume"])

    df = pd.DataFrame(rows)
    df.sort_values("datetime", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def fetch_ohlcv(api, epic, resolution="HOUR", bars=300):
    """
    Fetch recent OHLCV data for an instrument.

    Args:
        api: CapitalAPI instance
        epic: Instrument epic (e.g., "EURUSD")
        resolution: "HOUR" for H1, "HOUR_4" for H4
        bars: Number of candles

    Returns:
        pd.DataFrame with columns: datetime, open, high, low, close, volume
    """
    raw = api.get_prices(epic, resolution=resolution, max_bars=bars)
    df = _parse_candles(raw)
    logger.info(f"Fetched {len(df)} {resolution} candles for {epic}")
    return df


def fetch_historical(api, epic, resolution="HOUR", days=365, use_cache=True):
    """
    Download historical OHLCV data with pagination, optionally using cache.

    Capital.com returns max ~1000 candles per request, so we paginate
    by stepping through date ranges.

    Args:
        api: CapitalAPI instance
        epic: Instrument epic
        resolution: "HOUR" or "HOUR_4"
        days: Number of days of history to download
        use_cache: If True, load from CSV cache if available

    Returns:
        pd.DataFrame
    """
    # Check cache first
    cache_file = os.path.join(
        CACHE_DIR,
        f"{epic}_{_resolution_to_str(resolution)}_{days}d.csv"
    )
    if use_cache and os.path.exists(cache_file):
        logger.info(f"Loading cached data: {cache_file}")
        df = pd.read_csv(cache_file, parse_dates=["datetime"])
        return df

    # Calculate date range
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)

    all_candles = []

    # Determine step size based on resolution
    if resolution == "HOUR":
        step_days = 40   # ~960 hourly candles per step
    elif resolution == "HOUR_4":
        step_days = 160  # ~960 4-hour candles per step
    else:
        step_days = 365  # Daily or larger

    current_start = start_date
    while current_start < end_date:
        current_end = min(current_start + timedelta(days=step_days), end_date)

        from_str = current_start.strftime("%Y-%m-%dT%H:%M:%S")
        to_str = current_end.strftime("%Y-%m-%dT%H:%M:%S")

        logger.info(
            f"Downloading {epic} {resolution}: {from_str} to {to_str}"
        )

        raw = api.get_prices_range(epic, resolution, from_str, to_str)
        if raw:
            all_candles.extend(raw)

        current_start = current_end

        # Small delay to respect rate limits
        import time
        time.sleep(0.5)

    df = _parse_candles(all_candles)

    # Remove duplicates (overlapping pagination)
    if not df.empty:
        df.drop_duplicates(subset=["datetime"], inplace=True)
        df.sort_values("datetime", inplace=True)
        df.reset_index(drop=True, inplace=True)

    # Save to cache
    if not df.empty:
        df.to_csv(cache_file, index=False)
        logger.info(f"Cached {len(df)} candles to {cache_file}")

    return df
