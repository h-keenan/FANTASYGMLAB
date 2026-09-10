"""Backend-only Stripe webhook service for Founder Premium.

Deployment topology (Render):
  - Service name: fantasygmlab-stripe-webhook
  - Entrypoint: uvicorn services.stripe_webhook_service:app --host 0.0.0.0 --port $PORT
  - Expected public host: https://fantasygmlab-stripe-webhook.onrender.com
  - GET  /health         — process liveness (no Stripe/Supabase dependency)
  - GET  /ready          — billing config readiness (no secret values)
  - POST /stripe/webhook — signed events matching the configured Stripe mode

Test mode is the safe default. Live mode requires explicit matching configuration.
"""

from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from modules import stripe_billing, stripe_webhook


SERVICE_NAME = "stripe-webhook"
EXPECTED_PUBLIC_HOST = "https://fantasygmlab-stripe-webhook.onrender.com"

app = FastAPI(
    title="FantasyGM Lab Stripe Webhook",
    version="0.2.0",
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
async def _unhandled_exception_handler(_request: Request, _exc: Exception):
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
        "webhook": "/stripe/webhook",
        "mode": "configured_server_side",
    }


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness only — must not depend on Stripe or Supabase reachability."""

    return {"status": "ok"}


@app.get("/ready")
def ready() -> JSONResponse:
    """Readiness: Test Mode secrets present; never returns secret values."""

    stripe_config = stripe_billing.load_stripe_config()
    supabase_config = stripe_webhook.load_supabase_webhook_config()
    issues: list[str] = []
    if stripe_config.billing_mode not in {"test", "live"}:
        issues.append("stripe_billing_mode_invalid")
    elif not stripe_config.secret_mode_configured:
        issues.append("stripe_secret_mode_mismatch")
    elif stripe_config.billing_mode == "live" and not stripe_config.configured:
        issues.append("stripe_live_prices_missing")
    if not stripe_config.webhook_configured:
        issues.append("stripe_webhook_secret_missing")
    if not supabase_config.configured:
        issues.append("supabase_service_role_missing")
    if issues:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "mode": stripe_config.billing_mode, "issues": issues},
        )
    return JSONResponse(
        content={
            "status": "ready",
            "mode": stripe_config.billing_mode,
            "service": SERVICE_NAME,
        }
    )


def _assert_billing_runtime(stripe_config: stripe_billing.StripeBillingConfig) -> None:
    if not stripe_config.secret_mode_configured:
        raise HTTPException(status_code=503, detail="Stripe billing mode and secret key do not match.")
    if stripe_config.billing_mode == "live" and not stripe_config.configured:
        raise HTTPException(status_code=503, detail="Stripe live price configuration is incomplete.")
    if not stripe_config.webhook_configured:
        raise HTTPException(status_code=500, detail="Stripe webhook secret is not configured.")
    webhook_secret = str(stripe_config.webhook_secret or "")
    if webhook_secret and not webhook_secret.startswith("whsec_"):
        raise HTTPException(
            status_code=500,
            detail="Stripe webhook signing secret is invalid for Test Mode.",
        )


@app.post("/stripe/webhook")
async def stripe_webhook_endpoint(
    request: Request,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
):
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature.")

    payload = await request.body()
    stripe_config = stripe_billing.load_stripe_config()
    supabase_config = stripe_webhook.load_supabase_webhook_config()
    _assert_billing_runtime(stripe_config)
    if not supabase_config.configured:
        raise HTTPException(
            status_code=500,
            detail="Supabase service-role update is not configured.",
        )

    try:
        result = stripe_webhook.process_verified_stripe_webhook(
            payload=payload,
            signature=stripe_signature,
            stripe_config=stripe_config,
            supabase_config=supabase_config,
        )
    except stripe_billing.BillingConfigurationError as exc:
        message = _safe_error_detail(exc)
        status = 400 if "signature" in message.casefold() or "event mode" in message.casefold() else 500
        raise HTTPException(status_code=status, detail=message) from None
    except Exception:
        raise HTTPException(status_code=500, detail="Webhook processing failed.") from None

    if not result.get("ok"):
        message = str(result.get("error") or "Stripe webhook processing failed.")
        status = (
            400
            if "signature" in message.casefold() or "user id" in message.casefold()
            else 500
        )
        raise HTTPException(status_code=status, detail=message)

    action = result.get("action") or {}
    return JSONResponse(
        {
            "received": True,
            "event_id": result.get("event_id", ""),
            "entitlement": action.get("entitlement", ""),
            "subscription_status": action.get("stripe_subscription_status", ""),
            "skipped": bool(result.get("skipped")),
        }
    )
