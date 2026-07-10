"""Safe Stripe test-mode end-to-end checklist.

This script does not create Checkout sessions, send webhooks, or charge cards.
It verifies local configuration status without printing secrets and prints the
manual sequence Harry should run against Render and Stripe test mode.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import stripe_billing, stripe_webhook


def main() -> int:
    stripe_config = stripe_billing.load_stripe_config()
    supabase_config = stripe_webhook.load_supabase_webhook_config()
    print("Stripe checkout configured:", stripe_config.configured)
    print("Stripe webhook configured:", stripe_config.webhook_configured)
    print("Supabase webhook update configured:", supabase_config.configured)
    print("Mode:", stripe_config.redacted.get("mode"))
    print()
    print("Manual test sequence:")
    steps = [
        "Run docs/supabase_stripe_billing.sql in Supabase.",
        "Deploy both Render services from render.yaml.",
        "Open the webhook health URL: https://<render-webhook-service-host>/health.",
        "Create Stripe test monthly and annual prices.",
        "Create a Stripe test webhook endpoint: https://<render-webhook-service-host>/stripe/webhook.",
        "Select checkout/session, subscription, and invoice events listed in docs/STRIPE_TEST_MODE_SETUP.md.",
        "Sign in to https://fantasygmlab.com as a Free account.",
        "Open Premium and create Founder Premium test checkout.",
        "Complete Stripe Checkout with a test card.",
        "Verify Stripe shows a successful webhook delivery.",
        "Verify public.profiles.entitlement is premium.",
        "Refresh FantasyGM Lab and confirm Premium unlocks.",
        "Open Manage Billing and cancel through the Stripe portal.",
        "Verify cancellation webhook delivers and entitlement returns to free.",
    ]
    for index, step in enumerate(steps, start=1):
        print(f"{index}. {step}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
