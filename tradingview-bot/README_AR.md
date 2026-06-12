# بوت التداول التلقائي — TradingView + Bybit + Claude AI

---

## نظرة عامة

هذا المشروع يربط تنبيهات TradingView بمنصة Bybit عبر:

1. **Webhook Server** (FastAPI) يستقبل التنبيهات من TradingView.
2. **Claude AI** (claude-sonnet-4-6) يحلل الإشارة ويقرر: شراء / بيع / انتظار.
3. **Bybit Client** ينفذ الأوامر تلقائياً باستخدام مفتاح RSA.

---

## متطلبات التشغيل

- Python 3.11+
- مفتاح API من Bybit (RSA)
- مفتاح API من Anthropic
- خادم يمكن الوصول إليه من الإنترنت (أو ngrok للاختبار)

---

## متغيرات البيئة المطلوبة

أنشئ ملف `.env` في مجلد `tradingview-bot/`:

```env
# Bybit
BYBIT_API_KEY=your_bybit_api_key
BYBIT_PRIVATE_KEY_PATH=/path/to/private.pem
BYBIT_ENV=testnet          # testnet أو mainnet

# Anthropic
ANTHROPIC_API_KEY=your_anthropic_api_key

# Webhook
WEBHOOK_SECRET=choose_a_long_random_secret

# إدارة المخاطر
MAX_TRADE_SIZE_USDT=100    # الحد الأقصى لحجم الصفقة بالدولار
RISK_PER_TRADE_PCT=1       # نسبة الرصيد المستخدمة لكل صفقة (%)

# الخادم (اختياري)
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=INFO
```

---

## إنشاء مفتاح RSA لـ Bybit

```bash
# إنشاء المفتاح الخاص
openssl genrsa -out private.pem 2048

# استخراج المفتاح العام
openssl rsa -in private.pem -pubout -out public.pem
```

ثم انسخ محتوى `public.pem` إلى إعدادات Bybit API.

---

## التثبيت والتشغيل

```bash
# الانتقال إلى مجلد المشروع
cd tradingview-bot

# تثبيت المكتبات
pip install -r requirements.txt

# تشغيل الخادم
python server.py
```

أو باستخدام uvicorn مباشرة:

```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

---

## إعداد تنبيه TradingView

### الخطوة 1: إنشاء التنبيه في TradingView

1. افتح الرسم البياني في TradingView.
2. اضغط على **Alert** (أيقونة الجرس) أو `Alt+A`.
3. في قسم **Notifications**، فعّل **Webhook URL**.
4. أدخل رابط الـ Webhook:
   ```
   https://your-server.com/webhook
   ```
   أو للاختبار المحلي مع ngrok:
   ```
   https://xxxx.ngrok.io/webhook
   ```

### الخطوة 2: تنسيق رسالة التنبيه (JSON)

في حقل **Message** في TradingView، أدخل JSON بهذا التنسيق:

```json
{
  "secret": "YOUR_WEBHOOK_SECRET",
  "symbol": "{{ticker}}",
  "action": "buy",
  "price": {{close}},
  "interval": "{{interval}}",
  "indicators": {
    "rsi": 45,
    "ema_fast": {{plot_0}},
    "ema_slow": {{plot_1}}
  },
  "message": "EMA crossover bullish signal"
}
```

**ملاحظات:**
- `{{ticker}}` — يُستبدل تلقائياً برمز العملة (مثال: BTCUSDT).
- `{{close}}` — سعر الإغلاق الحالي.
- `{{interval}}` — الإطار الزمني.
- `{{plot_0}}`, `{{plot_1}}` — قيم المؤشرات من Pine Script.
- `action` يجب أن يكون: `buy` أو `sell` أو `hold`.
- `secret` يجب أن يطابق قيمة `WEBHOOK_SECRET` في ملف `.env`.

---

## مثال Pine Script لإرسال التنبيه

```pine
//@version=5
strategy("EMA Crossover Bot", overlay=true)

ema_fast = ta.ema(close, 9)
ema_slow = ta.ema(close, 21)

buy_signal  = ta.crossover(ema_fast, ema_slow)
sell_signal = ta.crossunder(ema_fast, ema_slow)

if buy_signal
    alert('{"secret":"YOUR_SECRET","symbol":"' + syminfo.ticker + '","action":"buy","price":' + str.tostring(close) + ',"interval":"' + timeframe.period + '","indicators":{"rsi":' + str.tostring(ta.rsi(close,14)) + ',"ema_fast":' + str.tostring(ema_fast) + ',"ema_slow":' + str.tostring(ema_slow) + '},"message":"EMA crossover bullish"}', alert.freq_once_per_bar)

if sell_signal
    alert('{"secret":"YOUR_SECRET","symbol":"' + syminfo.ticker + '","action":"sell","price":' + str.tostring(close) + ',"interval":"' + timeframe.period + '","indicators":{"rsi":' + str.tostring(ta.rsi(close,14)) + ',"ema_fast":' + str.tostring(ema_fast) + ',"ema_slow":' + str.tostring(ema_slow) + '},"message":"EMA crossover bearish"}', alert.freq_once_per_bar)

plot(ema_fast, "EMA Fast", color.green)
plot(ema_slow, "EMA Slow", color.red)
```

---

## نقاط النهاية (API Endpoints)

| الطريقة | المسار      | الوصف                    |
|---------|-------------|--------------------------|
| GET     | `/health`   | التحقق من حالة الخادم    |
| POST    | `/webhook`  | استقبال تنبيهات TradingView |

---

## مثال على الاستجابة

```json
{
  "symbol": "BTCUSDT",
  "signal_action": "buy",
  "decision": {
    "action": "buy",
    "size_pct": 50,
    "reason": "RSI at 45 (neutral-bullish), EMA fast crossed above EMA slow. Buying with moderate size."
  },
  "trade_executed": true,
  "order": {
    "orderId": "abc123",
    "symbol": "BTCUSDT",
    "side": "Buy",
    "orderType": "Market",
    "qty": "0.001"
  },
  "error": null
}
```

---

## الاختبار المحلي مع ngrok

```bash
# تثبيت ngrok
pip install ngrok

# تشغيل البوت
python server.py &

# فتح نفق ngrok
ngrok http 8000
```

استخدم الرابط الذي يظهر (مثل `https://xxxx.ngrok.io`) كـ Webhook URL في TradingView.

---

## الأمان

- **لا تشارك** `WEBHOOK_SECRET` أو مفاتيح API مع أحد.
- استخدم `testnet` دائماً أثناء الاختبار قبل التحويل إلى `mainnet`.
- راجع ملف السجل `tradingview_bot.log` بانتظام لمراقبة النشاط.
- تأكد من أن ملف `private.pem` محمي: `chmod 600 private.pem`.

---

## هيكل الملفات

```
tradingview-bot/
├── server.py           # خادم FastAPI يستقبل Webhook
├── bybit_client.py     # عميل Bybit مع توقيع RSA
├── claude_analyzer.py  # محلل Claude AI باستخدام Tool Use
├── config.py           # إعدادات متغيرات البيئة
├── requirements.txt    # المكتبات المطلوبة
├── README_AR.md        # هذا الملف
└── .env                # متغيرات البيئة (لا ترفعه لـ Git)
```
