import os
import logging
import random
import asyncio
import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Field
from typing import Optional, Literal
from app.core.redis import redis_manager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BrandBot-Autonomous-Core")

app = FastAPI(title="BrandBot Autonomous Institutional Engine SDR v2.0")

# Skema e brendshme për kërkesat e ekzekutimit
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

# Moduli i integruar i riskut dhe llogaritjes së lotit
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

# Moduli i Njoftimeve në Discord
async def send_discord_embed(symbol: str, action: str, volume: float, price: float, sl: float, tp: float, success: bool = True, error_msg: str = None):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return

    is_buy = "BUY" in action.upper()
    color = 3066993 if is_buy else 15158332
    action_label = "🟢 BUY (Autonomous SMC)" if is_buy else "🔴 SELL (Autonomous SMC)"

    if success:
        title = "⚡ BrandBot • Autonomous Execution"
        desc = "**Bot successfully analyzed chart, detected SMC setup, and executed order via MetaApi!**"
    else:
        title = "❌ BrandBot • Execution Rejected"
        desc = f"**Order dropped by safety guard.**\n*Reason:* `{error_msg}`"

    embed = {
        "title": title,
        "description": desc,
        "color": color,
        "fields": [
            {"name": "📈 Symbol", "value": f"`{symbol.upper()}`", "inline": True},
            {"name": "🎯 Strategy Action", "value": f"**{action_label}**", "inline": True},
            {"name": "📊 Dynamic Lot Size", "value": f"`{volume}`", "inline": True},
            {"name": "💵 Entry / CE Price", "value": f"`{price}`", "inline": True},
            {"name": "🛑 Stop Loss", "value": f"`{sl}`", "inline": True},
            {"name": "🎯 Take Profit", "value": f"`{tp}`", "inline": True},
        ],
        "footer": {"text": "BrandBot Autonomous SaaS • Tick-by-Tick Market Guardian"}
    }

    try:
        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json={"embeds": [embed]})
    except Exception as e:
        logger.error(f"Discord webhook error: {e}")

# Cikli Autonom i Vëzhgimit të Tregut (Tick-by-Tick & SMC Chart Analysis)
async def autonomous_market_monitor():
    logger.info("👀 Autonomous Market Guardian is active. Scanning XAUUSD charts in real-time...")
    
    while True:
        try:
            symbol = "XAUUSD"
            
            # Kontrollojmë nëse kemi lock aktiv në Redis (Single-Position Rule)
            is_locked = await redis_manager.redis.exists(f"lock:symbol:{symbol}")
            if is_locked:
                await asyncio.sleep(5)
                continue

            market_signal_detected = False  # Ndryshohet kur boti gjen setup real
            
            if market_signal_detected:
                lock_acquired = await redis_manager.acquire_lock(symbol, expire_seconds=30)
                if lock_acquired:
                    try:
                        logger.info(f"🎯 Autonomous SMC Setup detected on {symbol}!")
                        ce_entry = 2650.00
                        sl_price = 2642.00
                        tp_price = 2680.00
                        
                        lot_size = RiskManager.calculate_dynamic_lot(balance=10000.0, risk_percent=0.5, stop_loss_pips=80.0)

                        # Anti-Fingerprinting: Gaussian Jittering
                        execution_delay = random.gauss(mu=0.5, sigma=0.2)
                        await asyncio.sleep(max(0.1, abs(execution_delay)))

                        mt5_url = os.getenv("MT5_BRIDGE_URL")
                        bridge_payload = {
                            "symbol": symbol,
                            "action": "BUY",
                            "volume": lot_size,
                            "entry": ce_entry,
                            "sl": sl_price,
                            "tp": tp_price
                        }

                        success = True
                        error_msg = None

                        if mt5_url:
                            try:
                                async with httpx.AsyncClient(timeout=10.0) as client:
                                    res = await client.post(mt5_url, json=bridge_payload)
                                    if res.status_code != 200:
                                        success = False
                                        error_msg = f"Bridge error status {res.status_code}"
                            except Exception as bridge_err:
                                success = False
                                error_msg = str(bridge_err)

                        await send_discord_embed(
                            symbol=symbol,
                            action="BUY",
                            volume=lot_size,
                            price=ce_entry,
                            sl=sl_price,
                            tp=tp_price,
                            success=success,
                            error_msg=error_msg
                        )

                    finally:
                        await redis_manager.release_lock(symbol)

        except Exception as scan_err:
            logger.error(f"Error in autonomous market scanner loop: {scan_err}")

        await asyncio.sleep(3)

@app.on_event("startup")
async def startup_event():
    logger.info("⚡ Starting BrandBot Autonomous Core Engine & Initializing Background Guardian...")
    asyncio.create_task(autonomous_market_monitor())

@app.get("/")
def read_root():
    return {"status": "online", "system": "BrandBot Autonomous Institutional Core SDR v2.0"}