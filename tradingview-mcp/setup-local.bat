@echo off
chcp 65001 >nul
echo.
echo ════════════════════════════════════════
echo   TradingView MCP - Windows Setup
echo ════════════════════════════════════════
echo.

:: التحقق من Node.js
node --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js غير مثبت
  echo حمله من: https://nodejs.org
  pause
  exit /b 1
)
echo [OK] Node.js موجود:
node --version

:: التحقق من npm
npm --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] npm غير موجود
  pause
  exit /b 1
)
echo [OK] npm موجود

echo.
echo [1/3] تثبيت الحزم...
call npm install
if errorlevel 1 (
  echo [ERROR] فشل npm install
  pause
  exit /b 1
)
echo [OK] الحزم مثبتة

echo.
echo [2/3] تثبيت متصفح Chromium...
call npx playwright install chromium
if errorlevel 1 (
  echo [ERROR] فشل تثبيت Chromium
  pause
  exit /b 1
)
echo [OK] Chromium مثبت

echo.
echo [3/3] إعداد Codex MCP...

set CONFIG_DIR=%USERPROFILE%\.codex
if not exist "%CONFIG_DIR%" mkdir "%CONFIG_DIR%"

set SCRIPT_DIR=%~dp0
set SCRIPT_DIR=%SCRIPT_DIR:~0,-1%

(
echo [mcp.tradingview]
echo name = "tradingview-mcp"
echo command = "node"
echo args = ["%SCRIPT_DIR:\=\\%\\server.js"]
echo enabled = true
echo description = "TradingView live reader - UAE stocks and crypto"
echo.
echo [settings]
echo auto_approve_tools = ["get_chart_data", "get_quote", "morning_brief", "analyze_scalp", "scan_uae_market"]
) > "%CONFIG_DIR%\config.toml"

echo [OK] config.toml تم في: %CONFIG_DIR%\config.toml

echo.
echo [اختبار] فحص الاتصال بـ TradingView...
node -e "import('playwright').then(async ({chromium})=>{const b=await chromium.launch({headless:true});const p=await b.newPage();await p.goto('https://www.tradingview.com',{waitUntil:'domcontentloaded',timeout:15000});console.log('[OK] TradingView متصل:',await p.title());await b.close();}).catch(e=>console.log('[ERROR]',e.message));"

echo.
echo ════════════════════════════════════════
echo   الإعداد اكتمل!
echo ════════════════════════════════════════
echo.
echo الخطوة التالية:
echo   1. افتح Command Prompt جديد
echo   2. اكتب: codex
echo   3. قل: صباح الخير - امسح الاسهم الاماراتية
echo.
pause
