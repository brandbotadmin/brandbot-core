import math
from typing import Any
from config.settings import settings
from app.engine.symbol_config import thresholds_for_symbol


class SMCStrategyEngine:
    """SDR §3.1–3.3: Session sweep → MSS → FVG / OB with CE entry and SMA20 volume filter."""

    @staticmethod
    def calculate_fvg_threshold(fvg_low: float, fvg_high: float, symbol: str = "XAUUSD") -> dict:
        if not all(math.isfinite(x) and x > 0 for x in (fvg_low, fvg_high)):
            return {"is_valid": False, "fvg_gap_pips": 0.0, "reason": "Invalid FVG prices"}

        cfg = thresholds_for_symbol(symbol)
        fvg_gap = round(abs(fvg_high - fvg_low), 5)
        return {
            "is_valid": fvg_gap >= cfg.min_fvg_gap,
            "fvg_gap_pips": fvg_gap,
            "min_required_gap": cfg.min_fvg_gap,
        }

    @staticmethod
    def _sma_volume(candles: list[dict[str, Any]], end_index: int, period: int) -> float | None:
        start = max(0, end_index - period)
        if end_index - start < period:
            return None
        window = candles[start:end_index]
        vols = [float(c.get("volume", 0) or 0) for c in window]
        if not vols:
            return None
        return sum(vols) / len(vols)

    @staticmethod
    def detect_fvg_from_candles(candles: list[dict[str, Any]], direction: str) -> dict | None:
        if len(candles) < 3:
            return None
        c1, c2, c3 = candles[-3], candles[-2], candles[-1]
        try:
            h1, l1 = float(c1["high"]), float(c1["low"])
            h3, l3 = float(c3["high"]), float(c3["low"])
        except (KeyError, TypeError, ValueError):
            return None

        if direction == "BUY" and h1 < l3:
            return {
                "fvg_low": round(h1, 5),
                "fvg_high": round(l3, 5),
                "middle_candle_index": len(candles) - 2,
                "middle_candle": c2,
            }
        if direction == "SELL" and l1 > h3:
            return {
                "fvg_low": round(h3, 5),
                "fvg_high": round(l1, 5),
                "middle_candle_index": len(candles) - 2,
                "middle_candle": c2,
            }
        return None

    @staticmethod
    def validate_middle_candle_volume(
        candles: list[dict[str, Any]], middle_index: int, multiplier: float | None = None
    ) -> dict:
        mult = multiplier if multiplier is not None else settings.FVG_VOLUME_SMA_MULTIPLIER
        period = settings.FVG_VOLUME_SMA_PERIOD
        sma = SMCStrategyEngine._sma_volume(candles, middle_index, period)
        try:
            middle_vol = float(candles[middle_index].get("volume", 0) or 0)
        except (IndexError, TypeError, ValueError):
            return {"is_valid": False, "reason": "Missing middle candle volume"}

        if sma is None or sma <= 0:
            return {"is_valid": False, "reason": f"Need at least {period} candles for SMA volume"}

        ratio = middle_vol / sma
        return {
            "is_valid": middle_vol >= sma * mult,
            "middle_volume": middle_vol,
            "volume_sma20": round(sma, 4),
            "volume_ratio_vs_sma20": round(ratio, 4),
            "required_multiplier": mult,
        }

    @staticmethod
    def consequent_encroachment(fvg_low: float, fvg_high: float) -> float:
        return round((fvg_low + fvg_high) / 2.0, 5)

    @staticmethod
    def order_block_from_fvg(candles: list[dict[str, Any]], direction: str) -> dict | None:
        if len(candles) < 3:
            return None
        ob_candle = candles[-3]
        try:
            return {
                "ob_high": round(float(ob_candle["high"]), 5),
                "ob_low": round(float(ob_candle["low"]), 5),
                "direction": direction,
            }
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def detect_asia_liquidity_sweep(
        candles: list[dict[str, Any]], asia_high: float, asia_low: float, symbol: str
    ) -> dict | None:
        if not candles or asia_high <= 0 or asia_low <= 0 or asia_high < asia_low:
            return None
        cfg = thresholds_for_symbol(symbol)
        sweep = cfg.sweep_buffer
        lookback = min(len(candles), settings.SMC_SWEEP_LOOKBACK_CANDLES)

        for candle in reversed(candles[-lookback:]):
            try:
                low = float(candle["low"])
                high = float(candle["high"])
                close = float(candle["close"])
            except (KeyError, TypeError, ValueError):
                continue
            if low <= (asia_low - sweep) and close > asia_low:
                return {"sweep_direction": "BUY", "swept_level": "asia_low"}
            if high >= (asia_high + sweep) and close < asia_high:
                return {"sweep_direction": "SELL", "swept_level": "asia_high"}
        return None

    @staticmethod
    def detect_market_structure_shift(
        candles: list[dict[str, Any]], expected_direction: str, lookback: int | None = None
    ) -> dict:
        lb = lookback if lookback is not None else settings.MSS_LOCAL_STRUCTURE_LOOKBACK
        if len(candles) < lb + 1:
            return {"is_valid": False, "reason": "Insufficient candles for MSS"}

        prior = candles[-(lb + 1) : -1]
        last = candles[-1]
        try:
            close = float(last["close"])
            local_high = max(float(c["high"]) for c in prior)
            local_low = min(float(c["low"]) for c in prior)
        except (KeyError, TypeError, ValueError):
            return {"is_valid": False, "reason": "Invalid candle data for MSS"}

        if expected_direction == "BUY":
            valid = close > local_high
            return {
                "is_valid": valid,
                "mss_type": "bullish",
                "break_level": round(local_high, 5),
                "close": round(close, 5),
            }
        valid = close < local_low
        return {
            "is_valid": valid,
            "mss_type": "bearish",
            "break_level": round(local_low, 5),
            "close": round(close, 5),
        }

    @staticmethod
    def _fvg_bounds_match(
        detected_low: float, detected_high: float, payload_low: float, payload_high: float, symbol: str
    ) -> bool:
        cfg = thresholds_for_symbol(symbol)
        tol = max(cfg.min_fvg_gap * 0.25, 0.05)
        return abs(detected_low - payload_low) <= tol and abs(detected_high - payload_high) <= tol

    @classmethod
    def analyze_smc_setup(
        cls,
        symbol: str,
        direction: str,
        fvg_low: float,
        fvg_high: float,
        sl_price: float,
        tp_price: float | None,
        asia_high: float | None,
        asia_low: float | None,
        candles: list[dict[str, Any]],
    ) -> dict:
        gap_check = cls.calculate_fvg_threshold(fvg_low, fvg_high, symbol=symbol)
        if not gap_check["is_valid"]:
            return {"is_valid": False, "reason": "FVG gap below minimum", **gap_check}

        min_candles = settings.FVG_VOLUME_SMA_PERIOD + 2
        if len(candles) < min_candles:
            return {
                "is_valid": False,
                "reason": f"SMC requires at least {min_candles} recent candles for FVG volume SMA",
            }

        if asia_high is None or asia_low is None:
            return {"is_valid": False, "reason": "Asia high/low required for SMC liquidity sweep"}

        sweep = cls.detect_asia_liquidity_sweep(candles, asia_high, asia_low, symbol)
        if not sweep:
            return {"is_valid": False, "reason": "No valid Asia liquidity sweep (SDR §3.1)"}

        if sweep["sweep_direction"] != direction:
            return {
                "is_valid": False,
                "reason": "Sweep direction does not match signal action",
                "sweep": sweep,
            }

        mss = cls.detect_market_structure_shift(candles, direction)
        if not mss.get("is_valid"):
            return {"is_valid": False, "reason": "Market Structure Shift not confirmed (SDR §3.2)", "mss": mss}

        detected_fvg = cls.detect_fvg_from_candles(candles, direction)
        if not detected_fvg:
            return {"is_valid": False, "reason": "Three-candle FVG pattern not found (SDR §3.3)"}

        if not cls._fvg_bounds_match(
            detected_fvg["fvg_low"], detected_fvg["fvg_high"], fvg_low, fvg_high, symbol
        ):
            return {
                "is_valid": False,
                "reason": "Webhook FVG bounds do not match candle FVG structure",
                "detected_fvg": detected_fvg,
            }

        volume_check = cls.validate_middle_candle_volume(candles, detected_fvg["middle_candle_index"])
        if not volume_check.get("is_valid"):
            return {
                "is_valid": False,
                "reason": "FVG middle candle volume below 1.5x SMA20 (SDR §3.3)",
                **volume_check,
            }

        ce_entry = cls.consequent_encroachment(fvg_low, fvg_high)
        order_block = cls.order_block_from_fvg(candles, direction)

        return {
            "is_valid": True,
            "engine": "SMC_FVG",
            "direction": direction,
            "entry": ce_entry,
            "stop_loss": sl_price,
            "take_profit": tp_price,
            "consequent_encroachment": ce_entry,
            "order_block": order_block,
            "sweep": sweep,
            "mss": mss,
            "fvg_gap_pips": gap_check["fvg_gap_pips"],
            "volume_sma20": volume_check.get("volume_sma20"),
            "volume_ratio_vs_sma20": volume_check.get("volume_ratio_vs_sma20"),
            "detected_fvg": detected_fvg,
        }
