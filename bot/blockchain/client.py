"""Web3 connection to Robinhood Chain."""

from __future__ import annotations

import logging
from typing import Any

from web3 import Web3

from bot.config import AppConfig
from bot.constants import EXPLORER_MAINNET, EXPLORER_TESTNET

try:
    from web3.middleware import ExtraDataToPOAMiddleware as _poa
except ImportError:
    from web3.middleware import geth_poa_middleware as _poa

log = logging.getLogger("mm.chain")


class ChainClient:
    def __init__(self, cfg: AppConfig) -> None:
        self.cfg = cfg
        self.w3: Web3 | None = None

    def connect(self) -> bool:
        timeout = self.cfg.chain.request_timeout_s
        self.w3 = Web3(
            Web3.HTTPProvider(
                self.cfg.chain.rpc_url,
                request_kwargs={"timeout": timeout},
            )
        )
        try:
            self.w3.middleware_onion.inject(_poa, layer=0)
        except Exception:
            pass
        if not self.w3.is_connected():
            log.error("Unable to connect to %s", self.cfg.chain.rpc_url)
            self.w3 = None
            return False
        chain_id = self.w3.eth.chain_id
        block = self.w3.eth.block_number
        log.info("Connected chain_id=%s block=%s", chain_id, block)
        if chain_id != self.cfg.chain.chain_id:
            log.error("Expected chain_id=%s got %s", self.cfg.chain.chain_id, chain_id)
            return False
        return True

    @property
    def connected(self) -> bool:
        return self.w3 is not None and self.w3.is_connected()

    def checksum(self, addr: str) -> str:
        assert self.w3 is not None
        return self.w3.to_checksum_address(addr)

    def contract(self, address: str, abi: list) -> Any:
        assert self.w3 is not None
        return self.w3.eth.contract(address=self.checksum(address), abi=abi)

    def block_number(self) -> int:
        assert self.w3 is not None
        return int(self.w3.eth.block_number)

    def native_balance(self, address: str) -> int:
        assert self.w3 is not None
        return int(self.w3.eth.get_balance(self.checksum(address)))

    def wait_for_receipt(self, tx_hash: str, timeout_s: float) -> dict | None:
        assert self.w3 is not None
        try:
            receipt = self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout_s)
            return dict(receipt)
        except Exception as exc:
            log.warning("Receipt timeout for %s: %s", tx_hash, exc)
            return None

    def fill_gas_price(self, tx: dict) -> dict:
        assert self.w3 is not None
        out = dict(tx)
        if "maxFeePerGas" not in out and "gasPrice" not in out:
            try:
                block = self.w3.eth.get_block("latest")
                base = int(block.get("baseFeePerGas") or 0)
                priority = self.w3.eth.max_priority_fee
                out["maxFeePerGas"] = base * 2 + int(priority)
                out["maxPriorityFeePerGas"] = int(priority)
            except Exception:
                out["gasPrice"] = int(self.w3.eth.gas_price)
        return out

    def gas_cost_eth(self, gas_used: int, receipt: dict) -> float:
        assert self.w3 is not None
        if "effectiveGasPrice" in receipt:
            price = int(receipt["effectiveGasPrice"])
        elif "gasPrice" in receipt:
            price = int(receipt["gasPrice"])
        else:
            price = int(self.w3.eth.gas_price)
        return (gas_used * price) / 1e18

    def explorer_tx(self, tx_hash: str) -> str:
        base = EXPLORER_MAINNET if self.cfg.chain.chain_id == 4663 else EXPLORER_TESTNET
        hx = tx_hash if tx_hash.startswith("0x") else f"0x{tx_hash}"
        return f"{base}/tx/{hx}"
