import hashlib
import json
import logging
from fastapi import APIRouter, HTTPException, Request, status
import httpx
from app.models.schemas import (
    TradingViewWebhookPayload,
    default_take_profit,
    validate_sl_tp_geometry,
)
from app.core.redis import (
    acquire_lock,
    release_lock,
    extend_lock,
    check_idempotency,
    store_idempotency,
    check_rate_limit,
)
from app.core.control import is_global_frozen
from app.core.webhook_security import verify_webhook_secret, verify_client_ip, verify_hmac_signature
from app.core.risk import is_drawdown_exceeded, calculate_lot_size
from app.engine.smc_strategy import SMCStrategyEngine
from app.engine.crt_strategy import CRTStrategyEngine
from app.engine.news_guard import NewsGuard
from app.engine.anti_fingerprint import AntiFingerprintEngine
from app.engine.volume_analysis import compute_volume_metrics
from app.ai.ml_scoring import MLScoringEngine
from app.ai.llm_context import AIContextAnalyzer
from app.execution.metaapi_client import MetaApiClient
from app.discord_bot.bot import send_trading_alert
from config.settings import settings

logger = logging.getLogger(__name__)
router = APIRouter()


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _idempotency_key(payload: TradingViewWebhookPayload, raw_body: bytes) -> str:
    if payload.idempotency_key:
        return payload.idempotency_key
    digest = hashlib.sha256(raw_body).hexdigest()
    return f"{payload.symbol}:{payload.normalized_action}:{digest[:32]}"


