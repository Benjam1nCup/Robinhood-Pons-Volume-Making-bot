"""Slippage estimation via Quoter V2."""

from __future__ import annotations

import logging

from bot.abis import QUOTER_V2_ABI
from bot.blockchain.client import ChainClient
from bot.config import AppConfig
from bot.models import LaunchState

log = logging.getLogger("mm.slippage")


class SlippageEngine:
    def __init__(self, chain: ChainClient, cfg: AppConfig) -> None:
        self.chain = chain
        self.cfg = cfg
        self.quoter = chain.contract(cfg.pons.quoter_v2, QUOTER_V2_ABI)

    def quote_exact_in(
        self,
        token_in: str,
        token_out: str,
        amount_in: int,
        pool_fee: int,
    ) -> int:
        if amount_in <= 0:
            return 0
        params = (
            self.chain.checksum(token_in),
            self.chain.checksum(token_out),
            amount_in,
            pool_fee,
            0,
        )
        try:
            result = self.quoter.functions.quoteExactInputSingle(params).call()
            return int(result[0])
        except Exception as exc:
            log.debug("Quoter failed %s->%s: %s", token_in, token_out, exc)
            return 0

    def quote_buy(self, token: str, amount_in_wei: int, launch_state: LaunchState) -> int:
        return self.quote_exact_in(
            self.cfg.pons.weth,
            token,
            amount_in_wei,
            launch_state.pool_fee,
        )

    def quote_sell(self, token: str, amount_in: int, launch_state: LaunchState) -> int:
        return self.quote_exact_in(
            token,
            self.cfg.pons.weth,
            amount_in,
            launch_state.pool_fee,
        )

    def min_out(self, quoted_out: int, max_slippage_bps: int) -> int:
        if quoted_out <= 0:
            return 0
        return quoted_out * (10_000 - max_slippage_bps) // 10_000

    def slippage_ratio(self, expected: int, quoted: int) -> float:
        if expected <= 0 or quoted <= 0:
            return 1.0
        return max(0.0, 1.0 - quoted / expected)
