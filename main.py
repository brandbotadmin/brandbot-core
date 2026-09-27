import logging
from fastapi import FastAPI
from app.api.v1.router import api_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="BrandBot SDR API", version="2.0.0")

@app.on_event("startup")
async def startup_event():
    try:
        from app.core.database import init_db
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.warning(f"Database connection skipped in local mode: {e}")

app.include_router(api_router)

@app.get("/")
async def root():
    return {"message": "BrandBot SDR v2.0 API is running"}