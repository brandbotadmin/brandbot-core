import math
import httpx
from config.settings import settings
from app.models.schemas import validate_sl_tp_geometry


class MetaApiClient:
    @staticmethod
    def _validate_order(direction: str, entry: float, stop_loss: float, take_profit: float) -> str | None:
        if not settings.METAAPI_ACCOUNT_ID:
            return "METAAPI_ACCOUNT_ID not configured"
        if not validate_sl_tp_geometry(direction, entry, stop_loss, take_profit):
            return "Invalid SL/TP geometry relative to entry"
        if not all(math.isfinite(x) for x in (stop_loss, take_profit, entry)):
            return "Non-finite price in order"
        return None

    @staticmethod
    async def execute_trade(
        account_id: str,
        symbol: str,
        action: str,
        volume: float,
        stop_loss: float,
        take_profit: float,
        entry_price: float,
        client: httpx.AsyncClient | None = None,
    ) -> dict:
        validation_error = MetaApiClient._validate_order(action, entry_price, stop_loss, take_profit)
        if validation_error:
            return {"status": "FAILED", "error": validation_error}

        if volume < settings.MIN_LOT_SIZE or volume > settings.MAX_LOT_SIZE:
            return {"status": "FAILED", "error": "Volume outside configured lot bounds"}

        token = settings.METAAPI_TOKEN
        if not token or token.startswith("your_"):
            if settings.ALLOW_SIMULATED_EXECUTION:
                return {"status": "SIMULATED", "order_id": "MOCK_SIMULATION"}
            return {"status": "FAILED", "error": "MetaApi token not configured"}

        url = (
            f"{settings.METAAPI_API_HOST.rstrip('/')}/users/current/accounts/"
            f"{account_id}/trade"
        )
        headers = {
            "auth-token": token,
            "Content-Type": "application/json",
        }
        payload = {
            "actionType": "ORDER_TYPE_BUY" if action == "BUY" else "ORDER_TYPE_SELL",
            "symbol": symbol,
            "volume": volume,
            "stopLoss": stop_loss,
            "takeProfit": take_profit,
        }

        owns_client = client is None
        http = client or httpx.AsyncClient(timeout=10.0)
        try:
            response = await http.post(url, json=payload, headers=headers)
            if response.status_code in (200, 201):
                return {"status": "EXECUTED", "data": response.json()}
            return {"status": "FAILED", "error": response.text, "http_status": response.status_code}
        except Exception as e:
            return {"status": "ERROR", "message": str(e)}
        finally:
            if owns_client:
                await http.aclose()

    @staticmethod
    def is_successful_execution(result: dict) -> bool:
        status = result.get("status")
        if status == "EXECUTED":
            return True
        if status == "SIMULATED" and settings.ALLOW_SIMULATED_EXECUTION:
            return True
        return False
