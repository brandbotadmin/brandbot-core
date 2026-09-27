import logging

logger = logging.getLogger(__name__)

# Klasë Dummy për Redis për të shmangur AttributeError në local mode
class DummyRedis:
    async def get(self, *args, **kwargs):
        return None
    
    async def set(self, *args, **kwargs):
        return True

    async def delete(self, *args, **kwargs):
        return True

redis_client = DummyRedis()

async def check_idempotency(*args, **kwargs):
    return False

async def store_idempotency(*args, **kwargs):
    pass

async def acquire_lock(*args, **kwargs):
    return True

async def release_lock(*args, **kwargs):
    pass

async def extend_lock(*args, **kwargs):
    return True

async def check_rate_limit(*args, **kwargs):
    return True, 1