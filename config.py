"""
config.py — Central configuration for the trading bot.
All indicator settings, instrument definitions, API credentials,
trade management parameters, and filter rules live here.
"""

# =============================================================================
#  CAPITAL.COM API CREDENTIALS
# =============================================================================
API_KEY = "wFD6JmaUYnYJNhUg"
API_IDENTIFIER = "feridsalamanov@gmail.com"         # Capital.com login email
API_PASSWORD = '314p15iAZe"""'                      # Capital.com login password

# Environment: "demo" or "live"
# Change to "live" when ready for real trading
ENVIRONMENT = "demo"

# Base URLs
BASE_URLS = {
    "demo": "https://demo-api-capital.backend-capital.com",
    "live": "https://api-capital.backend-capital.com",
}

# =============================================================================
#  GENERAL SETTINGS & RISK MANAGEMENT
# =============================================================================
STARTING_CAPITAL = 200.0       # USD

# Dynamic Risk Sizing
FULL_LOT_SIZE = 15.0            # USD margin (Sizin dediyiniz $15 lot)
SCORE_REDUCED_LOT_SIZE = 15.0
DRAWDOWN_REDUCED_LOT = 15.0
LEVERAGE = 30                   # x30 (Sabit 30x leverage)
BACKTEST_LEVERAGE = 30          # x30

# Account Protection
DAILY_LOSS_LIMIT_PCT = -100.0    # Gündəlik itki limitini deaktiv edirik
WEEKLY_LOSS_LIMIT_PCT = -100.0   # Həftəlik itki limitini deaktiv edirik
DRAWDOWN_PROTECTION_PCT = -0.15 # If drawn down > 15%, lot size drops
HARD_STOP_CAPITAL = 50.0        # Balans 50-yə düşsə bot tam dayanır
MAX_LOSS_PER_TRADE = 15.0        # Max $15 loss per trade (since lot is $15)
MAX_OPEN_TRADES = 10             # Overall maximum
MAX_OPEN_TRADES_PER_CLASS = 5   # Max per market class
CONSECUTIVE_LOSS_PAUSE_HOURS = 4 # Pause trading after 3 consecutive losses
HIGH_VOL_MAX_LOT = 15.0         
HIGH_VOL_INSTRUMENTS = ["SOLUSD", "XRPUSD", "XAGUSD", "DOGEUSD"]

# Faiz Əsaslı Risk/Qazanc Parametrləri
USE_PERCENTAGE_LEVELS = True    # Faiz əsaslı SL və TP rejimini aktiv edirik
SL_PCT = 0.015                  # 1.5% Stop-Loss
TP1_PCT = 0.02                  # 2.0% Take-Profit 1
TP2_PCT = 0.04                  # 4.0% Take-Profit 2

# Simvol Limitləri
MAX_OPEN_TRADES_PER_SYMBOL = {
    "BTCUSD": 2,
    "SOLUSD": 2
}

# Scoring thresholds
SCORE_FULL_LOT = 6              # 6/6 → full lot
SCORE_REDUCED_LOT = 5           # 5/6 → reduced lot
SCORE_MIN_TO_TRADE = 6          # Minimum score to open a trade (yalnız 6 xalla giriş)

