"""Liquidity analysis and position sizing."""

from __future__ import annotations

import logging

from bot.blockchain.client import ChainClient
from bot.config import AppConfig
from bot.models import LaunchState
from bot.pons.factory import FactoryReader
from bot.pons.pool import PoolMonitor

log = logging.getLogger("mm.liquidity")


def calculate_trade_size(liquidity: float, max_fraction: float) -> float:
    return liquidity * max_fraction


class LiquidityEngine:
    def __init__(self, chain: ChainClient, cfg: AppConfig, factory: FactoryReader) -> None:
        self.chain = chain
        self.cfg = cfg
        self.factory = factory
        self.pool_monitor = PoolMonitor(chain, cfg)

    def paired_weth(self, factory: str, token: str) -> float:
        status = self.factory.graduation_status(factory, token)
        if not status:
            return 0.0
        paired_principal, _, _ = status
        return paired_principal / 1e18

    def estimate_liquidity_weth(
        self,
        factory: str,
        pool: str,
        token: str,
        launch_state: LaunchState,
        price_weth: float,
    ) -> float:
        paired = self.paired_weth(factory, token)
        raw = self.pool_monitor.pool_liquidity_raw(pool)
        if raw == 0 or price_weth <= 0:
            return paired
        sqrt_price = price_weth ** 0.5 if launch_state.is_token0 else (1 / price_weth) ** 0.5
        approx = (raw / (2**96)) * sqrt_price / 1e18
        return max(approx, paired)

    def trade_size_eth(self, liquidity_weth: float) -> float:
        sized = calculate_trade_size(liquidity_weth, self.cfg.strategy.liquidity_fraction)
        return min(sized, self.cfg.strategy.max_trade_eth)

    def trade_size_tokens(self, liquidity_weth: float, price_weth: float) -> float:
        if price_weth <= 0:
            return 0.0
        eth_size = self.trade_size_eth(liquidity_weth)
        tokens = eth_size / price_weth
        return min(tokens, self.cfg.strategy.max_trade_size_tokens)
