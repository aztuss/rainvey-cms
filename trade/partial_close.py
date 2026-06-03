"""
trade/partial_close.py — Partial close and break-even management.

Monitors open trades for TP1 hits and manages the transition:
  1. Sub-order A (40%) closes at TP1
  2. Sub-order B (60%) SL moves to break-even (entry price)
  3. Sub-order B runs to TP2 or gets stopped at break-even
"""

import logging
from datetime import datetime, timezone

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logger = logging.getLogger(__name__)


class PartialCloseManager:
    """
    Manages partial close logic for all open trades.

    Works in tandem with TradeManager — this class provides the
    monitoring loop that detects TP1 hits and triggers break-even moves.
    """

    def __init__(self, trade_manager):
        """
        Args:
            trade_manager: TradeManager instance
        """
        self.trade_manager = trade_manager

    def check_and_manage(self):
        """
        Run the partial close check for all open trades.

        This should be called on each cycle (every H1 candle close).
        It syncs with the broker to detect which sub-orders are still alive
        and manages the TP1 → break-even transition.
        """
        # Sync positions with broker to detect SL/TP hits
        self.trade_manager.sync_positions()

        # Log status of remaining open trades
        for symbol, trade_info in self.trade_manager.open_trades.items():
            status_parts = [f"[{symbol}]"]

            if trade_info["tp1_hit"]:
                status_parts.append("TP1 ✓")
                if trade_info["breakeven_set"]:
                    status_parts.append("BE ✓")
                else:
                    status_parts.append("BE pending")
            else:
                status_parts.append("Waiting for TP1")

            logger.debug(" | ".join(status_parts))

    def get_trade_status(self, symbol):
        """
        Get the current status of a trade.

        Args:
            symbol: Instrument symbol

        Returns:
            Dict with status details or None if no trade found.
        """
        trade_info = self.trade_manager.open_trades.get(symbol)
        if trade_info is None:
            return None

        return {
            "symbol": symbol,
            "direction": trade_info["direction"],
            "entry_price": trade_info["entry_price"],
            "sl": trade_info["sl"],
            "tp1": trade_info["tp1"],
            "tp2": trade_info["tp2"],
            "tp1_hit": trade_info["tp1_hit"],
            "breakeven_set": trade_info["breakeven_set"],
            "opened_at": trade_info["opened_at"],
            "lot_a": trade_info["lot_a"],
            "lot_b": trade_info["lot_b"],
        }

    def get_all_statuses(self):
        """Get status for all open trades."""
        statuses = []
        for symbol in self.trade_manager.open_trades:
            status = self.get_trade_status(symbol)
            if status:
                statuses.append(status)
        return statuses
