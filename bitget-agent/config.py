"""
إعدادات بوت التداول الفوري على Bitget
أفضل إعدادات للتداول الآمن والمربح
"""

import os

# ── إعدادات API ──────────────────────────────────────────────
API_KEY        = os.getenv("BITGET_API_KEY", "")
API_SECRET     = os.getenv("BITGET_API_SECRET", "")
API_PASSPHRASE = os.getenv("BITGET_PASSPHRASE", "")
BASE_URL       = "https://api.bitget.com"
TESTNET_URL    = "https://api.bitget.com"   # Bitget لا يوفر testnet API مستقل
ENV            = os.getenv("BITGET_ENV", "mainnet")

# ── أزواج التداول المختارة (الأعلى سيولة وأقل خطر) ─────────
TRADING_PAIRS = [
    "BTCUSDT",   # بيتكوين — السيولة الأعلى
    "ETHUSDT",   # إيثريوم — استقرار ممتاز
    "SOLUSDT",   # سولانا — حركة جيدة
    "XRPUSDT",   # ريبل — حجم تداول عالي
    "BNBUSDT",   # بينانس كوين — سيولة عالية
]

# ── إعدادات استراتيجية الشبكة (Grid Trading) ─────────────────
GRID = {
    "enabled":          True,
    "num_grids":        30,       # عدد مستويات الشبكة (20-50 الأمثل)
    "grid_spacing_pct": 1.5,      # فجوة بين كل مستوى (1%-3%)
    "upper_pct":        15.0,     # الحد الأعلى فوق السعر الحالي (%)
    "lower_pct":        15.0,     # الحد الأدنى تحت السعر الحالي (%)
    "invest_per_grid":  10.0,     # USDT لكل مستوى شبكة
    "take_profit_pct":  0.8,      # ربح لكل صفقة شبكة (%)
    "reinvest":         True,     # إعادة استثمار الأرباح
}

# ── إعدادات استراتيجية DCA (Dollar Cost Averaging) ──────────
DCA = {
    "enabled":                  True,
    "base_order_usdt":          50.0,   # حجم الصفقة الأولى (USDT)
    "safety_order_usdt":        25.0,   # حجم كل أمر أمان
    "max_safety_orders":        6,      # أقصى عدد أوامر أمان
    "price_deviation_pct":      2.5,    # انخفاض % لتفعيل أمر أمان
    "safety_order_multiplier":  1.5,    # مضاعف حجم أوامر الأمان
    "deviation_multiplier":     1.2,    # مضاعف مسافة الانخفاض
    "take_profit_pct":          2.0,    # هدف الربح (%)
    "stop_loss_pct":            8.0,    # وقف الخسارة (%)
    "trailing_stop_enabled":    True,   # وقف خسارة متحرك
    "trailing_deviation_pct":   0.5,    # هامش الوقف المتحرك (%)
}

# ── إعدادات إدارة المخاطر ─────────────────────────────────────
RISK = {
    "max_portfolio_risk_pct":   20.0,   # أقصى نسبة من المحفظة في الصفقات
    "max_concurrent_positions": 3,      # أقصى عدد صفقات مفتوحة
    "max_risk_per_trade_pct":   2.0,    # أقصى خسارة لكل صفقة (من رأس المال)
    "min_usdt_balance":         50.0,   # احتياطي USDT لا يُلمس
    "daily_loss_limit_pct":     5.0,    # إيقاف التداول عند خسارة يومية (%)
    "weekly_loss_limit_pct":    10.0,   # إيقاف التداول عند خسارة أسبوعية (%)
}

# ── إعدادات المؤشرات الفنية ────────────────────────────────────
INDICATORS = {
    # RSI — مؤشر القوة النسبية
    "rsi_period":         14,
    "rsi_oversold":       30,    # شراء عند هذا المستوى
    "rsi_overbought":     70,    # بيع عند هذا المستوى

    # المتوسطات المتحركة
    "ema_fast":           9,     # EMA سريع
    "ema_slow":           21,    # EMA بطيء
    "ema_trend":          200,   # EMA اتجاه السوق

    # بولينجر باند
    "bb_period":          20,
    "bb_std_dev":         2.0,

    # MACD
    "macd_fast":          12,
    "macd_slow":          26,
    "macd_signal":        9,

    # حجم التداول
    "volume_ma_period":   20,    # متوسط حجم التداول
    "volume_spike_mult":  2.0,   # مضاعف ارتفاع الحجم للتأكيد
}

# ── إعدادات الأطر الزمنية ─────────────────────────────────────
TIMEFRAMES = {
    "primary":   "15m",    # الإطار الأساسي للتداول
    "trend":     "4h",     # تحديد الاتجاه العام
    "entry":     "5m",     # توقيت الدخول الدقيق
    "candles":   150,      # عدد الشموع للتحليل
}

# ── إعدادات الأوامر ───────────────────────────────────────────
ORDER = {
    "type":              "limit",     # limit أو market
    "post_only":         True,        # تجنب رسوم Taker
    "time_in_force":     "GTC",       # Good Till Cancelled
    "price_slippage":    0.1,         # أقصى انزلاق مقبول (%)
}

# ── إعدادات المراقبة والتحديث ─────────────────────────────────
MONITOR = {
    "refresh_seconds":       15,      # تحديث بيانات السوق كل 15 ثانية
    "balance_refresh":       60,      # تحديث الرصيد كل دقيقة
    "order_check_seconds":   5,       # التحقق من حالة الأوامر
    "log_level":             "INFO",  # مستوى السجلات
    "save_trades_log":       True,    # حفظ سجل الصفقات
}

# ── أفضل الأوقات للتداول (UTC) ───────────────────────────────
BEST_TRADING_HOURS = {
    "london_open":       "08:00",     # افتتاح لندن
    "new_york_open":     "13:00",     # افتتاح نيويورك
    "asia_open":         "00:00",     # افتتاح آسيا
    "avoid_hours":       ["22:00", "23:00", "00:00"],  # ساعات هادئة — تجنب
}

# ── رسوم التداول على Bitget ───────────────────────────────────
FEES = {
    "spot_maker": 0.001,   # 0.1% للـ Maker
    "spot_taker": 0.001,   # 0.1% للـ Taker (0.08% مع BGB)
}
