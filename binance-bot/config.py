import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # API
    API_KEY = os.getenv("BINANCE_API_KEY", "")
    API_SECRET = os.getenv("BINANCE_API_SECRET", "")

    # Mode
    TRADING_MODE = os.getenv("TRADING_MODE", "PAPER").upper()
    IS_LIVE = TRADING_MODE == "LIVE"

    # Risk Management
    MAX_POSITION_SIZE_USDT = float(os.getenv("MAX_POSITION_SIZE_USDT", 100))
    MAX_OPEN_POSITIONS = int(os.getenv("MAX_OPEN_POSITIONS", 3))
    RISK_PER_TRADE_PERCENT = float(os.getenv("RISK_PER_TRADE_PERCENT", 1.0))
    STOP_LOSS_PERCENT = float(os.getenv("STOP_LOSS_PERCENT", 2.0))
    TAKE_PROFIT_PERCENT = float(os.getenv("TAKE_PROFIT_PERCENT", 4.0))
    TRAILING_STOP_PERCENT = float(os.getenv("TRAILING_STOP_PERCENT", 1.5))

    # Pairs & Timeframe
    TRADING_PAIRS = os.getenv("TRADING_PAIRS", "BTCUSDT,ETHUSDT").split(",")
    TIMEFRAME = os.getenv("TIMEFRAME", "15m")

    # Strategy Parameters
    RSI_PERIOD = 14
    RSI_OVERSOLD = 35
    RSI_OVERBOUGHT = 65
    MACD_FAST = 12
    MACD_SLOW = 26
    MACD_SIGNAL = 9
    BB_PERIOD = 20
    BB_STD = 2.0
    EMA_FAST = 9
    EMA_SLOW = 21
    EMA_TREND = 50
    VOLUME_MA_PERIOD = 20
    VOLUME_MULTIPLIER = 1.5      # Minimum volume vs average to confirm signal

    # Telegram
    TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

    # Misc
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    CANDLES_LIMIT = 200
    SCAN_INTERVAL_SECONDS = 60

config = Config()
