"""Risk checks before execution."""

from __future__ import annotations

import logging
import time

from bot.config import AppConfig
from bot.storage.database import Database

log = logging.getLogger("mm.risk")


class RiskManager:
    def __init__(self, cfg: AppConfig, db: Database) -> None:
        self.cfg = cfg
        self.db = db
        self._last_trade_at: dict[str, float] = {}
        self._halted = False
        self._halt_reason = ""

    @property
    def halted(self) -> bool:
        return self._halted or not self.cfg.bot.enabled

    @property
    def halt_reason(self) -> str:
        if not self.cfg.bot.enabled:
            return "BOT_ENABLED=false"
        return self._halt_reason

    def halt(self, reason: str) -> None:
        self._halted = True
        self._halt_reason = reason
        log.warning("Risk halt: %s", reason)

    def reset_halt(self) -> None:
        self._halted = False
        self._halt_reason = ""

    def cooldown_ok(self, token: str) -> bool:
        last = self._last_trade_at.get(token.lower(), 0)
        return (time.time() - last) >= self.cfg.strategy.trade_cooldown_s

    def mark_trade(self, token: str) -> None:
        self._last_trade_at[token.lower()] = time.time()

    def check(
        self,
        token: str,
        side: str,
        position_tokens: float,
        trade_size_tokens: float,
        slippage: float,
        gas_cost_eth: float,
        liquidity_weth: float,
    ) -> tuple[bool, str]:
        if self.halted:
            return False, self.halt_reason

        if not self.cooldown_ok(token):
            return False, "trade cooldown active"

        if liquidity_weth < self.cfg.strategy.min_liquidity_weth:
            return False, f"liquidity {liquidity_weth:.6f} WETH below minimum"

        if trade_size_tokens > self.cfg.risk.max_trade_size_tokens:
            return False, f"trade size {trade_size_tokens:.2f} exceeds max"

        if slippage > self.cfg.risk.max_slippage:
            return False, f"slippage {slippage:.4f} exceeds max"

        if gas_cost_eth > self.cfg.risk.max_gas_cost_eth:
            return False, f"estimated gas {gas_cost_eth:.6f} ETH exceeds max"

        daily_loss = self.db.daily_realized_loss_eth()
        if daily_loss >= self.cfg.risk.max_daily_loss_eth:
            self.halt("daily loss limit reached")
            return False, "daily loss limit reached"

        if side == "BUY":
            if position_tokens + trade_size_tokens > self.cfg.risk.max_position_tokens:
                return False, f"position {position_tokens + trade_size_tokens:.2f} exceeds max"

        return True, "ok"
