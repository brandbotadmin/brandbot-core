import sys
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
import uvicorn
import MetaTrader5 as mt5

# Configuration of Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - MT5Bridge - %(levelname)s - %(message)s"
)
logger = logging.getLogger("mt5_bridge")

app = FastAPI(
    title="BrandBot MT5 Direct Bridge",
    description="Direct Execution Bridge connecting BrandBot Core to MT5 Terminal",
    version="1.0.0"
)

# Request Data Schema
class TradeSignal(BaseModel):
    symbol: Optional[str] = "XAUUSD"
    action: str  # "BUY" ose "SELL"
    volume: Optional[float] = 0.01
    sl: Optional[float] = None
    tp: Optional[float] = None
    comment: Optional[str] = "BrandBot Trade"


def initialize_mt5():
    """Inicon lidhjen me terminalin MT5 të hapur."""
    if not mt5.initialize():
        logger.error(f"❌ Initialization failed, error code: {mt5.last_error()}")
        return False
    
    account_info = mt5.account_info()
    if account_info is not None:
        logger.info(f"✅ Successfully connected to MT5 Account: #{account_info.login}")
        logger.info(f"📊 Broker: {account_info.company} | Balance: ${account_info.balance:.2f} | Equity: ${account_info.equity:.2f}")
        return True
    else:
        logger.error("❌ Connected to MT5, but could not fetch account info!")
        return False


@app.on_event("startup")
async def startup_event():
    logger.info("⚡ Starting MT5 Direct Bridge Server...")
    if not initialize_mt5():
        logger.warning("⚠️ MT5 Terminal is not running or not logged in yet. Please start MT5 Terminal!")


@app.get("/")
async def root():
    return {
        "status": "online",
        "service": "BrandBot MT5 Bridge",
        "mt5_connected": mt5.account_info() is not None
    }


@app.post("/trade")
async def execute_trade(trade: TradeSignal):
    """
    Merr sinjalin nga BrandBot te Railway dhe ekzekuton urdhrin te MT5 Terminal.
    """
    # Sigurohemi që lidhja me MT5 është aktive
    if mt5.account_info() is None:
        if not initialize_mt5():
            raise HTTPException(status_code=500, detail="MT5 Terminal is not connected!")

    symbol = trade.symbol.upper()
    action = trade.action.upper()
    volume = float(trade.volume)

    # Verifikojmë nëse simboli ekziston te brokeri (IC Markets)
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        logger.error(f"❌ Symbol {symbol} not found in MT5 Terminal!")
        raise HTTPException(status_code=400, detail=f"Symbol {symbol} not found")

    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            logger.error(f"❌ Failed to select symbol {symbol}")
            raise HTTPException(status_code=400, detail=f"Symbol {symbol} selection failed")

    # Përcaktojmë llojin e urdhrit dhe çmimin aktual
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise HTTPException(status_code=500, detail=f"Failed to get price tick for {symbol}")

    if action == "BUY":
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask
    elif action == "SELL":
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid
    else:
        raise HTTPException(status_code=400, detail="Action must be 'BUY' or 'SELL'")

    # Ndërtimi i kërkesës për ekzekutim në MT5
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": volume,
        "type": order_type,
        "price": price,
        "deviation": 20,
        "magic": 999888,  # Magic Number unikal për BrandBot
        "comment": trade.comment,
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    # Shtojmë Stop Loss (SL) dhe Take Profit (TP) nëse janë dërguar
    if trade.sl:
        request["sl"] = float(trade.sl)
    if trade.tp:
        request["tp"] = float(trade.tp)

    logger.info(f"⏳ Sending Order to MT5: {action} {volume} lot(s) {symbol} @ {price}")

    # Ekzekutimi përfundimtar te Brokeri
    result = mt5.order_send(request)

    if result is None:
        logger.error("❌ order_send failed, returned None")
        raise HTTPException(status_code=500, detail="Order execution failed at MT5 level")

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        logger.error(f"❌ Trade Execution Failed! Retcode: {result.retcode}, Comment: {result.comment}")
        return {
            "status": "failed",
            "error_code": result.retcode,
            "message": result.comment
        }

    logger.info(f"🎉 TRADE EXECUTED SUCCESSFULLY! Order Ticket: #{result.order}")
    return {
        "status": "success",
        "order_id": result.order,
        "volume": result.volume,
        "price": result.price,
        "comment": result.comment
    }


if __name__ == "__main__":
    uvicorn.run("mt5_bridge:app", host="0.0.0.0", port=8000, reload=True)