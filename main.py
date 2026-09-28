import asyncio
import logging
import json
import os
import urllib.request
from fastapi import FastAPI
from app.api.v1.router import api_router
from config.settings import settings

try:
    from app.execution.metaapi_client import MetaApiClient
except Exception as e:
    MetaApiClient = None
    logging.warning(f"MetaApiClient import warning: {e}")

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

async def process_and_execute_signal(signal: dict):
    if not signal or not isinstance(signal, dict) or not signal.get("action"):
        return

    account_id = getattr(settings, "METAAPI_ACCOUNT_ID", None) or os.getenv("METAAPI_ACCOUNT_ID", "")
    
    if MetaApiClient:
        trade_func = (
            getattr(MetaApiClient, 'execute_trade', None) or 
            getattr(MetaApiClient, 'send_order', None) or 
            getattr(MetaApiClient, 'place_order', None) or 
            getattr(MetaApiClient, 'execute', None)
        )

        if trade_func:
            try:
                if asyncio.iscoroutinefunction(trade_func):
                    await trade_func(
                        account_id=account_id,
                        symbol=signal.get("symbol", "XAUUSD"),
                        action=signal.get("action"),
                        volume=float(signal.get("volume", getattr(settings, "MIN_LOT_SIZE", 0.01))),
                        stop_loss=float(signal.get("stop_loss", 0.0)),
                        take_profit=float(signal.get("take_profit", 0.0)),
                        entry_price=float(signal.get("entry_price", 0.0))
                    )
                else:
                    trade_func(
                        account_id=account_id,
                        symbol=signal.get("symbol", "XAUUSD"),
                        action=signal.get("action"),
                        volume=float(signal.get("volume", getattr(settings, "MIN_LOT_SIZE", 0.01))),
                        stop_loss=float(signal.get("stop_loss", 0.0)),
                        take_profit=float(signal.get("take_profit", 0.0)),
                        entry_price=float(signal.get("entry_price", 0.0))
                    )
                logger.info(f"🚀 Trade executed: {signal}")
            except Exception as e:
                logger.error(f"❌ Error executing trade: {e}")
        else:
            logger.warning("⚠️ MetaApiClient does not have a recognized trade execution method.")

async def autonomous_trading_loop():
    logger.info("🤖 BrandtBot SDR: Market Scanner Started...")
    
    try:
        import app.engine.smc_strategy as smc_module
        import app.engine.crt_strategy as crt_module
        import app.engine.news_guard as news_module

        smc_func = getattr(smc_module, 'check_smc_signals', None) or getattr(smc_module, 'analyze_smc', None)
        crt_func = getattr(crt_module, 'check_crt_signals', None) or getattr(crt_module, 'analyze_crt', None)
        news_func = getattr(news_module, 'is_news_safe', None) or getattr(news_module, 'check_news', None) or getattr(news_module, 'is_safe_to_trade', None)

        while True:
            try:
                logger.info("🔎 Checking XAUUSD market signals...")

                news_safe = True
                if news_func:
                    news_safe = await news_func(symbol="XAUUSD") if asyncio.iscoroutinefunction(news_func) else news_func(symbol="XAUUSD")

                if news_safe:
                    if smc_func:
                        smc_signal = await smc_func(symbol="XAUUSD") if asyncio.iscoroutinefunction(smc_func) else smc_func(symbol="XAUUSD")
                        if smc_signal:
                            await process_and_execute_signal(smc_signal)

                    if crt_func:
                        crt_signal = await crt_func(symbol="XAUUSD") if asyncio.iscoroutinefunction(crt_func) else crt_func(symbol="XAUUSD")
                        if crt_signal:
                            await process_and_execute_signal(crt_signal)

            except Exception as e:
                logger.warning(f"⚠️ Scanner Loop Warning: {e}")
                
            await asyncio.sleep(60)
    except Exception as e:
        logger.error(f"❌ Critical Scanner Error: {e}")

@app.on_event("startup")
async def startup_event():
    try:
        from app.core.database import init_db
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.warning(f"Database connection skipped: {e}")

    send_discord_msg_sync("🟢 **BrandtBot SDR v2.0**: Server Online! Scanner Active.")
    
    asyncio.create_task(autonomous_trading_loop())
    asyncio.create_task(keep_alive_loop())

app.include_router(api_router)

@app.api_route("/", methods=["GET", "HEAD"])
async def root():
    return {"message": "BrandtBot SDR v2.0 API is running", "mode": "fully_autonomous"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)