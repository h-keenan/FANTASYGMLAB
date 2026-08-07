"""Repeatable Stripe webhook service harness (no live charges).

Usage:
  python scripts/stripe_webhook_harness.py
  python scripts/stripe_webhook_harness.py --base-url http://127.0.0.1:8787

Local server (optional):
  uvicorn services.stripe_webhook_service:app --host 127.0.0.1 --port 8787

Stripe CLI (optional, after local server + Test Mode secrets):
  stripe listen --forward-to localhost:8787/stripe/webhook
  stripe trigger customer.subscription.updated
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _run_asgi_cases() -> dict:
    from fastapi.testclient import TestClient

    from modules import stripe_billing, stripe_webhook
    from services import stripe_webhook_service

    stripe_webhook.clear_processed_event_ids_for_tests()
    client = TestClient(stripe_webhook_service.app)
    results: dict[str, object] = {}

    health = client.get("/health")
    results["health"] = {
        "status_code": health.status_code,
        "body": health.json(),
    }

    missing = client.post("/stripe/webhook", content=b"{}")
    results["missing_signature"] = {
        "status_code": missing.status_code,
        "body": missing.json(),
    }

    env = {
        "STRIPE_SECRET_KEY": "sk_test_harness",
        "STRIPE_WEBHOOK_SECRET": "whsec_harness",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "service-role-harness",
    }

    class FakeWebhook:
        @staticmethod
        def construct_event(payload, signature, secret):  # noqa: ANN001
            if signature == "bad":
                raise ValueError("bad sig")
            if signature == "live":
                return {
                    "id": "evt_live",
                    "livemode": True,
                    "type": "customer.subscription.updated",
                    "data": {"object": {"status": "active", "metadata": {"supabase_user_id": "u1"}}},
                }
            if signature == "unknown":
                return {
                    "id": "evt_unknown",
                    "livemode": False,
                    "type": "radar.early_fraud_warning.created",
                    "data": {"object": {}},
                }
            return {
                "id": "evt_dup",
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
    session.patch.return_value = type(
        "R", (), {"status_code": 204, "text": "", "json": lambda self: {}}
    )()

    with (
        patch.dict(os.environ, env, clear=False),
        patch.dict(sys.modules, {"stripe": fake_stripe}),
        patch("modules.stripe_webhook.requests.patch", session.patch),
    ):
        # Invalid signature
        bad = client.post(
            "/stripe/webhook",
            content=b"{}",
            headers={"Stripe-Signature": "bad"},
        )
        results["invalid_signature"] = {
            "status_code": bad.status_code,
            "body": bad.json(),
        }

        # Live-mode rejected
        live = client.post(
            "/stripe/webhook",
            content=b"{}",
            headers={"Stripe-Signature": "live"},
        )
        results["live_mode_rejected"] = {
            "status_code": live.status_code,
            "body": live.json(),
        }

        # Unknown event → success no-op
        unknown = client.post(
            "/stripe/webhook",
            content=b"{}",
            headers={"Stripe-Signature": "unknown"},
        )
        results["unknown_event"] = {
            "status_code": unknown.status_code,
            "body": unknown.json(),
        }

        # Valid event
        ok = client.post(
            "/stripe/webhook",
            content=b"{}",
            headers={"Stripe-Signature": "ok"},
        )
        results["valid_event"] = {
            "status_code": ok.status_code,
            "body": ok.json(),
            "supabase_patch_calls": session.patch.call_count,
        }

        # Duplicate event id — idempotent skip (no second PATCH)
        dup = client.post(
            "/stripe/webhook",
            content=b"{}",
            headers={"Stripe-Signature": "ok"},
        )
        results["duplicate_event"] = {
            "status_code": dup.status_code,
            "body": dup.json(),
            "supabase_patch_calls": session.patch.call_count,
        }

        ready = client.get("/ready")
        results["ready"] = {
            "status_code": ready.status_code,
            "body": ready.json(),
        }

    # Assert contract for CI-friendly exit code
    assert results["health"]["status_code"] == 200
    assert results["health"]["body"]["status"] == "ok"
    assert results["missing_signature"]["status_code"] == 400
    assert results["invalid_signature"]["status_code"] == 400
    assert results["live_mode_rejected"]["status_code"] == 400
    assert results["unknown_event"]["status_code"] == 200
    assert results["valid_event"]["status_code"] == 200
    assert results["duplicate_event"]["status_code"] == 200
    assert results["duplicate_event"]["body"].get("skipped") is True
    assert results["valid_event"]["supabase_patch_calls"] == 1
    assert results["duplicate_event"]["supabase_patch_calls"] == 1
    return results


def _probe_remote(base_url: str) -> dict:
    import ssl
    import urllib.error
    import urllib.request

    context = ssl.create_default_context()
    out: dict[str, object] = {"base_url": base_url.rstrip("/")}

    def get(path: str) -> dict:
        url = f"{base_url.rstrip('/')}{path}"
        req = urllib.request.Request(url, method="GET", headers={"User-Agent": "FGL-WebhookHarness/1"})
        try:
            with urllib.request.urlopen(req, context=context, timeout=20) as response:
                body = response.read(400)
                return {
                    "status": int(response.status),
                    "headers": {k.lower(): v for k, v in response.headers.items()},
                    "body": body.decode("utf-8", "replace"),
                }
        except urllib.error.HTTPError as exc:
            body = exc.read(400)
            return {
                "status": int(exc.code),
                "headers": {k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])},
                "body": body.decode("utf-8", "replace") if body else "",
                "render_routing": (exc.headers or {}).get("x-render-routing"),
            }
        except Exception as exc:  # noqa: BLE001
            return {"error": f"{type(exc).__name__}: {exc}"}

    out["health"] = get("/health")
    out["root"] = get("/")
    # Unsigned POST must not 404 once the service exists.
    url = f"{base_url.rstrip('/')}/stripe/webhook"
    req = urllib.request.Request(
        url,
        data=b"{}",
        method="POST",
        headers={"User-Agent": "FGL-WebhookHarness/1", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, context=context, timeout=20) as response:
            out["webhook_unsigned"] = {
                "status": int(response.status),
                "body": response.read(400).decode("utf-8", "replace"),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(400)
        out["webhook_unsigned"] = {
            "status": int(exc.code),
            "body": body.decode("utf-8", "replace") if body else "",
            "render_routing": (exc.headers or {}).get("x-render-routing"),
        }
    except Exception as exc:  # noqa: BLE001
        out["webhook_unsigned"] = {"error": f"{type(exc).__name__}: {exc}"}
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-url",
        default="",
        help="If set, probe a remote/local HTTP server instead of in-process ASGI.",
    )
    args = parser.parse_args()
    if args.base_url:
        report = {"mode": "remote", **_probe_remote(args.base_url)}
    else:
        report = {"mode": "asgi", "cases": _run_asgi_cases()}
    print(json.dumps(report, indent=2, sort_keys=True))
    if args.base_url:
        health = report.get("health") or {}
        webhook = report.get("webhook_unsigned") or {}
        if health.get("render_routing") == "no-server":
            print(
                "ROOT_CAUSE: Render reports x-render-routing=no-server "
                "(webhook web service not deployed under this hostname).",
                file=sys.stderr,
            )
            return 2
        if health.get("status") != 200:
            return 1
        # Reachable service should reject unsigned POST with 4xx, not 404.
        if webhook.get("status") == 404:
            return 1
        if webhook.get("status") not in {400, 401, 403, 422}:
            # 5xx may mean secrets missing — still proves route exists.
            if not (isinstance(webhook.get("status"), int) and webhook["status"] >= 400):
                return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
