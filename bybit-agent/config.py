# ============================================================
#  WLD/USDT Scalping Bot — Config
#  Exchange: Binance Spot
#  Updated: 2026-06-19  |  Spot price ~0.6462
# ============================================================

# --- Binance API ---
API_KEY    = "KKKEnfIrH8uYaMC9aeabbAxhIw4AoFsRTuC8YgG7yXzhNPjMYReMrvAS7jcw6evw"
API_SECRET = "1yDIH0OjA57dw8mO9dqE1WV3hSkTXLk4MRNbEud1uRV3ING1osKPh5exoMlPVRp8"
TESTNET    = False   # True = testnet.binance.vision

# --- Symbol ---
SYMBOL      = "WLDUSDT"
BASE_ASSET  = "WLD"
QUOTE_ASSET = "USDT"

# --- Capital ---
TOTAL_CAPITAL_USDT = 40.0
MAX_POSITION_PCT   = 0.40
PER_GRID_USDT      = 8.0       # 40 / 5 مستويات

# --- Grid (مُحدَّث للسعر الحالي 0.6462) ---
GRID_LOWER_PRICE = 0.6150
GRID_UPPER_PRICE = 0.6700
GRID_LEVELS      = 5
GRID_PROFIT_PCT  = 0.005

# --- RSI ---
RSI_PERIOD    = 7
RSI_OVERSOLD  = 38
RSI_OVERBOUGHT = 63

# --- EMA ---
EMA_FAST          = 3
EMA_SLOW          = 8
VOLUME_FILTER     = True
VOLUME_MULTIPLIER = 1.2

# --- Risk ---
STOP_LOSS_PCT     = 0.012
TAKE_PROFIT_PCT   = 0.007
TRAILING_STOP_PCT = 0.004
MAX_OPEN_ORDERS   = 3
MAX_DAILY_TRADES  = 50

# --- Timing ---
CANDLE_INTERVAL  = "1m"
LOOP_SLEEP_SEC   = 5
ORDER_TIMEOUT_MIN = 3

# --- Logs ---
LOG_FILE       = "logs/wld_bot.log"
LOG_LEVEL      = "INFO"
TRADE_LOG_FILE = "logs/wld_trades.csv"

# --- Telegram ---
TELEGRAM_ENABLED = False
TELEGRAM_TOKEN   = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID = "YOUR_CHAT_ID"
