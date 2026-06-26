"""
Main trading bot loop.
"""
import time
import logging
import signal
import sys
from datetime import datetime
from colorama import Fore, Style, init

from config import config
from exchange import BinanceExchange
from strategy import analyze, Signal
from risk_manager import RiskManager
from notifier import notify_signal, notify_trade_open, notify_trade_close, notify_stats

init(autoreset=True)

logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL),
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def print_banner():
    banner = f"""
{Fore.CYAN}╔══════════════════════════════════════════════════════╗
║         BINANCE TRADING BOT  v1.0                    ║
║   Strategy: RSI + MACD + Bollinger Bands + EMA       ║
╚══════════════════════════════════════════════════════╝{Style.RESET_ALL}
Mode    : {Fore.YELLOW}{config.TRADING_MODE}{Style.RESET_ALL}
Pairs   : {', '.join(config.TRADING_PAIRS)}
TF      : {config.TIMEFRAME}
SL      : {config.STOP_LOSS_PERCENT}% | TP: {config.TAKE_PROFIT_PERCENT}% | Trail: {config.TRAILING_STOP_PERCENT}%
Max Pos : {config.MAX_OPEN_POSITIONS} | Max Size: ${config.MAX_POSITION_SIZE_USDT}
"""
    print(banner)


class TradingBot:
    def __init__(self):
        self.exchange = BinanceExchange()
        self.risk_manager = RiskManager()
        self.running = False
        self.cycle_count = 0

    def scan_pair(self, symbol: str):
        try:
            df = self.exchange.get_klines(symbol, config.TIMEFRAME, config.CANDLES_LIMIT)
            result = analyze(df, symbol)
            current_price = result.price

            # Update trailing stops for open positions
            if symbol in self.risk_manager.positions:
                pos = self.risk_manager.positions[symbol]
                pos.update_trailing_stop(current_price)
                should_close, reason = pos.should_close(current_price)
                if should_close:
                    self._close_position(symbol, current_price, reason)
                    return

            # Log current state
            signal_color = Fore.GREEN if result.signal == Signal.BUY else (Fore.RED if result.signal == Signal.SELL else Fore.WHITE)
            logger.debug(
                f"{symbol} | {signal_color}{result.signal.value}{Style.RESET_ALL} "
                f"| RSI={result.rsi:.1f} | Vol={result.volume_ratio:.1f}x | {result.reason}"
            )

            # Act on signal
            if result.signal == Signal.BUY:
                can_open, reason = self.risk_manager.can_open_position(symbol)
                if can_open:
                    self._open_position(symbol, "BUY", current_price, result)
                else:
                    logger.debug(f"[{symbol}] Cannot open BUY: {reason}")

            elif result.signal == Signal.SELL:
                # Only short if we have an open long to close, or short-selling enabled
                if symbol in self.risk_manager.positions:
                    pos = self.risk_manager.positions[symbol]
                    if pos.side == "BUY":
                        self._close_position(symbol, current_price, "SELL_SIGNAL")

        except Exception as e:
            logger.error(f"Error scanning {symbol}: {e}")

    def _open_position(self, symbol: str, side: str, price: float, result):
        sl_price = price * (1 - config.STOP_LOSS_PERCENT / 100)
        quantity = self.risk_manager.calculate_position_size(price, sl_price)
        if quantity <= 0:
            logger.warning(f"[{symbol}] Calculated quantity is 0, skipping")
            return

        try:
            order = self.exchange.place_market_order(symbol, side, quantity, price)
            pos = self.risk_manager.open_position(symbol, side, price, quantity, str(order.get("orderId", "")))

            print(f"{Fore.GREEN}✓ OPENED {side} {symbol} @ {price:.4f} | Qty={quantity:.6f}{Style.RESET_ALL}")
            notify_signal(symbol, side, price, result.reason, result.strength)
            notify_trade_open(symbol, side, price, quantity, pos.stop_loss, pos.take_profit)

        except Exception as e:
            logger.error(f"[{symbol}] Failed to open position: {e}")

    def _close_position(self, symbol: str, price: float, reason: str):
        pos = self.risk_manager.positions.get(symbol)
        if not pos:
            return
        close_side = "SELL" if pos.side == "BUY" else "BUY"
        try:
            self.exchange.place_market_order(symbol, close_side, pos.quantity, price)
            closed = self.risk_manager.close_position(symbol, price, reason)

            color = Fore.GREEN if closed.pnl > 0 else Fore.RED
            print(f"{color}✗ CLOSED {symbol} @ {price:.4f} | PnL={closed.pnl:+.2f}% | {reason}{Style.RESET_ALL}")
            notify_trade_close(symbol, pos.side, pos.entry_price, price, closed.pnl, reason)

        except Exception as e:
            logger.error(f"[{symbol}] Failed to close position: {e}")

    def print_status(self):
        stats = self.risk_manager.get_stats()
        balance = self.exchange.get_balance_usdt()
        ts = datetime.now().strftime("%H:%M:%S")
        open_pos = len(self.risk_manager.positions)

        print(f"\n{Fore.CYAN}── [{ts}] Cycle #{self.cycle_count} | Balance: ${balance:.2f} USDT | Open: {open_pos}{Style.RESET_ALL}")

        for sym, pos in self.risk_manager.positions.items():
            try:
                price = self.exchange.get_price(sym)
                pnl = pos.current_pnl(price)
                color = Fore.GREEN if pnl > 0 else Fore.RED
                print(f"  {sym}: {pos.side} @ {pos.entry_price:.4f} | Now={price:.4f} | PnL={color}{pnl:+.2f}%{Style.RESET_ALL}")
            except:
                pass

        if stats.get("total_trades", 0) > 0:
            print(f"  Stats: {stats['total_trades']} trades | WR={stats['win_rate']:.1f}% | Total PnL={stats['total_pnl']:+.2f}%")

    def run(self):
        print_banner()
        self.running = True

        def _shutdown(sig, frame):
            logger.info("Shutdown signal received...")
            self.running = False
            stats = self.risk_manager.get_stats()
            notify_stats(stats)
            sys.exit(0)

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)

        logger.info(f"Bot started. Scanning {len(config.TRADING_PAIRS)} pairs every {config.SCAN_INTERVAL_SECONDS}s")

        while self.running:
            self.cycle_count += 1
            for symbol in config.TRADING_PAIRS:
                self.scan_pair(symbol)
                time.sleep(0.5)  # Rate limit between pairs

            self.print_status()

            # Send stats to Telegram every 50 cycles
            if self.cycle_count % 50 == 0:
                notify_stats(self.risk_manager.get_stats())

            time.sleep(config.SCAN_INTERVAL_SECONDS)


if __name__ == "__main__":
    bot = TradingBot()
    bot.run()
