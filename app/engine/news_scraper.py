import asyncio
import logging

logger = logging.getLogger(__name__)


async def start_news_cron():
    """Placeholder cron: extend to pull Forex Factory / API and call NewsGuard.set_freeze_window."""
    while True:
        try:
            # Integrate real calendar feed here; no-op until configured.
            pass
        except Exception:
            logger.exception("news_scraper cycle failed")
        await asyncio.sleep(3600)
