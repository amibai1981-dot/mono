#!/bin/bash
# إعداد TradingView MCP على جهازك المحلي

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo "════════════════════════════════════════"
echo "  TradingView MCP — إعداد الأسهم الإماراتية"
echo "════════════════════════════════════════"
echo ""

# 1. التحقق من Node.js
if ! command -v node &> /dev/null; then
  echo -e "${RED}❌ Node.js غير مثبّت. حمّله من: https://nodejs.org${NC}"
  exit 1
fi
echo -e "${GREEN}✅ Node.js $(node --version)${NC}"

# 2. تثبيت المتطلبات
echo ""
echo "🔄 تثبيت الحزم..."
npm install

# 3. تثبيت متصفح Playwright
echo ""
echo "🔄 تثبيت متصفح Chromium..."
npx playwright install chromium

# 4. اكتشاف نظام التشغيل وإنشاء إعداد Codex
echo ""
echo "🔄 إعداد Codex MCP..."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OS="$(uname -s)"

if [[ "$OS" == "Darwin" ]]; then
  CONFIG_DIR="$HOME/.codex"
elif [[ "$OS" == "Linux" ]]; then
  CONFIG_DIR="$HOME/.codex"
else
  CONFIG_DIR="$APPDATA/codex"
fi

mkdir -p "$CONFIG_DIR"

cat > "$CONFIG_DIR/config.toml" << EOF
[mcp.tradingview]
name = "tradingview-mcp"
command = "node"
args = ["$SCRIPT_DIR/server.js"]
enabled = true
description = "TradingView live reader — UAE stocks & crypto scalping"

[settings]
auto_approve_tools = ["get_chart_data", "get_quote", "morning_brief", "analyze_scalp"]
EOF

echo -e "${GREEN}✅ config.toml تم في: $CONFIG_DIR/config.toml${NC}"

# 5. اختبار الاتصال
echo ""
echo "🔄 اختبار الاتصال بـ TradingView..."

node -e "
import('playwright').then(async ({ chromium }) => {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();
  await page.goto('https://www.tradingview.com', { waitUntil: 'domcontentloaded', timeout: 15000 });
  const title = await page.title();
  console.log('✅ TradingView متصل:', title);
  await browser.close();
}).catch(e => {
  console.log('❌ فشل الاتصال:', e.message);
  process.exit(1);
});
" 2>/dev/null

echo ""
echo "════════════════════════════════════════"
echo -e "${GREEN}  ✅ الإعداد اكتمل بنجاح!${NC}"
echo "════════════════════════════════════════"
echo ""
echo "الخطوة التالية:"
echo "  1. شغّل Codex: codex"
echo "  2. انسخ والصق هذا الأمر:"
echo ""
echo '  "صباح الخير — حلّل قائمة الأسهم الإماراتية'
echo '   وأخبرني أي سهم فيه فرصة سكالب الآن"'
echo ""
