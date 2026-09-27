from app.core.redis import redis_client


async def set_global_freeze(freeze: bool):
    await redis_client.set("global_system_freeze", "true" if freeze else "false")


async def is_global_frozen() -> bool:
    val = await redis_client.get("global_system_freeze")
    return val == "true"