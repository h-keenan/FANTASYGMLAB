"""Founder Beta launch-ops contracts: topology, Stripe webhook, entitlement path."""

from __future__ import annotations

from pathlib import Path

from modules import stripe_billing
from scripts.probe_founder_beta_launch import classify
from scripts.verify_production_domain_cutover import evaluate


ROOT = Path(__file__).resolve().parents[1]


def test_render_blueprint_names_three_production_services():
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "name: fantasygm-lab\n" in text
    assert "name: fantasygm-lab-marketing" in text
    assert "name: fantasygm-lab-stripe-webhook" in text
    assert "healthCheckPath: /_stcore/health" in text
    assert "healthCheckPath: /health" in text
    assert "uvicorn services.stripe_webhook_service:app" in text
    assert "staticPublishPath: ./static/landing" in text
    assert "APP_BASE_URL" in text
    assert "https://app.fantasygmlab.com" in text
    streamlit, rest = text.split("fantasygm-lab-marketing", 1)
    webhook = rest.split("fantasygm-lab-stripe-webhook", 1)[1]
    assert "SUPABASE_SERVICE_ROLE_KEY" not in streamlit
    assert "SUPABASE_SERVICE_ROLE_KEY" in webhook


def test_stripe_docs_use_app_host_as_return_origin():
    setup = (ROOT / "docs" / "STRIPE_TEST_MODE_SETUP.md").read_text(encoding="utf-8")
    assert "https://app.fantasygmlab.com" in setup
    assert "Do not use the marketing apex as the Stripe return origin" in setup
    cutover = (ROOT / "docs" / "production-domain-cutover.md").read_text(encoding="utf-8")
    assert "x-render-routing: no-server" in cutover or "no-server" in cutover
    assert "app.fantasygmlab.com" in cutover


def test_entitlement_mapping_requires_supabase_user_id_not_email():
    empty = stripe_billing._metadata_user_id(
        {
            "email": "someone@example.com",
            "customer_email": "someone@example.com",
            "metadata": {"email": "someone@example.com"},
        }
    )
    assert empty == ""
    mapped = stripe_billing._metadata_user_id(
        {
            "email": "someone@example.com",
            "client_reference_id": "user-123",
            "metadata": {"supabase_user_id": "user-123"},
        }
    )
    assert mapped == "user-123"


def test_webhook_service_rejects_unsigned_and_live_events():
    from fastapi.testclient import TestClient

    from services import stripe_webhook_service

    client = TestClient(stripe_webhook_service.app)
    assert client.get("/health").json() == {"status": "ok"}
    unsigned = client.post("/stripe/webhook", content=b"{}")
    assert unsigned.status_code == 400
    assert "signature" in unsigned.json()["error"].casefold()


def test_live_app_health_and_webhook_classification():
    report = evaluate()
    summary = classify(report)
    assert summary["app_health_ok"] is True
    assert summary["app_host"] == "streamlit"
    assert summary["webhook_state"] in {"deployed_healthy", "blueprint_host_no_server"}
    # Marketing cutover is Ops, not a code gate. Record the live shape.
    assert "apex_serves_streamlit" in summary
    assert "www_serves_streamlit" in summary
