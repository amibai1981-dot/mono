# WLD/USDT Trading Bot — بوت تداول آلي احترافي

بوت تداول آلي لعملة **Worldcoin (WLD)** على منصة Binance يجمع بين:
- **Grid Trading** — شبكة أوامر بين سعرين
- **RSI Filter** — يشتري فقط عند الإفراط في البيع
- **EMA Trend** — يتجنب الشراء في الاتجاه الهبوطي
- **Risk Management** — وقف خسارة + هدف ربح + وقف متحرك
- **Telegram Alerts** — إشعارات فورية

---

## الملفات

```
trading-bot/wld/
├── config.py        ← إعدادات البوت (API، أسعار، استراتيجية)
├── bot.py           ← المحرك الرئيسي
├── exchange.py      ← Binance API wrapper
├── grid_manager.py  ← إدارة شبكة الأوامر
├── risk_manager.py  ← إدارة المخاطر
├── indicators.py    ← RSI، EMA، Bollinger، ATR
├── notifier.py      ← إشعارات Telegram
└── backtest.py      ← اختبار تاريخي
```

---

## التثبيت

```bash
pip install -r requirements.txt
```

---

## الإعداد

افتح `config.py` وعدّل:

```python
API_KEY    = "مفتاح API من Binance"
API_SECRET = "السر"
TESTNET    = True   # False للتداول الحقيقي

GRID_LOWER_PRICE = 1.20   # سعر الشراء الأدنى
GRID_UPPER_PRICE = 2.00   # سعر البيع الأعلى
GRID_LEVELS      = 8      # عدد مستويات الشبكة
PER_GRID_USDT    = 50.0   # حجم كل صفقة بالـ USDT
```

---

## التشغيل

```bash
# Testnet أولاً للاختبار
cd trading-bot/wld
python bot.py

# اختبار تاريخي على آخر 60 يوم
python backtest.py --symbol WLDUSDT --days 60
```

---

## الاستراتيجية بالتفصيل

| المرحلة | الشرط | الإجراء |
|---------|-------|---------|
| شراء    | RSI < 35 + EMA fast > EMA slow + السعر في نطاق الشبكة | أمر شراء عند مستوى الشبكة |
| بيع     | السعر يصل هدف الشبكة (1.2% ربح) | أمر بيع محدد |
| وقف خسارة | انخفاض 5% من سعر الدخول | بيع فوري بالسوق |
| هدف ربح | ارتفاع 8% من سعر الدخول | بيع بالحد |
| وقف متحرك | انخفاض 3% من أعلى سعر | بيع فوري |
| إيقاف يومي | خسارة 5% من رأس المال | إيقاف البوت لبقية اليوم |

---

## ⚠️ تحذير

التداول الآلي ينطوي على مخاطر حقيقية. ابدأ دائماً بـ **Testnet**
ثم بمبالغ صغيرة قبل رفع رأس المال.
