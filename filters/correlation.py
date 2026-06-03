"""
filters/correlation.py — Correlation blocking rules.

Prevents opening trades on correlated instruments when one of them
already has an open position, to avoid overexposure.
"""

import logging

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger(__name__)


def is_correlated_blocked(symbol, open_positions):
    """
    Check if a trade on `symbol` should be blocked due to correlation rules.

    Rules:
        1. Maximum 1 open trade per instrument at any time.
        2. No duplicate trades (same instrument + same direction).
        3. If a correlated instrument has an open trade, block.

    Args:
        symbol: Instrument symbol to check (e.g., "EURUSD")
        open_positions: List of dicts with at least {"symbol": str, "direction": str}
                        representing currently open positions.

    Returns:
        (blocked: bool, reason: str)
    """
    # Extract symbols from open positions
    open_symbols = set()
    open_position_map = {}  # symbol → list of directions

    for pos in open_positions:
        pos_symbol = pos.get("symbol", "")
        pos_direction = pos.get("direction", "")
        open_symbols.add(pos_symbol)

        if pos_symbol not in open_position_map:
            open_position_map[pos_symbol] = []
        open_position_map[pos_symbol].append(pos_direction)

    # Rule 1: Max open trades per symbol
    max_for_symbol = getattr(config, 'MAX_OPEN_TRADES_PER_SYMBOL', {}).get(symbol, 1)
    current_symbol_count = sum(1 for pos in open_positions if pos.get("symbol") == symbol)
    if current_symbol_count >= max_for_symbol:
        return True, f"Already reached max open positions ({max_for_symbol}) for {symbol}"

    # Rule 3: Check correlated instruments
    correlated = config.CORRELATION_MAP.get(symbol, [])
    for corr_symbol in correlated:
        if corr_symbol in open_symbols:
            return (
                True,
                f"Blocked by correlation: {corr_symbol} has an open trade "
                f"(correlated with {symbol})"
            )

    return False, "No correlation block"


def get_correlated_instruments(symbol):
    """
    Get the list of instruments correlated with the given symbol.

    Args:
        symbol: Instrument symbol

    Returns:
        List of correlated symbol strings.
    """
    return config.CORRELATION_MAP.get(symbol, [])
