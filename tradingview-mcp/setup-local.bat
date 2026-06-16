@echo off
echo.
echo ============================================
echo   TradingView MCP - Windows Setup
echo ============================================
echo.

node --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] Node.js not found. Download from: https://nodejs.org
  pause
  exit /b 1
)
echo [OK] Node.js found:
node --version

npm --version >nul 2>&1
if errorlevel 1 (
  echo [ERROR] npm not found
  pause
  exit /b 1
)
echo [OK] npm found:
npm --version

echo.
echo [1/3] Installing packages...
call npm install
if errorlevel 1 (
  echo [ERROR] npm install failed
  pause
  exit /b 1
)
echo [OK] Packages installed

echo.
echo [2/3] Installing Chromium browser...
call npx playwright install chromium
if errorlevel 1 (
  echo [ERROR] Chromium install failed
  pause
  exit /b 1
)
echo [OK] Chromium installed

echo.
echo [3/3] Configuring Codex MCP...

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
echo.
echo [settings]
echo auto_approve_tools = ["get_chart_data", "get_quote", "morning_brief", "analyze_scalp", "scan_uae_market"]
) > "%CONFIG_DIR%\config.toml"

echo [OK] Codex config saved to: %CONFIG_DIR%\config.toml

echo.
echo [Test] Checking TradingView connection...
node -e "import('playwright').then(async ({chromium})=>{const b=await chromium.launch({headless:true});const p=await b.newPage();await p.goto('https://www.tradingview.com',{waitUntil:'domcontentloaded',timeout:15000});console.log('[OK] TradingView connected:',await p.title());await b.close();}).catch(e=>console.log('[ERROR]',e.message));"

echo.
echo ============================================
echo   Setup Complete!
echo ============================================
echo.
echo Next steps:
echo   1. Open a new Command Prompt
echo   2. Type: codex
echo   3. Say: morning brief for UAE stocks and crypto
echo.
pause
