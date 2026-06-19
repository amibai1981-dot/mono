# XRP Scalping Bot — Binance

بوت تداول XRP سكالب تلقائي على منصة Binance.

## الملفات

| الملف | الوظيفة |
|---|---|
| `bot.py` | البوت الرئيسي للتداول الحي |
| `analyze.py` | تحليل فني شامل لـ XRP |
| `backtest.py` | اختبار الاستراتيجية على بيانات تاريخية |

## الإعداد

```bash
# 1. تثبيت المكتبات
pip install -r requirements.txt

# 2. إنشاء ملف الإعدادات
cp .env.example .env
# ثم عدّل .env وأضف مفاتيح Binance API

# 3. تحليل العملة أولاً
python analyze.py

# 4. اختبار الاستراتيجية على بيانات تاريخية
python backtest.py

# 5. تشغيل البوت (Testnet أولاً)
python bot.py
```

## الاستراتيجية

- **المؤشرات**: EMA 9/21 + RSI + Bollinger Bands
- **الإطار الزمني**: 1 دقيقة
- **وقف الخسارة**: 0.5%
- **هدف الربح**: 1.0%
- **نسبة المخاطرة/العائد**: 1:2

## إعدادات .env

```env
BINANCE_API_KEY=...
BINANCE_API_SECRET=...
TESTNET=true           # true للتجربة، false للتداول الحقيقي
TRADE_AMOUNT_USDT=10   # مبلغ كل صفقة
STOP_LOSS_PERCENT=0.5
TAKE_PROFIT_PERCENT=1.0
MAX_OPEN_TRADES=3
MAX_DAILY_LOSS_USDT=30
```

## ⚠️ تحذير

التداول الآلي ينطوي على مخاطر عالية. استخدم Testnet أولاً وتأكد من نتائج الاختبار الخلفي.
