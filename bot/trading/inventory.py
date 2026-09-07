"""Inventory tracking and on-chain balance sync."""

from __future__ import annotations

import logging
import time

from bot.abis import TOKEN_ABI
from bot.blockchain.client import ChainClient
from bot.config import AppConfig
from bot.storage.database import Database

log = logging.getLogger("mm.inventory")


class InventoryManager:
    def __init__(self, chain: ChainClient, cfg: AppConfig, db: Database) -> None:
        self.chain = chain
        self.cfg = cfg
        self.db = db
        self._cache: dict[str, float] = {}

    def tokens(self, token: str, wallet: str | None) -> float:
        if not wallet:
            return self._cache.get(token.lower(), 0.0)
        try:
            contract = self.chain.contract(token, TOKEN_ABI)
            raw = int(contract.functions.balanceOf(self.chain.checksum(wallet)).call())
            amount = raw / 1e18
            self._cache[token.lower()] = amount
            self.db.upsert_inventory(token, amount, self.db.get_inventory(token).average_entry)
            return amount
        except Exception as exc:
            log.debug("Balance read failed token=%s: %s", token, exc)
            return self._cache.get(token.lower(), 0.0)

    def record_buy(self, token: str, amount_tokens: float, price_weth: float) -> None:
        inv = self.db.get_inventory(token)
        total = inv.amount + amount_tokens
        if total > 0:
            avg = (inv.average_entry * inv.amount + price_weth * amount_tokens) / total
        else:
            avg = price_weth
        self.db.upsert_inventory(token, total, avg)
        self._cache[token.lower()] = total

    def record_sell(self, token: str, amount_tokens: float) -> None:
        inv = self.db.get_inventory(token)
        total = max(0.0, inv.amount - amount_tokens)
        self.db.upsert_inventory(token, total, inv.average_entry if total > 0 else 0.0)
        self._cache[token.lower()] = total

    def inventory_value_weth(self, token: str, price_weth: float, wallet: str | None) -> float:
        return self.tokens(token, wallet) * price_weth
