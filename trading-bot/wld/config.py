"""
WLD/USDT Trading Bot Configuration
Professional settings for large traders
"""

# ─── Binance API ───────────────────────────────────────────────────────────────
API_KEY    = "YOUR_BINANCE_API_KEY"
API_SECRET = "YOUR_BINANCE_API_SECRET"
TESTNET    = True          # ← اجعلها False عند التداول الحقيقي

# ─── Trading Pair ──────────────────────────────────────────────────────────────
SYMBOL      = "WLDUSDT"
BASE_ASSET  = "WLD"
QUOTE_ASSET = "USDT"

# ─── Capital Management ────────────────────────────────────────────────────────
TOTAL_CAPITAL_USDT   = 1000.0   # رأس المال الكلي بالـ USDT
MAX_POSITION_PCT     = 0.30     # أقصى 30% من رأس المال في صفقة واحدة
PER_GRID_USDT        = 50.0     # حجم كل شبكة بالـ USDT

# ─── Grid Strategy ─────────────────────────────────────────────────────────────
GRID_LOWER_PRICE     = 1.20     # أدنى سعر للشبكة (USDT)
GRID_UPPER_PRICE     = 2.00     # أعلى سعر للشبكة (USDT)
GRID_LEVELS          = 8        # عدد مستويات الشبكة
GRID_PROFIT_PCT      = 0.012    # نسبة الربح لكل خطوة (1.2%)

# ─── RSI Filter ────────────────────────────────────────────────────────────────
RSI_PERIOD           = 14
RSI_OVERSOLD         = 35       # شراء عند RSI < 35
RSI_OVERBOUGHT       = 65       # بيع عند RSI > 65

# ─── Risk Management ───────────────────────────────────────────────────────────
STOP_LOSS_PCT        = 0.05     # وقف خسارة 5% من سعر الشراء
TAKE_PROFIT_PCT      = 0.08     # هدف ربح 8% من سعر الشراء
TRAILING_STOP_PCT    = 0.03     # وقف خسارة متحرك 3%
MAX_OPEN_ORDERS      = 10       # أقصى عدد أوامر مفتوحة

# ─── Timing ────────────────────────────────────────────────────────────────────
CANDLE_INTERVAL      = "15m"    # الفريم الزمني للتحليل
LOOP_SLEEP_SEC       = 30       # الفحص كل 30 ثانية
ORDER_TIMEOUT_MIN    = 60       # إلغاء الأوامر بعد 60 دقيقة

# ─── Logging ───────────────────────────────────────────────────────────────────
LOG_FILE             = "logs/wld_bot.log"
LOG_LEVEL            = "INFO"
TRADE_LOG_FILE       = "logs/wld_trades.csv"

# ─── Notifications (Telegram) ──────────────────────────────────────────────────
TELEGRAM_ENABLED     = False
TELEGRAM_TOKEN       = "YOUR_TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID     = "YOUR_CHAT_ID"
