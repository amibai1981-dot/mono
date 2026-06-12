"""Configuration loaded from environment variables."""
import os
from dotenv import load_dotenv

load_dotenv()

# Bybit
BYBIT_API_KEY: str = os.environ["BYBIT_API_KEY"]
BYBIT_PRIVATE_KEY_PATH: str = os.environ["BYBIT_PRIVATE_KEY_PATH"]
BYBIT_ENV: str = os.getenv("BYBIT_ENV", "testnet")  # testnet | mainnet
BYBIT_BASE_URL: str = (
    "https://api-testnet.bybit.com" if BYBIT_ENV == "testnet" else "https://api.bybit.com"
)

# Anthropic
ANTHROPIC_API_KEY: str = os.environ["ANTHROPIC_API_KEY"]
CLAUDE_MODEL: str = "claude-sonnet-4-6"

# Webhook
WEBHOOK_SECRET: str = os.environ["WEBHOOK_SECRET"]

# Risk management
MAX_TRADE_SIZE_USDT: float = float(os.getenv("MAX_TRADE_SIZE_USDT", "100"))
RISK_PER_TRADE_PCT: float = float(os.getenv("RISK_PER_TRADE_PCT", "1.0"))  # % of balance

# Server
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8000"))
