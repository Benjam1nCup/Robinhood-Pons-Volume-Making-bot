"""Transaction building and signing."""

from __future__ import annotations

import logging

from eth_account import Account

from bot.abis import TOKEN_ABI
from bot.blockchain.client import ChainClient
from bot.config import AppConfig

log = logging.getLogger("mm.transaction")


class TransactionEngine:
    def __init__(self, chain: ChainClient, cfg: AppConfig) -> None:
        self.chain = chain
        self.cfg = cfg
        self._account = Account.from_key(cfg.wallet.private_key) if cfg.wallet.private_key else None

    @property
    def address(self) -> str | None:
        return self._account.address if self._account else None

    def next_nonce(self) -> int:
        assert self.chain.w3 is not None and self._account is not None
        return self.chain.w3.eth.get_transaction_count(self._account.address)

    def sign_and_send(self, tx: dict) -> str | None:
        if not self._account:
            log.error("No wallet configured")
            return None
        assert self.chain.w3 is not None
        w3 = self.chain.w3

        filled = self.chain.fill_gas_price(tx)
        if "nonce" not in filled:
            filled["nonce"] = self.next_nonce()
        if "chainId" not in filled:
            filled["chainId"] = self.cfg.chain.chain_id
        if "gas" not in filled:
            filled["gas"] = self.cfg.execution.gas_limit

        signed = self._account.sign_transaction(filled)
        raw = getattr(signed, "raw_transaction", None) or getattr(signed, "rawTransaction", None)
        tx_hash = w3.eth.send_raw_transaction(raw)
        hx = tx_hash.hex()
        log.info("Submitted tx %s", self.chain.explorer_tx(hx))
        return hx

    def build_approve_tx(self, token: str, spender: str, amount: int) -> dict:
        assert self._account is not None
        contract = self.chain.contract(token, TOKEN_ABI)
        fn = contract.functions.approve(self.chain.checksum(spender), amount)
        return fn.build_transaction(
            {
                "from": self._account.address,
                "chainId": self.cfg.chain.chain_id,
                "gas": 100_000,
            }
        )

    def ensure_token_allowance(self, token: str, spender: str, amount: int, dry_run: bool) -> None:
        wallet = self.address
        if not wallet or dry_run:
            return
        contract = self.chain.contract(token, TOKEN_ABI)
        allowance = int(contract.functions.allowance(wallet, self.chain.checksum(spender)).call())
        if allowance >= amount:
            return
        tx = self.build_approve_tx(token, spender, 2**256 - 1)
        self.sign_and_send(tx)
