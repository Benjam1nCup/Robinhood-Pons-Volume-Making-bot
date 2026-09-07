"""Uniswap V3 swap execution via pons swap router."""

from __future__ import annotations

import logging
import time

from bot.abis import SWAP_ROUTER_ABI, TOKEN_ABI, WETH_ABI
from bot.blockchain.client import ChainClient
from bot.config import AppConfig
from bot.models import LaunchState, RegisteredToken, TradeResult
from bot.trading.slippage import SlippageEngine
from bot.trading.transaction import TransactionEngine

log = logging.getLogger("mm.executor")


class TradeExecutor:
    def __init__(
        self,
        chain: ChainClient,
        cfg: AppConfig,
        slippage: SlippageEngine,
        tx_engine: TransactionEngine,
    ) -> None:
        self.chain = chain
        self.cfg = cfg
        self.slippage = slippage
        self.tx_engine = tx_engine
        self.router = chain.contract(cfg.pons.swap_router, SWAP_ROUTER_ABI)
        self.weth = chain.contract(cfg.pons.weth, WETH_ABI)

    def buy_token(
        self,
        registered: RegisteredToken,
        amount_in_wei: int,
        dry_run: bool,
    ) -> TradeResult:
        launch_state = registered.launch_state
        token = registered.address
        quoted_out = self.slippage.quote_buy(token, amount_in_wei, launch_state)
        min_out = self.slippage.min_out(quoted_out, self.cfg.execution.max_slippage_bps)
        slippage_bps = int(self.slippage.slippage_ratio(amount_in_wei, quoted_out) * 10_000)
        price = amount_in_wei / 1e18 / (quoted_out / 1e18) if quoted_out > 0 else 0.0

        if dry_run:
            log.info(
                "[DRY RUN] BUY %s amount_in=%s wei min_out=%s tokens",
                registered.symbol,
                amount_in_wei,
                min_out,
            )
            return TradeResult(
                side="BUY",
                token=token,
                tx_hash=None,
                amount_in=amount_in_wei,
                amount_out=min_out,
                price_weth=price,
                gas_used=0,
                gas_cost_eth=0.0,
                slippage_bps=slippage_bps,
                status=1,
                dry_run=True,
            )

        wallet = self.tx_engine.address
        if not wallet:
            return self._failed("BUY", token, amount_in_wei, "no wallet")

        self._ensure_weth(amount_in_wei, wallet)
        weth = self.chain.checksum(self.cfg.pons.weth)
        token_cs = self.chain.checksum(token)
        params = (weth, token_cs, launch_state.pool_fee, wallet, amount_in_wei, min_out, 0)
        fn = self.router.functions.exactInputSingle(params)
        tx = fn.build_transaction(
            {
                "from": wallet,
                "chainId": self.cfg.chain.chain_id,
                "gas": self.cfg.execution.gas_limit,
                "value": 0,
            }
        )
        tx_hash = self.tx_engine.sign_and_send(tx)
        return self._reconcile("BUY", token, tx_hash, amount_in_wei, min_out, price, slippage_bps, dry_run=False)

    def sell_token(
        self,
        registered: RegisteredToken,
        amount_in: int,
        dry_run: bool,
    ) -> TradeResult:
        launch_state = registered.launch_state
        token = registered.address
        quoted_out = self.slippage.quote_sell(token, amount_in, launch_state)
        min_out = self.slippage.min_out(quoted_out, self.cfg.execution.max_slippage_bps)
        slippage_bps = int(self.slippage.slippage_ratio(amount_in, quoted_out) * 10_000)
        price = (quoted_out / 1e18) / (amount_in / 1e18) if amount_in > 0 else 0.0

        if dry_run:
            log.info(
                "[DRY RUN] SELL %s amount_in=%s tokens min_out=%s wei",
                registered.symbol,
                amount_in,
                min_out,
            )
            return TradeResult(
                side="SELL",
                token=token,
                tx_hash=None,
                amount_in=amount_in,
                amount_out=min_out,
                price_weth=price,
                gas_used=0,
                gas_cost_eth=0.0,
                slippage_bps=slippage_bps,
                status=1,
                dry_run=True,
            )

        wallet = self.tx_engine.address
        if not wallet:
            return self._failed("SELL", token, amount_in, "no wallet")

        self.tx_engine.ensure_token_allowance(
            token, self.cfg.pons.swap_router, amount_in, dry_run=False
        )
        weth = self.chain.checksum(self.cfg.pons.weth)
        token_cs = self.chain.checksum(token)
        params = (token_cs, weth, launch_state.pool_fee, wallet, amount_in, min_out, 0)
        fn = self.router.functions.exactInputSingle(params)
        tx = fn.build_transaction(
            {
                "from": wallet,
                "chainId": self.cfg.chain.chain_id,
                "gas": self.cfg.execution.gas_limit,
            }
        )
        tx_hash = self.tx_engine.sign_and_send(tx)
        return self._reconcile("SELL", token, tx_hash, amount_in, min_out, price, slippage_bps, dry_run=False)

    def _ensure_weth(self, amount: int, wallet: str) -> None:
        weth_addr = self.chain.checksum(self.cfg.pons.weth)
        balance = int(self.weth.functions.balanceOf(wallet).call())
        if balance < amount:
            deposit_tx = self.weth.functions.deposit().build_transaction(
                {
                    "from": wallet,
                    "value": amount - balance,
                    "chainId": self.cfg.chain.chain_id,
                    "gas": 80_000,
                }
            )
            self.tx_engine.sign_and_send(deposit_tx)

        allowance = self.chain.contract(weth_addr, TOKEN_ABI).functions.allowance(
            wallet, self.chain.checksum(self.cfg.pons.swap_router)
        ).call()
        if allowance < amount:
            approve_tx = self.tx_engine.build_approve_tx(
                weth_addr, self.cfg.pons.swap_router, 2**256 - 1
            )
            self.tx_engine.sign_and_send(approve_tx)

    def _reconcile(
        self,
        side: str,
        token: str,
        tx_hash: str | None,
        amount_in: int,
        expected_out: int,
        price: float,
        slippage_bps: int,
        dry_run: bool,
    ) -> TradeResult:
        if not tx_hash:
            return self._failed(side, token, amount_in, "broadcast failed")

        receipt = self.chain.wait_for_receipt(tx_hash, self.cfg.execution.tx_confirm_timeout_s)
        if not receipt:
            return self._failed(side, token, amount_in, "receipt timeout", tx_hash)

        gas_used = int(receipt.get("gasUsed", 0))
        gas_cost = self.chain.gas_cost_eth(gas_used, receipt)
        status = int(receipt.get("status", 0))

        if status != 1:
            log.error("Transaction reverted %s", self.chain.explorer_tx(tx_hash))
            return TradeResult(
                side=side,  # type: ignore[arg-type]
                token=token,
                tx_hash=tx_hash,
                amount_in=amount_in,
                amount_out=0,
                price_weth=price,
                gas_used=gas_used,
                gas_cost_eth=gas_cost,
                slippage_bps=slippage_bps,
                status=status,
                dry_run=dry_run,
            )

        log.info(
            "Trade confirmed %s token=%s tx=%s gas=%.6f ETH",
            side,
            token,
            tx_hash[:10],
            gas_cost,
        )
        return TradeResult(
            side=side,  # type: ignore[arg-type]
            token=token,
            tx_hash=tx_hash,
            amount_in=amount_in,
            amount_out=expected_out,
            price_weth=price,
            gas_used=gas_used,
            gas_cost_eth=gas_cost,
            slippage_bps=slippage_bps,
            status=status,
            dry_run=dry_run,
        )

    def _failed(
        self,
        side: str,
        token: str,
        amount_in: int,
        reason: str,
        tx_hash: str | None = None,
    ) -> TradeResult:
        log.error("Trade failed %s token=%s: %s", side, token, reason)
        return TradeResult(
            side=side,  # type: ignore[arg-type]
            token=token,
            tx_hash=tx_hash,
            amount_in=amount_in,
            amount_out=0,
            price_weth=0.0,
            gas_used=0,
            gas_cost_eth=0.0,
            slippage_bps=0,
            status=0,
            dry_run=False,
        )
