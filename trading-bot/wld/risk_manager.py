"""
Risk Management Engine
Stop-loss, take-profit, trailing stop, daily drawdown limits.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, date

logger = logging.getLogger("risk")


@dataclass
class Position:
    symbol:        str
    entry_price:   float
    qty:           float
    side:          str          # "BUY"
    entry_time:    datetime = field(default_factory=datetime.utcnow)
    highest_price: float = 0.0
    order_id:      str = ""

    @property
    def cost_usdt(self) -> float:
        return self.entry_price * self.qty


class RiskManager:
    def __init__(self,
                 stop_loss_pct:    float = 0.05,
                 take_profit_pct:  float = 0.08,
                 trailing_stop_pct: float = 0.03,
                 max_daily_loss:   float = 50.0,
                 max_open_orders:  int   = 10):
        self.sl_pct      = stop_loss_pct
        self.tp_pct      = take_profit_pct
        self.trail_pct   = trailing_stop_pct
        self.max_dl      = max_daily_loss
        self.max_orders  = max_open_orders

        self.positions:  dict[str, Position] = {}
        self.daily_pnl:  float = 0.0
        self._day:       date  = date.today()

    def add_position(self, pos: Position):
        pos.highest_price = pos.entry_price
        self.positions[pos.order_id] = pos
        logger.info("Position added: %s @ %.4f qty=%.4f", pos.symbol, pos.entry_price, pos.qty)

    def remove_position(self, order_id: str, exit_price: float) -> float:
        pos = self.positions.pop(order_id, None)
        if not pos:
            return 0.0
        pnl = (exit_price - pos.entry_price) * pos.qty
        self._accum_pnl(pnl)
        logger.info("Position closed: pnl=%.4f USDT daily_pnl=%.4f", pnl, self.daily_pnl)
        return pnl

    def check_position(self, order_id: str, current_price: float) -> str | None:
        """Returns 'STOP_LOSS', 'TAKE_PROFIT', 'TRAILING_STOP', or None."""
        pos = self.positions.get(order_id)
        if not pos:
            return None

        if current_price > pos.highest_price:
            pos.highest_price = current_price

        stop_loss_price     = pos.entry_price * (1 - self.sl_pct)
        take_profit_price   = pos.entry_price * (1 + self.tp_pct)
        trailing_stop_price = pos.highest_price * (1 - self.trail_pct)

        if current_price <= stop_loss_price:
            logger.warning("STOP LOSS triggered @ %.4f (entry=%.4f)", current_price, pos.entry_price)
            return "STOP_LOSS"
        if current_price >= take_profit_price:
            logger.info("TAKE PROFIT triggered @ %.4f", current_price)
            return "TAKE_PROFIT"
        if current_price <= trailing_stop_price and pos.highest_price > pos.entry_price:
            logger.info("TRAILING STOP triggered @ %.4f (high=%.4f)", current_price, pos.highest_price)
            return "TRAILING_STOP"
        return None

    def can_open_order(self) -> bool:
        if len(self.positions) >= self.max_orders:
            logger.warning("Max open orders reached (%d)", self.max_orders)
            return False
        if self.daily_pnl <= -self.max_dl:
            logger.warning("Daily loss limit hit: %.2f USDT", self.daily_pnl)
            return False
        return True

    def halted(self) -> bool:
        return self.daily_pnl <= -self.max_dl

    def _accum_pnl(self, pnl: float):
        today = date.today()
        if today != self._day:
            self.daily_pnl = 0.0
            self._day = today
        self.daily_pnl = round(self.daily_pnl + pnl, 4)

    def stats(self) -> dict:
        return {
            "open_positions": len(self.positions),
            "daily_pnl":      self.daily_pnl,
            "halted":         self.halted(),
        }
