"""Inventory database tests."""

from __future__ import annotations

from bot.storage.database import Database


def test_inventory_upsert_and_read(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.upsert_inventory("0xtoken", 1000.0, 0.012)
    inv = db.get_inventory("0xtoken")
    assert inv.amount == 1000.0
    assert inv.average_entry == 0.012


def test_trade_persistence(tmp_path):
    db = Database(str(tmp_path / "test.db"))
    db.insert_trade(
        token="0xtoken",
        tx_hash="0xhash",
        side="BUY",
        amount_in=10**15,
        amount_out=10**18,
        price=0.001,
        gas_used=100000,
        slippage_bps=50,
        gas_cost_eth=0.0001,
        status=1,
        dry_run=True,
    )
    assert db.trade_count() == 1
