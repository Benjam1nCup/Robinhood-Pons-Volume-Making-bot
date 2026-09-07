"""Price calculations from Uniswap V3 pool slot0."""

from __future__ import annotations

import logging

from bot.abis import POOL_ABI
from bot.blockchain.client import ChainClient
from bot.models import LaunchState

log = logging.getLogger("mm.price")


def price_from_sqrt_price_x96(sqrt_price_x96: int, is_token0: bool) -> float:
    ratio = sqrt_price_x96 / (2**96)
    token1_per_token0 = ratio * ratio
    if token1_per_token0 <= 0:
        return 0.0
    return token1_per_token0 if is_token0 else 1.0 / token1_per_token0


class PriceTracker:
    """Short moving average reference price (tutorial section 10)."""

    def __init__(self, window: int = 10) -> None:
        self.window = window
        self.prices: list[float] = []

    def add(self, price: float) -> None:
        if price <= 0:
            return
        self.prices.append(price)
        if len(self.prices) > self.window:
            self.prices.pop(0)

    def average(self) -> float | None:
        if not self.prices:
            return None
        return sum(self.prices) / len(self.prices)

    def volatility(self) -> float:
        if len(self.prices) < 2:
            return 0.0
        returns = []
        for i in range(1, len(self.prices)):
            if self.prices[i - 1] > 0:
                returns.append(abs(self.prices[i] - self.prices[i - 1]) / self.prices[i - 1])
        return sum(returns) / len(returns) if returns else 0.0


class PriceEngine:
    def __init__(self, chain: ChainClient) -> None:
        self.chain = chain
        self._trackers: dict[str, PriceTracker] = {}

    def tracker_for(self, token: str, window: int) -> PriceTracker:
        key = token.lower()
        if key not in self._trackers:
            self._trackers[key] = PriceTracker(window=window)
        return self._trackers[key]

    def current_price_weth(self, pool: str, launch_state: LaunchState) -> float:
        try:
            contract = self.chain.contract(pool, POOL_ABI)
            slot0 = contract.functions.slot0().call()
            sqrt_price_x96 = int(slot0[0])
            return price_from_sqrt_price_x96(sqrt_price_x96, launch_state.is_token0)
        except Exception as exc:
            log.debug("Price read failed pool=%s: %s", pool, exc)
            return 0.0

    def fair_price(self, token: str, pool: str, launch_state: LaunchState, window: int) -> float:
        spot = self.current_price_weth(pool, launch_state)
        tracker = self.tracker_for(token, window)
        tracker.add(spot)
        avg = tracker.average()
        return avg if avg is not None else spot