# =============================================================================
#  INSTRUMENTS — 100 Bazarlıq Geniş Siyahı
# =============================================================================
INSTRUMENTS = {
    # ----- Forex (25 Symbols) -----
    "EURUSD":  {"epic": "EURUSD",  "class": "forex", "active": False}, # Deaktiv (Zərərli)
    "GBPUSD":  {"epic": "GBPUSD",  "class": "forex", "active": False}, # Deaktiv (Zərərli)
    "USDJPY":  {"epic": "USDJPY",  "class": "forex", "active": False},  # Deaktiv (Zərərli)
    "USDCHF":  {"epic": "USDCHF",  "class": "forex", "active": False},
    "AUDUSD":  {"epic": "AUDUSD",  "class": "forex", "active": False},
    "USDCAD":  {"epic": "USDCAD",  "class": "forex", "active": False},
    "NZDUSD":  {"epic": "NZDUSD",  "class": "forex", "active": False},
    "EURGBP":  {"epic": "EURGBP",  "class": "forex", "active": False},
    "EURJPY":  {"epic": "EURJPY",  "class": "forex", "active": False},
    "GBPJPY":  {"epic": "GBPJPY",  "class": "forex", "active": False},
    "CADJPY":  {"epic": "CADJPY",  "class": "forex", "active": False},
    "AUDCAD":  {"epic": "AUDCAD",  "class": "forex", "active": False},
    "AUDNZD":  {"epic": "AUDNZD",  "class": "forex", "active": False},
    "GBPAUD":  {"epic": "GBPAUD",  "class": "forex", "active": False},
    "EURAUD":  {"epic": "EURAUD",  "class": "forex", "active": False},
    "EURCAD":  {"epic": "EURCAD",  "class": "forex", "active": False},
    "GBPCAD":  {"epic": "GBPCAD",  "class": "forex", "active": False},
    "GBPCHF":  {"epic": "GBPCHF",  "class": "forex", "active": False},
    "CHFJPY":  {"epic": "CHFJPY",  "class": "forex", "active": False},
    "NZDJPY":  {"epic": "NZDJPY",  "class": "forex", "active": False},
    "AUDJPY":  {"epic": "AUDJPY",  "class": "forex", "active": False},
    "GBPNZD":  {"epic": "GBPNZD",  "class": "forex", "active": False},
    "EURCHF":  {"epic": "EURCHF",  "class": "forex", "active": False},
    "CADCHF":  {"epic": "CADCHF",  "class": "forex", "active": False},
    "NZDCAD":  {"epic": "NZDCAD",  "class": "forex", "active": False},

    # ----- Crypto (20 Symbols) -----
    "BTCUSD":  {"epic": "BTCUSD",  "class": "crypto", "active": True},
    "ETHUSD":  {"epic": "ETHUSD",  "class": "crypto", "active": False}, # Deaktiv (Zərərli)
    "SOLUSD":  {"epic": "SOLUSD",  "class": "crypto", "active": True},
    "XRPUSD":  {"epic": "XRPUSD",  "class": "crypto", "active": True},
    "BNBUSD":  {"epic": "BNBUSD",  "class": "crypto", "active": False}, # Deaktiv (Zərərli)
    "ADAUSD":  {"epic": "ADAUSD",  "class": "crypto", "active": False},
    "DOGEUSD": {"epic": "DOGEUSD", "class": "crypto", "active": False}, # Deaktiv (Zərərli)
    "AVAXUSD": {"epic": "AVAXUSD", "class": "crypto", "active": False},
    "LINKUSD": {"epic": "LINKUSD", "class": "crypto", "active": False},
    "MATICUSD":{"epic": "MATICUSD","class": "crypto", "active": False},
    "DOTUSD":  {"epic": "DOTUSD",  "class": "crypto", "active": False},
    "UNIUSD":  {"epic": "UNIUSD",  "class": "crypto", "active": False},
    "LTCUSD":  {"epic": "LTCUSD",  "class": "crypto", "active": False},
    "ATOMUSD": {"epic": "ATOMUSD", "class": "crypto", "active": False},
    "BCHUSD":  {"epic": "BCHUSD",  "class": "crypto", "active": False},
    "XLMUSD":  {"epic": "XLMUSD",  "class": "crypto", "active": False},
    "TRXUSD":  {"epic": "TRXUSD",  "class": "crypto", "active": False},
    "EOSUSD":  {"epic": "EOSUSD",  "class": "crypto", "active": False},
    "ALGOUSD": {"epic": "ALGOUSD", "class": "crypto", "active": False},
    "NEARUSD": {"epic": "NEARUSD", "class": "crypto", "active": False},

    # ----- Indices (10 Symbols) -----
    "US100":   {"epic": "US100",   "class": "indices", "active": True},
    "US500":   {"epic": "US500",   "class": "indices", "active": False}, # Deaktiv (Zərərli)
    "US30":    {"epic": "US30",    "class": "indices", "active": True},
    "DE40":    {"epic": "DE40",    "class": "indices", "active": False}, # Deaktiv (Zərərli)
    "UK100":   {"epic": "UK100",   "class": "indices", "active": False},
    "JP225":   {"epic": "JP225",   "class": "indices", "active": False},
    "AU200":   {"epic": "AU200",   "class": "indices", "active": False},
    "HK50":    {"epic": "HK50",    "class": "indices", "active": False},
    "FR40":    {"epic": "FR40",    "class": "indices", "active": False},
    "EU50":    {"epic": "EU50",    "class": "indices", "active": False},

    # ----- Commodities (10 Symbols) -----
    "XAUUSD":  {"epic": "GOLD",      "class": "commodities", "active": False}, # Deaktiv (Zərərli)
    "XAGUSD":  {"epic": "SILVER",    "class": "commodities", "active": False},
    "WTI":     {"epic": "OIL_CRUDE", "class": "commodities", "active": False}, # Deaktiv (Zərərli)
    "BRENT":   {"epic": "OIL_BRENT", "class": "commodities", "active": False}, # Deaktiv (Zərərli)
    "NATGAS":  {"epic": "NAT_GAS",   "class": "commodities", "active": False},
    "COPPER":  {"epic": "COPPER",    "class": "commodities", "active": False},
    "PLATINUM":{"epic": "PLATINUM",  "class": "commodities", "active": False},
    "PALLADIUM":{"epic": "PALLADIUM","class": "commodities", "active": False},
    "COFFEE":  {"epic": "COFFEE",    "class": "commodities", "active": False},
    "SUGAR":   {"epic": "SUGAR",     "class": "commodities", "active": False},

    # ----- Stocks (35 Symbols) -----
    "AAPL":    {"epic": "AAPL",    "class": "stocks", "active": True},
    "MSFT":    {"epic": "MSFT",    "class": "stocks", "active": False},
    "NVDA":    {"epic": "NVDA",    "class": "stocks", "active": False},
    "TSLA":    {"epic": "TSLA",    "class": "stocks", "active": False},
    "AMZN":    {"epic": "AMZN",    "class": "stocks", "active": False}, # Deaktiv (Zərərli)
    "GOOG":    {"epic": "GOOG",    "class": "stocks", "active": False},
    "META":    {"epic": "META",    "class": "stocks", "active": False},
    "NFLX":    {"epic": "NFLX",    "class": "stocks", "active": False},
    "AMD":     {"epic": "AMD",     "class": "stocks", "active": False},
    "INTC":    {"epic": "INTC",    "class": "stocks", "active": False},
    "PYPL":    {"epic": "PYPL",    "class": "stocks", "active": False},
    "BABA":    {"epic": "BABA",    "class": "stocks", "active": False},
    "JPM":     {"epic": "JPM",     "class": "stocks", "active": False},
    "BAC":     {"epic": "BAC",     "class": "stocks", "active": False},
    "DIS":     {"epic": "DIS",     "class": "stocks", "active": False},
    "NKE":     {"epic": "NKE",     "class": "stocks", "active": False},
    "WMT":     {"epic": "WMT",     "class": "stocks", "active": False},
    "KO":      {"epic": "KO",      "class": "stocks", "active": False},
    "PEP":     {"epic": "PEP",     "class": "stocks", "active": False},
    "XOM":     {"epic": "XOM",     "class": "stocks", "active": False},
    "CVX":     {"epic": "CVX",     "class": "stocks", "active": False},
    "LLY":     {"epic": "LLY",     "class": "stocks", "active": False},
    "UNH":     {"epic": "UNH",     "class": "stocks", "active": False},
    "HD":      {"epic": "HD",      "class": "stocks", "active": False},
    "COST":    {"epic": "COST",    "class": "stocks", "active": False},
    "V":       {"epic": "V",       "class": "stocks", "active": False},
    "MA":      {"epic": "MA",      "class": "stocks", "active": False},
    "PG":      {"epic": "PG",      "class": "stocks", "active": False},
    "JNJ":     {"epic": "JNJ",     "class": "stocks", "active": False},
    "MRK":     {"epic": "MRK",     "class": "stocks", "active": False},
    "ABBV":    {"epic": "ABBV",    "class": "stocks", "active": False},
    "AVGO":    {"epic": "AVGO",    "class": "stocks", "active": False},
    "QCOM":    {"epic": "QCOM",    "class": "stocks", "active": False},
    "CRM":     {"epic": "CRM",     "class": "stocks", "active": False},
}

