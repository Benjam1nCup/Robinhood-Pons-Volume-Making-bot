"""Risk manager unit tests."""

from __future__ import annotations

from bot.config import AppConfig
from bot.storage.database import Database
from bot.trading.risk import RiskManager


def test_risk_rejects_oversized_trade(tmp_path):
    cfg = AppConfig()
    cfg.risk.max_trade_size_tokens = 100
    db = Database(str(tmp_path / "test.db"))
    risk = RiskManager(cfg, db)

    ok, reason = risk.check(
        token="0xabc",
        side="BUY",
        position_tokens=0,
        trade_size_tokens=500,
        slippage=0.01,
        gas_cost_eth=0.001,
        liquidity_weth=1.0,
    )
    assert not ok
    assert "exceeds max" in reason


def test_risk_rejects_low_liquidity(tmp_path):
    cfg = AppConfig()
    cfg.strategy.min_liquidity_weth = 0.5
    db = Database(str(tmp_path / "test.db"))
    risk = RiskManager(cfg, db)

    ok, reason = risk.check(
        token="0xabc",
        side="BUY",
        position_tokens=0,
        trade_size_tokens=10,
        slippage=0.01,
        gas_cost_eth=0.001,
        liquidity_weth=0.01,
    )
    assert not ok
    assert "liquidity" in reason


def test_risk_approves_valid_buy(tmp_path):
    cfg = AppConfig()
    db = Database(str(tmp_path / "test.db"))
    risk = RiskManager(cfg, db)
    risk.mark_trade("0xabc")
    risk._last_trade_at.clear()

    ok, reason = risk.check(
        token="0xabc",
        side="BUY",
        position_tokens=100,
        trade_size_tokens=50,
        slippage=0.01,
        gas_cost_eth=0.001,
        liquidity_weth=2.0,
    )
    assert ok
    assert reason == "ok"
