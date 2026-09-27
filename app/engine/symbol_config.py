from dataclasses import dataclass


@dataclass(frozen=True)
class SymbolThresholds:
    sweep_buffer: float
    stop_buffer: float
    min_fvg_gap: float
    price_jitter: float


_DEFAULT = SymbolThresholds(sweep_buffer=0.00015, stop_buffer=0.00030, min_fvg_gap=0.00030, price_jitter=0.0002)
_GOLD = SymbolThresholds(sweep_buffer=0.15, stop_buffer=0.30, min_fvg_gap=0.30, price_jitter=0.2)


def thresholds_for_symbol(symbol: str) -> SymbolThresholds:
    s = symbol.upper()
    if any(k in s for k in ("XAU", "GOLD", "XAG", "SILVER")):
        return _GOLD
    return _DEFAULT
