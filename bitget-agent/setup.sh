#!/bin/bash
# ====================================================
# إعداد بوت التداول الفوري على Bitget
# ====================================================

echo "==================================================="
echo "  إعداد Bitget Spot Trading Bot"
echo "==================================================="

# التحقق من Python
if ! command -v python3 &>/dev/null; then
    echo "✗ Python3 غير مثبت"
    exit 1
fi
echo "✓ Python3 متاح: $(python3 --version)"

# إنشاء ملف .env إذا لم يكن موجوداً
if [ ! -f .env ]; then
    cat > .env <<'EOF'
# ─────────────────────────────────────────────────────────
# مفاتيح Bitget API
# احصل عليها من: Bitget > الإعدادات > إدارة API
# ─────────────────────────────────────────────────────────

BITGET_API_KEY=ضع_مفتاح_API_هنا
BITGET_API_SECRET=ضع_السر_هنا
BITGET_PASSPHRASE=ضع_كلمة_المرور_هنا
BITGET_ENV=mainnet
EOF
    echo "✓ تم إنشاء ملف .env — يرجى تعبئة مفاتيح API"
else
    echo "✓ ملف .env موجود مسبقاً"
fi

echo ""
echo "==================================================="
echo "  كيفية الحصول على مفاتيح API:"
echo "  1. سجل دخول على Bitget"
echo "  2. اذهب إلى: الإعدادات > إدارة API"
echo "  3. أنشئ مفتاح جديد مع صلاحية: Trade + Read"
echo "  4. احفظ: API Key + Secret Key + Passphrase"
echo "  5. ضعها في ملف .env"
echo "==================================================="
echo ""
echo "  أوامر التشغيل:"
echo "  ─────────────────────────────────────────────────"
echo "  مراقبة السوق:    python3 bot.py market"
echo "  تحليل فني:       python3 bot.py analysis"
echo "  عرض الرصيد:      python3 bot.py balance"
echo "  تشغيل البوت:     python3 bot.py bot"
echo "==================================================="
