from typing import Dict, Any, List
from app.engine.symbol_config import thresholds_for_symbol


class CRTStrategyEngine:
    @classmethod
    def analyze_advanced_crt_setup(
        cls,
        symbol: str,
        current_price: float,
        asia_high: float,
        asia_low: float,
        recent_candles_m1: List[Dict[str, Any]],
        recent_candles_m5: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        if not recent_candles_m1 or asia_high <= 0 or asia_low <= 0 or asia_high < asia_low:
            return {"is_valid": False, "reason": "Të dhëna të pamjaftueshme"}

        if not all(x > 0 for x in (current_price,)):
            return {"is_valid": False, "reason": "Invalid current price"}

        cfg = thresholds_for_symbol(symbol)
        m1_last = recent_candles_m1[-1]
        try:
            low = float(m1_last["low"])
            high = float(m1_last["high"])
            close = float(m1_last["close"])
        except (KeyError, TypeError, ValueError):
            return {"is_valid": False, "reason": "Invalid candle structure"}

        sweep = cfg.sweep_buffer
        stop_buf = cfg.stop_buffer

        if low <= (asia_low - sweep) and close > asia_low:
            sl = round(low - stop_buf, 5)
            tp = round(asia_high, 5)
            return {"is_valid": True, "direction": "BUY", "stop_loss": sl, "take_profit": tp}

        if high >= (asia_high + sweep) and close < asia_high:
            sl = round(high + stop_buf, 5)
            tp = round(asia_low, 5)
            return {"is_valid": True, "direction": "SELL", "stop_loss": sl, "take_profit": tp}

        if recent_candles_m5 and len(recent_candles_m5) >= 2:
            m5_last = recent_candles_m5[-1]
            try:
                m5_close = float(m5_last["close"])
            except (KeyError, TypeError, ValueError):
                m5_close = close
            if close > asia_low and m5_close > asia_low and low <= (asia_low - sweep):
                sl = round(low - stop_buf, 5)
                tp = round(asia_high, 5)
                return {"is_valid": True, "direction": "BUY", "stop_loss": sl, "take_profit": tp}

        return {"is_valid": False, "reason": "Nuk ka sweep valid"}
