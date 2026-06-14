#!/bin/bash
# إعداد بوت تداول Binance

echo "=== إعداد Binance Trading Bot ==="

# تثبيت المكتبات المطلوبة
echo "تثبيت المكتبات..."
pip3 install requests python-dotenv 2>/dev/null || pip install requests python-dotenv

# إنشاء ملف .env إذا لم يكن موجوداً
if [ ! -f .env ]; then
    cat > .env <<EOF
BINANCE_API_KEY=ضع_مفتاح_API_هنا
BINANCE_SECRET_KEY=ضع_المفتاح_السري_هنا
BINANCE_ENV=testnet
SYMBOL=BTCUSDT
TRADE_AMOUNT=10
RSI_PERIOD=14
RSI_OVERBOUGHT=70
RSI_OVERSOLD=30
EMA_FAST=9
EMA_SLOW=21
REFRESH_SECONDS=60
EOF
    echo "✓ تم إنشاء ملف .env — عدّل القيم قبل التشغيل"
else
    echo "✓ ملف .env موجود مسبقاً"
fi

echo ""
echo "=== جاهز للتشغيل ==="
echo "مراقبة السوق:          python3 bot.py monitor"
echo "تشغيل استراتيجية RSI:  python3 bot.py rsi"
echo "تشغيل استراتيجية EMA:  python3 bot.py ema"
echo "عرض الرصيد:            python3 bot.py balance"
echo "عرض الصفقات المفتوحة: python3 bot.py orders"
