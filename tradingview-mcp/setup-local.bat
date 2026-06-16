@echo off
echo === Step 1: npm install ===
npm install
echo.
echo === Step 2: Install Chromium ===
npx playwright install chromium
echo.
echo === Step 3: Create Codex config ===
if not exist "%USERPROFILE%\.codex" mkdir "%USERPROFILE%\.codex"
(
echo [mcp.tradingview]
echo name = "tradingview-mcp"
echo command = "node"
echo args = ["%CD:\=\\%\\server.js"]
echo enabled = true
echo.
echo [settings]
echo auto_approve_tools = ["get_chart_data", "get_quote", "morning_brief", "analyze_scalp", "scan_uae_market"]
) > "%USERPROFILE%\.codex\config.toml"
echo Config saved to: %USERPROFILE%\.codex\config.toml
echo.
echo === Done! Now run: codex ===
pause