# =============================================================================
#  INDICATOR PARAMETERS — per market class
# =============================================================================
INDICATOR_PARAMS = {
    "forex": {
        "trend_ma_type": "EMA",
        "trend_ma_period": 200,
        "adx_period": 14,
        "adx_threshold": 25,
        "rsi_period": 14,
        "rsi_long_zone": (45, 65),
        "rsi_short_zone": (35, 55),
        "atr_period": 14,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "supertrend_period": 10,
        "supertrend_multiplier": 3.0,
        # Indicators used for scoring (ordered)
        "scoring_indicators": [
            "trend_ma", "adx", "rsi", "macd", "supertrend", "atr_trend"
        ],
    },
    "crypto": {
        "trend_ma_type": "EMA",
        "trend_ma_period": 200,
        "adx_period": 14,
        "adx_threshold": 25,
        "rsi_period": 14,
        "rsi_long_zone": (40, 65),
        "rsi_short_zone": (35, 60),
        "atr_period": 14,
        "supertrend_period": 10,
        "supertrend_multiplier": 2.5,
        "scoring_indicators": [
            "trend_ma", "adx", "rsi", "obv", "supertrend", "atr_trend"
        ],
    },
    "indices": {
        "trend_ma_type": "SMA",
        "trend_ma_period": 200,
        "adx_period": 14,
        "adx_threshold": 25,
        "rsi_period": 10,
        "rsi_long_zone": (52, 65),
        "rsi_short_zone": (35, 48),
        "atr_period": 10,
        "supertrend_period": 7,
        "supertrend_multiplier": 3.0,
        "scoring_indicators": [
            "trend_ma", "adx", "rsi", "vwap", "supertrend", "atr_trend"
        ],
    },
    "commodities": {
        "trend_ma_type": "EMA",
        "trend_ma_period": 200,
        "adx_period": 14,
        "adx_threshold": 25,
        "rsi_period": 14,
        "rsi_long_zone": (40, 65),
        "rsi_short_zone": (35, 60),
        "atr_period": 14,
        "supertrend_period": 10,
        "supertrend_multiplier": 3.0,
        "bb_period": 20,
        "bb_std": 2.0,
        "scoring_indicators": [
            "trend_ma", "adx", "rsi", "bollinger", "supertrend", "atr_trend"
        ],
    },
    "stocks": {
        "trend_ma_type": "SMA",
        "trend_ma_period": 200,
        "adx_period": 14,
        "adx_threshold": 25,
        "rsi_period": 14,
        "rsi_long_zone": (45, 65),
        "rsi_short_zone": (35, 55),
        "atr_period": 14,
        "macd_fast": 12,
        "macd_slow": 26,
        "macd_signal": 9,
        "scoring_indicators": [
            "trend_ma", "adx", "rsi", "macd", "vwap", "atr_trend"
        ],
    },
}

