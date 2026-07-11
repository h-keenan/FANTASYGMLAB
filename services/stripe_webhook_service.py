"""Backend-only Stripe webhook service for test-mode Founder Premium."""

from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from modules import stripe_billing, stripe_webhook


app = FastAPI(title="FantasyGM Lab Stripe Webhook", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "stripe-webhook"}


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
    if not stripe_config.webhook_configured:
        raise HTTPException(status_code=500, detail="Stripe webhook secret is not configured.")
    if not supabase_config.configured:
        raise HTTPException(status_code=500, detail="Supabase service-role update is not configured.")

    result = stripe_webhook.process_verified_stripe_webhook(
        payload=payload,
        signature=stripe_signature,
        stripe_config=stripe_config,
        supabase_config=supabase_config,
    )
    if not result.get("ok"):
        message = str(result.get("error") or "Stripe webhook processing failed.")
        status = 400 if "signature" in message.casefold() or "user id" in message.casefold() else 500
        raise HTTPException(status_code=status, detail=message)

    action = result.get("action") or {}
    return JSONResponse(
        {
            "received": True,
            "event_id": result.get("event_id", ""),
            "entitlement": action.get("entitlement", ""),
            "subscription_status": action.get("stripe_subscription_status", ""),
        }
    )
