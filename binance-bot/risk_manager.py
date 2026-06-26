"""
Risk management: position sizing, stop-loss, take-profit, trailing stop.
"""
from dataclasses import dataclass, field
from typing import Dict, Optional
import time
import logging
from config import config

logger = logging.getLogger(__name__)


@dataclass
class Position:
    symbol: str
    side: str              # BUY or SELL
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    trailing_stop_price: float
    opened_at: float = field(default_factory=time.time)
    order_id: Optional[str] = None
    pnl: float = 0.0

    def update_trailing_stop(self, current_price: float):
        if self.side == "BUY":
            new_stop = current_price * (1 - config.TRAILING_STOP_PERCENT / 100)
            if new_stop > self.trailing_stop_price:
                self.trailing_stop_price = new_stop
        else:
            new_stop = current_price * (1 + config.TRAILING_STOP_PERCENT / 100)
            if new_stop < self.trailing_stop_price:
                self.trailing_stop_price = new_stop

    def should_close(self, current_price: float) -> tuple[bool, str]:
        if self.side == "BUY":
            if current_price <= self.stop_loss:
                return True, "STOP_LOSS"
            if current_price >= self.take_profit:
                return True, "TAKE_PROFIT"
            if current_price <= self.trailing_stop_price:
                return True, "TRAILING_STOP"
        else:
            if current_price >= self.stop_loss:
                return True, "STOP_LOSS"
            if current_price <= self.take_profit:
                return True, "TAKE_PROFIT"
            if current_price >= self.trailing_stop_price:
                return True, "TRAILING_STOP"
        return False, ""

    def current_pnl(self, current_price: float) -> float:
        if self.side == "BUY":
            return (current_price - self.entry_price) / self.entry_price * 100
        else:
            return (self.entry_price - current_price) / self.entry_price * 100


class RiskManager:
    def __init__(self):
        self.positions: Dict[str, Position] = {}
        self.total_capital = config.MAX_POSITION_SIZE_USDT * config.MAX_OPEN_POSITIONS
        self.trade_history = []

    def can_open_position(self, symbol: str) -> tuple[bool, str]:
        if symbol in self.positions:
            return False, f"Already have open position for {symbol}"
        if len(self.positions) >= config.MAX_OPEN_POSITIONS:
            return False, f"Max positions ({config.MAX_OPEN_POSITIONS}) reached"
        return True, "OK"

    def calculate_position_size(self, price: float, stop_loss_price: float) -> float:
        risk_amount = self.total_capital * (config.RISK_PER_TRADE_PERCENT / 100)
        risk_per_unit = abs(price - stop_loss_price)
        if risk_per_unit == 0:
            return 0
        quantity = risk_amount / risk_per_unit
        # Cap at max position size
        max_qty = config.MAX_POSITION_SIZE_USDT / price
        return min(quantity, max_qty)

    def open_position(self, symbol: str, side: str, entry_price: float, quantity: float, order_id: str = None) -> Position:
        sl_pct = config.STOP_LOSS_PERCENT / 100
        tp_pct = config.TAKE_PROFIT_PERCENT / 100
        trail_pct = config.TRAILING_STOP_PERCENT / 100

        if side == "BUY":
            stop_loss = entry_price * (1 - sl_pct)
            take_profit = entry_price * (1 + tp_pct)
            trailing_stop = entry_price * (1 - trail_pct)
        else:
            stop_loss = entry_price * (1 + sl_pct)
            take_profit = entry_price * (1 - tp_pct)
            trailing_stop = entry_price * (1 + trail_pct)

        pos = Position(
            symbol=symbol,
            side=side,
            entry_price=entry_price,
            quantity=quantity,
            stop_loss=stop_loss,
            take_profit=take_profit,
            trailing_stop_price=trailing_stop,
            order_id=order_id,
        )
        self.positions[symbol] = pos
        logger.info(f"[{symbol}] Opened {side} @ {entry_price:.4f} | SL={stop_loss:.4f} | TP={take_profit:.4f}")
        return pos

    def close_position(self, symbol: str, exit_price: float, reason: str):
        if symbol not in self.positions:
            return None
        pos = self.positions.pop(symbol)
        pos.pnl = pos.current_pnl(exit_price)
        self.trade_history.append({
            "symbol": symbol,
            "side": pos.side,
            "entry": pos.entry_price,
            "exit": exit_price,
            "pnl_pct": pos.pnl,
            "reason": reason,
            "duration_min": (time.time() - pos.opened_at) / 60,
        })
        logger.info(f"[{symbol}] Closed {pos.side} @ {exit_price:.4f} | PnL={pos.pnl:.2f}% | Reason={reason}")
        return pos

    def get_stats(self) -> dict:
        if not self.trade_history:
            return {"total_trades": 0}
        pnls = [t["pnl_pct"] for t in self.trade_history]
        wins = [p for p in pnls if p > 0]
        return {
            "total_trades": len(pnls),
            "win_rate": len(wins) / len(pnls) * 100,
            "total_pnl": sum(pnls),
            "avg_pnl": sum(pnls) / len(pnls),
            "best_trade": max(pnls),
            "worst_trade": min(pnls),
            "open_positions": len(self.positions),
        }
