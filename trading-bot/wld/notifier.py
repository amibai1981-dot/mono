"""
Telegram Notifier — optional real-time alerts.
"""
import logging
import requests

logger = logging.getLogger("notifier")


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, enabled: bool = False):
        self.token   = token
        self.chat_id = chat_id
        self.enabled = enabled
        self._base   = f"https://api.telegram.org/bot{token}/sendMessage"

    def send(self, message: str):
        if not self.enabled:
            return
        try:
            requests.post(self._base, json={
                "chat_id":    self.chat_id,
                "text":       message,
                "parse_mode": "HTML",
            }, timeout=5)
        except Exception as e:
            logger.warning("Telegram send failed: %s", e)

    def order_placed(self, side: str, price: float, qty: float, symbol: str):
        emoji = "🟢" if side == "BUY" else "🔴"
        self.send(f"{emoji} <b>{side}</b> {symbol}\n"
                  f"Price: <code>{price:.4f}</code>\n"
                  f"Qty:   <code>{qty:.4f}</code>")

    def trade_closed(self, pnl: float, reason: str):
        emoji = "✅" if pnl >= 0 else "❌"
        self.send(f"{emoji} Trade closed — <b>{reason}</b>\n"
                  f"PnL: <code>{pnl:+.4f} USDT</code>")

    def alert(self, msg: str):
        self.send(f"⚠️ <b>ALERT</b>\n{msg}")
