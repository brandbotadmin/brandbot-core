import asyncio
import logging
import json
import os
import urllib.request
from fastapi import FastAPI
from app.api.v1.router import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BrandtBot SDR API", version="2.0.0")

def send_discord_msg_sync(message: str):
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

async def keep_alive_loop():
    """Dërgon kërkesë (ping) çdo 10 minuta që Render të mos hyjë në gjumë."""
    while True:
        try:
            render_url = os.getenv("RENDER_EXTERNAL_URL")
            if render_url:
                req = urllib.request.Request(render_url, headers={'User-Agent': 'Mozilla/5.0'})
                urllib.request.urlopen(req)
                logger.info("⚡ Keep-alive ping sent to Render.")
        except Exception as e:
            logger.warning(f"Keep-alive ping warning: {e}")
        await asyncio.sleep(600)  # Çdo 10 minuta (600 sekonda)

async def autonomous_trading_loop():
    logger.info("🤖 BrandtBot SDR: Market Scanner Started...")
    
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

    send_discord_msg_sync("🟢 **BrandtBot SDR v2.0**: Server is Online & Keep-Alive Active! Bot is actively scanning XAUUSD 24/7.")
    
    # Nisim skanerin e tregut dhe keep-alive loop-in në prapavijë
    asyncio.create_task(autonomous_trading_loop())
    asyncio.create_task(keep_alive_loop())

app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "BrandtBot SDR v2.0 API is running", "mode": "fully_autonomous"}