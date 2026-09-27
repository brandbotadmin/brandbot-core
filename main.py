import asyncio
import logging
import json
import os
import urllib.request
from fastapi import FastAPI
from app.api.v1.router import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BrandBot SDR API", version="2.0.0")

def send_discord_msg_sync(message: str):
    """Dërgon njoftim në Discord duke marrë URL direkt nga Environment Variables."""
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL") or os.getenv("DISCORD_WEBHOOK")
    if webhook_url:
        try:
            req = urllib.request.Request(
                webhook_url,
                data=json.dumps({"content": message}).encode('utf-8'),
                headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
            )
            urllib.request.urlopen(req)
            logger.info("Discord notification sent successfully.")
        except Exception as e:
            logger.error(f"Discord Webhook Error: {e}")
    else:
        logger.warning("DISCORD_WEBHOOK_URL not set in environment variables.")

async def autonomous_trading_loop():
    """Loop automatik që skanon tregun 24/7 sipas specifikimeve të SDR v2.0."""
    logger.info("🤖 BrandBot SDR: Market Scanner Started...")
    
    from app.engine.smc_strategy import check_smc_signals
    from app.engine.crt_strategy import check_crt_signals
    from app.engine.news_guard import is_news_safe
    from app.execution.metaapi_client import execute_trade

    while True:
        try:
            if is_news_safe(symbol="XAUUSD"):
                smc_signal = await check_smc_signals(symbol="XAUUSD")
                crt_signal = await check_crt_signals(symbol="XAUUSD")
                
                if smc_signal and smc_signal.get("action"):
                    await execute_trade(smc_signal)
                elif crt_signal and crt_signal.get("action"):
                    await execute_trade(crt_signal)

        except Exception as e:
            logger.warning(f"⚠️ Scanner Error: {e}")
            
        await asyncio.sleep(60)

@app.on_event("startup")
async def startup_event():
    try:
        from app.core.database import init_db
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.warning(f"Database connection skipped: {e}")

    # Njoftimi në Anglisht për Discord
    send_discord_msg_sync("🟢 **BrandBot SDR v2.0**: Server is Online on Render! Bot is actively scanning XAUUSD 24/7 for SMC & CRT setups.")
    
    # Nisja e skanerit autonom në background
    asyncio.create_task(autonomous_trading_loop())

app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "BrandBot SDR v2.0 API is running", "mode": "fully_autonomous"}