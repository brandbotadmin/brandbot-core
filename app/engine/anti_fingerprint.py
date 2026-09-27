import random
import asyncio
import math
from app.engine.symbol_config import thresholds_for_symbol
from app.models.schemas import validate_sl_tp_geometry


class AntiFingerprintEngine:
    @staticmethod
    async def apply_gaussian_jitter() -> int:
        delay = max(0.1, min(random.gauss(0.5, 0.2), 1.5))
        await asyncio.sleep(delay)
        return int(delay * 1000)

    @staticmethod
    def apply_micro_price_variation(
        symbol: str,
        direction: str,
        entry: float,
        sl: float,
        tp: float,
    ) -> tuple[float, float]:
        jitter = thresholds_for_symbol(symbol).price_jitter
        sl_adj = round(sl + random.choice([-jitter, jitter]), 5)
        tp_adj = round(tp + random.choice([-jitter, jitter]), 5)
        if not validate_sl_tp_geometry(direction, entry, sl_adj, tp_adj):
            return round(sl, 5), round(tp, 5)
        return sl_adj, tp_adj
