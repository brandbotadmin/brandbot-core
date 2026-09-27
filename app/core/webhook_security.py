import hmac
import hashlib
import secrets
from fastapi import HTTPException, Request, status
from config.settings import settings


def verify_webhook_secret(provided: str) -> None:
    if not settings.WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured",
        )
    if not secrets.compare_digest(provided, settings.WEBHOOK_SECRET):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid webhook secret")


def verify_client_ip(request: Request) -> None:
    allowlist = settings.webhook_ip_allowlist()
    if not allowlist:
        return
    forwarded = request.headers.get("X-Forwarded-For")
    client_ip = forwarded.split(",")[0].strip() if forwarded else (request.client.host if request.client else "")
    if client_ip not in allowlist:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="IP not allowed")


def verify_hmac_signature(raw_body: bytes, signature_header: str | None) -> None:
    if not settings.WEBHOOK_HMAC_ENABLED:
        return
    if not settings.WEBHOOK_SECRET:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Webhook secret not configured for HMAC",
        )
    if not signature_header:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Missing HMAC signature")
    expected = hmac.new(
        settings.WEBHOOK_SECRET.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).hexdigest()
    provided = signature_header.removeprefix("sha256=").strip()
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid HMAC signature")
