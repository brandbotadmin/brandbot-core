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
    """Dërgon kërkesë ping çdo 10 minuta që Render të mos hyjë në gjumë."""
    while True:
        try:
            render_url = os.getenv("RENDER_EXTERNAL_URL")
            if render_url:
                req = urllib.request.Request(render_url, headers={'User-Agent': 'Mozilla/5.0'})
                urllib.request.urlopen(req)
                logger.info("⚡ Keep-alive ping sent to Render.")
        except Exception as e:
            logger.warning(f"Keep-alive ping warning: {e}")
        await asyncio.sleep(600)

async def autonomous_trading_loop():
    logger.info("🤖 BrandtBot SDR: Market Scanner Started...")
    
    # Importojmë strategjitë me dinamikë mbrojtëse
    import app.engine.smc_strategy as smc_module
    import app.engine.crt_strategy as crt_module
    from app.engine.news_guard import is_news_safe
    from app.execution.metaapi_client import execute_trade

    # Gjejmë funksionet e sakta brenda mekatizmave SMC dhe CRT
    smc_func = getattr(smc_module, 'check_smc_signals', None) or getattr(smc_module, 'analyze_smc', None)
    crt_func = getattr(crt_module, 'check_crt_signals', None) or getattr(crt_module, 'analyze_crt', None)

    while True:
        try:
            if is_news_safe(symbol="XAUUSD"):
                smc_signal = None
                crt_signal = None

                if smc_func:
                    smc_signal = await smc_func(symbol="XAUUSD") if asyncio.iscoroutinefunction(smc_func) else smc_func(symbol="XAUUSD")
                
                if crt_func:
                    crt_signal = await crt_func(symbol="XAUUSD") if asyncio.iscoroutinefunction(crt_func) else crt_func(symbol="XAUUSD")

                if smc_signal and isinstance(smc_signal, dict) and smc_signal.get("action"):
                    await execute_trade(smc_signal)
                elif crt_signal and isinstance(crt_signal, dict) and crt_signal.get("action"):
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
    
    asyncio.create_task(autonomous_trading_loop())
    asyncio.create_task(keep_alive_loop())

app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "BrandtBot SDR v2.0 API is running", "mode": "fully_autonomous"}