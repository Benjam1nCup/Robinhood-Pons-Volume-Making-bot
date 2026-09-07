"""pons factory reads and chunked log fetching."""

from __future__ import annotations

import logging
from typing import Iterator

from web3 import Web3

from bot.abis import FACTORY_ABI
from bot.blockchain.client import ChainClient
from bot.config import AppConfig
from bot.constants import TOKEN_LAUNCHED_TOPIC
from bot.models import LaunchEvent, LaunchState

log = logging.getLogger("mm.factory")


class FactoryReader:
    def __init__(self, chain: ChainClient, cfg: AppConfig) -> None:
        self.chain = chain
        self.cfg = cfg

    def _factory_contract(self, factory: str):
        return self.chain.contract(factory, FACTORY_ABI)

    def resolve_factory(self, token: str) -> str | None:
        for factory, _ in self.cfg.factories:
            state = self.get_launched_token(factory, token)
            if state and state.exists:
                return factory
        return None

    def get_launched_token(self, factory: str, token: str) -> LaunchState | None:
        try:
            contract = self._factory_contract(factory)
            launched = contract.functions.getLaunchedToken(self.chain.checksum(token)).call()
            return LaunchState(
                token=launched[0],
                deployer=launched[1],
                paired_token=launched[2],
                position_manager=launched[3],
                position_id=int(launched[4]),
                dex_id=int(launched[5]),
                launch_config_id=int(launched[6]),
                restrictions_end_block=int(launched[7]),
                supply=int(launched[8]),
                is_token0=bool(launched[9]),
                pool_fee=int(launched[10]),
                exists=bool(launched[11]),
                initial_buy_amount=int(launched[12]),
            )
        except Exception as exc:
            log.debug("getLaunchedToken failed for %s: %s", token, exc)
            return None

    def graduation_status(self, factory: str, token: str) -> tuple[int, int, bool] | None:
        try:
            contract = self._factory_contract(factory)
            result = contract.functions.graduationStatus(self.chain.checksum(token)).call()
            return int(result[0]), int(result[1]), bool(result[2])
        except Exception as exc:
            log.debug("graduationStatus failed for %s: %s", token, exc)
            return None

    def iter_launch_logs(
        self,
        factory: str,
        from_block: int,
        to_block: int | None = None,
    ) -> Iterator[LaunchEvent]:
        assert self.chain.w3 is not None
        w3 = self.chain.w3
        end = to_block if to_block is not None else w3.eth.block_number
        chunk = self.cfg.chain.log_chunk_size
        factory_cs = self.chain.checksum(factory)

        for start in range(from_block, end + 1, chunk):
            stop = min(start + chunk - 1, end)
            try:
                logs = w3.eth.get_logs(
                    {
                        "address": factory_cs,
                        "fromBlock": start,
                        "toBlock": stop,
                        "topics": [TOKEN_LAUNCHED_TOPIC],
                    }
                )
            except Exception as exc:
                log.warning("getLogs failed blocks %s-%s: %s", start, stop, exc)
                continue

            for entry in logs:
                yield self._decode_launch_log(entry, factory)

    def _decode_launch_log(self, entry: dict, factory: str) -> LaunchEvent:
        topics = entry["topics"]
        token = Web3.to_checksum_address("0x" + topics[1].hex()[-40:])
        deployer = Web3.to_checksum_address("0x" + topics[2].hex()[-40:])
        dex_factory = Web3.to_checksum_address("0x" + topics[3].hex()[-40:])

        decoded = self._factory_contract(factory).events.TokenLaunched().process_log(entry)
        args = decoded["args"]
        return LaunchEvent(
            token=token,
            deployer=deployer,
            dex_factory=dex_factory,
            pair_token=args["pairToken"],
            pool=args["pool"],
            dex_id=int(args["dexId"]),
            launch_config_id=int(args["launchConfigId"]),
            position_id=int(args["positionId"]),
            restrictions_end_block=int(args["restrictionsEndBlock"]),
            initial_buy_amount=int(args["initialBuyAmount"]),
            block_number=int(entry["blockNumber"]),
            transaction_hash=entry["transactionHash"].hex(),
            factory=factory,
        )
