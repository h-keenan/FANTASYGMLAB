"""DEPRECATED (2026-10-24) -- ROLLBACK ONLY. Stripe/RevenueCat webhooks are processed by Supabase Edge Functions now (docs/billing-on-supabase.md); this service is no longer deployed on the self-hosted box (removed from docker-compose.yml and the Caddyfile). Kept in the repo only so billing can be rolled back; do not extend it.

Backend-only RevenueCat webhook service for Founder Premium (mobile + web RC Billing).

Deployment topology (Render):
  - Service name: fantasygm-lab-revenuecat-webhook
  - Entrypoint: uvicorn services.revenuecat_webhook_service:app --host 0.0.0.0 --port $PORT
  - Expected public host: https://fantasygm-lab-revenuecat-webhook.onrender.com
  - GET  /health             — process liveness (no RevenueCat/Supabase dependency)
  - GET  /ready              — billing config readiness (no secret values)
  - POST /revenuecat/webhook — authorized events matching the configured billing mode

Test mode is the safe default. Live mode requires explicit matching configuration.
"""

from __future__ import annotations

import logging
import os
import sys

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from modules import revenuecat_billing, revenuecat_webhook


SERVICE_NAME = "revenuecat-webhook"
EXPECTED_PUBLIC_HOST = "https://fantasygm-lab-revenuecat-webhook.onrender.com"

# Mirrors services/stripe_webhook_service.py's identical fix — before this,
# an unhandled exception here left zero trace anywhere a human could see it.
logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
    force=True,
)
logger = logging.getLogger("fantasygm.revenuecat_webhook")

app = FastAPI(
    title="FantasyDesk RevenueCat Webhook",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


def _safe_error_detail(exc: Exception) -> str:
    message = str(exc).strip() or "Request failed."
    # Never leak nested exception chains / paths to clients.
    return message.splitlines()[0][:240]


@app.exception_handler(HTTPException)
async def _http_exception_handler(_request: Request, exc: HTTPException):
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
    return JSONResponse(status_code=exc.status_code, content={"ok": False, "error": detail})


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(_request: Request, _exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"ok": False, "error": "Invalid request."},
    )


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception):
    logger.error(
        "Unhandled exception on %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=500,
        content={"ok": False, "error": "Webhook processing failed."},
    )


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "health": "/health",
        "ready": "/ready",
        "webhook": "/revenuecat/webhook",
        "mode": "configured_server_side",
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness only — must not depend on RevenueCat or Supabase reachability."""

    return {"status": "ok"}


@app.get("/ready")
def ready() -> JSONResponse:
    """Readiness: webhook auth + API + Supabase secrets present; never returns secret values."""

    revenuecat_config = revenuecat_billing.load_revenuecat_config()
    supabase_config = revenuecat_webhook.load_supabase_webhook_config()
    issues: list[str] = []
    if revenuecat_config.billing_mode not in {"test", "live"}:
        issues.append("revenuecat_billing_mode_invalid")
    if not revenuecat_config.webhook_configured:
        issues.append("revenuecat_webhook_auth_token_missing")
    if not revenuecat_config.api_configured:
        issues.append("revenuecat_api_credentials_missing")
    if not supabase_config.configured:
        issues.append("supabase_service_role_missing")
    if issues:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "mode": revenuecat_config.billing_mode, "issues": issues},
        )
    return JSONResponse(
        content={
            "status": "ready",
            "mode": revenuecat_config.billing_mode,
            "service": SERVICE_NAME,
        }
    )


@app.post("/revenuecat/webhook")
async def revenuecat_webhook_endpoint(
    request: Request,
    authorization: str | None = Header(default=None),
):
    if not authorization:
        raise HTTPException(status_code=400, detail="Missing Authorization header.")

    payload = await request.body()
    revenuecat_config = revenuecat_billing.load_revenuecat_config()
    supabase_config = revenuecat_webhook.load_supabase_webhook_config()
    if not revenuecat_config.webhook_configured:
        raise HTTPException(status_code=500, detail="RevenueCat webhook auth token is not configured.")
    if not supabase_config.configured:
        raise HTTPException(
            status_code=500,
            detail="Supabase service-role update is not configured.",
        )

    try:
        result = revenuecat_webhook.process_verified_revenuecat_webhook(
            payload=payload,
            authorization_header=authorization,
            revenuecat_config=revenuecat_config,
            supabase_config=supabase_config,
        )
    except revenuecat_billing.BillingConfigurationError as exc:
        message = _safe_error_detail(exc)
        status = 401 if "authoriz" in message.casefold() else 400
        raise HTTPException(status_code=status, detail=message) from None
    except Exception:
        raise HTTPException(status_code=500, detail="Webhook processing failed.") from None

    if not result.get("ok"):
        message = str(result.get("error") or "RevenueCat webhook processing failed.")
        status = 400 if "user id" in message.casefold() else 500
        raise HTTPException(status_code=status, detail=message)

    action = result.get("action") or {}
    return JSONResponse(
        {
            "received": True,
            "event_id": result.get("event_id", ""),
            "entitlement": action.get("entitlement", ""),
            "event_type": action.get("event_type", ""),
            "skipped": bool(result.get("skipped")),
        }
    )
