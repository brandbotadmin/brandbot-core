import asyncio
import logging
import json
import urllib.request
from fastapi import FastAPI
from app.api.v1.router import api_router
from config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BrandBot SDR API", version="2.0.0")

def send_discord_msg_sync(message: str):
    """Dërgon njoftim direkt në Discord duke përdorur librarinë standarde."""
    if settings.DISCORD_WEBHOOK_URL:
        try:
            req = urllib.request.Request(
                settings.DISCORD_WEBHOOK_URL,
                data=json.dumps({"content": message}).encode('utf-8'),
                headers={'Content-Type': 'application/json', 'User-Agent': 'Mozilla/5.0'}
            )
            urllib.request.urlopen(req)
        except Exception as e:
            logger.error(f"Discord Webhook Error: {e}")

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
        logger.warning(f"Database connection skipped in local mode: {e}")

    # Njoftim në Anglisht për Discord me urllib standard
    send_discord_msg_sync("🟢 **BrandBot SDR v2.0**: Server is Online on Render! Bot is actively scanning XAUUSD 24/7 for SMC & CRT setups.")
    
    asyncio.create_task(autonomous_trading_loop())

app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "BrandBot SDR v2.0 API is running", "mode": "fully_autonomous"}