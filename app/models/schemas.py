import math
import re
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, List, Literal


_SYMBOL_PATTERN = re.compile(r"^[A-Za-z0-9._-]{3,32}$")


class CandleData(BaseModel):
    open: float
    high: float
    low: float
    close: float
    volume: float

    @field_validator("open", "high", "low", "close", "volume")
    @classmethod
    def finite_positive_ohlc(cls, v: float, info) -> float:
        if not math.isfinite(v):
            raise ValueError(f"{info.field_name} must be finite")
        if info.field_name != "volume" and v <= 0:
            raise ValueError(f"{info.field_name} must be positive")
        if info.field_name == "volume" and v < 0:
            raise ValueError("volume must be non-negative")
        return v

    @model_validator(mode="after")
    def ohlc_consistent(self) -> "CandleData":
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high must be >= open, close, and low")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low must be <= open, close, and high")
        return self


class TradingViewWebhookPayload(BaseModel):
    secret_key: str
    symbol: str
    action: Literal["BUY", "SELL", "buy", "sell"]
    entry_price: float
    fvg_low: float
    fvg_high: float
    sl_price: float
    tp_price: Optional[float] = None
    asia_high: Optional[float] = None
    asia_low: Optional[float] = None
    recent_candles: Optional[List[CandleData]] = None
    idempotency_key: Optional[str] = Field(default=None, max_length=128)

    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        v = v.strip()
        if not _SYMBOL_PATTERN.match(v):
            raise ValueError("invalid symbol format")
        return v.upper()

    @field_validator(
        "entry_price", "fvg_low", "fvg_high", "sl_price", "tp_price",
        "asia_high", "asia_low", mode="before"
    )
    @classmethod
    def finite_price(cls, v):
        if v is None:
            return v
        v = float(v)
        if not math.isfinite(v) or v <= 0:
            raise ValueError("price fields must be finite and positive")
        return v

    @model_validator(mode="after")
    def fvg_and_asia_ranges(self) -> "TradingViewWebhookPayload":
        if self.fvg_low > self.fvg_high:
            raise ValueError("fvg_low must be <= fvg_high")
        if self.asia_high is not None and self.asia_low is not None:
            if self.asia_high < self.asia_low:
                raise ValueError("asia_high must be >= asia_low")
        return self

    @property
    def normalized_action(self) -> Literal["BUY", "SELL"]:
        return "BUY" if self.action.upper() == "BUY" else "SELL"


def validate_sl_tp_geometry(direction: str, entry: float, sl: float, tp: float) -> bool:
    if not all(math.isfinite(x) for x in (entry, sl, tp)):
        return False
    if direction == "BUY":
        return sl < entry < tp
    return tp < entry < sl


def default_take_profit(direction: str, entry: float, fvg_low: float, fvg_high: float, offset: float = 3.0) -> float:
    if direction == "BUY":
        return round(entry + offset, 2)
    return round(entry - offset, 2)


class OrderExecutionRequest(BaseModel):
    account_id: str
    symbol: str
    action: Literal["BUY", "SELL"]
    lot_size: float
    entry_price: float
    stop_loss: float
    take_profit: float
    order_type: Literal["MARKET", "LIMIT"]
    delay_ms: int
