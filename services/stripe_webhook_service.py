"""Backend-only Stripe webhook service for test-mode Founder Premium.

Deployment topology (Render):
  - Service name: fantasygm-lab-stripe-webhook
  - Entrypoint: uvicorn services.stripe_webhook_service:app --host 0.0.0.0 --port $PORT
  - Expected public host: https://fantasygm-lab-stripe-webhook.onrender.com
  - GET  /health         — process liveness (no Stripe/Supabase dependency)
  - GET  /ready          — test-mode config readiness (no secret values)
  - POST /stripe/webhook — signed Stripe Test Mode events only

Live billing is not enabled. Live Stripe secrets and livemode events are rejected.
"""

from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from modules import stripe_billing, stripe_webhook


SERVICE_NAME = "stripe-webhook"
EXPECTED_PUBLIC_HOST = "https://fantasygm-lab-stripe-webhook.onrender.com"

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
        "mode": "test_only",
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
    secret = str(stripe_config.secret_key or "")
    if secret.startswith("sk_live_"):
        issues.append("live_stripe_secret_rejected")
    elif not secret.startswith("sk_test_"):
        issues.append("stripe_test_secret_missing")
    if not stripe_config.webhook_configured:
        issues.append("stripe_webhook_secret_missing")
    if not supabase_config.configured:
        issues.append("supabase_service_role_missing")
    if issues:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "mode": "test_only", "issues": issues},
        )
    return JSONResponse(
        content={
            "status": "ready",
            "mode": "test",
            "service": SERVICE_NAME,
        }
    )


def _assert_test_mode_runtime(stripe_config: stripe_billing.StripeBillingConfig) -> None:
    secret = str(stripe_config.secret_key or "")
    if secret.startswith("sk_live_"):
        raise HTTPException(
            status_code=503,
            detail="Live Stripe secrets are not accepted by this test webhook service.",
        )
    if secret and not secret.startswith("sk_test_"):
        raise HTTPException(
            status_code=503,
            detail="Stripe test secret key is required for webhook processing.",
        )
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
    _assert_test_mode_runtime(stripe_config)
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
        status = 400 if "signature" in message.casefold() or "live-mode" in message.casefold() else 500
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
