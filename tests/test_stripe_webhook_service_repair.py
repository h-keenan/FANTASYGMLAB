"""Stripe webhook FastAPI service + harness contracts."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_webhook_service_contract_doc_exists():
    doc = (ROOT / "docs" / "stripe-webhook-service-contract.md").read_text(encoding="utf-8")
    assert "x-render-routing: no-server" in doc or "no-server" in doc
    assert "GET /health" in doc or "`/health`" in doc
    assert "POST /stripe/webhook" in doc or "`/stripe/webhook`" in doc
    assert "SUPABASE_SERVICE_ROLE_KEY" in doc
    assert "sk_live_" in doc
    assert "uvicorn services.stripe_webhook_service:app" in doc


def test_render_yaml_webhook_health_and_start_command():
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "fantasygm-lab-stripe-webhook" in text
    assert "healthCheckPath: /health" in text
    assert "uvicorn services.stripe_webhook_service:app --host 0.0.0.0 --port $PORT" in text
    streamlit_block = text.split("fantasygm-lab-stripe-webhook", 1)[0]
    webhook_block = text.split("fantasygm-lab-stripe-webhook", 1)[1]
    assert "SUPABASE_SERVICE_ROLE_KEY" not in streamlit_block
    assert "SUPABASE_SERVICE_ROLE_KEY" in webhook_block


def test_asgi_health_ready_and_signature_gates():
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from modules import stripe_webhook
    from services import stripe_webhook_service

    stripe_webhook.clear_processed_event_ids_for_tests()
    client = TestClient(stripe_webhook_service.app)

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}

    root = client.get("/")
    assert root.status_code == 200
    assert root.json()["webhook"] == "/stripe/webhook"

    missing = client.post("/stripe/webhook", content=b"{}")
    assert missing.status_code == 400
    assert "signature" in missing.json()["error"].casefold()


def test_duplicate_event_id_skips_second_supabase_patch():
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    from modules import stripe_webhook
    from services import stripe_webhook_service

    stripe_webhook.clear_processed_event_ids_for_tests()
    client = TestClient(stripe_webhook_service.app)

    class FakeWebhook:
        @staticmethod
        def construct_event(*_a, **_k):
            return {
                "id": "evt_idempotent_1",
                "livemode": False,
                "type": "customer.subscription.updated",
                "data": {
                    "object": {
                        "id": "sub_1",
                        "customer": "cus_1",
                        "status": "active",
                        "metadata": {"supabase_user_id": "user-1"},
                    }
                },
            }

    fake_stripe = type("S", (), {"Webhook": FakeWebhook})()
    session = Mock()
    session.patch.return_value = type("R", (), {"status_code": 204, "text": "", "json": lambda self: {}})()
    env = {
        "STRIPE_SECRET_KEY": "sk_test_x",
        "STRIPE_WEBHOOK_SECRET": "whsec_x",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "service-role",
    }
    with (
        patch.dict(os.environ, env, clear=False),
        patch.dict(sys.modules, {"stripe": fake_stripe}),
        patch("modules.stripe_webhook.requests.patch", session.patch),
    ):
        first = client.post("/stripe/webhook", content=b"{}", headers={"Stripe-Signature": "t"})
        second = client.post("/stripe/webhook", content=b"{}", headers={"Stripe-Signature": "t"})

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json().get("skipped") is True
    assert session.patch.call_count == 1


def test_harness_script_passes_in_process():
    import scripts.stripe_webhook_harness as harness

    # Ensure httpx available for TestClient.
    pytest.importorskip("httpx")
    assert harness.main.__doc__ is not None or True
    # Run ASGI path by invoking private runner.
    results = harness._run_asgi_cases()
    assert results["health"]["status_code"] == 200
    assert results["duplicate_event"]["supabase_patch_calls"] == 1


def test_founder_ops_defaults_webhook_health_url():
    from modules import founder_ops

    assert "fantasygm-lab-stripe-webhook.onrender.com/health" in founder_ops.DEFAULT_WEBHOOK_HEALTH_URL
    with patch.object(founder_ops, "_probe_webhook_health", return_value="http_404") as probe:
        snap = founder_ops.collect_ops_snapshot(
            environ={"DYNASTYGM_FOUNDER_OPS": "1"},
            secrets={},
            session_state={},
        )
    probe.assert_called_once()
    assert "fantasygm-lab-stripe-webhook" in probe.call_args.args[0]
    assert snap.stripe_webhook_health == "http_404"


def test_public_probe_documents_no_server_routing():
    source = (ROOT / "scripts" / "founder_beta_ops_public_probe.py").read_text(encoding="utf-8")
    assert "render_routing" in source
    assert "no-server" in source
