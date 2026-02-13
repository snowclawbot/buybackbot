# ATH Dip Buyback Bot ($recoilcoin)

Automated buyback bot for Solana tokens. Monitors price and executes buybacks when price dips from all-time high.

## How It Works

1. Monitors token price via DexScreener
2. Tracks all-time high (ATH)
3. When price dips X% below ATH → triggers buyback
4. Uses dev wallet fees to buy tokens via pump.fun or Raydium
5. Resets ATH after buyback
6. Repeats

## Features

- **ATH Tracking** — Automatically tracks highest price
- **Configurable Dip Threshold** — Default 25% from ATH
- **Pump.fun Support** — Works with bonding curve AND graduated tokens (PumpSwap)
- **Raydium Fallback** — Falls back to Raydium for other AMM pools
- **Transaction Confirmation** — Waits for actual on-chain confirmation
- **Minimal Dependencies** — Only requires `solana`, `solders`, `base58`

## Setup

### 1. Clone & Install

```bash
git clone https://github.com/YOUR_USERNAME/ath-buyback-bot.git
cd ath-buyback-bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

Copy the example config and fill in your details:

```bash
cp config.example.json config.json
nano config.json
```

```json
{
  "token_mint": "YOUR_TOKEN_MINT_ADDRESS",
  "dev_wallet_pubkey": "YOUR_WALLET_PUBLIC_KEY",
  "dev_wallet_private_key": "YOUR_PRIVATE_KEY_BASE58",
  "rpc_url": "https://mainnet.helius-rpc.com/?api-key=YOUR_KEY",
  "dip_threshold": 0.25,
  "buyback_percent": 0.90,
  "min_sol_balance": 0.01,
  "poll_interval": 3,
  "slippage_bps": 100
}
```

### 3. Run

```bash
python buyback_full.py
```

Run in background:
```bash
nohup python buyback_full.py > buyback.log 2>&1 &
```

## Configuration Options

| Option | Default | Description |
|--------|---------|-------------|
| `token_mint` | - | Token contract address |
| `dev_wallet_pubkey` | - | Your wallet public key |
| `dev_wallet_private_key` | - | Your wallet private key (base58) |
| `rpc_url` | - | Solana RPC endpoint (Helius recommended) |
| `dip_threshold` | 0.25 | Trigger buyback at 25% dip from ATH |
| `buyback_percent` | 0.90 | Use 90% of wallet balance |
| `min_sol_balance` | 0.01 | Keep 0.01 SOL for gas |
| `poll_interval` | 3 | Check price every 3 seconds |
| `slippage_bps` | 100 | 1% slippage tolerance |

## RPC Recommendations

Use a dedicated RPC to avoid rate limits:
- **Helius** — https://helius.dev (recommended)
- **Quicknode** — https://quicknode.com
- **Triton** — https://triton.one

## Commands

```bash
# Check logs
tail -f buyback.log

# Check if running
ps aux | grep buyback

# Stop bot
pkill -f buyback_full.py
```

## How Buyback Logic Works

```
Price: $0.00001 (ATH set)
Price: $0.00001 (ATH $0.00001 | 0%)
Price: $0.000008 (ATH $0.00001 | -20%)
Price: $0.0000075 (ATH $0.00001 | -25%) ← TRIGGER!
→ Buyback executes with 90% of wallet
→ ATH resets to $0.0000075
→ Monitoring continues...
```

## Supported Platforms

- ✅ Pump.fun (bonding curve)
- ✅ PumpSwap (graduated pump.fun tokens)
- ✅ Raydium (fallback)

## Security

⚠️ **Never commit your `config.json` with private keys!**

The `.gitignore` excludes `config.json` by default. Use `config.example.json` as a template.

## License

MIT
