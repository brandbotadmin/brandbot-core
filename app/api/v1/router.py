from fastapi import APIRouter
from app.api.v1.webhooks import router as webhooks_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(webhooks_router, tags=["Webhooks"])