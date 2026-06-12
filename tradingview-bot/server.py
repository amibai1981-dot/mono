"""FastAPI webhook server for TradingView signals."""
import asyncio
import logging
import math
import sys
from contextlib import asynccontextmanager
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

import config
from bybit_client import BybitClient
from claude_analyzer import ClaudeAnalyzer, TradeDecision

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("tradingview_bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("tradingview_bot")

# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class Indicators(BaseModel):
    rsi: float | None = None
    ema_fast: float | None = None
    ema_slow: float | None = None

    class Config:
        extra = "allow"


class WebhookPayload(BaseModel):
    secret: str
    symbol: str
    action: str = Field(..., pattern="^(buy|sell|hold)$")
    price: float
    interval: str = "1h"
    indicators: Indicators = Field(default_factory=Indicators)
    message: str = ""


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

bybit: BybitClient
analyzer: ClaudeAnalyzer


@asynccontextmanager
async def lifespan(app: FastAPI):
    global bybit, analyzer
    bybit = BybitClient()
    analyzer = ClaudeAnalyzer()
    logger.info(
        "TradingView bot started — env=%s, max_trade=%s USDT",
        config.BYBIT_ENV,
        config.MAX_TRADE_SIZE_USDT,
    )
    yield
    await bybit.close()
    logger.info("TradingView bot stopped")


app = FastAPI(title="TradingView Webhook Bot", lifespan=lifespan)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _compute_qty(symbol: str, side: str, size_pct: float) -> str | None:
    """
    Compute order quantity string.
    For spot buys: use USDT balance.
    For spot sells: use coin balance (derived from symbol).
    Returns None if balance is insufficient.
    """
    if size_pct <= 0:
        return None

    fraction = size_pct / 100.0

    try:
        if side.lower() == "buy":
            balance_usdt = await bybit.get_balance("USDT")
            usdt_to_spend = min(
                balance_usdt * fraction * (config.RISK_PER_TRADE_PCT / 100),
                config.MAX_TRADE_SIZE_USDT,
            )
            if usdt_to_spend < 1:
                logger.warning("Insufficient USDT balance for trade: %.4f", usdt_to_spend)
                return None
            ticker = await bybit.get_ticker(symbol)
            last_price = float(ticker["lastPrice"])
            qty = usdt_to_spend / last_price
            # Round to reasonable precision
            qty = math.floor(qty * 1e6) / 1e6
            return str(qty)
        else:  # sell
            coin = symbol.replace("USDT", "").replace("PERP", "")
            coin_balance = await bybit.get_balance(coin)
            qty = coin_balance * fraction * (config.RISK_PER_TRADE_PCT / 100)
            qty = math.floor(qty * 1e6) / 1e6
            if qty <= 0:
                logger.warning("Insufficient %s balance for sell", coin)
                return None
            return str(qty)
    except Exception as exc:
        logger.error("Error computing qty: %s", exc)
        return None


async def _execute_decision(payload: WebhookPayload, decision: TradeDecision) -> dict[str, Any]:
    """Execute the trade decision and return a result dict."""
    result: dict[str, Any] = {
        "symbol": payload.symbol,
        "signal_action": payload.action,
        "decision": decision.to_dict(),
        "trade_executed": False,
        "order": None,
        "error": None,
    }

    if decision.action == "hold":
        logger.info("Decision: HOLD — %s", decision.reason)
        return result

    side = "Buy" if decision.action == "buy" else "Sell"
    qty = await _compute_qty(payload.symbol, decision.action, decision.size_pct)

    if qty is None:
        result["error"] = "Insufficient balance or zero qty computed"
        logger.warning("Skipping trade for %s: %s", payload.symbol, result["error"])
        return result

    try:
        order = await bybit.place_market_order(payload.symbol, side, qty)
        result["trade_executed"] = True
        result["order"] = order
        logger.info(
            "Trade executed: %s %s %s qty=%s | %s",
            side,
            payload.symbol,
            qty,
            qty,
            decision.reason,
        )
    except Exception as exc:
        result["error"] = str(exc)
        logger.error("Order placement failed for %s: %s", payload.symbol, exc)

    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "env": config.BYBIT_ENV}


@app.post("/webhook", status_code=status.HTTP_200_OK)
async def webhook(request: Request) -> JSONResponse:
    # Parse body manually for better error messages
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Validate secret first (before full pydantic validation to avoid leaking info)
    if raw.get("secret") != config.WEBHOOK_SECRET:
        logger.warning("Webhook received with invalid secret from %s", request.client)
        raise HTTPException(status_code=401, detail="Invalid secret")

    try:
        payload = WebhookPayload(**raw)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    logger.info(
        "Webhook received: symbol=%s action=%s price=%s interval=%s message=%r",
        payload.symbol,
        payload.action,
        payload.price,
        payload.interval,
        payload.message,
    )

    # Run Claude analysis in a thread (synchronous Anthropic SDK)
    loop = asyncio.get_event_loop()
    signal_dict = raw.copy()
    signal_dict.pop("secret", None)

    try:
        decision: TradeDecision = await loop.run_in_executor(
            None, analyzer.analyze, signal_dict
        )
    except Exception as exc:
        logger.error("Claude analysis failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Claude analysis error: {exc}")

    result = await _execute_decision(payload, decision)
    return JSONResponse(content=result)


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host=config.HOST,
        port=config.PORT,
        reload=False,
        log_level="info",
    )
