import os
import logging
import asyncio
import httpx
from fastapi import FastAPI, HTTPException, Request, BackgroundTasks
from pydantic import BaseModel
from typing import Optional

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BrandBot-Core")

app = FastAPI(title="BrandBot Core Engine")

# Model standard per sinjalet nga TradingView ose skaneri brendshem
class SignalPayload(BaseModel):
    symbol: str
    action: str  # "BUY" ose "SELL"
    volume: float = 0.01
    price: Optional[float] = None
    sl: Optional[float] = None
    tp: Optional[float] = None
    comment: Optional[str] = "BrandBot Trade"

# Funksioni per dertimin dhe dergimin e kartes se bukur te Discord (Embed)
async def send_discord_signal(symbol: str, action: str, volume: float, price: float = None, sl: float = None, tp: float = None, comment: str = None):
    discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not discord_webhook_url:
        logger.warning("⚠️ DISCORD_WEBHOOK_URL is not set in environment variables.")
        return

    is_buy = action.upper() == "BUY"
    color = 3066993 if is_buy else 15158332  # E gjelber per BUY (0x2ECC71), E kuqe per SELL (0xE74C3C)
    action_emoji = "🟢 BUY" if is_buy else "🔴 SELL"

    embed = {
        "title": "⚡ BrandBot Execution Signal",
        "description": f"**Tregti e re u ekzekutua me sukses në MT5!**\n*{comment or 'Auto Execution'}*",
        "color": color,
        "fields": [
            {"name": "📈 Simboli", "value": f"`{symbol.upper()}`", "inline": True},
            {"name": "🎯 Veprimi", "value": f"**{action_emoji}**", "inline": True},
            {"name": "📊 Loti (Volume)", "value": f"`{volume}`", "inline": True},
        ],
        "footer": {
            "text": "BrandBot Core • Direct MT5 Bridge Engine",
            "icon_url": "https://cdn-icons-png.flaticon.com/512/2586/2586120.png"
        }
    }

    if price:
        embed["fields"].append({"name": "💵 Çmimi i Hyrjes", "value": f"`{price}`", "inline": True})
    if sl:
        embed["fields"].append({"name": "🛑 Stop Loss", "value": f"`{sl}`", "inline": True})
    if tp:
        embed["fields"].append({"name": "🎯 Take Profit", "value": f"`{tp}`", "inline": True})

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(discord_webhook_url, json={"embeds": [embed]})
            if res.status_code in [200, 204]:
                logger.info("✅ Discord notification sent successfully.")
            else:
                logger.error(f"❌ Failed to send Discord notification: {res.text}")
    except Exception as e:
        logger.error(f"❌ Error sending Discord notification: {e}")

# Funksioni qe e dërgon urdhrin te MT5 Bridge lokal
async def send_to_mt5_bridge(payload: dict):
    mt5_bridge_url = os.getenv("MT5_BRIDGE_URL")
    if not mt5_bridge_url:
        logger.error("❌ MT5_BRIDGE_URL is not configured in Railway environment variables!")
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(mt5_bridge_url, json=payload)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"❌ Error forwarding trade signal to MT5 Bridge: {e}")
        return None

# Funksioni kryesor qe ekzekuton tregtine dhe njofton Discord-in
async def process_and_execute_signal(signal: SignalPayload):
    payload = {
        "symbol": signal.symbol,
        "action": signal.action.upper(),
        "volume": signal.volume,
        "sl": signal.sl,
        "tp": signal.tp,
        "comment": signal.comment
    }

    # 1. Ekzekutojme urdhrin te MT5 Bridge
    result = await send_to_mt5_bridge(payload)

    # 2. Dërgojmë njoftimin e formatuar te Discord
    executed_price = signal.price
    if result and isinstance(result, dict) and result.get("status") == "success":
        executed_price = result.get("price", signal.price)

    await send_discord_signal(
        symbol=signal.symbol,
        action=signal.action,
        volume=signal.volume,
        price=executed_price,
        sl=signal.sl,
        tp=signal.tp,
        comment=signal.comment
    )

    return result

@app.on_event("startup")
async def startup_event():
    logger.info("⚡ Starting BrandBot Core Engine...")
    
    # Njoftim ne Discord kur boti ndizet
    discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if discord_webhook_url:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(discord_webhook_url, json={
                    "embeds": [{
                        "title": "🟢 BrandBot Core Engine",
                        "description": "🚀 **Sistemi u ndez dhe është online!** Direct MT5 Bridge është aktiv.",
                        "color": 3066993
                    }]
                })
        except Exception as e:
            logger.warning(f"⚠️ Could not send startup message: {e}")

@app.get("/")
def read_root():
    return {"status": "online", "system": "BrandBot Core Engine"}

@app.post("/webhook/tradingview")
async def tradingview_webhook(signal: SignalPayload, background_tasks: BackgroundTasks):
    logger.info(f"📥 Received Webhook Signal: {signal.symbol} - {signal.action} - Volume: {signal.volume}")
    
    # Ekzekutohet ne background per pergjigje te shpejte
    background_tasks.add_task(process_and_execute_signal, signal)
    
    return {"status": "received", "message": "Signal accepted for processing"}