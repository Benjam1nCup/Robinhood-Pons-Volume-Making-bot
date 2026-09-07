"""Realized and unrealized PnL tracking."""

from __future__ import annotations

import logging

from bot.models import TradeResult
from bot.storage.database import Database, InventoryRow

log = logging.getLogger("mm.pnl")


class PnLTracker:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.realized_pnl_eth = 0.0

    def on_trade(self, result: TradeResult, inv: InventoryRow) -> None:
        if result.status != 1:
            return

        if result.side == "SELL":
            tokens_sold = result.amount_in / 1e18
            proceeds_eth = result.amount_out / 1e18
            cost_basis = inv.average_entry * tokens_sold
            pnl = proceeds_eth - cost_basis - result.gas_cost_eth
            self.realized_pnl_eth += pnl
            self.db.add_realized_pnl(result.token, pnl)

    def unrealized_pnl_eth(self, token: str, amount_tokens: float, price_weth: float) -> float:
        inv = self.db.get_inventory(token)
        if amount_tokens <= 0 or inv.average_entry <= 0:
            return 0.0
        return (price_weth - inv.average_entry) * amount_tokens

    def net_pnl_eth(self, token: str, amount_tokens: float, price_weth: float, gas_cost_eth: float) -> float:
        return (
            self.db.total_realized_pnl()
            + self.unrealized_pnl_eth(token, amount_tokens, price_weth)
            - gas_cost_eth
        )
