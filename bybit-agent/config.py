# ============================================================
#  WLD/USDT Scalping Bot — Config
#  Updated: 2026-06-19  |  Spot price ~0.6462
#  Strategy: Grid + RSI/EMA Scalping on 1m candles
# ============================================================

# --- API Credentials ---
API_KEY    = "KKKEnfIrH8uYaMC9aeabbAxhIw4AoFsRTuC8YgG7yXzhNPjMYReMrvAS7jcw6evw"
API_SECRET = "1yDIH0OjA57dw8mO9dqE1WV3hSkTXLk4MRNbEud1uRV3ING1osKPh5exoMlPVRp8"
TESTNET    = False

# --- Symbol ---
SYMBOL      = "WLDUSDT"
BASE_ASSET  = "WLD"
QUOTE_ASSET = "USDT"

# --- Capital Management ---
TOTAL_CAPITAL_USDT   = 40.0
MAX_POSITION_PCT     = 0.40       # max 40% of capital per position
PER_GRID_USDT        = 8.0        # تقسيم رأس المال على 5 مستويات (40/5)

# --- Grid Settings (مُحدَّث بناءً على السعر الحالي 0.6462) ---
# النطاق يغطي المدى الفعلي للساعتين الأخيرتين مع هامش أمان
GRID_LOWER_PRICE     = 0.6150     # دعم أسفل المدى الحالي
GRID_UPPER_PRICE     = 0.6700     # مقاومة أعلى المدى الحالي
GRID_LEVELS          = 5
GRID_PROFIT_PCT      = 0.005      # 0.5% ربح لكل مستوى (مناسب لسعر 0.65)

# --- RSI (مُضبط للسكالبينج في السوق الهابط قصير المدى) ---
RSI_PERIOD           = 7
RSI_OVERSOLD         = 38         # أكثر حساسية في السوق الهابط
RSI_OVERBOUGHT       = 63

# --- EMA (مُضبط للسكالبينج السريع) ---
EMA_FAST             = 3          # أسرع استجابة على 1m
EMA_SLOW             = 8          # إشارة اتجاه قصير
VOLUME_FILTER        = True       # تفعيل فلتر الحجم لتجنب الإشارات الوهمية
VOLUME_MULTIPLIER    = 1.2        # يشترط حجم أعلى من المتوسط

# --- Risk Management ---
STOP_LOSS_PCT        = 0.012      # 1.2% وقف خسارة (مناسب لتقلب WLD)
TAKE_PROFIT_PCT      = 0.007      # 0.7% هدف ربح
TRAILING_STOP_PCT    = 0.004      # 0.4% تريلينج ستوب
MAX_OPEN_ORDERS      = 3
MAX_DAILY_TRADES     = 50

# --- Timing (مُحسَّن للسكالبينج) ---
CANDLE_INTERVAL      = "1m"       # 1 دقيقة بدلاً من 5m للسكالبينج الحقيقي
LOOP_SLEEP_SEC       = 5          # استطلاع كل 5 ثوانٍ
ORDER_TIMEOUT_MIN    = 3          # إلغاء الأوامر المعلقة بعد 3 دقائق

# --- Logging ---
LOG_FILE             = "logs/wld_bot.log"
LOG_LEVEL            = "INFO"
TRADE_LOG_FILE       = "logs/wld_trades.csv"

# --- Telegram Notifications ---
TELEGRAM_ENABLED     = False
TELEGRAM_TOKEN       = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID     = "YOUR_CHAT_ID"
