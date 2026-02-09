#!/usr/bin/env python3
"""
ATH Dip Buyback Bot - Full Version with Transaction Signing
Requires: pip install solders solana base58
"""

import json
import time
import base64
import base58
import urllib.request
from datetime import datetime

# Solana imports
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction
from solana.rpc.api import Client
from solana.rpc.types import TxOpts
from solana.rpc.commitment import Confirmed

# =============================================================================
# LOAD CONFIG
# =============================================================================

with open("config.json") as f:
    CONFIG = json.load(f)

TOKEN_MINT = CONFIG["token_mint"]
RPC_URL = CONFIG["rpc_url"]
DIP_THRESHOLD = CONFIG["dip_threshold"]
BUYBACK_PERCENT = CONFIG["buyback_percent"]
MIN_SOL_BALANCE = CONFIG["min_sol_balance"]
POLL_INTERVAL = CONFIG["poll_interval"]
SLIPPAGE_BPS = CONFIG.get("slippage_bps", 100)

# Load wallet
WALLET = Keypair.from_base58_string(CONFIG["dev_wallet_private_key"])
WALLET_PUBKEY = str(WALLET.pubkey())

# RPC client
RPC = Client(RPC_URL)

# State
ath = 0.0

# =============================================================================
# HELPERS
# =============================================================================

def log(msg):
    ts = datetime.utcnow().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}")

def fetch_json(url, method="GET", data=None):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    req = urllib.request.Request(url, headers=headers, method=method)
    if data:
        req.data = json.dumps(data).encode()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        log(f"Fetch error: {e}")
        return None

def get_price():
    """Get token price from DexScreener"""
    url = f"https://api.dexscreener.com/latest/dex/tokens/{TOKEN_MINT}"
    data = fetch_json(url)
    if data and "pairs" in data and data["pairs"]:
        pair = data["pairs"][0]
        price = pair.get("priceNative")
        if price:
            return float(price)
    return None

def get_balance():
    """Get wallet SOL balance"""
    try:
        resp = RPC.get_balance(WALLET.pubkey())
        return resp.value / 1e9
    except:
        return None

def get_quote(amount_lamports):
    """For pump.fun tokens, we skip quote and go straight to trade"""
    # Just return the amount - pumpportal handles everything in one call
    return {"amount_sol": amount_lamports / 1e9}

def execute_swap_pumpfun(amount_sol):
    """Execute pump.fun swap via pumpportal (bonding curve)"""
    log(f"Trying pump.fun bonding curve...")
    
    url = "https://pumpportal.fun/api/trade-local"
    payload = {
        "publicKey": WALLET_PUBKEY,
        "action": "buy",
        "mint": TOKEN_MINT,
        "amount": amount_sol,
        "denominatedInSol": "true",
        "slippage": SLIPPAGE_BPS / 100,
        "priorityFee": 0.005  # Increased priority fee
    }
    
    headers = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
    
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            tx_bytes = resp.read()
            log(f"Got {len(tx_bytes)} bytes from pumpportal")
            if len(tx_bytes) < 100:
                log(f"Response too short: {tx_bytes[:200]}")
                return None
            
            # Sign the versioned transaction properly
            from solders.transaction import VersionedTransaction as VTx
            
            tx = VTx.from_bytes(tx_bytes)
            signed_tx = VTx(tx.message, [WALLET])
            
            log("Transaction signed, sending...")
            result = RPC.send_raw_transaction(bytes(signed_tx), opts=TxOpts(skip_preflight=False, preflight_commitment=Confirmed))
            sig = str(result.value)
            log(f"TX submitted: {sig}")
            
            # Wait and confirm
            log("Waiting for confirmation...")
            for i in range(30):  # Wait up to 30 seconds
                time.sleep(1)
                status = RPC.get_signature_statuses([result.value])
                if status.value[0] is not None:
                    if status.value[0].err is None:
                        log("TX CONFIRMED!")
                        return sig
                    else:
                        log(f"TX FAILED: {status.value[0].err}")
                        return None
            log("TX not confirmed after 30s - may have dropped")
            return None
    except Exception as e:
        log(f"Pumpfun error: {e}")
        return None