# =============================================================================
#  MINIMUM ATR FILTER
#  Minimum absolute ATR required to open a trade per class or symbol
# =============================================================================
MIN_ATR_FILTER = {
    "BTCUSD": 50.0,
    "ETHUSD": 2.0,
    "XAUUSD": 0.5,
    "XAGUSD": 0.3,
    "WTI": 0.5,
    "BRENT": 0.5,
    "NATGAS": 0.05,
    "COPPER": 0.02,
    "DOGEUSD": 0.0005,
    "XRPUSD": 0.005,
    "MATICUSD": 0.005,
    "forex": 0.0005,
    "crypto": 0.5,     # Default for other cryptos
    "indices": 10.0,
    "commodities": 0.5,
    "stocks": 0.5,
}

# =============================================================================
#  TRADE MANAGEMENT
# =============================================================================
SL_ATR_MULTIPLIER = 2.0         # Stop-Loss = 2.0 × ATR
TP1_ATR_MULTIPLIER = 2.0        # TP1 = 2.0 × ATR
TP2_ATR_MULTIPLIER = 4.0        # TP2 = 4.0 × ATR
TRAILING_SL_ATR_MULTIPLIER = 1.0 # Trailing stop distance after TP1
TP1_CLOSE_PCT = 0.40            # Close 40% of position at TP1
TP2_CLOSE_PCT = 0.60            # Close remaining 60% at TP2

