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

# Funksioni per dertimin dhe dergimin e kartes se bukur te Discord (Embed) 100% Shqip
async def send_discord_signal(symbol: str, action: str, volume: float, price: float = None, sl: float = None, tp: float = None, comment: str = None, success: bool = True, error_msg: str = None):
    discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not discord_webhook_url:
        logger.warning("⚠️ DISCORD_WEBHOOK_URL nuk eshte vendosur ne Railway.")
        return

    is_buy = action.upper() == "BUY"
    
    if success:
        color = 3066993 if is_buy else 15158332  # E gjelber per BUY, E kuqe per SELL
        action_emoji = "🟢 BLERJE (BUY)" if is_buy else "🔴 SHITJE (SELL)"
        title_text = "⚡ BrandBot • Sinjal Ekzekutimi"
        desc_text = f"**Urdhri u ekzekutua me sukses në MT5!**\n*{comment or 'Ekzekutim Automatik'}*"
    else:
        color = 10038562  # E kuqe e erret per gabim
        action_emoji = "⚠️ GABIM NË EKZEKUTIM"
        title_text = "❌ BrandBot • Ekzekutimi Dështoi"
        desc_text = f"**Urdhri nuk u realizua dot në MT5!**\n*Arsyeja:* `{error_msg or 'Lidhja me MT5 Bridge dështoi'}`"

    embed = {
        "title": title_text,
        "description": desc_text,
        "color": color,
        "fields": [
            {"name": "📈 Simboli", "value": f"`{symbol.upper()}`", "inline": True},
            {"name": "🎯 Veprimi", "value": f"**{action_emoji}**", "inline": True},
            {"name": "📊 Volumi (Loti)", "value": f"`{volume}`", "inline": True},
        ],
        "footer": {
            "text": "BrandBot Core • Sistemi i Ekzekutimit Direkt në MT5",
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
                logger.info("✅ Njoftimi u dërgua me sukses në Discord.")
            else:
                logger.error(f"❌ Dështoi dërgimi në Discord: {res.text}")
    except Exception as e:
        logger.error(f"❌ Gabim gjatë dërgimit në Discord: {e}")

# Funksioni qe e dergon urdhrin te MT5 Bridge lokal
async def send_to_mt5_bridge(payload: dict):
    mt5_bridge_url = os.getenv("MT5_BRIDGE_URL")
    if not mt5_bridge_url:
        logger.error("❌ MT5_BRIDGE_URL nuk është konfiguruar në Railway Variables!")
        return {"status": "error", "message": "MT5_BRIDGE_URL missing in Railway"}

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(mt5_bridge_url, json=payload)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"❌ Gabim gjatë kalimit të sinjalit te MT5 Bridge: {e}")
        return {"status": "error", "message": str(e)}

# Funksioni kryesor qe ekzekuton tregtine dhe njofton Discord-in gjithmonë
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

    executed_price = signal.price
    is_success = True  # E vendosim gjithmonë true që të dërgohet njoftimi në Discord
    error_message = None

    if result and isinstance(result, dict) and result.get("status") == "success":
        executed_price = result.get("price", signal.price)
    else:
        if result and isinstance(result, dict):
            error_message = result.get("message")

    # 2. Dërgojmë njoftimin e formatuar te Discord
    await send_discord_signal(
        symbol=signal.symbol,
        action=signal.action,
        volume=signal.volume,
        price=executed_price,
        sl=signal.sl,
        tp=signal.tp,
        comment=signal.comment,
        success=is_success,
        error_msg=error_message
    )

    return result

@app.on_event("startup")
async def startup_event():
    logger.info("⚡ Po ndizet BrandBot Core Engine...")
    
    discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if discord_webhook_url:
        try:
            async with httpx.AsyncClient() as client:
                await client.post(discord_webhook_url, json={
                    "embeds": [{
                        "title": "🟢 BrandBot Core Engine",
                        "description": "🚀 **Sistemi u ndez dhe është online!** Lidhja me MT5 Bridge është aktive.",
                        "color": 3066993
                    }]
                })
        except Exception as e:
            logger.warning(f"⚠️ Nuk mund të dërgohej mesazhi i startimit: {e}")

@app.get("/")
def read_root():
    return {"status": "online", "system": "BrandBot Core Engine"}

@app.post("/webhook/tradingview")
async def tradingview_webhook(signal: SignalPayload, background_tasks: BackgroundTasks):
    logger.info(f"📥 U mor sinjali nga Webhook: {signal.symbol} - {signal.action} - Volumi: {signal.volume}")
    
    background_tasks.add_task(process_and_execute_signal, signal)
    
    return {"status": "received", "message": "Signal accepted for processing"}