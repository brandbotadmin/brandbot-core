import asyncio
import logging
import os
from fastapi import FastAPI, BackgroundTasks, HTTPException, Request
from pydantic import BaseModel
from typing import Optional
import httpx

# -----------------------------------------------------------------------------
# 1. LOGGING CONFIGURATION
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("brandbot")

# -----------------------------------------------------------------------------
# 2. FASTAPI APP INITIALIZATION
# -----------------------------------------------------------------------------
app = FastAPI(
    title="BrandBot Core Engine",
    description="Automated Institutional Trading Bot for XAUUSD & Forex",
    version="1.0.0"
)

# -----------------------------------------------------------------------------
# 3. HELPER & EXECUTION FUNCTIONS
# -----------------------------------------------------------------------------
async def process_and_execute_signal(signal_data: dict):
    """
    Përpunon sinjalin e gjeneruar (SMC/CRT), aplikon risk management,
    ekzekuton urdhrin te MT5 Direct Bridge dhe dërgon njoftim në Discord Webhook.
    """
    try:
        logger.info(f"🚀 Processing Signal for Execution: {signal_data}")

        # Lexojmë URL-në e MT5 Bridge dhe Discord Webhook nga Environment Variables
        mt5_bridge_url = os.getenv("MT5_BRIDGE_URL", "http://127.0.0.1:8000/trade")
        discord_webhook_url = os.getenv("DISCORD_WEBHOOK_URL")

        # 1. Ekzekutimi i urdhrit te MT5 Bridge (Kompjuteri lokal ose VPS)
        try:
            async with httpx.AsyncClient() as client:
                res = await client.post(mt5_bridge_url, json=signal_data, timeout=10.0)
                logger.info(f"✅ MT5 Bridge Response: {res.status_code} - {res.text}")
        except Exception as bridge_err:
            logger.error(f"❌ Failed to reach MT5 Bridge: {bridge_err}")

        # 2. Dërgimi i njoftimit në Discord
        if discord_webhook_url:
            logger.info("📡 Sending trade notification to Discord...")
            async with httpx.AsyncClient() as client:
                discord_payload = {
                    "content": f"🚨 **BRANDBOT TRADE EXECUTED** 🚨\n```json\n{signal_data}\n```"
                }
                await client.post(discord_webhook_url, json=discord_payload)
        else:
            logger.warning("⚠️ DISCORD_WEBHOOK_URL is not configured in Environment Variables.")

    except Exception as e:
        logger.error(f"❌ Error processing and executing signal: {e}", exc_info=True)


async def autonomous_trading_loop():
    """
    Loop-i kryesor asinkron që ekzekutohet çdo minutë për të skanuar tregun,
    kontrolluar lajmet dhe ekzekutuar sinjalet.
    """
    try:
        import app.engine.smc_strategy as smc_module
        import app.engine.crt_strategy as crt_module
        import app.engine.news_guard as news_module

        smc_func = getattr(smc_module, 'check_smc_signals', None) or getattr(smc_module, 'analyze_smc', None)
        crt_func = getattr(crt_module, 'check_crt_signals', None) or getattr(crt_module, 'analyze_crt', None)
        news_func = getattr(news_module, 'is_news_safe', None) or getattr(news_module, 'check_news', None)

        while True:
            try:
                logger.info("🔎 Checking XAUUSD market signals...")

                news_safe = True
                if news_func:
                    news_safe = await news_func(symbol="XAUUSD") if asyncio.iscoroutinefunction(news_func) else news_func(symbol="XAUUSD")
                    logger.info(f"📊 News Check: Safe={news_safe}")

                if news_safe:
                    if smc_func:
                        smc_signal = await smc_func(symbol="XAUUSD") if asyncio.iscoroutinefunction(smc_func) else smc_func(symbol="XAUUSD")
                        logger.info(f"🔍 SMC Signal Result: {smc_signal}")
                        if smc_signal:
                            await process_and_execute_signal(smc_signal)

                    if crt_func:
                        crt_signal = await crt_func(symbol="XAUUSD") if asyncio.iscoroutinefunction(crt_func) else crt_func(symbol="XAUUSD")
                        logger.info(f"🔍 CRT Signal Result: {crt_signal}")
                        if crt_signal:
                            await process_and_execute_signal(crt_signal)
                else:
                    logger.warning("⚠️ News Guard active - Skipping market check for XAUUSD")

            except Exception as e:
                logger.warning(f"⚠️ Scanner Loop Warning: {e}")

            await asyncio.sleep(60)

    except Exception as e:
        logger.error(f"❌ Critical error in autonomous trading loop: {e}", exc_info=True)

# -----------------------------------------------------------------------------
# 4. STARTUP & SHUTDOWN EVENTS
# -----------------------------------------------------------------------------
@app.on_event("startup")
async def startup_event():
    logger.info("⚡ Starting BrandBot Core Engine...")

    # Inicimi i Bazës së Të Dhënave (PostgreSQL / Redis)
    try:
        from app.core.database import init_db
        await init_db()
        logger.info("✅ Database initialized successfully.")
    except Exception as e:
        logger.warning(f"⚠️ Database initialization warning: {e}")

    # Nisja e Background Task për skanimin e vazhdueshëm të tregut
    asyncio.create_task(autonomous_trading_loop())
    logger.info("🌀 Autonomous Trading Loop started successfully.")

# -----------------------------------------------------------------------------
# 5. API ENDPOINTS
# -----------------------------------------------------------------------------
@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "BrandBot Core Engine",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/webhook/tradingview")
async def tradingview_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Endpoint për marrjen e sinjaleve të jashtme nga TradingView Webhook.
    """
    try:
        data = await request.json()
        logger.info(f"📥 Received TradingView Webhook: {data}")
        background_tasks.add_task(process_and_execute_signal, data)
        return {"status": "signal_received"}
    except Exception as e:
        logger.error(f"❌ Error processing webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid webhook payload")