from datetime import datetime, timezone
from app.core.redis import redis_client


class NewsGuard:
    @staticmethod
    async def is_news_freeze_active(currency: str = "USD") -> bool:
        key = f"news:freeze:{currency.upper()}"
        until_raw = await redis_client.get(key)
        if not until_raw:
            return False
        try:
            until_ts = float(until_raw)
        except ValueError:
            return False
        return datetime.now(timezone.utc).timestamp() < until_ts

    @staticmethod
    async def set_freeze_window(currency: str, duration_seconds: int = 900) -> None:
        until = datetime.now(timezone.utc).timestamp() + duration_seconds
        await redis_client.set(f"news:freeze:{currency.upper()}", str(until), ex=duration_seconds + 60)
