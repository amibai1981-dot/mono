"""
Telegram notifications for trade signals and status updates.
"""
import logging
import requests
from config import config

logger = logging.getLogger(__name__)


def send_telegram(message: str):
    if not config.TELEGRAM_TOKEN or not config.TELEGRAM_CHAT_ID:
        return
    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={
            "chat_id": config.TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
        }, timeout=5)
    except Exception as e:
        logger.warning(f"Telegram notification failed: {e}")


def notify_signal(symbol: str, signal: str, price: float, reason: str, strength: int):
    emoji = "🟢" if signal == "BUY" else "🔴"
    msg = (
        f"{emoji} <b>{signal} Signal</b> - {symbol}\n"
        f"💰 Price: <code>{price:.4f}</code>\n"
        f"💪 Strength: {strength}/6\n"
        f"📊 Reasons: {reason}"
    )
    send_telegram(msg)
    logger.info(f"SIGNAL: {signal} {symbol} @ {price:.4f} | {reason}")


def notify_trade_open(symbol: str, side: str, price: float, qty: float, sl: float, tp: float):
    emoji = "📈" if side == "BUY" else "📉"
    msg = (
        f"{emoji} <b>Trade Opened</b> - {symbol}\n"
        f"Side: <b>{side}</b>\n"
        f"Entry: <code>{price:.4f}</code>\n"
        f"Qty: {qty:.6f}\n"
        f"Stop Loss: <code>{sl:.4f}</code>\n"
        f"Take Profit: <code>{tp:.4f}</code>"
    )
    send_telegram(msg)


def notify_trade_close(symbol: str, side: str, entry: float, exit_price: float, pnl: float, reason: str):
    emoji = "✅" if pnl > 0 else "❌"
    msg = (
        f"{emoji} <b>Trade Closed</b> - {symbol}\n"
        f"Side: {side} | Reason: <b>{reason}</b>\n"
        f"Entry: <code>{entry:.4f}</code> → Exit: <code>{exit_price:.4f}</code>\n"
        f"PnL: <b>{pnl:+.2f}%</b>"
    )
    send_telegram(msg)


def notify_stats(stats: dict):
    if not stats.get("total_trades"):
        return
    msg = (
        f"📊 <b>Bot Statistics</b>\n"
        f"Total Trades: {stats['total_trades']}\n"
        f"Win Rate: {stats.get('win_rate', 0):.1f}%\n"
        f"Total PnL: {stats.get('total_pnl', 0):+.2f}%\n"
        f"Open Positions: {stats.get('open_positions', 0)}"
    )
    send_telegram(msg)
