import math
from datetime import datetime, timezone
from config.settings import settings
from app.core.redis import redis_client


async def _reset_daily_baseline_if_needed(current_equity: float) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    stored_date = await redis_client.get("risk:daily_date")
    if stored_date == today:
        return
    await redis_client.set("risk:daily_date", today)
    await redis_client.set("risk:daily_start_equity", str(current_equity))
    await redis_client.set("risk:daily_peak_equity", str(current_equity))


async def is_drawdown_exceeded() -> tuple[bool, str, float]:
    """
    Returns (exceeded, limit_type, drawdown_percent).
    limit_type: 'none' | 'max' | 'daily'
    """
    peak_raw = await redis_client.get("risk:equity_peak")
    current_raw = await redis_client.get("risk:equity_current")
    peak = float(peak_raw) if peak_raw else settings.ACCOUNT_BALANCE
    current = float(current_raw) if current_raw else settings.ACCOUNT_BALANCE

    await _reset_daily_baseline_if_needed(current)

    daily_start_raw = await redis_client.get("risk:daily_start_equity")
    daily_peak_raw = await redis_client.get("risk:daily_peak_equity")
    daily_start = float(daily_start_raw) if daily_start_raw else current
    daily_peak = float(daily_peak_raw) if daily_peak_raw else current
    daily_peak = max(daily_peak, current)
    await redis_client.set("risk:daily_peak_equity", str(daily_peak))

    if peak > 0:
        max_dd = max(0.0, (peak - current) / peak * 100.0)
        if max_dd > settings.MAX_DRAWDOWN_PERCENT:
            return True, "max", round(max_dd, 2)

    if daily_start > 0:
        daily_dd = max(0.0, (daily_start - current) / daily_start * 100.0)
        if daily_dd > settings.MAX_DAILY_DRAWDOWN_PERCENT:
            return True, "daily", round(daily_dd, 2)

    return False, "none", 0.0


async def record_equity(equity: float) -> None:
    if not math.isfinite(equity) or equity <= 0:
        return
    peak_raw = await redis_client.get("risk:equity_peak")
    peak = float(peak_raw) if peak_raw else equity
    peak = max(peak, equity)
    await redis_client.set("risk:equity_peak", str(peak))
    await redis_client.set("risk:equity_current", str(equity))

    await _reset_daily_baseline_if_needed(equity)
    daily_peak_raw = await redis_client.get("risk:daily_peak_equity")
    daily_peak = float(daily_peak_raw) if daily_peak_raw else equity
    daily_peak = max(daily_peak, equity)
    await redis_client.set("risk:daily_peak_equity", str(daily_peak))


def calculate_lot_size(entry: float, stop_loss: float, balance: float | None = None) -> float:
    bal = balance if balance is not None else settings.ACCOUNT_BALANCE
    sl_distance = abs(entry - stop_loss)
    if not math.isfinite(sl_distance) or sl_distance <= 0:
        return settings.MIN_LOT_SIZE
    risk_amount = bal * (settings.RISK_PERCENT_PER_TRADE / 100.0)
    raw_lots = risk_amount / (sl_distance * 100.0)
    lots = max(settings.MIN_LOT_SIZE, min(settings.MAX_LOT_SIZE, round(raw_lots, 2)))
    return lots
