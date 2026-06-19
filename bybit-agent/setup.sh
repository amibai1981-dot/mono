#!/bin/bash
# إعداد الوكيل على جهازك المحلي

echo "=== إعداد Bybit Agent ==="

# 1. توليد مفاتيح RSA
if [ ! -f private.pem ]; then
    echo "توليد مفاتيح RSA..."
    openssl genrsa -out private.pem 4096
    openssl rsa -in private.pem -pubout -out public.pem
    chmod 600 private.pem
    echo "✓ تم توليد المفاتيح"
    echo ""
    echo "=== المفتاح العام (ارفعه إلى Bybit) ==="
    cat public.pem
else
    echo "✓ المفاتيح موجودة مسبقاً"
fi

# 2. إنشاء ملف .env
if [ ! -f .env ]; then
    cat > .env <<EOF
BYBIT_API_KEY=OOtP0fbulyroD2LAHI
BYBIT_API_PRIVATE_KEY_PATH=$(pwd)/private.pem
BYBIT_ENV=mainnet
REFRESH_SECONDS=10
WEBHOOK_SECRET=change_me_to_a_strong_secret
WEBHOOK_PORT=8080
EOF
    echo "✓ تم إنشاء ملف .env"
fi

echo ""
echo "=== جاهز للتشغيل ==="
echo "مراقبة السوق:  python3 monitor.py monitor"
echo "عرض الرصيد:    python3 monitor.py balance"
echo "الاثنان معاً:  python3 monitor.py all"
echo "Webhook:       python3 webhook.py"
