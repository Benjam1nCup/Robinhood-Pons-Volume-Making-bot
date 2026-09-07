"""Trading activity analytics."""

from __future__ import annotations

from dataclasses import dataclass, field

from bot.models import TradeResult


@dataclass
class TradingAnalytics:
    buy_volume_weth: float = 0.0
    sell_volume_weth: float = 0.0
    trade_count: int = 0
    gas_cost_eth: float = 0.0
    failed_trades: int = 0

    def record_trade(self, result: TradeResult) -> None:
        if result.status != 1:
            self.failed_trades += 1
            return

        self.trade_count += 1
        self.gas_cost_eth += result.gas_cost_eth

        if result.side == "BUY":
            self.buy_volume_weth += result.amount_in / 1e18
        else:
            self.sell_volume_weth += result.amount_out / 1e18

    @property
    def total_volume_weth(self) -> float:
        return self.buy_volume_weth + self.sell_volume_weth
