"""Unit tests for quote, risk, and inventory logic."""

from __future__ import annotations

from bot.market.quotes import (
    dynamic_spread,
    generate_inventory_quotes,
    generate_quotes,
    inventory_adjustment,
)
from bot.market.liquidity import calculate_trade_size


def test_generate_quotes():
    bid, ask = generate_quotes(0.012, 0.025)
    assert abs(bid - 0.0117) < 1e-6
    assert abs(ask - 0.0123) < 1e-6


def test_dynamic_spread_widens_with_volatility():
    low = dynamic_spread(0.025, 0.0, 1.5)
    high = dynamic_spread(0.025, 0.05, 1.5)
    assert high > low


def test_inventory_quotes_skew_with_position():
    neutral = generate_inventory_quotes(0.012, 0, 10000, 0.025)
    heavy = generate_inventory_quotes(0.012, 5000, 10000, 0.025)
    assert heavy.bid < neutral.bid
    assert heavy.ask < neutral.ask


def test_inventory_adjustment_capped():
    assert inventory_adjustment(5000, 10000) == 0.5
    assert inventory_adjustment(20000, 10000) == 1.0


def test_trade_size_scales_with_liquidity():
    small = calculate_trade_size(1.0, 0.02)
    large = calculate_trade_size(10.0, 0.02)
    assert large == 10 * small
