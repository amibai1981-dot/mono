"""
WLD/USDT Grid + RSI Trading Bot — Main Engine
Strategy: Grid trading filtered by RSI + EMA trend confirmation.
         Risk managed with stop-loss, take-profit, trailing stop.
"""
import csv
import logging
import os
import time
from datetime import datetime

import config
from exchange import BinanceClient
from grid_manager import GridManager
from indicators import atr, bollinger_bands, ema, rsi, volume_sma
from notifier import TelegramNotifier
from risk_manager import Position, RiskManager

# ─── Logging setup ────────────────────────────────────────────────────────────
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.FileHandler(config.LOG_FILE),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("bot")


class WLDBot:
    def __init__(self):
        self.exchange = BinanceClient(config.API_KEY, config.API_SECRET, config.TESTNET)
        self.grid     = GridManager(
            lower         = config.GRID_LOWER_PRICE,
            upper         = config.GRID_UPPER_PRICE,
            levels        = config.GRID_LEVELS,
            per_grid_usdt = config.PER_GRID_USDT,
            profit_pct    = config.GRID_PROFIT_PCT,
        )
        self.risk     = RiskManager(
            stop_loss_pct     = config.STOP_LOSS_PCT,
            take_profit_pct   = config.TAKE_PROFIT_PCT,
            trailing_stop_pct = config.TRAILING_STOP_PCT,
            max_daily_loss    = config.TOTAL_CAPITAL_USDT * 0.05,
            max_open_orders   = config.MAX_OPEN_ORDERS,
        )
        self.notifier = TelegramNotifier(
            token   = config.TELEGRAM_TOKEN,
            chat_id = config.TELEGRAM_CHAT_ID,
            enabled = config.TELEGRAM_ENABLED,
        )
        self._init_trade_log()
        logger.info("WLD Bot initialized. Grid: %.4f → %.4f (%d levels)",
                    config.GRID_LOWER_PRICE, config.GRID_UPPER_PRICE, config.GRID_LEVELS)

    # ─── Trade Log ────────────────────────────────────────────────────────────

    def _init_trade_log(self):
        if not os.path.exists(config.TRADE_LOG_FILE):
            with open(config.TRADE_LOG_FILE, "w", newline="") as f:
                csv.writer(f).writerow(
                    ["timestamp", "side", "price", "qty", "usdt", "pnl", "reason"])

    def _log_trade(self, side, price, qty, pnl=0.0, reason=""):
        with open(config.TRADE_LOG_FILE, "a", newline="") as f:
            csv.writer(f).writerow([
                datetime.utcnow().isoformat(), side,
                f"{price:.6f}", f"{qty:.6f}",
                f"{price * qty:.4f}", f"{pnl:.4f}", reason,
            ])

    # ─── Market Analysis ─────────────────────────────────────────────────────

    def _analyse(self) -> dict:
        klines  = self.exchange.get_klines(config.SYMBOL, config.CANDLE_INTERVAL, limit=100)
        closes  = [k["close"]  for k in klines]
        highs   = [k["high"]   for k in klines]
        lows    = [k["low"]    for k in klines]
        volumes = [k["volume"] for k in klines]

        current_rsi           = rsi(closes, config.RSI_PERIOD)
        ema_fast              = ema(closes, 9)
        ema_slow              = ema(closes, 21)
        bb_upper, bb_mid, bb_lower = bollinger_bands(closes)
        current_atr           = atr(highs, lows, closes)
        vol_avg               = volume_sma(volumes)
        vol_ratio             = volumes[-1] / vol_avg if vol_avg else 1.0

        trend = "UP" if ema_fast > ema_slow else "DOWN"

        analysis = {
            "price":     closes[-1],
            "rsi":       current_rsi,
            "ema_fast":  ema_fast,
            "ema_slow":  ema_slow,
            "bb_upper":  bb_upper,
            "bb_lower":  bb_lower,
            "atr":       current_atr,
            "vol_ratio": round(vol_ratio, 2),
            "trend":     trend,
        }
        logger.info("Market: price=%.4f RSI=%.1f trend=%s vol_ratio=%.2f",
                    closes[-1], current_rsi, trend, vol_ratio)
        return analysis

    # ─── Signal Logic ────────────────────────────────────────────────────────

    def _should_buy(self, analysis: dict) -> bool:
        return (
            analysis["rsi"] < config.RSI_OVERSOLD
            and analysis["trend"] != "DOWN"           # avoid buying in downtrend
            and analysis["price"] >= config.GRID_LOWER_PRICE
            and analysis["price"] <= config.GRID_UPPER_PRICE
            and self.risk.can_open_order()
        )

    def _should_skip_sell(self, analysis: dict) -> bool:
        """Hold position if RSI still very low — potential further upside."""
        return analysis["rsi"] < 40 and analysis["trend"] == "UP"

    # ─── Order Execution ─────────────────────────────────────────────────────

    def _place_grid_buys(self, analysis: dict):
        levels = self.grid.get_active_buy_levels(analysis["price"])
        for level in levels:
            if not self.risk.can_open_order():
                break
            try:
                order = self.exchange.place_limit_buy(
                    config.SYMBOL, level.qty, level.buy_price)
                level.buy_order_id = order["orderId"]
                self.notifier.order_placed("BUY", level.buy_price, level.qty, config.SYMBOL)
                logger.info("Grid buy queued: level=%d price=%.4f", level.level_id, level.buy_price)
            except Exception as e:
                logger.error("Failed to place grid buy: %s", e)

    def _check_filled_orders(self, analysis: dict):
        for level in self.grid.grid:
            # Check pending buys
            if level.buy_order_id and not level.filled_buy:
                status = self.exchange.get_order_status(config.SYMBOL, level.buy_order_id)
                if status["status"] == "FILLED":
                    fill_price = float(status["price"])
                    fill_qty   = float(status["executedQty"])
                    self.grid.mark_buy_filled(level.level_id, fill_price, fill_qty)
                    self._log_trade("BUY", fill_price, fill_qty)
                    pos = Position(
                        symbol      = config.SYMBOL,
                        entry_price = fill_price,
                        qty         = fill_qty,
                        side        = "BUY",
                        order_id    = str(level.buy_order_id),
                    )
                    self.risk.add_position(pos)
                    self.notifier.order_placed("BUY FILLED", fill_price, fill_qty, config.SYMBOL)

            # Check pending sells
            if level.sell_order_id and level.filled_buy and not level.filled_sell:
                status = self.exchange.get_order_status(config.SYMBOL, level.sell_order_id)
                if status["status"] == "FILLED":
                    fill_price = float(status["price"])
                    pnl = self.risk.remove_position(
                        str(level.sell_order_id - 1), fill_price)  # approximate
                    self.grid.mark_sell_filled(level.level_id, fill_price)
                    self._log_trade("SELL", fill_price, level.qty, pnl, "GRID_SELL")
                    self.notifier.trade_closed(pnl, "GRID_SELL")

    def _place_grid_sells(self, analysis: dict):
        if self._should_skip_sell(analysis):
            return
        levels = self.grid.get_sell_ready_levels()
        for level in levels:
            try:
                order = self.exchange.place_limit_sell(
                    config.SYMBOL, level.qty, level.sell_price)
                level.sell_order_id = order["orderId"]
                self.notifier.order_placed("SELL", level.sell_price, level.qty, config.SYMBOL)
            except Exception as e:
                logger.error("Failed to place grid sell: %s", e)

    def _check_risk_exits(self, analysis: dict):
        price = analysis["price"]
        for order_id, pos in list(self.risk.positions.items()):
            signal = self.risk.check_position(order_id, price)
            if signal:
                logger.warning("Risk exit: %s @ %.4f", signal, price)
                try:
                    order = self.exchange.place_market_sell(config.SYMBOL, pos.qty)
                    fill_price = float(order.get("fills", [{}])[0].get("price", price))
                    pnl = self.risk.remove_position(order_id, fill_price)
                    self._log_trade("SELL", fill_price, pos.qty, pnl, signal)
                    self.notifier.trade_closed(pnl, signal)
                except Exception as e:
                    logger.error("Risk exit order failed: %s", e)

    # ─── Main Loop ────────────────────────────────────────────────────────────

    def run(self):
        logger.info("=" * 60)
        logger.info("WLD Bot started — %s", datetime.utcnow().isoformat())
        logger.info("=" * 60)
        self.notifier.alert("🤖 WLD Bot started!")

        while True:
            try:
                if self.risk.halted():
                    logger.warning("Bot halted: daily loss limit reached.")
                    self.notifier.alert("🛑 Bot HALTED — daily loss limit reached.")
                    time.sleep(300)
                    continue

                analysis = self._analyse()

                self._check_filled_orders(analysis)
                self._check_risk_exits(analysis)

                if self._should_buy(analysis):
                    self._place_grid_buys(analysis)

                self._place_grid_sells(analysis)

                # Status log every cycle
                logger.info("Risk: %s | Grid: %s",
                            self.risk.stats(), self.grid.summary())

            except KeyboardInterrupt:
                logger.info("Bot stopped by user.")
                self.notifier.alert("⛔ Bot stopped by user.")
                break
            except Exception as e:
                logger.exception("Unhandled error: %s", e)
                self.notifier.alert(f"❌ Error: {e}")

            time.sleep(config.LOOP_SLEEP_SEC)


if __name__ == "__main__":
    WLDBot().run()