# =============================================================================
#  CORRELATION MAP
#  If instrument X is open, block all instruments in its correlated list.
# =============================================================================
CORRELATION_MAP = {
    "EURUSD":  ["GBPUSD", "AUDUSD", "NZDUSD", "EURJPY"],
    "GBPUSD":  ["EURUSD", "EURGBP", "GBPJPY"],
    "USDJPY":  ["USDCHF", "USDCAD", "EURJPY", "GBPJPY", "CADJPY"],
    "USDCHF":  ["USDJPY", "USDCAD"],
    "USDCAD":  ["USDJPY", "USDCHF"],
    "AUDUSD":  ["EURUSD", "NZDUSD", "AUDCAD", "AUDNZD"],
    "NZDUSD":  ["EURUSD", "AUDUSD", "AUDNZD"],
    "EURGBP":  ["GBPUSD"],
    "EURJPY":  ["USDJPY", "EURUSD"],
    "GBPJPY":  ["USDJPY", "GBPUSD"],
    "CADJPY":  ["USDJPY", "USDCAD"],
    "AUDCAD":  ["AUDUSD", "USDCAD"],
    "AUDNZD":  ["AUDUSD", "NZDUSD"],
    "GBPAUD":  ["GBPUSD", "AUDUSD"],

    "BTCUSD":  ["ETHUSD", "SOLUSD", "BNBUSD", "LINKUSD", "DOTUSD", "LTCUSD"],
    "ETHUSD":  ["BTCUSD", "SOLUSD", "BNBUSD", "LINKUSD"],
    "SOLUSD":  ["BTCUSD", "ETHUSD"],
    "BNBUSD":  ["BTCUSD", "ETHUSD"],
    "XRPUSD":  ["ADAUSD", "DOGEUSD"],
    "ADAUSD":  ["XRPUSD", "DOGEUSD"],
    "DOGEUSD": ["XRPUSD", "ADAUSD"],
    "AVAXUSD": [],
    "LINKUSD": ["BTCUSD", "ETHUSD"],
    "MATICUSD":[],
    "DOTUSD":  ["BTCUSD"],
    "UNIUSD":  [],
    "LTCUSD":  ["BTCUSD"],
    "ATOMUSD": [],

    "XAUUSD":  ["XAGUSD"],
    "XAGUSD":  ["XAUUSD"],
    "WTI":     ["BRENT"],
    "BRENT":   ["WTI"],
    "NATGAS":  [],
    "COPPER":  [],

    "US100":   ["US500", "US30"],
    "US500":   ["US100", "US30"],
    "US30":    ["US100", "US500"],
    "DE40":    ["FR40"],
    "UK100":   [],
    "JP225":   [],
    "AU200":   [],
    "HK50":    [],
    "FR40":    ["DE40"],

    "AAPL":    [],
    "MSFT":    [],
    "NVDA":    [],
    "TSLA":    [],
    "AMZN":    [],
}

