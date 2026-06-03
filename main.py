"""
main.py — Trading bot entry point.

Initializes the broker API, sets up the scheduler, and runs the
main trading loop on every H1 candle close.

Usage:
    python main.py              # Start the live bot
    python main.py --backtest   # Run backtesting instead
"""

import os
import sys
import io
import time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
import logging
import argparse
from datetime import datetime, timezone

import schedule

# Ensure the trading_bot package is importable
sys.path.insert(0, os.path.dirname(__file__))

import config
from broker.capital_api import CapitalAPI
from data.fetcher import fetch_ohlcv
from signals.scorer import score_instrument, get_atr_value
from filters.session import is_session_active
from filters.correlation import is_correlated_blocked
from filters.news import should_block_trade
from trade.manager import TradeManager
from trade.partial_close import PartialCloseManager
from trade.risk_manager import RiskManager
from trade.performance import PerformanceTracker

# =============================================================================
#  Logging Setup
# =============================================================================
os.makedirs(config.LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(config.BOT_LOG_FILE, mode="a", encoding="utf-8"),
    ],
)
logger = logging.getLogger("TradingBot")


# =============================================================================
#  Global instances
# =============================================================================
api = None
trade_manager = None
partial_close_manager = None
risk_manager = None
performance_tracker = None


def initialize():
    """Initialize API connection and managers."""
    global api, trade_manager, partial_close_manager, risk_manager, performance_tracker

    logger.info("=" * 60)
    logger.info("TRADING BOT INITIALIZING")
    logger.info(f"Environment: {config.ENVIRONMENT.upper()}")
    logger.info(f"Instruments: {len(config.INSTRUMENTS)}")
    logger.info(f"Max Loss per trade: ${config.MAX_LOSS_PER_TRADE}")
    logger.info(f"Leverage: x{config.LEVERAGE}")
    logger.info("=" * 60)

    api = CapitalAPI()
    if not api.create_session():
        logger.error("FATAL: Could not authenticate with Capital.com. Exiting.")
        sys.exit(1)

    risk_manager = RiskManager(api)
    performance_tracker = PerformanceTracker()

    # Update initial capital from API if available
    account_info = api.get_account_info()
    if account_info and "accounts" in account_info and account_info["accounts"]:
        balance_obj = account_info["accounts"][0].get("balance", config.STARTING_CAPITAL)
        balance = balance_obj.get("balance", config.STARTING_CAPITAL) if isinstance(balance_obj, dict) else balance_obj
        risk_manager.update_capital(balance)
        logger.info(f"Live account balance: ${balance}")

    trade_manager = TradeManager(
        api, 
        risk_manager=risk_manager, 
        performance_tracker=performance_tracker
    )
    partial_close_manager = PartialCloseManager(trade_manager)

    logger.info("Bot initialized successfully. Waiting for next H1 candle close...")


