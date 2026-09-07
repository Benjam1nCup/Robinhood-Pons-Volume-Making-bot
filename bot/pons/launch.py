"""Launch detection and token registry."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from bot.abis import TOKEN_ABI
from bot.blockchain.client import ChainClient
from bot.config import AppConfig
from bot.models import LaunchEvent, MarketStatus, RegisteredToken
from bot.pons.factory import FactoryReader

log = logging.getLogger("mm.launch")


class TokenRegistry:
    def __init__(self) -> None:
        self.tokens: dict[str, RegisteredToken] = {}

    def add(self, token: RegisteredToken) -> None:
        self.tokens[token.address.lower()] = token
        log.info("Registered token %s (%s) pool=%s", token.symbol, token.address, token.pool)

    def get(self, address: str) -> RegisteredToken | None:
        return self.tokens.get(address.lower())

    def list_active(self) -> list[RegisteredToken]:
        return [t for t in self.tokens.values() if t.status == MarketStatus.ACTIVE]

    def pause(self, address: str) -> None:
        token = self.get(address)
        if token:
            token.status = MarketStatus.PAUSED


class LaunchMonitor:
    def __init__(
        self,
        chain: ChainClient,
        cfg: AppConfig,
        registry: TokenRegistry,
        on_launch: Callable[[RegisteredToken], None] | None = None,
    ) -> None:
        self.chain = chain
        self.cfg = cfg
        self.registry = registry
        self.on_launch = on_launch
        self.factory = FactoryReader(chain, cfg)
        self._last_blocks: dict[str, int] = {}
        self._seen_tokens: set[str] = set()

    def register_from_launch(self, launch: LaunchEvent) -> RegisteredToken | None:
        launch_state = self.factory.get_launched_token(launch.factory, launch.token)
        if not launch_state or not launch_state.exists:
            log.warning("Launch state missing for %s", launch.token)
            return None

        try:
            token_contract = self.chain.contract(launch.token, TOKEN_ABI)
            name = token_contract.functions.name().call()
            symbol = token_contract.functions.symbol().call()
            on_chain_pool = token_contract.functions.liquidityPool().call()
        except Exception as exc:
            log.warning("Token metadata read failed %s: %s", launch.token, exc)
            return None

        if on_chain_pool.lower() != launch.pool.lower():
            log.warning("Pool mismatch token=%s event=%s onchain=%s", launch.token, launch.pool, on_chain_pool)
            return None

        registered = RegisteredToken(
            address=launch.token,
            symbol=symbol,
            name=name,
            pool=launch.pool,
            factory=launch.factory,
            launch_block=launch.block_number,
            launch_state=launch_state,
        )
        self.registry.add(registered)
        if self.on_launch:
            self.on_launch(registered)
        return registered

    def register_target_token(self, token_address: str) -> RegisteredToken | None:
        factory = self.factory.resolve_factory(token_address)
        if not factory:
            log.error("Token %s not found in pons factories", token_address)
            return None

        launch_state = self.factory.get_launched_token(factory, token_address)
        if not launch_state or not launch_state.exists:
            return None

        token_contract = self.chain.contract(token_address, TOKEN_ABI)
        name = token_contract.functions.name().call()
        symbol = token_contract.functions.symbol().call()
        pool = token_contract.functions.liquidityPool().call()

        registered = RegisteredToken(
            address=token_address,
            symbol=symbol,
            name=name,
            pool=pool,
            factory=factory,
            launch_block=0,
            launch_state=launch_state,
        )
        self.registry.add(registered)
        return registered

    def _init_cursors(self) -> None:
        current = self.chain.block_number()
        for factory, start_block in self.cfg.factories:
            self._last_blocks[factory.lower()] = max(start_block, current - 1)

    def poll_once(self) -> int:
        if not self.cfg.strategy.auto_register_launches:
            return 0
        if not self._last_blocks:
            self._init_cursors()

        current = self.chain.block_number()
        discovered = 0

        for factory, start_block in self.cfg.factories:
            key = factory.lower()
            from_block = self._last_blocks.get(key, start_block) + 1
            if from_block > current:
                continue

            for launch in self.factory.iter_launch_logs(factory, from_block, current):
                token_key = launch.token.lower()
                if token_key in self._seen_tokens:
                    continue
                self._seen_tokens.add(token_key)
                if self.register_from_launch(launch):
                    discovered += 1

            self._last_blocks[key] = current

        return discovered

    def run_forever(self, stop_event) -> None:
        log.info("Launch monitor started (poll=%ss)", self.cfg.bot.poll_interval_s)
        while not stop_event.is_set():
            try:
                count = self.poll_once()
                if count:
                    log.info("Registered %s new launch(es)", count)
            except Exception as exc:
                log.exception("Launch monitor error: %s", exc)
            stop_event.wait(self.cfg.bot.poll_interval_s)