def execute_swap_raydium(amount_lamports):
    """Execute Raydium/PumpSwap swap (after graduation)"""
    log(f"Trying Raydium/PumpSwap...")
    
    sol = "So11111111111111111111111111111111111111112"
    url = f"https://transaction-v1.raydium.io/transaction/swap-base-in?inputMint={sol}&outputMint={TOKEN_MINT}&amount={amount_lamports}&slippageBps={SLIPPAGE_BPS}&txVersion=V0&wallet={WALLET_PUBKEY}&computeUnitPriceMicroLamports=100000"
    
    swap_data = fetch_json(url)
    if not swap_data or not swap_data.get("success") or "data" not in swap_data:
        return None
    
    tx_list = swap_data["data"]
    if not tx_list:
        return None
    
    for tx_data in tx_list:
        tx_b64 = tx_data.get("transaction")
        if not tx_b64:
            continue
        tx_bytes = base64.b64decode(tx_b64)
        
        # Sign properly
        from solders.transaction import VersionedTransaction as VTx
        tx = VTx.from_bytes(tx_bytes)
        signed_tx = VTx(tx.message, [WALLET])
        
        try:
            result = RPC.send_raw_transaction(bytes(signed_tx), opts=TxOpts(skip_preflight=True, preflight_commitment=Confirmed))
            return str(result.value)
        except Exception as e:
            log(f"Raydium TX error: {e}")
            return None
    return None

def execute_swap(quote):
    """Execute swap - tries pump.fun first, then Raydium/PumpSwap"""
    amount_sol = quote["amount_sol"]
    amount_lamports = int(amount_sol * 1e9)
    
    # Try pump.fun bonding curve first
    sig = execute_swap_pumpfun(amount_sol)
    if sig:
        log(f"TX SENT (pump.fun): {sig}")
        return sig
    
    log("Pump.fun failed, trying Raydium...")
    
    # Fallback to Raydium/PumpSwap
    sig = execute_swap_raydium(amount_lamports)
    if sig:
        log(f"TX SENT (Raydium): {sig}")
        return sig
    
    log("ERROR: All swap methods failed")
    return None

# =============================================================================
# MAIN
# =============================================================================

def check_buyback(price):
    global ath
    
    if price > ath:
        if ath > 0:
            log(f"NEW ATH: {price:.10f}")
        ath = price
        return
    
    dip = (ath - price) / ath
    
    # Debug: show when we're getting close
    if dip >= 0.15:
        log(f"DIP CHECK: {dip*100:.2f}% >= {DIP_THRESHOLD*100}%? {dip >= DIP_THRESHOLD}")
    
    if dip >= DIP_THRESHOLD:
        log(f"")
        log(f"{'='*50}")
        log(f"TRIGGER: -{dip*100:.1f}% from ATH")
        log(f"{'='*50}")
        
        balance = get_balance()
        if not balance:
            log("ERROR: Could not get balance")
            return
        
        available = balance - MIN_SOL_BALANCE
        if available <= 0:
            log("ERROR: Insufficient balance")
            return
        
        buyback_sol = available * BUYBACK_PERCENT
        buyback_lamports = int(buyback_sol * 1e9)
        
        log(f"Balance: {balance:.4f} SOL")
        log(f"Buyback: {buyback_sol:.4f} SOL ({BUYBACK_PERCENT*100}%)")
        
        quote = get_quote(buyback_lamports)
        if not quote:
            log("ERROR: Could not get quote")
            return
        
        log(f"Buying via pump.fun bonding curve...")
        
        sig = execute_swap(quote)
        
        if sig:
            log(f"BUYBACK COMPLETE")
            log(f"https://solscan.io/tx/{sig}")
            ath = price  # Reset ATH
            log(f"ATH reset to {price:.10f}")
        
        log(f"{'='*50}")
        log(f"")

def main():
    global ath
    
    print(f"""
╔══════════════════════════════════════════════════════╗
║          ATH DIP BUYBACK BOT v1.0                    ║
╠══════════════════════════════════════════════════════╣
║  Token:     {TOKEN_MINT[:20]}...
║  Wallet:    {WALLET_PUBKEY[:20]}...
║  Threshold: {DIP_THRESHOLD*100}% dip from ATH
║  Buyback:   {BUYBACK_PERCENT*100}% of fees
╚══════════════════════════════════════════════════════╝
    """)
    
    balance = get_balance()
    log(f"Wallet balance: {balance:.4f} SOL")
    log(f"Monitoring price...")
    log("")
    
    while True:
        try:
            price = get_price()
            if price is None:
                time.sleep(POLL_INTERVAL)
                continue
            
            if ath > 0:
                if price >= ath:
                    log(f"PRICE {price:.10f} | ATH {ath:.10f} | NEW HIGH")
                else:
                    dip = (ath - price) / ath * 100
                    log(f"PRICE {price:.10f} | ATH {ath:.10f} | -{dip:.1f}%")
            else:
                ath = price
                log(f"PRICE {price:.10f} | ATH set")
            
            check_buyback(price)
            
        except KeyboardInterrupt:
            log("Stopped.")
            break
        except Exception as e:
            log(f"Error: {e}")
        
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
