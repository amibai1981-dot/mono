"""
WLD/USDT Scalping Bot — 5 Minute Strategy
Buy: RSI < 40 + EMA cross + Volume spike
Sell: RSI > 60 OR TP/SL/Trailing hit — fast exits
"""
import csv, logging, os, time
from datetime import datetime
import config
from exchange import BinanceClient
from indicators import rsi, ema, volume_sma
from risk_manager import Position, RiskManager
from notifier import TelegramNotifier

os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[logging.FileHandler(config.LOG_FILE), logging.StreamHandler()])
logger = logging.getLogger("bot")


class WLDScalpBot:
    def __init__(self):
        self.exchange      = BinanceClient(config.API_KEY, config.API_SECRET, config.TESTNET)
        self.risk          = RiskManager(
            stop_loss_pct      = config.STOP_LOSS_PCT,
            take_profit_pct    = config.TAKE_PROFIT_PCT,
            trailing_stop_pct  = config.TRAILING_STOP_PCT,
            max_daily_loss     = config.TOTAL_CAPITAL_USDT * 0.03,  # 3% يومياً للسكالب
            max_open_orders    = config.MAX_OPEN_ORDERS,
        )
        self.notifier      = TelegramNotifier(
            config.TELEGRAM_TOKEN, config.TELEGRAM_CHAT_ID, config.TELEGRAM_ENABLED)
        self.daily_trades  = 0
        self.last_trade_day = datetime.utcnow().date()
        self._init_log()
        logger.info("=== WLD Scalp Bot Started | Interval: %s ===", config.CANDLE_INTERVAL)

    # ─── Trade Log ───────────────────────────────────────────────────────────

    def _init_log(self):
        if not os.path.exists(config.TRADE_LOG_FILE):
            with open(config.TRADE_LOG_FILE, "w", newline="") as f:
                csv.writer(f).writerow(["time","side","price","qty","pnl","reason","daily_trade_#"])

    def _log_trade(self, side, price, qty, pnl=0.0, reason=""):
        with open(config.TRADE_LOG_FILE, "a", newline="") as f:
            csv.writer(f).writerow([
                datetime.utcnow().isoformat(), side,
                f"{price:.5f}", f"{qty:.4f}",
                f"{pnl:.4f}", reason, self.daily_trades])

    # ─── Daily counter reset ─────────────────────────────────────────────────

    def _check_day_reset(self):
        today = datetime.utcnow().date()
        if today != self.last_trade_day:
            self.daily_trades   = 0
            self.last_trade_day = today
            logger.info("New day — trade counter reset")

    # ─── Market Analysis ─────────────────────────────────────────────────────

    def _analyse(self) -> dict:
        klines  = self.exchange.get_klines(config.SYMBOL, config.CANDLE_INTERVAL, limit=50)
        closes  = [k["close"]  for k in klines]
        volumes = [k["volume"] for k in klines]

        current_rsi  = rsi(closes, config.RSI_PERIOD)
        ema_fast     = ema(closes, config.EMA_FAST)
        ema_slow     = ema(closes, config.EMA_SLOW)
        vol_avg      = volume_sma(volumes, 10)
        vol_ratio    = round(volumes[-1] / vol_avg, 2) if vol_avg else 1.0
        price        = closes[-1]

        # EMA cross direction
        prev_ema_fast = ema(closes[:-1], config.EMA_FAST)
        prev_ema_slow = ema(closes[:-1], config.EMA_SLOW)
        ema_crossed_up   = prev_ema_fast <= prev_ema_slow and ema_fast > ema_slow
        ema_crossed_down = prev_ema_fast >= prev_ema_slow and ema_fast < ema_slow

        logger.info("price=%.5f | RSI=%.1f | EMA%d=%.5f EMA%d=%.5f | vol_ratio=%.2f",
                    price, current_rsi,
                    config.EMA_FAST, ema_fast, config.EMA_SLOW, ema_slow,
                    vol_ratio)

        return {
            "price":           price,
            "rsi":             current_rsi,
            "ema_fast":        ema_fast,
            "ema_slow":        ema_slow,
            "ema_crossed_up":  ema_crossed_up,
            "ema_crossed_down": ema_crossed_down,
            "vol_ratio":       vol_ratio,
        }

    # ─── Scalping Signals ────────────────────────────────────────────────────

    def _buy_signal(self, a: dict) -> bool:
        rsi_ok    = a["rsi"] < config.RSI_OVERSOLD
        ema_ok    = a["ema_fast"] > a["ema_slow"] or a["ema_crossed_up"]
        vol_ok    = a["vol_ratio"] >= config.VOLUME_MULTIPLIER if config.VOLUME_FILTER else True
        risk_ok   = self.risk.can_open_order()
        quota_ok  = self.daily_trades < config.MAX_DAILY_TRADES

        signal = rsi_ok and ema_ok and vol_ok and risk_ok and quota_ok
        if signal:
            logger.info("BUY SIGNAL: RSI=%.1f ema_up=%s vol=%.2f",
                        a["rsi"], ema_ok, a["vol_ratio"])
        return signal

    def _sell_signal(self, a: dict) -> bool:
        return (a["rsi"] > config.RSI_OVERBOUGHT
                or a["ema_crossed_down"])

    # ─── Order Execution ─────────────────────────────────────────────────────

    def _open_scalp(self, analysis: dict):
        price = analysis["price"]
        qty   = round(config.PER_GRID_USDT / price, 4)
        if qty <= 0:
            return
        try:
            order = self.exchange.place_limit_buy(config.SYMBOL, qty, price)
            pos   = Position(config.SYMBOL, price, qty, "BUY",
                             order_id=str(order["orderId"]))
            self.risk.add_position(pos)
            self.daily_trades += 1
            self._log_trade("BUY", price, qty)
            self.notifier.order_placed("BUY", price, qty, config.SYMBOL)
            logger.info("SCALP BUY #%d @ %.5f qty=%.4f", self.daily_trades, price, qty)
        except Exception as e:
            logger.error("Buy failed: %s", e)

    def _close_position(self, order_id: str, pos: Position, price: float, reason: str):
        try:
            order = self.exchange.place_market_sell(config.SYMBOL, pos.qty)
            pnl   = self.risk.remove_position(order_id, price)
            self._log_trade("SELL", price, pos.qty, pnl, reason)
            self.notifier.trade_closed(pnl, reason)
            logger.info("SCALP SELL [%s] @ %.5f pnl=%.4f", reason, price, pnl)
        except Exception as e:
            logger.error("Sell failed [%s]: %s", reason, e)

    def _manage_positions(self, analysis: dict):
        price = analysis["price"]
        for oid, pos in list(self.risk.positions.items()):
            # Risk manager check (SL / TP / Trailing)
            signal = self.risk.check_position(oid, price)
            if signal:
                self._close_position(oid, pos, price, signal)
                continue
            # RSI / EMA sell signal
            if self._sell_signal(analysis):
                self._close_position(oid, pos, price, "RSI_SIGNAL")

    # ─── Stale order cleanup ─────────────────────────────────────────────────

    def _cancel_stale_orders(self):
        try:
            open_orders = self.exchange.get_open_orders(config.SYMBOL)
            now = datetime.utcnow().timestamp() * 1000
            for o in open_orders:
                age_min = (now - o["time"]) / 60000
                if age_min > config.ORDER_TIMEOUT_MIN:
                    self.exchange.cancel_order(config.SYMBOL, o["orderId"])
                    logger.info("Cancelled stale order %s (%.1f min old)", o["orderId"], age_min)
        except Exception as e:
            logger.warning("Stale order cleanup failed: %s", e)

    # ─── Main Loop ───────────────────────────────────────────────────────────

    def run(self):
        logger.info("Scalping WLD/USDT on %s | SL=%.1f%% TP=%.1f%% | RSI<%d/>%d",
                    config.CANDLE_INTERVAL,
                    config.STOP_LOSS_PCT * 100, config.TAKE_PROFIT_PCT * 100,
                    config.RSI_OVERSOLD, config.RSI_OVERBOUGHT)
        self.notifier.alert(f"🚀 WLD Scalp Bot started! ({config.CANDLE_INTERVAL})")

        cycle = 0
        while True:
            try:
                self._check_day_reset()

                if self.risk.halted():
                    logger.warning("HALTED — daily loss limit reached. Sleeping 5 min...")
                    self.notifier.alert("🛑 Bot HALTED — daily loss limit!")
                    time.sleep(300)
                    continue

                analysis = self._analyse()

                # Manage open positions first (exits)
                self._manage_positions(analysis)

                # Look for new entry
                if not self.risk.positions and self._buy_signal(analysis):
                    self._open_scalp(analysis)

                # Clean stale orders every 10 cycles
                cycle += 1
                if cycle % 10 == 0:
                    self._cancel_stale_orders()
                    logger.info("Daily trades: %d/%d | PnL: %.4f USDT",
                                self.daily_trades, config.MAX_DAILY_TRADES,
                                self.risk.daily_pnl)

            except KeyboardInterrupt:
                logger.info("Bot stopped by user.")
                self.notifier.alert("⛔ Bot stopped.")
                break
            except Exception as e:
                logger.exception("Unhandled error: %s", e)

            time.sleep(config.LOOP_SLEEP_SEC)


if __name__ == "__main__":
    WLDScalpBot().run()
