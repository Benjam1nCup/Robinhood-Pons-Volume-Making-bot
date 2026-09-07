"""Shared data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Literal


class SwapSide(str, Enum):
    BUY = "buy"
    SELL = "sell"


class MarketStatus(str, Enum):
    ACTIVE = "active"
    PAUSED = "paused"
    STOPPED = "stopped"


@dataclass
class LaunchEvent:
    token: str
    deployer: str
    dex_factory: str
    pair_token: str
    pool: str
    dex_id: int
    launch_config_id: int
    position_id: int
    restrictions_end_block: int
    initial_buy_amount: int
    block_number: int
    transaction_hash: str
    factory: str


@dataclass
class LaunchState:
    token: str
    deployer: str
    paired_token: str
    position_manager: str
    position_id: int
    dex_id: int
    launch_config_id: int
    restrictions_end_block: int
    supply: int
    is_token0: bool
    pool_fee: int
    exists: bool
    initial_buy_amount: int


@dataclass
class RegisteredToken:
    address: str
    symbol: str
    name: str
    pool: str
    factory: str
    launch_block: int
    launch_state: LaunchState
    status: MarketStatus = MarketStatus.ACTIVE


@dataclass
class SwapRecord:
    pool: str
    block_number: int
    transaction_hash: str
    side: SwapSide
    amount0: int
    amount1: int
    sqrt_price_x96: int
    liquidity: int


@dataclass
class MarketState:
    token: str
    pool: str
    price_weth: float
    fair_price_weth: float
    bid_weth: float
    ask_weth: float
    spread_pct: float
    liquidity_weth: float
    volatility: float
    swap_count: int
    buy_volume_weth: float
    sell_volume_weth: float
    block_number: int
    graduated: bool
    graduation_progress: float


@dataclass
class Quote:
    bid: float
    ask: float
    fair_price: float
    spread: float


@dataclass
class TradeResult:
    side: Literal["BUY", "SELL"]
    token: str
    tx_hash: str | None
    amount_in: int
    amount_out: int
    price_weth: float
    gas_used: int
    gas_cost_eth: float
    slippage_bps: int
    status: int
    dry_run: bool


@dataclass
class DashboardSnapshot:
    token: str
    symbol: str
    fair_price_weth: float
    bid_weth: float
    ask_weth: float
    spread_pct: float
    inventory_tokens: float
    inventory_value_weth: float
    trade_count: int
    buy_volume_weth: float
    sell_volume_weth: float
    gas_cost_eth: float
    realized_pnl_eth: float
    unrealized_pnl_eth: float
    status: str
