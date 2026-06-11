"""
Grid Trading Manager
Manages buy/sell grid levels, tracks open orders and PnL.
"""
import logging
import math

logger = logging.getLogger("grid")


class GridLevel:
    def __init__(self, level_id: int, buy_price: float, sell_price: float, usdt_size: float):
        self.level_id   = level_id
        self.buy_price  = round(buy_price, 4)
        self.sell_price = round(sell_price, 4)
        self.usdt_size  = usdt_size
        self.qty        = round(usdt_size / buy_price, 4)

        self.buy_order_id  = None
        self.sell_order_id = None
        self.filled_buy    = False
        self.filled_sell   = False
        self.realized_pnl  = 0.0

    def __repr__(self):
        return (f"Grid#{self.level_id} buy={self.buy_price} sell={self.sell_price} "
                f"qty={self.qty} pnl={self.realized_pnl:.4f}")


class GridManager:
    def __init__(self, lower: float, upper: float, levels: int,
                 per_grid_usdt: float, profit_pct: float):
        self.lower        = lower
        self.upper        = upper
        self.levels       = levels
        self.per_grid     = per_grid_usdt
        self.profit_pct   = profit_pct
        self.grid: list[GridLevel] = []
        self._build_grid()

    def _build_grid(self):
        step = (self.upper - self.lower) / self.levels
        for i in range(self.levels):
            buy_price  = self.lower + i * step
            sell_price = buy_price * (1 + self.profit_pct)
            sell_price = min(sell_price, self.upper)
            self.grid.append(GridLevel(i, buy_price, sell_price, self.per_grid))
        logger.info("Grid built with %d levels: %.4f → %.4f", self.levels, self.lower, self.upper)
        for g in self.grid:
            logger.info("  %s", g)

    def get_active_buy_levels(self, current_price: float) -> list[GridLevel]:
        """Return levels where current price is near or below buy price."""
        return [
            g for g in self.grid
            if not g.filled_buy
            and g.buy_order_id is None
            and current_price <= g.buy_price * 1.005
        ]

    def get_sell_ready_levels(self) -> list[GridLevel]:
        """Return levels where buy is filled but sell order not placed."""
        return [
            g for g in self.grid
            if g.filled_buy and not g.filled_sell and g.sell_order_id is None
        ]

    def mark_buy_filled(self, level_id: int, fill_price: float, fill_qty: float):
        g = self.grid[level_id]
        g.filled_buy   = True
        g.buy_price    = fill_price
        g.qty          = fill_qty
        g.buy_order_id = None
        logger.info("Level %d: BUY filled @ %.4f qty=%.4f", level_id, fill_price, fill_qty)

    def mark_sell_filled(self, level_id: int, fill_price: float):
        g = self.grid[level_id]
        g.filled_sell    = True
        g.sell_order_id  = None
        g.realized_pnl   = (fill_price - g.buy_price) * g.qty
        logger.info("Level %d: SELL filled @ %.4f PnL=%.4f USDT",
                    level_id, fill_price, g.realized_pnl)
        # Reset level for next cycle
        g.filled_buy  = False
        g.filled_sell = False

    def total_pnl(self) -> float:
        return round(sum(g.realized_pnl for g in self.grid), 4)

    def summary(self) -> dict:
        filled_buys  = sum(1 for g in self.grid if g.filled_buy)
        filled_sells = sum(1 for g in self.grid if g.filled_sell)
        return {
            "levels":       self.levels,
            "filled_buys":  filled_buys,
            "filled_sells": filled_sells,
            "total_pnl":    self.total_pnl(),
        }