# =============================================================================
#  SESSION FILTER
#  Defines which sessions each instrument is allowed to trade in.
#  Times are in UTC.
# =============================================================================
SESSIONS = {
    "london":   {"start": "08:00", "end": "16:00"},
    "new_york": {"start": "13:00", "end": "21:00"},
    "asia":     {"start": "00:00", "end": "08:00"},
    "crypto":   {"start": "00:00", "end": "23:59"},  # 24/7
}

# Map: instrument → list of allowed session names
INSTRUMENT_SESSIONS = {
    # Forex
    "EURUSD":  ["london", "new_york"],
    "GBPUSD":  ["london", "new_york"],
    "USDJPY":  ["london", "new_york", "asia"],
    "USDCHF":  ["london", "new_york"],
    "AUDUSD":  ["london", "new_york", "asia"],
    "USDCAD":  ["london", "new_york"],
    "NZDUSD":  ["london", "new_york", "asia"],
    "EURGBP":  ["london", "new_york"],
    "EURJPY":  ["london", "new_york", "asia"],
    "GBPJPY":  ["london", "new_york", "asia"],
    "CADJPY":  ["london", "new_york", "asia"],
    "AUDCAD":  ["london", "new_york", "asia"],
    "AUDNZD":  ["london", "new_york", "asia"],
    "GBPAUD":  ["london", "new_york", "asia"],

    # Crypto — 24/7
    "BTCUSD":  ["crypto"],
    "ETHUSD":  ["crypto"],
    "SOLUSD":  ["crypto"],
    "XRPUSD":  ["crypto"],
    "BNBUSD":  ["crypto"],
    "ADAUSD":  ["crypto"],
    "DOGEUSD": ["crypto"],
    "AVAXUSD": ["crypto"],
    "LINKUSD": ["crypto"],
    "MATICUSD":["crypto"],
    "DOTUSD":  ["crypto"],
    "UNIUSD":  ["crypto"],
    "LTCUSD":  ["crypto"],
    "ATOMUSD": ["crypto"],

    # Indices
    "US100":   ["london", "new_york"],
    "US500":   ["london", "new_york"],
    "US30":    ["london", "new_york"],
    "DE40":    ["london"],
    "UK100":   ["london"],
    "JP225":   ["asia", "london"],
    "AU200":   ["asia", "london"],
    "HK50":    ["asia"],
    "FR40":    ["london"],

    # Commodities
    "XAUUSD":  ["london", "new_york"],
    "XAGUSD":  ["london", "new_york"],
    "WTI":     ["new_york"],
    "BRENT":   ["london", "new_york"],
    "NATGAS":  ["new_york", "london"],
    "COPPER":  ["new_york", "london"],

    # Stocks — New York
    "AAPL":    ["new_york"],
    "MSFT":    ["new_york"],
    "NVDA":    ["new_york"],
    "TSLA":    ["new_york"],
    "AMZN":    ["new_york"],
}

# =============================================================================
#  NEWS FILTER — ForexFactory
# =============================================================================
NEWS_WINDOW_MINUTES = 30  # ±30 minutes around high-impact events

