# Robinhood Pons Market-Making Bot

Educational market-making / liquidity bot for [pons](https://docs.ponsfamily.com/) tokens on **Robinhood Chain** (chain ID `4663`).

The bot monitors pons Uniswap V3 pools, calculates fair value and inventory-aware bid/ask quotes, executes controlled trades through the official swap router, and tracks PnL, gas, and volume in SQLite.

> **Disclaimer:** For education, testing, research, and authorized liquidity provision only. Not financial advice. Newly launched tokens are volatile and illiquid. Never commit private keys.

## Architecture

```
Robinhood Chain RPC
        │
        ▼
Launch Detection ──► Token Registry
        │
        ▼
Pool Monitor ──► Price Engine ──► Quote Engine
        │              │               │
        └──────────────┴───────────────┘
                       ▼
              Inventory + Risk
                       ▼
              Trade Executor (Swap Router)
                       ▼
              Reconciliation + SQLite
```

Based on the [pons integration docs](https://docs.ponsfamily.com/):

- **Active factory:** `0xA5aAb3F0c6EeadF30Ef1D3Eb997108E976351feB`
- **Swap router:** `0xCaf681a66D020601342297493863E78C959E5cb2`
- **Quoter V2:** `0x33e885eD0Ec9bF04EcfB19341582aADCb4c8A9E7`
- **WETH:** `0x0Bd7D308f8E1639FAb988df18A8011f41EAcAD73`

## Quick Start

```bash
cd Robinhood-Pons-Volume-Making-bot
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Verify RPC connection:

```bash
python main.py --connect
```

Run in dry-run mode against the pons reference token (PONS):

```bash
python main.py --reference
```

Or target any pons token:

```bash
python main.py --token 0xYourTokenAddress
```

Auto-detect new launches (no `--token`):

```bash
python main.py
```

## Configuration

Edit `config/default.yaml` for strategy parameters:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `strategy.base_spread` | `0.025` | Base bid/ask spread (2.5%) |
| `strategy.max_inventory_tokens` | `10000` | Max token inventory |
| `strategy.max_trade_eth` | `0.005` | Max WETH per buy |
| `strategy.trade_cooldown_s` | `60` | Seconds between trades |
| `risk.max_daily_loss_eth` | `0.1` | Daily loss halt threshold |
| `execution.max_slippage` | `0.02` | Max acceptable slippage |

Environment overrides (`.env`):

| Variable | Purpose |
|----------|---------|
| `RH_RPC_URL` | RPC endpoint |
| `PRIVATE_KEY` | Trading wallet |
| `DRY_RUN` | `true` / `false` |
| `CONFIRM_LIVE_TRADING` | Must be `YES` for live |
| `TARGET_TOKEN` | Token address override |
| `BOT_ENABLED` | Emergency stop (`false` halts trading) |

## Live Trading Safety

Live execution requires **all three**:

1. `DRY_RUN=false`
2. `CONFIRM_LIVE_TRADING=YES`
3. `PRIVATE_KEY` set in `.env`

Without these, the bot logs `[DRY RUN]` actions only.

## Project Structure

```
├── main.py                 # CLI entry point
├── config/default.yaml     # Strategy + chain config
├── bot/
│   ├── engine.py           # Main market-making loop
│   ├── blockchain/         # Web3 client
│   ├── pons/               # Launch detection, pool monitoring
│   ├── market/             # Price, quotes, liquidity
│   ├── trading/            # Executor, risk, inventory, slippage
│   ├── analytics/          # PnL and volume tracking
│   └── storage/            # SQLite persistence
└── tests/
```

## Tests

```bash
pytest tests/ -v
```

## Contact

Telegram: [@BenjaminCup](https://t.me/BenjaminCup)

## Resources

- [Pons Documentation](https://docs.ponsfamily.com/)
- [Robinhood Chain RPC](https://rpc.mainnet.chain.robinhood.com)
- [Block Explorer](https://robinhoodchain.blockscout.com)
