"""
WLD/USDT Trading Bot Configuration
Scalping Strategy — 5 minute timeframe
"""

# ─── Binance API ───────────────────────────────────────────────────────────────
API_KEY    = "YOUR_BINANCE_API_KEY"
API_SECRET = "YOUR_BINANCE_API_SECRET"
TESTNET    = False         # ← True للاختبار / False للحقيقي

# ─── Trading Pair ──────────────────────────────────────────────────────────────
SYMBOL      = "WLDUSDT"
BASE_ASSET  = "WLD"
QUOTE_ASSET = "USDT"

# ─── Capital Management ────────────────────────────────────────────────────────
TOTAL_CAPITAL_USDT   = 200.0    # رأس المال الكلي
MAX_POSITION_PCT     = 0.40     # أقصى 40% في صفقة واحدة
PER_GRID_USDT        = 40.0     # حجم كل صفقة سكالب

# ─── Scalping Grid ─────────────────────────────────────────────────────────────
GRID_LOWER_PRICE     = 1.00     # أدنى سعر (يتحدث تلقائياً مع السوق)
GRID_UPPER_PRICE     = 9.99     # أعلى سعر
GRID_LEVELS          = 5        # عدد مستويات أقل — سكالب سريع
GRID_PROFIT_PCT      = 0.004    # ربح 0.4% لكل صفقة (سكالب)

# ─── RSI Scalping ──────────────────────────────────────────────────────────────
RSI_PERIOD           = 7        # فترة أقصر للسكالب
RSI_OVERSOLD         = 40       # شراء عند RSI < 40 (أسرع دخول)
RSI_OVERBOUGHT       = 60       # بيع عند RSI > 60 (أسرع خروج)

# ─── Scalping Indicators ───────────────────────────────────────────────────────
EMA_FAST             = 5        # EMA سريع
EMA_SLOW             = 13       # EMA بطيء
VOLUME_FILTER        = True     # شراء فقط عند ارتفاع الحجم
VOLUME_MULTIPLIER    = 1.2      # الحجم يجب أن يكون 1.2x فوق المتوسط

# ─── Scalping Risk Management ──────────────────────────────────────────────────
STOP_LOSS_PCT        = 0.008    # وقف خسارة 0.8% (ضيق للسكالب)
TAKE_PROFIT_PCT      = 0.006    # هدف ربح 0.6% سريع
TRAILING_STOP_PCT    = 0.003    # وقف متحرك 0.3%
MAX_OPEN_ORDERS      = 3        # صفقات مفتوحة أقل للسكالب
MAX_DAILY_TRADES     = 50       # أقصى عدد صفقات يومياً

# ─── Timing — Scalping ─────────────────────────────────────────────────────────
CANDLE_INTERVAL      = "5m"     # فريم 5 دقائق
LOOP_SLEEP_SEC       = 10       # فحص كل 10 ثواني (سريع)
ORDER_TIMEOUT_MIN    = 5        # إلغاء الأوامر بعد 5 دقائق فقط

# ─── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE             = "logs/wld_bot.log"
LOG_LEVEL            = "INFO"
TRADE_LOG_FILE       = "logs/wld_trades.csv"

# ─── Notifications (Telegram) ──────────────────────────────────────────────────
TELEGRAM_ENABLED     = False
TELEGRAM_TOKEN       = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID     = "YOUR_CHAT_ID"
