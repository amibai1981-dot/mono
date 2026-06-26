# Binance Trading Bot 🤖

بوت تداول آلي احترافي لمنصة Binance مع استراتيجية متعددة المؤشرات.

## الاستراتيجية

يستخدم البوت **توافق المؤشرات (Confluence)** — يتطلب 3 إشارات على الأقل من 6 مؤشرات لتأكيد الصفقة:

| المؤشر | إشارة الشراء | إشارة البيع |
|--------|-------------|-------------|
| **RSI (14)** | < 35 (oversold) | > 65 (overbought) |
| **MACD (12,26,9)** | تقاطع صاعد | تقاطع هابط |
| **Bollinger Bands** | السعر عند الحد الأدنى | السعر عند الحد الأعلى |
| **EMA 9/21** | EMA9 > EMA21 | EMA9 < EMA21 |
| **EMA 50 (Trend)** | السعر > EMA50 | السعر < EMA50 |
| **Volume** | حجم > 1.5x المتوسط | حجم > 1.5x المتوسط |

## إدارة المخاطر

- **Stop Loss**: 2% من سعر الدخول
- **Take Profit**: 4% من سعر الدخول (نسبة ربح/خسارة 2:1)
- **Trailing Stop**: 1.5% يتحرك مع السعر لحماية الأرباح
- **Max Positions**: 3 صفقات مفتوحة في نفس الوقت
- **Risk per Trade**: 1% من رأس المال

## التثبيت

```bash
cd binance-bot
pip install -r requirements.txt
cp .env.example .env
# عدّل .env بمفاتيح API الخاصة بك
```

## الإعداد

```bash
# .env
BINANCE_API_KEY=your_key
BINANCE_API_SECRET=your_secret
TRADING_MODE=PAPER          # PAPER للاختبار، LIVE للتداول الحقيقي
TRADING_PAIRS=BTCUSDT,ETHUSDT,BNBUSDT,SOLUSDT
TIMEFRAME=15m
MAX_POSITION_SIZE_USDT=100
```

## الاستخدام

```bash
# تشغيل البوت (Paper Trading افتراضياً)
python bot.py

# اختبار الاستراتيجية على البيانات التاريخية
python backtest.py --symbol BTCUSDT --interval 15m --days 30
python backtest.py --symbol ETHUSDT --interval 1h --days 60
```

## تنبيهات تيليغرام (اختياري)

1. أنشئ بوت تيليغرام عبر @BotFather
2. احصل على `BOT_TOKEN` و `CHAT_ID`
3. أضفهما في `.env`

## تحذير مهم ⚠️

- **ابدأ دائماً بـ PAPER trading** قبل المخاطرة بأموال حقيقية
- التداول الآلي ينطوي على مخاطر خسارة رأس المال
- لا يُعدّ هذا نصيحة مالية

## هيكل الملفات

```
binance-bot/
├── bot.py          # البوت الرئيسي
├── strategy.py     # منطق الاستراتيجية
├── risk_manager.py # إدارة المخاطر والمراكز
├── exchange.py     # تكامل Binance API + Paper Trading
├── notifier.py     # تنبيهات تيليغرام
├── backtest.py     # اختبار الاستراتيجية تاريخياً
├── config.py       # الإعدادات
└── .env.example    # مثال على المتغيرات البيئية
```
