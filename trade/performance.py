"""
trade/performance.py — Per-instrument performance tracking.

Monitors the rolling win rate over the last 20 trades per instrument.
If win rate < 45%, pauses trading on the instrument for 48 hours.
If win rate > 60%, multiplies lot size by 1.2.
Generates a daily report of performance metrics.
"""

import os
import csv
import logging
from datetime import datetime, timedelta, timezone

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger(__name__)


class PerformanceTracker:
    def __init__(self):
        self.stats = {}  # symbol -> { "trades": [], "paused_until": None, "win_rate": 0.0 }
        self.last_report_date = None

    def update_trade(self, symbol, pnl):
        """Add a completed trade's PnL to track win rate."""
        if symbol not in self.stats:
            self.stats[symbol] = {
                "trades": [],
                "paused_until": None,
                "win_rate": 0.0,
                "lot_multiplier": 1.0,
            }

        # Keep last 20 trades
        self.stats[symbol]["trades"].append(pnl)
        if len(self.stats[symbol]["trades"]) > 20:
            self.stats[symbol]["trades"].pop(0)

        self._recalculate_stats(symbol)

    def _recalculate_stats(self, symbol):
        """Recalculate win rate and apply rules."""
        trades = self.stats[symbol]["trades"]
        if not trades:
            return

        wins = sum(1 for p in trades if p > 0)
        total = len(trades)
        win_rate = wins / total

        self.stats[symbol]["win_rate"] = win_rate

        # Only apply rules if we have at least 5 trades
        if total >= 5:
            if win_rate < 0.45:
                # Pause for 48 hours
                self.stats[symbol]["paused_until"] = datetime.now(timezone.utc) + timedelta(hours=48)
                self.stats[symbol]["lot_multiplier"] = 1.0
                logger.warning(f"[{symbol}] Win rate {win_rate*100:.1f}% (< 45%). Pausing for 48 hours.")
            elif win_rate > 0.60:
                self.stats[symbol]["lot_multiplier"] = 1.2
                self.stats[symbol]["paused_until"] = None
                logger.info(f"[{symbol}] Win rate {win_rate*100:.1f}% (> 60%). Lot multiplier set to 1.2x.")
            else:
                self.stats[symbol]["lot_multiplier"] = 1.0
                self.stats[symbol]["paused_until"] = None

    def is_paused(self, symbol):
        """Check if trading is paused for this instrument."""
        if symbol not in self.stats:
            return False
            
        paused_until = self.stats[symbol]["paused_until"]
        if paused_until:
            if datetime.now(timezone.utc) < paused_until:
                return True
            else:
                self.stats[symbol]["paused_until"] = None
        return False

    def get_lot_multiplier(self, symbol):
        """Get the dynamic lot multiplier for this instrument."""
        if symbol not in self.stats:
            return 1.0
        return self.stats[symbol].get("lot_multiplier", 1.0)

    def generate_daily_report(self):
        """Generate daily CSV report of performance metrics."""
        current_date = datetime.now(timezone.utc).date()
        if self.last_report_date == current_date:
            return
            
        self.last_report_date = current_date
        os.makedirs(config.LOG_DIR, exist_ok=True)
        report_file = os.path.join(config.LOG_DIR, f"daily_report_{current_date}.csv")
        
        try:
            with open(report_file, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["Symbol", "Trades (Last 20)", "Win Rate", "Multiplier", "Status"])
                for symbol, data in self.stats.items():
                    status = "PAUSED" if self.is_paused(symbol) else "ACTIVE"
                    writer.writerow([
                        symbol,
                        len(data["trades"]),
                        f"{data['win_rate']*100:.1f}%",
                        data["lot_multiplier"],
                        status
                    ])
            logger.info(f"Generated daily performance report: {report_file}")
        except Exception as e:
            logger.error(f"Failed to generate daily report: {e}")
