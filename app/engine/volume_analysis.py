from typing import Any


def compute_volume_metrics(candles: list[dict[str, Any]]) -> dict[str, float]:
    if len(candles) < 2:
        return {"volume_delta_ratio": 1.0, "volume_ratio": 1.0}

    volumes = [float(c.get("volume", 0) or 0) for c in candles[-10:]]
    if not volumes or max(volumes) <= 0:
        return {"volume_delta_ratio": 1.0, "volume_ratio": 1.0}

    last_vol = volumes[-1]
    prev_vol = volumes[-2]
    avg_vol = sum(volumes) / len(volumes)
    delta_ratio = (last_vol - prev_vol) / prev_vol if prev_vol > 0 else 1.0
    volume_ratio = last_vol / avg_vol if avg_vol > 0 else 1.0
    return {
        "volume_delta_ratio": round(delta_ratio, 4),
        "volume_ratio": round(volume_ratio, 4),
    }
