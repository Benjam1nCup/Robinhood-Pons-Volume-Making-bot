"""SQLite persistence for trades and inventory."""

from __future__ import annotations

import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class InventoryRow:
    token: str
    amount: float
    average_entry: float
    updated_at: int


class Database:
    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.path)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY,
                token TEXT NOT NULL,
                tx_hash TEXT,
                side TEXT NOT NULL,
                amount_in REAL NOT NULL,
                amount_out REAL NOT NULL,
                price REAL NOT NULL,
                gas_used INTEGER,
                slippage_bps INTEGER,
                gas_cost_eth REAL,
                status INTEGER,
                dry_run INTEGER,
                timestamp INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS inventory (
                token TEXT PRIMARY KEY,
                amount REAL NOT NULL,
                average_entry REAL NOT NULL,
                updated_at INTEGER NOT NULL
            );

            CREATE TABLE IF NOT EXISTS pnl_daily (
                id INTEGER PRIMARY KEY,
                token TEXT NOT NULL,
                realized_pnl_eth REAL NOT NULL,
                day TEXT NOT NULL,
                timestamp INTEGER NOT NULL
            );
            """
        )
        self._conn.commit()

    def insert_trade(
        self,
        token: str,
        tx_hash: str | None,
        side: str,
        amount_in: int,
        amount_out: int,
        price: float,
        gas_used: int,
        slippage_bps: int,
        gas_cost_eth: float,
        status: int,
        dry_run: bool,
    ) -> None:
        self._conn.execute(
            """
            INSERT INTO trades (
                token, tx_hash, side, amount_in, amount_out, price,
                gas_used, slippage_bps, gas_cost_eth, status, dry_run, timestamp
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token,
                tx_hash,
                side,
                amount_in,
                amount_out,
                price,
                gas_used,
                slippage_bps,
                gas_cost_eth,
                status,
                int(dry_run),
                int(time.time()),
            ),
        )
        self._conn.commit()

    def upsert_inventory(self, token: str, amount: float, average_entry: float) -> None:
        self._conn.execute(
            """
            INSERT INTO inventory (token, amount, average_entry, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(token) DO UPDATE SET
                amount=excluded.amount,
                average_entry=excluded.average_entry,
                updated_at=excluded.updated_at
            """,
            (token, amount, average_entry, int(time.time())),
        )
        self._conn.commit()

    def get_inventory(self, token: str) -> InventoryRow:
        row = self._conn.execute(
            "SELECT token, amount, average_entry, updated_at FROM inventory WHERE token = ?",
            (token,),
        ).fetchone()
        if not row:
            return InventoryRow(token=token, amount=0.0, average_entry=0.0, updated_at=0)
        return InventoryRow(
            token=row["token"],
            amount=float(row["amount"]),
            average_entry=float(row["average_entry"]),
            updated_at=int(row["updated_at"]),
        )

    def add_realized_pnl(self, token: str, pnl_eth: float) -> None:
        day = time.strftime("%Y-%m-%d", time.gmtime())
        self._conn.execute(
            "INSERT INTO pnl_daily (token, realized_pnl_eth, day, timestamp) VALUES (?, ?, ?, ?)",
            (token, pnl_eth, day, int(time.time())),
        )
        self._conn.commit()

    def daily_realized_loss_eth(self) -> float:
        day = time.strftime("%Y-%m-%d", time.gmtime())
        row = self._conn.execute(
            "SELECT COALESCE(SUM(realized_pnl_eth), 0) AS total FROM pnl_daily WHERE day = ?",
            (day,),
        ).fetchone()
        total = float(row["total"]) if row else 0.0
        return abs(min(0.0, total))

    def total_realized_pnl(self) -> float:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(realized_pnl_eth), 0) AS total FROM pnl_daily"
        ).fetchone()
        return float(row["total"]) if row else 0.0

    def trade_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) AS c FROM trades WHERE status = 1").fetchone()
        return int(row["c"]) if row else 0

    def total_gas_cost_eth(self) -> float:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(gas_cost_eth), 0) AS total FROM trades WHERE status = 1"
        ).fetchone()
        return float(row["total"]) if row else 0.0

    def buy_volume_weth(self) -> float:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(amount_in), 0) AS total FROM trades WHERE side = 'BUY' AND status = 1"
        ).fetchone()
        return float(row["total"]) / 1e18 if row else 0.0

    def sell_volume_weth(self) -> float:
        row = self._conn.execute(
            "SELECT COALESCE(SUM(amount_out), 0) AS total FROM trades WHERE side = 'SELL' AND status = 1"
        ).fetchone()
        return float(row["total"]) / 1e18 if row else 0.0