def run_cycle():
    """
    Main trading cycle — runs once per H1 candle close.

    For each instrument:
        1. Check session filter
        2. Check correlation filter
        3. Check news filter
        4. Fetch H1 + H4 data
        5. Score signal
        6. Execute or skip trade
        7. Log everything
    """
    cycle_start = datetime.now(timezone.utc)
    logger.info(f"\n{'='*60}")
    logger.info(f"CYCLE START: {cycle_start.strftime('%Y-%m-%d %H:%M UTC')}")
    logger.info(f"{'='*60}")

    # Refresh API session
    api._ensure_session()

    # Update account balance for risk manager
    account_info = api.get_account_info()
    if account_info and "accounts" in account_info and account_info["accounts"]:
        balance_obj = account_info["accounts"][0].get("balance", risk_manager.current_capital)
        balance = balance_obj.get("balance", risk_manager.current_capital) if isinstance(balance_obj, dict) else balance_obj
        risk_manager.update_capital(balance, cycle_start)

    # Manage existing trades (partial close / break-even)
    partial_close_manager.check_and_manage()

    # Generate daily performance report
    performance_tracker.generate_daily_report()

    # Get current open positions for filter checks
    open_positions = trade_manager.get_open_position_list()
    logger.info(f"Open positions: {len(open_positions)}")
    
    # Account Risk Limits
    allowed, limit_reason = risk_manager.is_trading_allowed(len(open_positions), 0)
    if not allowed:
        logger.warning(f"GLOBAL SKIP: {limit_reason}")
        return

    signals_checked = 0
    trades_opened = 0
    trades_skipped = 0

    for symbol in config.INSTRUMENTS:
        if not config.INSTRUMENTS[symbol].get("active", True):
            continue

        signals_checked += 1

        # ----- Check Performance Pauses -----
        if performance_tracker.is_paused(symbol):
            logger.info(f"[{symbol}] SKIP: Paused due to poor performance")
            trades_skipped += 1
            continue

        # ----- Filter 1: Session -----
        session_active, session_name, session_reason = is_session_active(
            symbol, cycle_start
        )
        if not session_active:
            logger.debug(f"[{symbol}] SKIP (session): {session_reason}")
            _log_skipped_signal(symbol, f"Session filter: {session_reason}")
            trades_skipped += 1
            continue

        # ----- Filter 2: Correlation -----
        corr_blocked, corr_reason = is_correlated_blocked(
            symbol, open_positions
        )
        if corr_blocked:
            logger.info(f"[{symbol}] SKIP (correlation): {corr_reason}")
            _log_skipped_signal(symbol, f"Correlation: {corr_reason}")
            trades_skipped += 1
            continue

        # ----- Filter 3: News -----
        news_blocked, news_reason, lot_multiplier = should_block_trade(
            symbol, cycle_start
        )
        if news_blocked:
            logger.info(f"[{symbol}] SKIP (news): {news_reason}")
            _log_skipped_signal(symbol, f"News: {news_reason}")
            trades_skipped += 1
            continue

        # ----- Fetch data -----
        market_class = config.INSTRUMENTS[symbol]["class"]
        epic = config.INSTRUMENTS[symbol]["epic"]

        try:
            df_h1 = fetch_ohlcv(api, epic, resolution="HOUR", bars=300)
            df_h4 = fetch_ohlcv(api, epic, resolution="HOUR_4", bars=100)
        except Exception as e:
            logger.error(f"[{symbol}] Data fetch error: {e}")
            trades_skipped += 1
            continue

        if df_h1.empty or df_h4.empty:
            logger.warning(f"[{symbol}] Empty data — skipping")
            trades_skipped += 1
            continue

        # ----- Score signal -----
        signal = score_instrument(symbol, df_h1, df_h4)

        # Log every signal (including skipped)
        trade_manager.log_signal(signal)

        if signal["action"] == "SKIP":
            logger.info(
                f"[{symbol}] SKIP: {signal.get('skip_reason', 'Score too low')} "
                f"| Score={signal['score']}/6 | H4={signal['h4_trend']} "
                f"| H1={signal['h1_direction']}"
            )
            trades_skipped += 1
            continue

        # ----- Determine lot size -----
        # 1. Base on ATR and Account Risk
        # Re-compute indicators on H1 to get ATR early
        from indicators import forex, crypto, indices, commodities, stocks
        module_map = {
            "forex": forex, "crypto": crypto, "indices": indices,
            "commodities": commodities, "stocks": stocks,
        }
        module = module_map[market_class]
        params = config.INDICATOR_PARAMS[market_class]
        df_h1_ind = module.compute_indicators(df_h1, params)
        atr_value = get_atr_value(df_h1_ind, market_class)

        if atr_value is None or atr_value == 0:
            logger.warning(f"[{symbol}] No valid ATR — skipping")
            trades_skipped += 1
            continue

        min_atr = config.MIN_ATR_FILTER.get(symbol, config.MIN_ATR_FILTER.get(market_class, 0.0))
        if atr_value < min_atr:
            logger.info(f"[{symbol}] SKIP: ATR ({atr_value:.5f}) below minimum ({min_atr})")
            trades_skipped += 1
            continue

        base_lot = risk_manager.calculate_lot_size(symbol, atr_value)

        # Score discount is removed: we use a fixed lot size
        
        # 3. News multiplier
        lot_size = base_lot * lot_multiplier
        
        # 4. Performance multiplier
        perf_mult = performance_tracker.get_lot_multiplier(symbol)
        lot_size = round(lot_size * perf_mult, 2)

        if lot_size < 1:
            logger.info(f"[{symbol}] SKIP: Lot size ({lot_size}) too small after modifiers")
            trades_skipped += 1
            continue



        # ----- Execute trade -----
        entry_price = df_h1.iloc[-1]["close"]

        trade_info = trade_manager.open_trade(
            symbol=symbol,
            direction=signal["direction"],
            lot_size=lot_size,
            atr_value=atr_value,
            entry_price=entry_price,
            score=signal["score"],
            confidence=signal["confidence"],
            market_structure=signal.get("market_structure", {}),  # Add market structure
        )

        if trade_info:
            trades_opened += 1
            # Update open positions for correlation checks
            open_positions = trade_manager.get_open_position_list()
        else:
            logger.error(f"[{symbol}] Failed to open trade")
            trades_skipped += 1

    # ----- Cycle summary -----
    logger.info(f"\nCYCLE COMPLETE: "
                f"Checked={signals_checked} | "
                f"Opened={trades_opened} | "
                f"Skipped={trades_skipped} | "
                f"Total open={len(trade_manager.open_trades)}")


def _log_skipped_signal(symbol, reason):
    """Log a skipped signal (filtered before scoring)."""
    trade_manager.log_signal({
        "symbol": symbol,
        "direction": "NONE",
        "score": 0,
        "confidence": 0,
        "action": "SKIP",
        "skip_reason": reason,
        "h4_trend": "N/A",
        "h1_direction": "N/A",
        "indicator_details": {},
        "market_structure": {},  # Add empty market structure for consistency
    })


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Algorithmic Trading Bot")
    parser.add_argument(
        "--backtest", action="store_true",
        help="Run backtesting instead of live trading"
    )
    parser.add_argument(
        "--once", action="store_true",
        help="Run a single cycle then exit (for testing)"
    )
    args = parser.parse_args()

    if args.backtest:
        # Run backtesting engine
        from backtest.engine import BacktestEngine
        logging.basicConfig(level=logging.INFO)
        engine = BacktestEngine()
        engine.run_all()
        return

    # Live trading mode
    initialize()

    if args.once:
        # Single cycle for testing
        run_cycle()
        logger.info("Single cycle complete. Exiting.")
        return

    # Schedule the bot to run at the top of every hour (H1 candle close)
    schedule.every().hour.at(":01").do(run_cycle)

    logger.info("Scheduler started. Running every hour at :01 past.")
    logger.info("Press Ctrl+C to stop.\n")

    # Run first cycle immediately
    run_cycle()

    # Keep running
    try:
        while True:
            schedule.run_pending()
            time.sleep(10)
    except KeyboardInterrupt:
        logger.info("\nBot stopped by user. Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