@router.post("/webhook/tradingview", status_code=status.HTTP_200_OK)
async def handle_tradingview_webhook(request: Request):
    raw_body = await request.body()
    
    # 1. Verifiko HMAC vetëm nëse hederi ekziston, përndryshe mos e blloko
    signature = request.headers.get("X-Brandbot-Signature")
    if signature:
        verify_hmac_signature(raw_body, signature)

    # 2. Parse JSON Payload
    try:
        data = json.loads(raw_body.decode("utf-8"))
        payload = TradingViewWebhookPayload.model_validate(data)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=f"Invalid payload: {exc}") from exc

    # 3. Verifiko Secret Key nga JSON Payload
    verify_webhook_secret(payload.secret_key)

    # 4. Verifiko IP dhe Rate Limit
    client_ip = _client_ip(request)
    if not await check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

    idem_key = _idempotency_key(payload, raw_body)
    if await check_idempotency(idem_key):
        return {"status": "DUPLICATE", "reason": "Idempotency key already processed", "idempotency_key": idem_key}

    if await is_global_frozen():
        return {"status": "REJECTED", "reason": "Sistemi i tregtimit është i ngrirë (Global Freeze)"}

    drawdown_hit, drawdown_type, drawdown_pct = await is_drawdown_exceeded()
    if drawdown_hit:
        limit = (
            settings.MAX_DAILY_DRAWDOWN_PERCENT
            if drawdown_type == "daily"
            else settings.MAX_DRAWDOWN_PERCENT
        )
        label = "Daily drawdown" if drawdown_type == "daily" else "Max drawdown"
        return {
            "status": "REJECTED",
            "reason": f"{label} limit exceeded ({drawdown_pct}% > {limit}%)",
            "drawdown_type": drawdown_type,
        }

    lock_name = f"symbol:{payload.symbol}"
    lock_token = await acquire_lock(lock_name)
    if not lock_token:
        return {"status": "REJECTED", "reason": "Një tregti për këtë simbol është duke u procesuar"}

    http_client: httpx.AsyncClient | None = getattr(request.app.state, "http_client", None)

    try:
        if await NewsGuard.is_news_freeze_active("USD"):
            return {"status": "REJECTED", "reason": "Dritare aktive e lajmeve me ndikim të lartë (15-min freeze)"}

        direction = payload.normalized_action
        trade_entry = payload.entry_price
        candles = [c.model_dump() for c in (payload.recent_candles or [])]
        volume_metrics = compute_volume_metrics(candles)

        selected_setup = None

        smc_check = SMCStrategyEngine.analyze_smc_setup(
            symbol=payload.symbol,
            direction=direction,
            fvg_low=payload.fvg_low,
            fvg_high=payload.fvg_high,
            sl_price=payload.sl_price,
            tp_price=payload.tp_price,
            asia_high=payload.asia_high,
            asia_low=payload.asia_low,
            candles=candles,
        )
        if smc_check.get("is_valid"):
            ce_entry = smc_check["entry"]
            tp = payload.tp_price or default_take_profit(
                direction, ce_entry, payload.fvg_low, payload.fvg_high
            )
            if validate_sl_tp_geometry(direction, ce_entry, payload.sl_price, tp):
                selected_setup = {
                    "engine": "SMC_FVG",
                    "direction": direction,
                    "entry": ce_entry,
                    "stop_loss": payload.sl_price,
                    "take_profit": tp,
                    "metrics": {**smc_check, **volume_metrics},
                }

        if not selected_setup and payload.asia_high is not None and payload.asia_low is not None:
            crt_price = candles[-1]["close"] if candles else trade_entry
            crt_check = CRTStrategyEngine.analyze_advanced_crt_setup(
                symbol=payload.symbol,
                current_price=crt_price,
                asia_high=payload.asia_high,
                asia_low=payload.asia_low,
                recent_candles_m1=candles,
                recent_candles_m5=candles,
            )
            if crt_check.get("is_valid"):
                sl = crt_check["stop_loss"]
                tp = crt_check["take_profit"]
                if validate_sl_tp_geometry(crt_check["direction"], crt_price, sl, tp):
                    selected_setup = {
                        "engine": "CRT_SWEEP",
                        "direction": crt_check["direction"],
                        "entry": crt_price,
                        "stop_loss": sl,
                        "take_profit": tp,
                        "metrics": {**crt_check, **volume_metrics},
                    }

        if not selected_setup:
            return {"status": "REJECTED", "reason": "Kushtet e SMC dhe CRT nuk u plotësuan."}

        await extend_lock(lock_name, lock_token)

        ai_macro = await AIContextAnalyzer.analyze_market_context(
            [f"{payload.symbol} {selected_setup['direction']} setup"],
            client=http_client,
        )
        if ai_macro.get("context_score", 100) < 50:
            return {
                "status": "REJECTED",
                "reason": f"AI Risk Score i ulët ({ai_macro.get('context_score')}): {ai_macro.get('reason')}",
            }

        ml_features = [
            3,
            2,
            selected_setup["metrics"].get("fvg_gap_pips", 0.40),
            volume_metrics["volume_delta_ratio"],
            1.5,
            abs(selected_setup["entry"] - (payload.asia_high or selected_setup["entry"])),
            volume_metrics["volume_ratio"],
        ]
        win_prob, ml_source = MLScoringEngine.predict_win_probability(ml_features)
        if win_prob < settings.ML_MIN_WIN_PROBABILITY:
            return {
                "status": "REJECTED",
                "reason": f"ML Win-Probability e pamjaftueshme ({win_prob} < {settings.ML_MIN_WIN_PROBABILITY})",
                "ml_source": ml_source,
            }

        jitter_delay = await AntiFingerprintEngine.apply_gaussian_jitter()
        await extend_lock(lock_name, lock_token)

        trade_entry = selected_setup["entry"]
        final_sl, final_tp = AntiFingerprintEngine.apply_micro_price_variation(
            payload.symbol,
            selected_setup["direction"],
            trade_entry,
            selected_setup["stop_loss"],
            selected_setup["take_profit"],
        )
        if not validate_sl_tp_geometry(selected_setup["direction"], trade_entry, final_sl, final_tp):
            return {"status": "REJECTED", "reason": "SL/TP invalid after anti-fingerprint adjustment"}

        lot_size = calculate_lot_size(trade_entry, final_sl)

        await extend_lock(lock_name, lock_token)

        metaapi_result = await MetaApiClient.execute_trade(
            account_id=settings.METAAPI_ACCOUNT_ID,
            symbol=payload.symbol,
            action=selected_setup["direction"],
            volume=lot_size,
            stop_loss=final_sl,
            take_profit=final_tp,
            entry_price=trade_entry,
            client=http_client,
        )

        if MetaApiClient.is_successful_execution(metaapi_result):
            await store_idempotency(idem_key, "executed")
            return {
                "status": "APPROVED_AND_EXECUTED",
                "executed_engine": selected_setup["engine"],
                "direction": selected_setup["direction"],
                "symbol": payload.symbol,
                "entry_price": trade_entry,
                "volume": lot_size,
                "adjusted_sl": final_sl,
                "adjusted_tp": final_tp,
                "execution_delay_ms": jitter_delay,
                "win_probability": win_prob,
                "ml_source": ml_source,
                "ai_context_score": ai_macro.get("context_score"),
                "idempotency_key": idem_key,
                "metaapi_response": metaapi_result,
            }

        await send_trading_alert(
            f"BrandBot execution FAILED | {payload.symbol} {selected_setup['direction']} | "
            f"result={metaapi_result.get('status')} detail={metaapi_result.get('error') or metaapi_result.get('message')}"
        )
        logger.error("MetaApi execution failed: %s", metaapi_result)
        return {
            "status": "FAILED",
            "reason": "Broker execution failed or was not confirmed",
            "executed_engine": selected_setup["engine"],
            "direction": selected_setup["direction"],
            "symbol": payload.symbol,
            "entry_price": trade_entry,
            "volume": lot_size,
            "metaapi_response": metaapi_result,
        }

    finally:
        if lock_token:
            await release_lock(lock_name, lock_token)
