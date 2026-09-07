"""Bid/ask quote generation with inventory and volatility awareness."""

from __future__ import annotations

from bot.config import AppConfig
from bot.models import Quote


def generate_quotes(fair_price: float, spread: float) -> tuple[float, float]:
    bid = fair_price * (1 - spread)
    ask = fair_price * (1 + spread)
    return bid, ask


def dynamic_spread(base_spread: float, volatility: float, multiplier: float) -> float:
    return base_spread + volatility * multiplier


def inventory_adjustment(inventory: float, max_inventory: float) -> float:
    if max_inventory <= 0:
        return 0.0
    return min(1.0, max(0.0, inventory / max_inventory))


def generate_inventory_quotes(
    fair_price: float,
    inventory: float,
    max_inventory: float,
    spread: float,
) -> Quote:
    ratio = inventory_adjustment(inventory, max_inventory)
    adjustment = ratio * spread

    bid = fair_price * (1 - spread - adjustment)
    ask = fair_price * (1 + spread - adjustment)

    return Quote(
        bid=bid,
        ask=ask,
        fair_price=fair_price,
        spread=spread,
    )


class QuoteEngine:
    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg

    def build_quote(
        self,
        fair_price: float,
        inventory_tokens: float,
        volatility: float,
    ) -> Quote:
        spread = dynamic_spread(
            self.cfg.strategy.base_spread,
            volatility,
            self.cfg.strategy.volatility_spread_multiplier,
        )
        return generate_inventory_quotes(
            fair_price=fair_price,
            inventory=inventory_tokens,
            max_inventory=self.cfg.strategy.max_inventory_tokens,
            spread=spread,
        )
