"""Probe the four #271 P0 launch blockers (read-only; no secrets).

Exit 0 only when all P0 probes are green. Control-plane gaps print exact
founder actions — this script cannot attach DNS or create Render services.

Usage:
  python scripts/verify_p0_launch_blockers.py
  python scripts/verify_p0_launch_blockers.py --json-out /tmp/p0.json
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_production_domain_cutover import evaluate as evaluate_domain  # noqa: E402


WEBHOOK_BASE = "https://fantasygm-lab-stripe-webhook.onrender.com"
APP_HOST = "app.fantasygmlab.com"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dns_cname(host: str) -> dict[str, Any]:
    try:
        # Prefer system resolver answers; CNAME may be absent when apex A-only.
        answers = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addrs = sorted({item[4][0] for item in answers})
        return {"ok": True, "addresses": addrs}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _http(url: str, *, method: str = "GET", data: bytes | None = None) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        method=method,
        data=data,
        headers={"User-Agent": "FantasyGMLab-P0Blockers/1.0", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            body = response.read(512)
            return {
                "ok": True,
                "status": int(response.status),
                "x_render_routing": response.headers.get("x-render-routing", ""),
                "sample": body[:160].decode("utf-8", errors="replace"),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(512) if exc.fp else b""
        return {
            "ok": False,
            "status": int(exc.code),
            "x_render_routing": (exc.headers.get("x-render-routing", "") if exc.headers else ""),
            "sample": body[:160].decode("utf-8", errors="replace"),
            "error": str(exc),
        }
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def evaluate() -> dict[str, Any]:
    domain = evaluate_domain()
    health = _http(f"{WEBHOOK_BASE}/health")
    root = _http(f"{WEBHOOK_BASE}/")
    unsigned = _http(
        f"{WEBHOOK_BASE}/stripe/webhook",
        method="POST",
        data=b"{}",
    )
    dns_app = _dns_cname(APP_HOST)

    webhook_live = bool(
        health.get("ok")
        and health.get("status") == 200
        and "ok" in (health.get("sample") or "").casefold()
    )
    # After deploy: unsigned POST must be 4xx (signature), never 404 / no-server.
    webhook_rejects_unsigned = bool(
        (not unsigned.get("ok"))
        and int(unsigned.get("status") or 0) in {400, 401, 403}
        and str(unsigned.get("x_render_routing") or "").casefold() != "no-server"
    )
    webhook_no_server = str(health.get("x_render_routing") or "").casefold() == "no-server"

    app_ready = bool(domain["gates"].get("app_serves_streamlit") and domain["gates"].get("app_health_ok"))
    marketing_ready = bool(
        domain["gates"].get("static_is_marketing_html")
        and domain["gates"].get("static_is_not_streamlit")
    )

    blockers = {
        "P0_app_subdomain": {
            "cleared": app_ready,
            "root_cause": (
                "PASS"
                if app_ready
                else "DNS CNAME still points at Porkbun parking (pixie 404); "
                "Render custom domain app.fantasygmlab.com not attached to fantasygm-lab"
            ),
            "owner": "founder_control_plane",
            "evidence": {
                "dns": dns_app,
                "app_probe": domain["probes"]["app"],
                "app_health": domain["probes"]["app_health"],
                "porkbun_parking": domain["gates"].get("app_is_porkbun_parking"),
            },
            "founder_action": [
                "Render → fantasygm-lab → Custom Domains → Add app.fantasygmlab.com",
                "Copy Render CNAME target for app.",
                "Porkbun DNS: replace app CNAME uixie.porkbun.com with Render target",
                "Wait for TLS; verify https://app.fantasygmlab.com/_stcore/health → ok",
            ],
        },
        "P0_apex_www_cutover": {
            "cleared": marketing_ready,
            "root_cause": (
                "PASS"
                if marketing_ready
                else "apex/www still serve Streamlit; fantasygm-lab-marketing static "
                "service not live (onrender host 404 / domains still on Streamlit)"
            ),
            "owner": "founder_control_plane",
            "evidence": {
                "static": domain["probes"]["static"],
                "www": domain["probes"]["www"],
                "gates": {
                    k: domain["gates"].get(k)
                    for k in (
                        "static_is_marketing_html",
                        "static_is_not_streamlit",
                        "www_canonical_or_static",
                    )
                },
            },
            "founder_action": [
                "Render Blueprint Apply → create fantasygm-lab-marketing static site",
                "Attach custom domains fantasygmlab.com + www to marketing service",
                "Remove apex/www custom domains from fantasygm-lab (Streamlit)",
                "Confirm CTA on landing points to https://app.fantasygmlab.com/",
            ],
        },
        "P0_stripe_webhook": {
            "cleared": webhook_live and webhook_rejects_unsigned,
            "root_cause": (
                "PASS"
                if webhook_live and webhook_rejects_unsigned
                else (
                    "x-render-routing: no-server — Blueprint webhook web service never "
                    "created under fantasygm-lab-stripe-webhook (code routes OK locally)"
                    if webhook_no_server
                    else "Webhook host responds but health/signature gates failed"
                )
            ),
            "classification": "B_wrong_or_missing_Render_service"
            if webhook_no_server
            else ("OK" if webhook_live else "unknown"),
            "owner": "founder_control_plane",
            "evidence": {"health": health, "root": root, "unsigned_post": unsigned},
            "founder_action": [
                "Render Blueprint Apply → create fantasygm-lab-stripe-webhook",
                "Or New Web Service: uvicorn services.stripe_webhook_service:app "
                "--host 0.0.0.0 --port $PORT; healthCheckPath=/health",
                "Set env: STRIPE_SECRET_KEY=sk_test_…, STRIPE_WEBHOOK_SECRET=whsec_…, "
                "SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY (webhook only)",
                "Stripe Dashboard Test Mode webhook → "
                "https://fantasygm-lab-stripe-webhook.onrender.com/stripe/webhook",
                "Re-run: python scripts/stripe_webhook_harness.py --base-url "
                "https://fantasygm-lab-stripe-webhook.onrender.com",
            ],
        },
        "P0_authenticated_restore": {
            "cleared": False,
            "root_cause": (
                "Agent has no founder/test credentials; Supabase MCP unauthenticated; "
                "canonical auth host app. still 404 — auth restore cannot be production-proven"
            ),
            "owner": "founder_manual",
            "evidence": {"app_ready": app_ready},
            "founder_action": [
                "Complete app. cutover first",
                "Set Supabase Site URL + redirect allowlist to https://app.fantasygmlab.com",
                "Run docs/iphone-safari-manual-gate.md auth section on desktop + Safari",
                "Complete authenticated Free matrix in docs/p0-launch-blocker-clearance.md",
            ],
        },
    }

    remaining = [name for name, row in blockers.items() if not row["cleared"]]
    return {
        "measured_at": _now(),
        "verdict": "P0 CLEARED" if not remaining else "P0 NOT CLEARED",
        "remaining_p0": remaining,
        "domain_verdict": domain.get("verdict"),
        "blockers": blockers,
        "analytics_note": {
            "classification": "B_ephemeral_single_host_beta_debt",
            "storage": "data/launch_analytics.jsonl on serving Streamlit instance",
            "readback": "Founder Ops on same process/filesystem",
            "limitation": (
                "Host-local JSONL; lost on disk wipe/redeploy; broken across multiple "
                "instances. Acceptable Founder Beta debt if single always-on instance "
                "and founder confirms DYNASTYGM_LAUNCH_ANALYTICS=1 + Founder Ops cards."
            ),
        },
        "billing_note": {
            "mode": "disabled_or_test_only",
            "launch_vs_paid": (
                "App launch can proceed with billing disabled; paid Premium requires "
                "webhook live + Test Mode secrets before enabling checkout."
            ),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()
    report = evaluate()
    text = json.dumps(report, indent=2)
    print(text)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            handle.write(text)
    return 0 if report["verdict"] == "P0 CLEARED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
