"""
trade/risk_manager.py — Account-level risk and dynamic sizing.

Tracks daily/weekly PnL and manages position sizing based on account equity,
ATR, and maximum drawdown limits.
"""

import logging
from datetime import datetime, timezone
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger(__name__)


class RiskManager:
    """Manages risk limits and dynamic position sizing."""

    def __init__(self, api_or_engine=None):
        self.api = api_or_engine
        
        # State tracking
        self.initial_capital = config.STARTING_CAPITAL
        self.current_capital = self.initial_capital
        self.peak_capital = self.initial_capital
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        
        # Tracking dates to reset daily/weekly PnL
        self.last_day = None
        self.last_week = None
        
        # New protections
        self.consecutive_losses = 0
        self.pause_until = None

    def update_capital(self, new_capital, current_time=None):
        """Update current capital and reset daily/weekly if necessary."""
        if current_time is None:
            current_time = datetime.now(timezone.utc)
            
        current_day = current_time.date()
        current_week = current_time.isocalendar()[1]
        
        # Reset trackers on new day/week
        if self.last_day != current_day:
            self.daily_pnl = 0.0
            self.last_day = current_day
            
        if self.last_week != current_week:
            self.weekly_pnl = 0.0
            self.last_week = current_week

        # Track PnL change
        pnl_change = new_capital - self.current_capital
        self.daily_pnl += pnl_change
        self.weekly_pnl += pnl_change
        
        self.current_capital = new_capital
        if self.current_capital > self.peak_capital:
            self.peak_capital = self.current_capital

    def is_trading_allowed(self, open_trades_count, market_class_count, current_time=None):
        """Check if we are allowed to open new trades based on risk limits."""
        # 1. Check max open trades
        if open_trades_count >= config.MAX_OPEN_TRADES:
            return False, "Max open trades reached"
            
        if market_class_count >= config.MAX_OPEN_TRADES_PER_CLASS:
            return False, "Max open trades for this market class reached"

        # 2. Check daily loss limit
        daily_loss_limit = self.initial_capital * config.DAILY_LOSS_LIMIT_PCT
        if self.daily_pnl <= daily_loss_limit:
            return False, "Daily loss limit reached"

        # 3. Check weekly loss limit
        weekly_loss_limit = self.initial_capital * config.WEEKLY_LOSS_LIMIT_PCT
        if self.weekly_pnl <= weekly_loss_limit:
            return False, "Weekly loss limit reached"

        # 4. Daily hard loss limit ($200)
        daily_hard_limit = getattr(config, 'DAILY_HARD_LOSS_LIMIT', 200.0)
        if self.daily_pnl <= -daily_hard_limit:
            return False, f"Daily hard loss limit (${daily_hard_limit}) reached"

        # Check hard stop capital
        if self.current_capital < config.HARD_STOP_CAPITAL:
            return False, "Capital below $800 hard stop"

        # Check pause
        if current_time and self.pause_until and current_time < self.pause_until:
            return False, f"Trading paused until {self.pause_until}"

        return True, "Trading allowed"

    def register_trade_result(self, pnl, current_time):
        """Update consecutive losses and pause logic based on trade outcome."""
        if pnl < 0:
            self.consecutive_losses += 1
            if self.consecutive_losses >= 3:
                # Pause for 4 hours
                from datetime import timedelta
                self.pause_until = current_time + timedelta(hours=config.CONSECUTIVE_LOSS_PAUSE_HOURS)
                self.consecutive_losses = 0
                logger.info(f"3 consecutive losses. Pausing trading until {self.pause_until}")
        else:
            self.consecutive_losses = 0

    def calculate_lot_size(self, symbol, atr_value=None):
        """
        Calculate lot size. Uses config.FULL_LOT_SIZE (fixed lot) if defined,
        otherwise falls back to dynamic sizing (6% of current capital).
        """
        if getattr(config, 'FULL_LOT_SIZE', None) is not None:
            lot_size = config.FULL_LOT_SIZE
        else:
            base_pct = 0.06
            lot_size = self.current_capital * base_pct
            
            if symbol in config.HIGH_VOL_INSTRUMENTS:
                lot_size = self.current_capital * (base_pct / 2.0)
                
            # Check drawdown protection
            drawdown = (self.peak_capital - self.current_capital) / self.peak_capital
            if drawdown >= abs(config.DRAWDOWN_PROTECTION_PCT):
                lot_size = lot_size * 0.5
                logger.info(f"Drawdown protection active: lot size reduced to ${lot_size:.2f}")
            
        return max(1.0, round(lot_size, 2))
