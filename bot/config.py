"""YAML + environment configuration."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel

from bot.constants import (
    ACTIVE_FACTORY,
    ACTIVE_FACTORY_START_BLOCK,
    LEGACY_FACTORY,
    LEGACY_FACTORY_START_BLOCK,
    QUOTER_V2,
    SWAP_ROUTER,
    WETH,
)


class BotCfg(BaseModel):
    dry_run: bool = True
    enabled: bool = True
    log_level: str = "INFO"
    log_file: str = "logs/market_maker.log"
    confirm_live_trading: str = "NO"
    poll_interval_s: float = 5.0
    dashboard_interval_s: float = 30.0


class ChainCfg(BaseModel):
    chain_id: int = 4663
    rpc_url: str = "https://rpc.mainnet.chain.robinhood.com"
    request_timeout_s: float = 30.0
    log_chunk_size: int = 1000


class PonsCfg(BaseModel):
    active_factory: str = ACTIVE_FACTORY
    active_factory_start_block: int = ACTIVE_FACTORY_START_BLOCK
    legacy_factory: str = LEGACY_FACTORY
    legacy_factory_start_block: int = LEGACY_FACTORY_START_BLOCK
    swap_router: str = SWAP_ROUTER
    quoter_v2: str = QUOTER_V2
    weth: str = WETH
    fixed_supply: int = 1_000_000_000
    pool_fee: int = 10_000
    graduation_threshold_eth: float = 4.2


class StrategyCfg(BaseModel):
    base_spread: float = 0.025
    price_window: int = 10
    volatility_spread_multiplier: float = 1.5
    max_inventory_tokens: float = 10_000
    max_trade_size_tokens: float = 500
    max_trade_eth: float = 0.005
    min_liquidity_weth: float = 0.01
    min_pool_swaps: int = 1
    trade_cooldown_s: float = 60.0
    liquidity_fraction: float = 0.02
    auto_register_launches: bool = True
    target_token: str = ""


class ExecutionCfg(BaseModel):
    gas_limit: int = 500_000
    max_slippage: float = 0.02
    max_slippage_bps: int = 200
    tx_confirm_timeout_s: float = 120.0
    min_gas_balance_eth: float = 0.002
    max_gas_cost_eth: float = 0.01


class RiskCfg(BaseModel):
    max_position_tokens: float = 10_000
    max_trade_size_tokens: float = 500
    max_slippage: float = 0.02
    max_daily_loss_eth: float = 0.1
    max_gas_cost_eth: float = 0.01


class WalletCfg(BaseModel):
    private_key: str = ""


class StorageCfg(BaseModel):
    database_path: str = "data/market_maker.db"


class AppConfig(BaseModel):
    bot: BotCfg = BotCfg()
    chain: ChainCfg = ChainCfg()
    pons: PonsCfg = PonsCfg()
    strategy: StrategyCfg = StrategyCfg()
    execution: ExecutionCfg = ExecutionCfg()
    risk: RiskCfg = RiskCfg()
    wallet: WalletCfg = WalletCfg()
    storage: StorageCfg = StorageCfg()

    @property
    def live_enabled(self) -> bool:
        return (
            not self.bot.dry_run
            and self.bot.confirm_live_trading.strip().upper() == "YES"
            and bool(self.wallet.private_key)
        )

    @property
    def factories(self) -> list[tuple[str, int]]:
        return [
            (self.pons.active_factory, self.pons.active_factory_start_block),
            (self.pons.legacy_factory, self.pons.legacy_factory_start_block),
        ]


def _as_bool(raw: str | None, default: bool) -> bool:
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def load_config(path: str | Path | None = None) -> AppConfig:
    load_dotenv()
    root = Path(__file__).resolve().parents[1]
    cfg_path = Path(path) if path else root / "config" / "default.yaml"
    raw: dict = {}
    if cfg_path.exists():
        with cfg_path.open() as f:
            raw = yaml.safe_load(f) or {}
    cfg = AppConfig.model_validate(raw)

    if os.getenv("RH_RPC_URL"):
        cfg.chain.rpc_url = os.environ["RH_RPC_URL"]
    if os.getenv("PRIVATE_KEY"):
        cfg.wallet.private_key = os.environ["PRIVATE_KEY"]
    if os.getenv("TARGET_TOKEN"):
        cfg.strategy.target_token = os.environ["TARGET_TOKEN"]
    cfg.bot.confirm_live_trading = os.getenv("CONFIRM_LIVE_TRADING", cfg.bot.confirm_live_trading)
    cfg.bot.dry_run = _as_bool(os.getenv("DRY_RUN"), cfg.bot.dry_run)
    cfg.bot.enabled = _as_bool(os.getenv("BOT_ENABLED"), cfg.bot.enabled)

    return cfg
