#!/usr/bin/env python3
"""Pons Market-Making Bot — Robinhood Chain."""

from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading

from bot.blockchain.client import ChainClient
from bot.config import load_config
from bot.constants import REFERENCE_TOKEN
from bot.engine import MarketMakingEngine
from bot.logging_setup import setup_logging

log = logging.getLogger("mm.main")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pons market-making bot on Robinhood Chain (chain ID 4663)"
    )
    parser.add_argument("--config", default=None, help="Path to config YAML")
    parser.add_argument(
        "--connect",
        action="store_true",
        help="Verify RPC connection and exit",
    )
    parser.add_argument(
        "--token",
        default=None,
        help="Target token address (overrides config strategy.target_token)",
    )
    parser.add_argument(
        "--reference",
        action="store_true",
        help=f"Use pons reference token {REFERENCE_TOKEN}",
    )
    parser.add_argument(
        "--scan-only",
        action="store_true",
        help="Detect launches without trading",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)

    if args.reference:
        cfg.strategy.target_token = REFERENCE_TOKEN
    if args.token:
        cfg.strategy.target_token = args.token
    if args.scan_only:
        cfg = cfg.model_copy(update={"bot": cfg.bot.model_copy(update={"dry_run": True})})

    setup_logging(cfg.bot.log_level, cfg.bot.log_file)

    log.info("Starting Pons Market Maker (dry_run=%s live=%s)", cfg.bot.dry_run, cfg.live_enabled)
    if not cfg.bot.dry_run and not cfg.live_enabled:
        log.warning(
            "Live trading disabled — set DRY_RUN=false, CONFIRM_LIVE_TRADING=YES, and PRIVATE_KEY"
        )

    chain = ChainClient(cfg)
    if not chain.connect():
        return 1

    if args.connect:
        log.info("Connection OK — chain_id=%s block=%s", cfg.chain.chain_id, chain.block_number())
        return 0

    engine = MarketMakingEngine(chain, cfg)
    if not engine.bootstrap():
        return 1

    stop = threading.Event()

    def _shutdown(signum, frame) -> None:
        log.info("Shutdown signal received")
        stop.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    log.info("Monitoring pons on Robinhood Chain (chain_id=%s)", cfg.chain.chain_id)
    for factory, start in cfg.factories:
        log.info("  factory=%s from_block=%s", factory, start)

    engine.run_forever(stop)
    log.info("Market maker stopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
