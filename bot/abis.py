"""Minimal ABIs for pons market-making operations."""

from __future__ import annotations

TOKEN_ABI = [
    {"name": "name", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "string"}]},
    {"name": "symbol", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "string"}]},
    {"name": "decimals", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "uint8"}]},
    {"name": "totalSupply", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "uint256"}]},
    {"name": "liquidityPool", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "address"}]},
    {"name": "balanceOf", "type": "function", "stateMutability": "view", "inputs": [{"name": "account", "type": "address"}], "outputs": [{"type": "uint256"}]},
    {"name": "allowance", "type": "function", "stateMutability": "view", "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}], "outputs": [{"type": "uint256"}]},
    {"name": "approve", "type": "function", "stateMutability": "nonpayable", "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}], "outputs": [{"type": "bool"}]},
]

FACTORY_ABI = [
    {
        "name": "getLaunchedToken",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "token", "type": "address"}],
        "outputs": [
            {
                "name": "launched",
                "type": "tuple",
                "components": [
                    {"name": "token", "type": "address"},
                    {"name": "deployer", "type": "address"},
                    {"name": "pairedToken", "type": "address"},
                    {"name": "positionManager", "type": "address"},
                    {"name": "positionId", "type": "uint256"},
                    {"name": "dexId", "type": "uint256"},
                    {"name": "launchConfigId", "type": "uint256"},
                    {"name": "restrictionsEndBlock", "type": "uint256"},
                    {"name": "supply", "type": "uint256"},
                    {"name": "isToken0", "type": "bool"},
                    {"name": "poolFee", "type": "uint24"},
                    {"name": "exists", "type": "bool"},
                    {"name": "initialBuyAmount", "type": "uint256"},
                ],
            }
        ],
    },
    {
        "name": "graduationStatus",
        "type": "function",
        "stateMutability": "view",
        "inputs": [{"name": "token", "type": "address"}],
        "outputs": [
            {"name": "pairedPrincipal", "type": "uint256"},
            {"name": "threshold", "type": "uint256"},
            {"name": "graduated", "type": "bool"},
        ],
    },
    {
        "name": "TokenLaunched",
        "type": "event",
        "inputs": [
            {"name": "token", "type": "address", "indexed": True},
            {"name": "deployer", "type": "address", "indexed": True},
            {"name": "dexFactory", "type": "address", "indexed": True},
            {"name": "pairToken", "type": "address", "indexed": False},
            {"name": "pool", "type": "address", "indexed": False},
            {"name": "dexId", "type": "uint256", "indexed": False},
            {"name": "launchConfigId", "type": "uint256", "indexed": False},
            {"name": "positionId", "type": "uint256", "indexed": False},
            {"name": "restrictionsEndBlock", "type": "uint256", "indexed": False},
            {"name": "initialBuyAmount", "type": "uint256", "indexed": False},
        ],
    },
]

POOL_ABI = [
    {
        "name": "slot0",
        "type": "function",
        "stateMutability": "view",
        "inputs": [],
        "outputs": [
            {"name": "sqrtPriceX96", "type": "uint160"},
            {"name": "tick", "type": "int24"},
            {"name": "observationIndex", "type": "uint16"},
            {"name": "observationCardinality", "type": "uint16"},
            {"name": "observationCardinalityNext", "type": "uint16"},
            {"name": "feeProtocol", "type": "uint8"},
            {"name": "unlocked", "type": "bool"},
        ],
    },
    {"name": "liquidity", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "uint128"}]},
    {"name": "token0", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "address"}]},
    {"name": "token1", "type": "function", "stateMutability": "view", "inputs": [], "outputs": [{"type": "address"}]},
    {
        "name": "Swap",
        "type": "event",
        "inputs": [
            {"name": "sender", "type": "address", "indexed": True},
            {"name": "recipient", "type": "address", "indexed": True},
            {"name": "amount0", "type": "int256", "indexed": False},
            {"name": "amount1", "type": "int256", "indexed": False},
            {"name": "sqrtPriceX96", "type": "uint160", "indexed": False},
            {"name": "liquidity", "type": "uint128", "indexed": False},
            {"name": "tick", "type": "int24", "indexed": False},
        ],
    },
]

QUOTER_V2_ABI = [
    {
        "name": "quoteExactInputSingle",
        "type": "function",
        "stateMutability": "nonpayable",
        "inputs": [
            {
                "name": "params",
                "type": "tuple",
                "components": [
                    {"name": "tokenIn", "type": "address"},
                    {"name": "tokenOut", "type": "address"},
                    {"name": "amountIn", "type": "uint256"},
                    {"name": "fee", "type": "uint24"},
                    {"name": "sqrtPriceLimitX96", "type": "uint160"},
                ],
            }
        ],
        "outputs": [
            {"name": "amountOut", "type": "uint256"},
            {"name": "sqrtPriceX96After", "type": "uint160"},
            {"name": "initializedTicksCrossed", "type": "uint32"},
            {"name": "gasEstimate", "type": "uint256"},
        ],
    },
]

SWAP_ROUTER_ABI = [
    {
        "name": "exactInputSingle",
        "type": "function",
        "stateMutability": "payable",
        "inputs": [
            {
                "name": "params",
                "type": "tuple",
                "components": [
                    {"name": "tokenIn", "type": "address"},
                    {"name": "tokenOut", "type": "address"},
                    {"name": "fee", "type": "uint24"},
                    {"name": "recipient", "type": "address"},
                    {"name": "amountIn", "type": "uint256"},
                    {"name": "amountOutMinimum", "type": "uint256"},
                    {"name": "sqrtPriceLimitX96", "type": "uint160"},
                ],
            }
        ],
        "outputs": [{"name": "amountOut", "type": "uint256"}],
    },
]

WETH_ABI = [
    {"name": "deposit", "type": "function", "stateMutability": "payable", "inputs": [], "outputs": []},
    {"name": "withdraw", "type": "function", "stateMutability": "nonpayable", "inputs": [{"name": "wad", "type": "uint256"}], "outputs": []},
    {"name": "approve", "type": "function", "stateMutability": "nonpayable", "inputs": [{"name": "guy", "type": "address"}, {"name": "wad", "type": "uint256"}], "outputs": [{"type": "bool"}]},
    {"name": "balanceOf", "type": "function", "stateMutability": "view", "inputs": [{"name": "", "type": "address"}], "outputs": [{"type": "uint256"}]},
]
