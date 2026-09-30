import os
import logging
import asyncio
import httpx
from fastapi import FastAPI
from pydantic import BaseModel, Literal
import redis.asyncio as redis

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("BrandBot-Autonomous-Core")

app = FastAPI(title="BrandBot Autonomous Institutional Engine")

# Lidhja me Redis për të menaxhuar gjendjen dhe bllokimin e pozicioneve
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

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

# Dërgimi i njoftimeve direkte në Discord
async def send_discord_embed(symbol: str, action: str, volume: float, price: float, sl: float, tp: float):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return

    is_buy = "BUY" in action.upper()
    color = 3066993 if is_buy else 15158332
    action_label = "🟢 BUY (Autonomous SMC Setup)" if is_buy else "🔴 SELL (Autonomous SMC Setup)"

    embed = {
        "title": "⚡ BrandBot • Autonomous Market Execution",
        "description": "**Market Guardian analyzed live XAUUSD feed, identified institutional zone, and triggered execution.**",
        "color": color,
        "fields": [
            {"name": "📈 Symbol", "value": f"`{symbol.upper()}`", "inline": True},
            {"name": "🎯 Setup", "value": f"**{action_label}**", "inline": True},
            {"name": "📊 Lot Size", "value": f"`{volume}`", "inline": True},
            {"name": "💵 Entry Price", "value": f"`{price}`", "inline": True},
            {"name": "🛑 Stop Loss", "value": f"`{sl}`", "inline": True},
            {"name": "🎯 Take Profit", "value": f"`{tp}`", "inline": True},
        ],
        "footer": {"text": "BrandBot Institutional Engine • Fully Autonomous"}
    }

    try:
        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json={"embeds": [embed]})
    except Exception as e:
        logger.error(f"Discord webhook error: {e}")

# Marrja e çmimit live të XAUUSD nga një burim i jashtëm publik
async def fetch_live_xauusd_price() -> float:
    try:
        # Përdorimi i një API publike për tërheqjen e çmimit të arit
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("https://api.coinbase.com/v2/prices/PAXG-USD/spot")
            if response.status_code == 200:
                data = response.json()
                return float(data["data"]["amount"])
    except Exception as e:
        logger.error(f"Error fetching live price: {e}")
    return 2650.00 # Çmim rezervë në rast se dështon lidhja e përkohshme

# Cikli Autonom që punon 24/7 në sfond
async def autonomous_market_monitor():
    logger.info("👀 BrandBot Autonomous Guardian started monitoring XAUUSD markets 24/7...")
    
    while True:
        try:
            symbol = "XAUUSD"
            lock_key = f"lock:symbol:{symbol}"
            
            # Kontrollojmë nëse ka ndonjë bllokim aktiv në Redis
            is_locked = await redis_client.exists(lock_key)
            if is_locked:
                await asyncio.sleep(30)
                continue

            # Marrja e çmimit aktual të tregut
            current_price = await fetch_live_xauusd_price()
            logger.info(f"📊 Live XAUUSD Market Price scanned: {current_price}")

            # Këtu mund të vendosësh kushtin tënd të saktë të SMC. 
            # Për momentin e lëmë si strukturë demonstrative/testuese që kap lëvizjet.
            # Kur dëshiron që boti të hapë pozicionin, ndryshojmë këtë kusht sipas dëshirës.
            simulated_smc_trigger = False  # Ndryshoje në True kur të duash testim live

            if simulated_smc_trigger:
                # Vendosim lock në Redis për të mos lejuar hapjen e dyfishtë të pozicionit (zgjat 10 minuta)
                acquired = await redis_client.set(lock_key, "locked", nx=True, ex=600)
                if acquired:
                    try:
                        logger.info(f"🎯 Institutional SMC setup confirmed on {symbol} at price {current_price}!")
                        
                        # Llogaritja e parametrave të tregtisë
                        entry = current_price
                        sl = round(entry - 8.00, 2) # Stop Loss me 8 dollarë largësi
                        tp = round(entry + 20.00, 2) # Take Profit me 20 dollarë fitim
                        
                        # Llogaritja e lotit dinamik (Llogaria: $10,000, Risk: 0.5%)
                        lot_size = RiskManager.calculate_dynamic_lot(balance=10000.0, risk_percent=0.5, stop_loss_pips=80.0)

                        # Dërgimi i njoftimit në Discord
                        await send_discord_embed(symbol, "BUY", lot_size, entry, sl, tp)

                    except Exception as inner_err:
                        logger.error(f"Error executing trade logic: {inner_err}")
                        await redis_client.delete(lock_key)

        except Exception as scan_err:
            logger.error(f"Error in autonomous background loop: {scan_err}")

        # Boti kontrollon tregun çdo 60 sekonda
        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    logger.info("⚡ Initializing BrandBot Core Background Tasks...")
    asyncio.create_task(autonomous_market_monitor())

@app.get("/")
def read_root():
    return {"status": "online", "system": "BrandBot Autonomous Institutional Engine"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8080))
    uvicorn.run("main:app", host="0.0.0.0", port=port)