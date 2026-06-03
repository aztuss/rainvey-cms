"""
trade/manager.py — Trade execution and management.

Handles opening trades (split into two sub-orders for partial close),
calculating SL/TP levels, and monitoring open positions.
"""

import os
import csv
import logging
from datetime import datetime, timezone

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import config

logger = logging.getLogger(__name__)


class TradeManager:
    """
    Manages trade execution, position tracking, and CSV logging.

    Each trade is split into two sub-orders:
        - Sub-order A: 40% of lot → TP1 (1×SL distance)
        - Sub-order B: 60% of lot → TP2 (2×SL distance)

    After sub-order A hits TP1, sub-order B's SL moves to break-even.
    """

    def __init__(self, api, risk_manager=None, performance_tracker=None):
        """
        Args:
            api: CapitalAPI instance for executing trades.
        """
        self.api = api
        self.risk_manager = risk_manager
        self.performance_tracker = performance_tracker
        self.open_trades = {}  # symbol → trade_info dict
        self._ensure_log_files()

    def _ensure_log_files(self):
        """Create log directory and CSV headers if they don't exist."""
        os.makedirs(config.LOG_DIR, exist_ok=True)

        # Trades log
        if not os.path.exists(config.TRADE_LOG_FILE):
            with open(config.TRADE_LOG_FILE, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "symbol", "direction", "entry_price",
                    "sl", "tp1", "tp2", "lot_size", "lot_a", "lot_b",
                    "score", "confidence", "status", "pnl",
                    "close_reason", "deal_ref_a", "deal_ref_b", "market_structure",
                ])

        # Signals log
        if not os.path.exists(config.SIGNAL_LOG_FILE):
            with open(config.SIGNAL_LOG_FILE, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "timestamp", "symbol", "direction", "score",
                    "confidence", "action", "skip_reason",
                    "h4_trend", "indicator_details", "market_structure",
                ])

    def log_signal(self, signal_result):
        """
        Log a signal (including skipped ones) to the signals CSV.

        Args:
            signal_result: Dict from scorer.score_instrument()
        """
        try:
            with open(config.SIGNAL_LOG_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now(timezone.utc).isoformat(),
                    signal_result["symbol"],
                    signal_result["direction"],
                    signal_result["score"],
                    signal_result["confidence"],
                    signal_result["action"],
                    signal_result.get("skip_reason", ""),
                    signal_result["h4_trend"],
                    str(signal_result["indicator_details"]),
                    str(signal_result.get("market_structure", {})),  # Add market structure
                ])
        except Exception as e:
            logger.error(f"Failed to log signal: {e}")

    def log_trade(self, trade_info, status="OPEN", pnl=0.0, close_reason=""):
        """
        Log a trade to the trades CSV.

        Args:
            trade_info: Trade info dict
            status: "OPEN", "CLOSED", "PARTIAL"
            pnl: Profit/loss in USD
            close_reason: Why the trade was closed
        """
        try:
            with open(config.TRADE_LOG_FILE, "a", newline="") as f:
                writer = csv.writer(f)
                writer.writerow([
                    datetime.now(timezone.utc).isoformat(),
                    trade_info["symbol"],
                    trade_info["direction"],
                    trade_info.get("entry_price", ""),
                    trade_info.get("sl", ""),
                    trade_info.get("tp1", ""),
                    trade_info.get("tp2", ""),
                    trade_info.get("lot_size", ""),
                    trade_info.get("lot_a", ""),
                    trade_info.get("lot_b", ""),
                    trade_info.get("score", ""),
                    trade_info.get("confidence", ""),
                    status,
                    pnl,
                    close_reason,
                    trade_info.get("deal_ref_a", ""),
                    trade_info.get("deal_ref_b", ""),
                    str(trade_info.get("market_structure", {})),  # Add market structure info
                ])
        except Exception as e:
            logger.error(f"Failed to log trade: {e}")

    def calculate_levels(self, entry_price, direction, atr_value, market_structure=None):
        """
        Calculate SL, TP1, and TP2 price levels using SMC Order Block logic.

        Priority order:
          1. Pre-calculated sl_tp from analyze_market_structure() (OB + Liquidity)
          2. Fallback: ATR-based levels from config

        Args:
            entry_price: Current entry price
            direction: "LONG" or "SHORT"
            atr_value: Current ATR value (for fallback)
            market_structure: Market structure analysis dict from scorer

        Returns:
            (sl, tp1, tp2) tuple of price levels
        """
        # ── Priority 1: Use pre-calculated OB-based levels ──
        if market_structure:
            sl_tp = market_structure.get("sl_tp", {})
            if sl_tp and sl_tp.get("sl") and sl_tp.get("tp1") and sl_tp.get("tp2"):
                sl  = sl_tp["sl"]
                tp1 = sl_tp["tp1"]
                tp2 = sl_tp["tp2"]

                # Sanity check: SL must be on the correct side of entry
                if direction == "LONG" and sl < entry_price and tp1 > entry_price:
                    logger.debug(
                        f"Using OB-based levels: SL={sl} TP1={tp1} TP2={tp2} "
                        f"RR={sl_tp.get('risk_reward', '?')} "
                        f"[OB={'✓' if sl_tp.get('ob_used') else '✗'} "
                        f"Liq={'✓' if sl_tp.get('liq_used') else '✗'}]"
                    )
                    return sl, tp1, tp2

                elif direction == "SHORT" and sl > entry_price and tp1 < entry_price:
                    logger.debug(
                        f"Using OB-based levels: SL={sl} TP1={tp1} TP2={tp2} "
                        f"RR={sl_tp.get('risk_reward', '?')} "
                        f"[OB={'✓' if sl_tp.get('ob_used') else '✗'} "
                        f"Liq={'✓' if sl_tp.get('liq_used') else '✗'}]"
                    )
                    return sl, tp1, tp2
                else:
                    logger.debug("OB-based levels failed sanity check, using ATR fallback")

        # ── Priority 2: ATR-based fallback ──
        if not atr_value or atr_value <= 0:
            atr_value = entry_price * 0.002  # 0.2% emergency fallback

        if getattr(config, 'USE_PERCENTAGE_LEVELS', False):
            sl_distance  = entry_price * config.SL_PCT
            tp1_distance = entry_price * config.TP1_PCT
            tp2_distance = entry_price * config.TP2_PCT
        else:
            sl_distance  = config.SL_ATR_MULTIPLIER  * atr_value
            tp1_distance = config.TP1_ATR_MULTIPLIER * atr_value
            tp2_distance = config.TP2_ATR_MULTIPLIER * atr_value

        if direction == "LONG":
            sl  = round(entry_price - sl_distance,  5)
            tp1 = round(entry_price + tp1_distance, 5)
            tp2 = round(entry_price + tp2_distance, 5)
        else:
            sl  = round(entry_price + sl_distance,  5)
            tp1 = round(entry_price - tp1_distance, 5)
            tp2 = round(entry_price - tp2_distance, 5)

        logger.debug(f"Using ATR fallback levels: SL={sl} TP1={tp1} TP2={tp2}")
        return sl, tp1, tp2

    def open_trade(self, symbol, direction, lot_size, atr_value, entry_price,
                   score=0, confidence=0.0, market_structure=None):
        """
        Open a trade by placing two sub-orders (40%/60% split).

        Args:
            symbol: Instrument symbol
            direction: "LONG" → "BUY", "SHORT" → "SELL"
            lot_size: Total lot size in USD margin
            atr_value: Current ATR for SL/TP calculation
            entry_price: Current price (for level calculation)
            score: Signal score (for logging)
            confidence: Signal confidence % (for logging)
            market_structure: Market structure analysis dict (optional)

        Returns:
            trade_info dict on success, None on failure
        """
        epic = config.INSTRUMENTS[symbol]["epic"]
        api_direction = "BUY" if direction == "LONG" else "SELL"

        # Calculate SL/TP levels (with market structure override)
        sl, tp1, tp2 = self.calculate_levels(entry_price, direction, atr_value, market_structure)

        # Split lot: 40% for TP1, 60% for TP2
        lot_a = round(lot_size * config.TP1_CLOSE_PCT, 2)
        lot_b = round(lot_size * config.TP2_CLOSE_PCT, 2)

        # Ensure minimum lot sizes
        if lot_a < 0.01:
            lot_a = 0.01
        if lot_b < 0.01:
            lot_b = 0.01

        # Calculate position sizes with leverage
        # size = (margin * leverage) / entry_price
        size_a = round((lot_a * config.LEVERAGE) / entry_price, 4)
        size_b = round((lot_b * config.LEVERAGE) / entry_price, 4)

        # Minimum size guard
        if size_a < 0.0001:
            size_a = 0.0001
        if size_b < 0.0001:
            size_b = 0.0001

        logger.info(
            f"Opening trade: {direction} {symbol} | "
            f"Entry={entry_price} SL={sl} TP1={tp1} TP2={tp2} | "
            f"Lot A={lot_a} (size={size_a}), Lot B={lot_b} (size={size_b})"
        )

        # Sub-order A: 40% with TP1
        deal_ref_a = self.api.place_order(
            epic=epic,
            direction=api_direction,
            size=size_a,
            stop_level=sl,
            profit_level=tp1,
        )

        # Sub-order B: 60% with TP2
        deal_ref_b = self.api.place_order(
            epic=epic,
            direction=api_direction,
            size=size_b,
            stop_level=sl,
            profit_level=tp2,
        )

        if deal_ref_a is None and deal_ref_b is None:
            logger.error(f"Failed to open any sub-orders for {symbol}")
            return None

        trade_info = {
            "symbol": symbol,
            "epic": epic,
            "direction": direction,
            "entry_price": entry_price,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "lot_size": lot_size,
            "lot_a": lot_a,
            "lot_b": lot_b,
            "size_a": size_a,
            "size_b": size_b,
            "deal_ref_a": deal_ref_a,
            "deal_ref_b": deal_ref_b,
            "deal_id_a": None,  # Will be resolved from confirmation
            "deal_id_b": None,
            "score": score,
            "confidence": confidence,
            "market_structure": market_structure or {},  # Store market structure
            "tp1_hit": False,
            "breakeven_set": False,
            "atr_at_entry": atr_value,
            "highest_price": entry_price,
            "lowest_price": entry_price,
            "opened_at": datetime.now(timezone.utc).isoformat(),
        }

        # Try to get deal confirmations and extract deal IDs
        if deal_ref_a:
            confirm = self.api.get_deal_confirmation(deal_ref_a)
            if confirm:
                trade_info["deal_id_a"] = confirm.get("dealId")

        if deal_ref_b:
            confirm = self.api.get_deal_confirmation(deal_ref_b)
            if confirm:
                trade_info["deal_id_b"] = confirm.get("dealId")

        # Track the trade
        self.open_trades[symbol] = trade_info

        # Log the trade
        self.log_trade(trade_info, status="OPEN")

        logger.info(
            f"Trade opened successfully: {direction} {symbol} | "
            f"Score={score}/6 ({confidence}%)"
        )
        return trade_info

    def close_trade(self, symbol, reason="Manual close"):
        """
        Close all sub-orders for a trade.

        Args:
            symbol: Instrument symbol
            reason: Close reason for logging

        Returns:
            True if closed successfully
        """
        trade_info = self.open_trades.get(symbol)
        if trade_info is None:
            logger.warning(f"No open trade found for {symbol}")
            return False

        closed = False

        # Close sub-order A
        if trade_info.get("deal_id_a"):
            if self.api.close_position(trade_info["deal_id_a"]):
                closed = True
                logger.info(f"Closed sub-order A for {symbol}")

        # Close sub-order B
        if trade_info.get("deal_id_b"):
            if self.api.close_position(trade_info["deal_id_b"]):
                closed = True
                logger.info(f"Closed sub-order B for {symbol}")

        if closed:
            self.log_trade(trade_info, status="CLOSED", close_reason=reason)
            del self.open_trades[symbol]

        return closed

    def get_open_position_list(self):
        """
        Get a simplified list of open positions for filter checks.

        Returns:
            List of dicts with {"symbol": str, "direction": str}
        """
        positions = []
        for symbol, info in self.open_trades.items():
            positions.append({
                "symbol": symbol,
                "direction": info["direction"],
            })
        return positions

    def sync_positions(self):
        """
        Sync local trade tracking with broker's actual open positions.
        Detects trades that were closed by SL/TP (not by us).
        """
        try:
            broker_positions = self.api.get_open_positions()
        except Exception as e:
            logger.error(f"Failed to sync positions: {e}")
            return

        # Extract deal IDs from broker
        broker_deal_ids = set()
        for pos in broker_positions:
            position_data = pos.get("position", {})
            deal_id = position_data.get("dealId", "")
            if deal_id:
                broker_deal_ids.add(deal_id)

        # Check each tracked trade
        symbols_to_remove = []
        for symbol, trade_info in self.open_trades.items():
            a_alive = trade_info.get("deal_id_a") in broker_deal_ids
            b_alive = trade_info.get("deal_id_b") in broker_deal_ids

            if not a_alive and not b_alive:
                # Both sub-orders are gone — trade fully closed
                logger.info(
                    f"[{symbol}] Trade fully closed by broker (SL/TP hit)"
                )
                
                # Estimate PnL state for performance tracking
                is_win = trade_info.get("tp1_hit", False)
                est_pnl = 1.0 if is_win else -1.0
                
                if self.performance_tracker:
                    self.performance_tracker.update_trade(symbol, est_pnl)
                    
                # Note: We don't have exact PnL here unless we query broker history.
                self.log_trade(
                    trade_info, status="CLOSED",
                    close_reason="SL/TP hit (auto-closed by broker)",
                    pnl=est_pnl
                )
                symbols_to_remove.append(symbol)

            elif not a_alive and b_alive and not trade_info["tp1_hit"]:
                # Sub-order A closed (TP1 hit) — move B to break-even
                trade_info["tp1_hit"] = True
                logger.info(
                    f"[{symbol}] TP1 hit — sub-order A closed. "
                    f"Moving sub-order B SL to break-even."
                )
                self._set_breakeven(trade_info)
                
            # Trailing stop for sub-order B
            if b_alive and trade_info.get("breakeven_set"):
                # Find current price from broker positions
                current_price = None
                for bp in broker_positions:
                    bp_data = bp.get("position", {})
                    if bp_data.get("dealId", "") == trade_info.get("deal_id_b"):
                        market_data = bp.get("market", {})
                        if trade_info["direction"] == "LONG":
                            current_price = market_data.get("bid")
                        else:
                            current_price = market_data.get("offer")
                        break
                        
                if current_price:
                    self._update_trailing_stop(trade_info, current_price)

        for symbol in symbols_to_remove:
            del self.open_trades[symbol]

    def _set_breakeven(self, trade_info):
        """
        Move sub-order B's stop-loss to the entry price (break-even).

        Args:
            trade_info: Trade info dict
        """
        if trade_info.get("breakeven_set"):
            return

        deal_id_b = trade_info.get("deal_id_b")
        if deal_id_b is None:
            return

        entry_price = trade_info["entry_price"]
        success = self.api.update_position(
            deal_id_b,
            stop_level=entry_price
        )

        if success:
            trade_info["breakeven_set"] = True
            trade_info["sl"] = entry_price
            logger.info(
                f"[{trade_info['symbol']}] Break-even set: "
                f"SL moved to {entry_price}"
            )
            self.log_trade(
                trade_info, status="BREAKEVEN",
                close_reason="TP1 hit — SL moved to entry"
            )
        else:
            logger.error(
                f"[{trade_info['symbol']}] Failed to set break-even"
            )

    def _update_trailing_stop(self, trade_info, current_price):
        """Update trailing stop for sub-order B."""
        symbol = trade_info["symbol"]
        direction = trade_info["direction"]
        atr = trade_info.get("atr_at_entry", 0)
        
        if not atr:
            return

        deal_id_b = trade_info.get("deal_id_b")
        if not deal_id_b:
            return

        trailing_dist = 1.0 * atr
        new_sl = None

        if direction == "LONG":
            if current_price > trade_info["highest_price"]:
                trade_info["highest_price"] = current_price
            
            potential_sl = trade_info["highest_price"] - trailing_dist
            if potential_sl > trade_info["sl"]:
                new_sl = round(potential_sl, 5)
                
        else: # SHORT
            if current_price < trade_info["lowest_price"]:
                trade_info["lowest_price"] = current_price
                
            potential_sl = trade_info["lowest_price"] + trailing_dist
            if potential_sl < trade_info["sl"]:
                new_sl = round(potential_sl, 5)

        if new_sl:
            success = self.api.update_position(deal_id_b, stop_level=new_sl)
            if success:
                trade_info["sl"] = new_sl
                logger.info(f"[{symbol}] Trailing SL updated to {new_sl}")

    def has_open_trade(self, symbol):
        """Check if there's an open trade for the given symbol."""
        return symbol in self.open_trades