# Map currency codes to affected instruments
CURRENCY_INSTRUMENT_MAP = {
    "USD": ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD",
            "NZDUSD", "BTCUSD", "ETHUSD", "XAUUSD", "XAGUSD", "WTI",
            "BRENT", "NATGAS", "COPPER", "US100", "US500", "US30", 
            "AAPL", "MSFT", "NVDA", "TSLA", "AMZN",
            "SOLUSD", "XRPUSD", "DOGEUSD", "LINKUSD", "DOTUSD", "LTCUSD"],
    "EUR": ["EURUSD", "EURGBP", "EURJPY", "DE40", "FR40"],
    "GBP": ["GBPUSD", "EURGBP", "GBPJPY", "GBPAUD", "UK100"],
    "JPY": ["USDJPY", "EURJPY", "GBPJPY", "CADJPY", "JP225"],
    "CHF": ["USDCHF"],
    "AUD": ["AUDUSD", "AUDCAD", "AUDNZD", "GBPAUD", "AU200"],
    "CAD": ["USDCAD", "CADJPY", "AUDCAD"],
    "NZD": ["NZDUSD", "AUDNZD"],
    "HKD": ["HK50"],
}

# =============================================================================
#  LOAD OPTIMIZED PARAMETERS
# =============================================================================
import os
import json

OPTIMIZED_PARAMS_FILE = os.path.join(os.path.dirname(__file__), "config", "optimized_params.json")
OPTIMIZED_PARAMS = {}

if os.path.exists(OPTIMIZED_PARAMS_FILE):
    try:
        with open(OPTIMIZED_PARAMS_FILE, "r") as f:
            OPTIMIZED_PARAMS = json.load(f)
    except Exception as e:
        pass

def get_instrument_params(symbol):
    """
    Get the indicator parameters for an instrument.
    Returns optimized parameters if available, otherwise falls back to market class default.
    """
    if symbol in OPTIMIZED_PARAMS:
        return OPTIMIZED_PARAMS[symbol]
        
    market_class = INSTRUMENTS.get(symbol, {}).get("class", "forex")
    return INDICATOR_PARAMS.get(market_class, INDICATOR_PARAMS["forex"])

# =============================================================================
#  BACKTEST SETTINGS
# =============================================================================
BACKTEST_LOOKBACK_DAYS = 365    # 1 year of data (for indicator warmup)
BACKTEST_TRADE_PERIOD_DAYS = 30 # Only count trades in the LAST 30 days
BACKTEST_LOT_SIZE = 15.0
BACKTEST_INITIAL_CAPITAL = STARTING_CAPITAL  # Initial capital for backtest
# 5 leverage səviyyəsi: 20x, 30x, 50x, 70x, 100x
BACKTEST_LEVERAGE_LIST = [20, 30, 50, 70, 100]
BACKTEST_LOT_SIZES = {
    20: 18.0,    # x20 → $18 lot (daha böyük, az leverage)
    30: 15.0,    # x30 → $15 lot (standard)
    50: 10.0,    # x50 → $10 lot (balanslaşdırılmış)
    70:  7.0,    # x70 → $7 lot (azaldılmış)
    100: 5.0,    # x100 → $5 lot (minimal, təhlükəsiz)
}
BACKTEST_MAX_LOSS_PER_TRADE_MAP = {
    20: 18.0,    # x20 → max $18 loss per trade
    30: 15.0,    # x30 → max $15 loss per trade
    50: 12.0,    # x50 → max $12 loss per trade
    70: 10.0,    # x70 → max $10 loss per trade
    100: 8.0,    # x100 → max $8 loss per trade
}

# Daily hard loss limit (applies to ALL leverage levels)
DAILY_HARD_LOSS_LIMIT = 15.0   # Stop ALL trading if daily loss >= $15 (7.5% of $200 balance)

# =============================================================================
#  LOGGING
# =============================================================================
LOG_DIR = "logs"
TRADE_LOG_FILE = "logs/trades.csv"
SIGNAL_LOG_FILE = "logs/signals.csv"
BOT_LOG_FILE = "logs/bot.log"

# =============================================================================
#  API RETRY SETTINGS
# =============================================================================
API_MAX_RETRIES = 3
API_RETRY_DELAY = 2             # seconds (base for exponential backoff)
API_TIMEOUT = 30                # seconds
