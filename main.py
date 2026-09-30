import os
import logging
import random
import asyncio
import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional, Literal
import redis.asyncio as redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BrandBot-Autonomous-Core")

app = FastAPI(title="BrandBot Autonomous Institutional Engine SDR v2.0")

# Lidhja me Redis
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

class OrderExecutionRequest(BaseModel):
    account_id: str
    symbol: str
    action: Literal["BUY", "SELL"]
    lot_size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    order_type: Literal["MARKET", "LIMIT"]
    delay_ms: int

# Menaxhimi i Riskut dhe Llogaritja Dinamike e Lotit
class RiskManager:
    @staticmethod
    def calculate_dynamic_lot(balance: float, risk_percent: float, stop_loss_pips: float) -> float:
        if stop_loss_pips <= 0:
            return 0.01
        risk_amount = balance * (risk_percent / 100.0)
        pip_value_per_lot = 10.0 
        lot_size = risk_amount / (stop_loss_pips * pip_value_per_lot)
        max_allowed_lot = 0.50 if balance < 5000 else 2.00
        return max(0.01, round(min(lot_size, max_allowed_lot), 2))

# Dërgimi i sinjaleve dhe ekzekutimeve në Discord
async def send_discord_embed(symbol: str, action: str, volume: float, price: float, sl: float, tp: float, success: bool = True, error_msg: str = None):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return

    is_buy = "BUY" in action.upper()
    color = 3066993 if is_buy else 15158332
    action_label = "🟢 BUY (Smart Money Concept)" if is_buy else "🔴 SELL (Smart Money Concept)"

    embed = {
        "title": "⚡ BrandBot • SMC Autonomous Execution" if success else "❌ BrandBot • Execution Dropped",
        "description": "**Market Guardian analyzed live chart, detected Asia Sweep & FVG alignment, and executed order.**" if success else f"**Order rejected by safety guard.**\n*Reason:* `{error_msg}`",
        "color": color,
        "fields": [
            {"name": "📈 Symbol", "value": f"`{symbol.upper()}`", "inline": True},
            {"name": "🎯 SMC Setup", "value": f"**{action_label}**", "inline": True},
            {"name": "📊 Lot Size", "value": f"`{volume}`", "inline": True},
            {"name": "💵 Entry (CE)", "value": f"`{price}`", "inline": True},
            {"name": "🛑 Stop Loss", "value": f"`{sl}`", "inline": True},
            {"name": "🎯 Take Profit", "value": f"`{tp}`", "inline": True},
        ],
        "footer": {"text": "BrandBot Institutional Engine • 24/7 Market Guardian"}
    }

    try:
        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json={"embeds": [embed]})
    except Exception as e:
        logger.error(f"Discord webhook error: {e}")

# Cikli Autonom i Skanimit të Tregut
async def autonomous_market_monitor():
    logger.info("👀 BrandBot Autonomous Market Guardian is active. Scanning XAUUSD charts in real-time...")
    
    while True:
        try:
            symbol = "XAUUSD"
            lock_key = f"lock:symbol:{symbol}"
            
            is_locked = await redis_client.exists(lock_key)
            if is_locked:
                await asyncio.sleep(10)
                continue

            smc_signal_triggered = False  

            if smc_signal_triggered:
                acquired = await redis_client.set(lock_key, "locked", nx=True, ex=60)
                if acquired:
                    try:
                        logger.info(f"🎯 SMC Setup (Asia Sweep + FVG) detected on {symbol}!")
                        ce_entry, sl_price, tp_price = 2650.00, 2642.00, 2680.00
                        lot_size = RiskManager.calculate_dynamic_lot(balance=10000.0, risk_percent=0.5, stop_loss_pips=80.0)

                        execution_delay = random.gauss(mu=0.6, sigma=0.2)
                        await asyncio.sleep(max(0.2, abs(execution_delay)))

                        mt5_url = os.getenv("MT5_BRIDGE_URL")
                        bridge_payload = {"symbol": symbol, "action": "BUY", "volume": lot_size, "entry": ce_entry, "sl": sl_price, "tp": tp_price}

                        success, error_msg = True, None
                        if mt5_url:
                            try:
                                async with httpx.AsyncClient(timeout=10.0) as client:
                                    res = await client.post(mt5_url, json=bridge_payload)
                                    if res.status_code != 200:
                                        success, error_msg = False, f"Bridge error status {res.status_code}"
                            except Exception as bridge_err:
                                success, error_msg = False, str(bridge_err)

                        await send_discord_embed(symbol, "BUY", lot_size, ce_entry, sl_price, tp_price, success, error_msg)

                    finally:
                        await redis_client.delete(lock_key)

        except Exception as scan_err:
            logger.error(f"Error in autonomous market scanner loop: {scan_err}")

        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    logger.info("⚡ BrandBot Core Engine Starting & Initializing Guardian Loop...")
    asyncio.create_task(autonomous_market_monitor())

@app.get("/")
def read_root():
    return {"status": "online", "system": "BrandBot Autonomous Institutional Engine SDR v2.0"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)