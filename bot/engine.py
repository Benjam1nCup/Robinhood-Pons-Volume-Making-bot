"""Market-making engine — main orchestration loop."""

from __future__ import annotations

import logging
import time

from bot.analytics.pnl import PnLTracker
from bot.analytics.volume import TradingAnalytics
from bot.blockchain.client import ChainClient
from bot.config import AppConfig
from bot.market.liquidity import LiquidityEngine
from bot.market.price import PriceEngine
from bot.market.quotes import QuoteEngine
from bot.models import DashboardSnapshot, MarketState, RegisteredToken, SwapSide
from bot.pons.factory import FactoryReader
from bot.pons.launch import LaunchMonitor, TokenRegistry
from bot.pons.pool import PoolMonitor
from bot.storage.database import Database
from bot.trading.executor import TradeExecutor
from bot.trading.inventory import InventoryManager
from bot.trading.risk import RiskManager
from bot.trading.slippage import SlippageEngine
from bot.trading.transaction import TransactionEngine

log = logging.getLogger("mm.engine")


class MarketMakingEngine:
    def __init__(self, chain: ChainClient, cfg: AppConfig) -> None:
        self.chain = chain
        self.cfg = cfg
        self.db = Database(cfg.storage.database_path)
        self.registry = TokenRegistry()
        self.factory = FactoryReader(chain, cfg)
        self.price_engine = PriceEngine(chain)
        self.quote_engine = QuoteEngine(cfg)
        self.liquidity_engine = LiquidityEngine(chain, cfg, self.factory)
        self.pool_monitor = PoolMonitor(chain, cfg)
        self.slippage = SlippageEngine(chain, cfg)
        self.tx_engine = TransactionEngine(chain, cfg)
        self.executor = TradeExecutor(chain, cfg, self.slippage, self.tx_engine)
        self.inventory = InventoryManager(chain, cfg, self.db)
        self.risk = RiskManager(cfg, self.db)
        self.pnl = PnLTracker(self.db)
        self.analytics = TradingAnalytics()
        self.launch_monitor = LaunchMonitor(chain, cfg, self.registry)
        self._last_swap_block: dict[str, int] = {}
        self._last_dashboard_at = 0.0

    def bootstrap(self) -> bool:
        target = self.cfg.strategy.target_token.strip()
        if target:
            registered = self.launch_monitor.register_target_token(target)
            if not registered:
                log.error("Failed to register target token %s", target)
                return False
            log.info("Target token registered: %s (%s)", registered.symbol, registered.address)
            return True

        if not self.cfg.strategy.auto_register_launches:
            log.error("No target_token and auto_register_launches=false")
            return False

        log.info("Waiting for pons launch (or set strategy.target_token in config)")
        return True

    def update_market_state(self, registered: RegisteredToken) -> MarketState | None:
        launch_state = registered.launch_state
        pool = registered.pool
        token = registered.address

        price_weth = self.price_engine.current_price_weth(pool, launch_state)
        if price_weth <= 0:
            return None

        fair_price = self.price_engine.fair_price(
            token, pool, launch_state, self.cfg.strategy.price_window
        )
        tracker = self.price_engine.tracker_for(token, self.cfg.strategy.price_window)
        volatility = tracker.volatility()
        quote = self.quote_engine.build_quote(
            fair_price=fair_price,
            inventory_tokens=self.inventory.tokens(token, self.tx_engine.address),
            volatility=volatility,
        )

        liquidity_weth = self.liquidity_engine.estimate_liquidity_weth(
            registered.factory, pool, token, launch_state, price_weth
        )

        from_block = self._last_swap_block.get(token.lower(), registered.launch_block or self.chain.block_number() - 50)
        swaps = self.pool_monitor.fetch_swaps(
            pool, token, launch_state.paired_token, from_block
        )
        if swaps:
            self._last_swap_block[token.lower()] = swaps[-1].block_number

        buy_vol = sum(
            self.pool_monitor.pair_volume_weth(s, launch_state)
            for s in swaps
            if s.side == SwapSide.BUY
        )
        sell_vol = sum(
            self.pool_monitor.pair_volume_weth(s, launch_state)
            for s in swaps
            if s.side == SwapSide.SELL
        )

        grad = self.factory.graduation_status(registered.factory, token)
        graduated = grad[2] if grad else False
        progress = (grad[0] / grad[1]) if grad and grad[1] > 0 else 0.0

        spread_pct = ((quote.ask - quote.bid) / fair_price * 100) if fair_price > 0 else 0.0

        return MarketState(
            token=token,
            pool=pool,
            price_weth=price_weth,
            fair_price_weth=fair_price,
            bid_weth=quote.bid,
            ask_weth=quote.ask,
            spread_pct=spread_pct,
            liquidity_weth=liquidity_weth,
            volatility=volatility,
            swap_count=len(swaps),
            buy_volume_weth=buy_vol,
            sell_volume_weth=sell_vol,
            block_number=self.chain.block_number(),
            graduated=graduated,
            graduation_progress=progress,
        )

    def execute_if_needed(self, registered: RegisteredToken, market: MarketState) -> None:
        if market.swap_count < self.cfg.strategy.min_pool_swaps and registered.launch_block > 0:
            return

        wallet = self.tx_engine.address
        position = self.inventory.tokens(registered.address, wallet)
        liquidity = market.liquidity_weth
        trade_eth = self.liquidity_engine.trade_size_eth(liquidity)
        trade_tokens = self.liquidity_engine.trade_size_tokens(liquidity, market.fair_price_weth)
        amount_in_wei = int(trade_eth * 1e18)
        amount_in_tokens = int(trade_tokens * 1e18)

        dry_run = not self.cfg.live_enabled
        side: str | None = None

        if market.price_weth <= market.bid_weth and position + trade_tokens <= self.cfg.risk.max_position_tokens:
            side = "BUY"
        elif market.price_weth >= market.ask_weth and position * 1e18 >= amount_in_tokens // 2:
            side = "SELL"

        if not side:
            return

        slippage = self.cfg.execution.max_slippage
        est_gas = self.cfg.execution.max_gas_cost_eth * 0.5

        ok, reason = self.risk.check(
            token=registered.address,
            side=side,
            position_tokens=position,
            trade_size_tokens=trade_tokens,
            slippage=slippage,
            gas_cost_eth=est_gas,
            liquidity_weth=liquidity,
        )
        if not ok:
            log.debug("Trade rejected: %s", reason)
            return

        if side == "BUY":
            result = self.executor.buy_token(registered, amount_in_wei, dry_run=dry_run)
            if result.status == 1:
                tokens = result.amount_out / 1e18
                self.inventory.record_buy(registered.address, tokens, result.price_weth)
        else:
            sell_amount = min(int(position * 1e18), amount_in_tokens)
            if sell_amount <= 0:
                return
            result = self.executor.sell_token(registered, sell_amount, dry_run=dry_run)
            if result.status == 1:
                self.inventory.record_sell(registered.address, sell_amount / 1e18)

        self.risk.mark_trade(registered.address)
        self.analytics.record_trade(result)
        inv = self.db.get_inventory(registered.address)
        self.pnl.on_trade(result, inv)

        self.db.insert_trade(
            token=registered.address,
            tx_hash=result.tx_hash,
            side=result.side,
            amount_in=result.amount_in,
            amount_out=result.amount_out,
            price=result.price_weth,
            gas_used=result.gas_used,
            slippage_bps=result.slippage_bps,
            gas_cost_eth=result.gas_cost_eth,
            status=result.status,
            dry_run=result.dry_run,
        )

    def dashboard_snapshot(self, registered: RegisteredToken, market: MarketState) -> DashboardSnapshot:
        wallet = self.tx_engine.address
        inv_tokens = self.inventory.tokens(registered.address, wallet)
        inv_value = inv_tokens * market.fair_price_weth
        gas = self.db.total_gas_cost_eth()
        realized = self.db.total_realized_pnl()
        unrealized = self.pnl.unrealized_pnl_eth(registered.address, inv_tokens, market.fair_price_weth)

        status = "ACTIVE"
        if self.risk.halted:
            status = f"HALTED ({self.risk.halt_reason})"
        elif not self.cfg.bot.enabled:
            status = "DISABLED"

        return DashboardSnapshot(
            token=registered.address,
            symbol=registered.symbol,
            fair_price_weth=market.fair_price_weth,
            bid_weth=market.bid_weth,
            ask_weth=market.ask_weth,
            spread_pct=market.spread_pct,
            inventory_tokens=inv_tokens,
            inventory_value_weth=inv_value,
            trade_count=self.db.trade_count(),
            buy_volume_weth=self.db.buy_volume_weth(),
            sell_volume_weth=self.db.sell_volume_weth(),
            gas_cost_eth=gas,
            realized_pnl_eth=realized,
            unrealized_pnl_eth=unrealized,
            status=status,
        )

    def print_dashboard(self, snap: DashboardSnapshot) -> None:
        log.info(
            "\n"
            "══════════════════════════════════════════\n"
            " Pons Market Maker\n"
            "──────────────────────────────────────────\n"
            " Token:       %s (%s)\n"
            " Fair Price:  %.8f WETH\n"
            " Bid:         %.8f WETH\n"
            " Ask:         %.8f WETH\n"
            " Spread:      %.2f%%\n"
            " Inventory:   %.4f tokens (%.6f WETH)\n"
            " Trades:      %d\n"
            " Buy Volume:  %.6f WETH\n"
            " Sell Volume: %.6f WETH\n"
            " Gas:         %.6f ETH\n"
            " Realized:    %+.6f ETH\n"
            " Unrealized:  %+.6f ETH\n"
            " Status:      %s\n"
            "══════════════════════════════════════════",
            snap.symbol,
            snap.token[:10] + "...",
            snap.fair_price_weth,
            snap.bid_weth,
            snap.ask_weth,
            snap.spread_pct,
            snap.inventory_tokens,
            snap.inventory_value_weth,
            snap.trade_count,
            snap.buy_volume_weth,
            snap.sell_volume_weth,
            snap.gas_cost_eth,
            snap.realized_pnl_eth,
            snap.unrealized_pnl_eth,
            snap.status,
        )

    def run_once(self) -> None:
        if self.cfg.strategy.auto_register_launches and not self.cfg.strategy.target_token:
            self.launch_monitor.poll_once()

        active = self.registry.list_active()
        if not active:
            return

        for registered in active:
            market = self.update_market_state(registered)
            if not market:
                continue

            self.execute_if_needed(registered, market)

            now = time.time()
            if now - self._last_dashboard_at >= self.cfg.bot.dashboard_interval_s:
                snap = self.dashboard_snapshot(registered, market)
                self.print_dashboard(snap)
                self._last_dashboard_at = now

    def run_forever(self, stop_event) -> None:
        log.info(
            "Market maker started (dry_run=%s live=%s poll=%ss)",
            self.cfg.bot.dry_run,
            self.cfg.live_enabled,
            self.cfg.bot.poll_interval_s,
        )
        while not stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:
                log.exception("Engine loop error: %s", exc)
            stop_event.wait(self.cfg.bot.poll_interval_s)
