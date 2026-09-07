"""Monitor Uniswap V3 Swap events on pons pools."""

from __future__ import annotations

import logging

from bot.abis import POOL_ABI
from bot.blockchain.client import ChainClient
from bot.config import AppConfig
from bot.constants import SWAP_TOPIC
from bot.models import LaunchState, SwapRecord, SwapSide

log = logging.getLogger("mm.pool")


def swap_side(token: str, pair_token: str, amount0: int, amount1: int) -> SwapSide:
    token_is_token0 = token.lower() < pair_token.lower()
    pair_signed = amount1 if token_is_token0 else amount0
    return SwapSide.BUY if pair_signed > 0 else SwapSide.SELL


class PoolMonitor:
    def __init__(self, chain: ChainClient, cfg: AppConfig) -> None:
        self.chain = chain
        self.cfg = cfg

    def fetch_swaps(
        self,
        pool: str,
        token: str,
        pair_token: str,
        from_block: int,
        to_block: int | None = None,
    ) -> list[SwapRecord]:
        assert self.chain.w3 is not None
        w3 = self.chain.w3
        end = to_block if to_block is not None else w3.eth.block_number
        pool_cs = self.chain.checksum(pool)
        pool_contract = self.chain.contract(pool_cs, POOL_ABI)

        try:
            logs = w3.eth.get_logs(
                {
                    "address": pool_cs,
                    "fromBlock": from_block,
                    "toBlock": end,
                    "topics": [SWAP_TOPIC],
                }
            )
        except Exception as exc:
            log.warning("Swap getLogs failed pool=%s blocks %s-%s: %s", pool, from_block, end, exc)
            return []

        records: list[SwapRecord] = []
        for entry in logs:
            try:
                decoded = pool_contract.events.Swap().process_log(entry)
                args = decoded["args"]
                amount0 = int(args["amount0"])
                amount1 = int(args["amount1"])
                side = swap_side(token, pair_token, amount0, amount1)
                records.append(
                    SwapRecord(
                        pool=pool,
                        block_number=int(entry["blockNumber"]),
                        transaction_hash=entry["transactionHash"].hex(),
                        side=side,
                        amount0=amount0,
                        amount1=amount1,
                        sqrt_price_x96=int(args["sqrtPriceX96"]),
                        liquidity=int(args["liquidity"]),
                    )
                )
            except Exception as exc:
                log.debug("Failed to decode swap: %s", exc)
        return records

    def pair_volume_weth(self, swap: SwapRecord, launch_state: LaunchState) -> float:
        if launch_state.is_token0:
            weth_amount = abs(swap.amount1)
        else:
            weth_amount = abs(swap.amount0)
        return weth_amount / 1e18

    def pool_liquidity_raw(self, pool: str) -> int:
        try:
            contract = self.chain.contract(pool, POOL_ABI)
            return int(contract.functions.liquidity().call())
        except Exception as exc:
            log.debug("Liquidity read failed pool=%s: %s", pool, exc)
            return 0
