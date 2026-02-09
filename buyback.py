#!/usr/bin/env python3
"""
ATH Dip Buyback Bot
- Tracks all-time high
- Buys back with 90% of dev fees when price dips 25% from ATH
- For pump.fun tokens on Solana
"""

import json
import time
import base64
import urllib.request
import urllib.error
from datetime import datetime

# =============================================================================
# CONFIG - EDIT THESE
# =============================================================================

TOKEN_MINT = "YOUR_TOKEN_MINT_ADDRESS"  # The token to buy
DEV_WALLET_PRIVATE_KEY = "YOUR_PRIVATE_KEY_BASE58"  # Dev wallet private key
DIP_THRESHOLD = 0.25  # 25% dip from ATH triggers buyback
BUYBACK_PERCENT = 0.90  # Use 90% of wallet balance
MIN_SOL_BALANCE = 0.01  # Minimum SOL to keep for gas
POLL_INTERVAL = 5  # Seconds between price checks
RPC_URL = "https://api.mainnet-beta.solana.com"

# =============================================================================
# STATE
# =============================================================================

ath = 0.0
last_buyback_time = 0

# =============================================================================
# HELPERS
# =============================================================================

def log(msg):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}")

def fetch_json(url, headers=None):
    """Fetch JSON from URL"""
    req = urllib.request.Request(url, headers=headers or {
        "User-Agent": "BuybackBot/1.0"
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        log(f"Fetch error: {e}")
        return None

def get_token_price(mint):
    """Get token price in SOL from Jupiter"""
    url = f"https://api.jup.ag/price/v2?ids={mint}&vsToken=So11111111111111111111111111111111111111112"
    data = fetch_json(url)
    if data and "data" in data and mint in data["data"]:
        price = data["data"][mint].get("price")
        if price:
            return float(price)
    
    # Fallback: try DexScreener
    url = f"https://api.dexscreener.com/latest/dex/tokens/{mint}"
    data = fetch_json(url)
    if data and "pairs" in data and data["pairs"]:
        pair = data["pairs"][0]
        return float(pair.get("priceNative", 0))
    
    return None

def get_wallet_balance(wallet_pubkey):
    """Get SOL balance of wallet"""
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "getBalance",
        "params": [wallet_pubkey]
    }
    req = urllib.request.Request(
        RPC_URL,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            lamports = data.get("result", {}).get("value", 0)
            return lamports / 1e9  # Convert to SOL
    except Exception as e:
        log(f"Balance fetch error: {e}")
        return None

def get_jupiter_quote(input_mint, output_mint, amount_lamports):
    """Get swap quote from Jupiter"""
    url = f"https://quote-api.jup.ag/v6/quote?inputMint={input_mint}&outputMint={output_mint}&amount={amount_lamports}&slippageBps=100"
    return fetch_json(url)

def execute_jupiter_swap(quote, wallet_pubkey):
    """Execute swap via Jupiter API"""
    url = "https://quote-api.jup.ag/v6/swap"
    payload = {
        "quoteResponse": quote,
        "userPublicKey": wallet_pubkey,
        "wrapAndUnwrapSol": True
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        log(f"Swap API error: {e}")
        return None

# =============================================================================
# MAIN LOGIC
# =============================================================================

def check_and_buyback(price, wallet_pubkey):
    """Check if buyback should trigger and execute"""
    global ath, last_buyback_time
    
    # Update ATH
    if price > ath:
        if ath > 0:
            log(f"NEW ATH: {price:.10f} SOL (prev: {ath:.10f})")
        ath = price
        return False
    
    # Calculate dip percentage
    dip_pct = (ath - price) / ath
    
    # Check if we hit threshold
    if dip_pct >= DIP_THRESHOLD:
        log(f"DIP THRESHOLD REACHED: -{dip_pct*100:.1f}% from ATH")
        
        # Get wallet balance
        balance = get_wallet_balance(wallet_pubkey)
        if balance is None:
            log("ERROR: Could not fetch wallet balance")
            return False
        
        log(f"Wallet balance: {balance:.4f} SOL")
        
        # Calculate buyback amount (90% of balance, minus gas buffer)
        available = balance - MIN_SOL_BALANCE
        if available <= 0:
            log("ERROR: Insufficient balance for buyback")
            return False
        
        buyback_amount = available * BUYBACK_PERCENT
        buyback_lamports = int(buyback_amount * 1e9)
        
        log(f"BUYBACK TRIGGERED: {buyback_amount:.4f} SOL")
        
        # Get Jupiter quote
        sol_mint = "So11111111111111111111111111111111111111112"
        quote = get_jupiter_quote(sol_mint, TOKEN_MINT, buyback_lamports)
        
        if not quote:
            log("ERROR: Could not get Jupiter quote")
            return False
        
        out_amount = int(quote.get("outAmount", 0))
        log(f"Quote: {buyback_amount:.4f} SOL -> {out_amount:,} tokens")
        
        # Execute swap
        swap_result = execute_jupiter_swap(quote, wallet_pubkey)
        
        if swap_result and "swapTransaction" in swap_result:
            log("SWAP TRANSACTION RECEIVED")
            log(">>> SIGN AND SEND TRANSACTION MANUALLY <<<")
            log(f"Transaction (base64): {swap_result['swapTransaction'][:80]}...")
            
            # In production, you would sign and send here
            # For now, we just log that it would execute
            
            # Reset ATH to current price after buyback
            ath = price
            last_buyback_time = time.time()
            log(f"ATH reset to: {ath:.10f}")
            return True
        else:
            log("ERROR: Swap execution failed")
            return False
    
    return False

def get_wallet_pubkey_from_private():
    """
    Note: In production, use solders or solana-py to derive pubkey
    For now, you need to set this manually
    """
    # You'll need to derive this from your private key
    # Or just set it directly:
    return "YOUR_WALLET_PUBLIC_KEY"

def main():
    global ath
    
    log("=" * 60)
    log("ATH DIP BUYBACK BOT")
    log("=" * 60)
    log(f"Token: {TOKEN_MINT}")
    log(f"Dip threshold: {DIP_THRESHOLD * 100}%")
    log(f"Buyback percent: {BUYBACK_PERCENT * 100}%")
    log(f"Poll interval: {POLL_INTERVAL}s")
    log("=" * 60)
    
    wallet_pubkey = get_wallet_pubkey_from_private()
    log(f"Wallet: {wallet_pubkey}")
    
    # Initial balance check
    balance = get_wallet_balance(wallet_pubkey)
    if balance:
        log(f"Initial balance: {balance:.4f} SOL")
    
    log("Starting price monitor...")
    log("")
    
    while True:
        try:
            price = get_token_price(TOKEN_MINT)
            
            if price is None:
                log("WARNING: Could not fetch price, retrying...")
                time.sleep(POLL_INTERVAL)
                continue
            
            # Calculate current dip from ATH (if we have an ATH)
            if ath > 0:
                dip_pct = (ath - price) / ath * 100
                log(f"PRICE: {price:.10f} | ATH: {ath:.10f} | DIP: {dip_pct:.1f}%")
            else:
                log(f"PRICE: {price:.10f} | Setting initial ATH...")
                ath = price
            
            # Check for buyback
            check_and_buyback(price, wallet_pubkey)
            
        except KeyboardInterrupt:
            log("Shutting down...")
            break
        except Exception as e:
            log(f"ERROR: {e}")
        
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
