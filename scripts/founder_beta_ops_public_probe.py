#!/usr/bin/env python3
"""Probe public production surfaces without secrets.

Prints JSON evidence for HTTPS, health, favicon, and configured webhook liveness/readiness.
Does not create accounts, call Stripe, or read Supabase.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from modules.webhook_probe_config import webhook_probe_urls, probe_webhook
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

PRODUCTION_BASELINE_SHA = "6d379dcd38f1a87f501dafa119dc58d0f0d6134a"

TARGETS = (
    ("apex_https", "https://fantasygmlab.com/"),
    ("www_https", "https://www.fantasygmlab.com/"),
    ("stcore_health", "https://www.fantasygmlab.com/_stcore/health"),
    ("onrender_app", "https://fantasygmlab.onrender.com/"),
    ("favicon_png", "https://www.fantasygmlab.com/favicon.png"),
    ("favicon_ico", "https://www.fantasygmlab.com/favicon.ico"),

)


def _probe(name: str, url: str) -> dict:
    started = time.perf_counter()
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"User-Agent": "FantasyGM-OpsPublicProbe/1.0"},
    )
    context = ssl.create_default_context()
    try:
        with urllib.request.urlopen(request, context=context, timeout=25) as response:
            body = response.read(240)
            headers = {k.lower(): v for k, v in response.headers.items()}
            return {
                "name": name,
                "url": url,
                "ok": True,
                "status": int(response.status),
                "final_url": response.geturl(),
                "ms": round((time.perf_counter() - started) * 1000, 1),
                "body_prefix": body.decode("utf-8", "replace"),
                "render_routing": headers.get("x-render-routing"),
            }
    except Exception as exc:  # noqa: BLE001 - probe must always report
        status = getattr(exc, "code", None) if isinstance(exc, urllib.error.HTTPError) else None
        headers = {}
        body_prefix = ""
        if isinstance(exc, urllib.error.HTTPError):
            try:
                headers = {k.lower(): v for k, v in (exc.headers.items() if exc.headers else [])}
                body_prefix = exc.read(240).decode("utf-8", "replace")
            except Exception:  # noqa: BLE001
                body_prefix = ""
        return {
            "name": name,
            "url": url,
            "ok": False,
            "status": status,
            "error": f"{type(exc).__name__}: {exc}",
            "ms": round((time.perf_counter() - started) * 1000, 1),
            "body_prefix": body_prefix,
            "render_routing": headers.get("x-render-routing"),
        }


def webhook_results(environ=None):
    endpoints = webhook_probe_urls(environ)
    return [dict(name="webhook_" + kind, **(probe_webhook(endpoints[kind])
        if endpoints["status"] == "configured" else {"ok": False, "configuration": endpoints["status"]}))
        for kind in ("health", "ready")]


def main() -> int:
    report = {
        "probed_at_utc": datetime.now(timezone.utc).isoformat(),
        "expected_main_baseline": PRODUCTION_BASELINE_SHA,
        "results": [_probe(name, url) for name, url in TARGETS] + webhook_results(),
        "notes": [
            "Webhook URLs require DYNASTYGM_WEBHOOK_HEALTH_URL; health is liveness, ready is billing readiness. "
            "Historical no-server results for guessed hosts are not current deployment evidence.",
            "Build SHA must be confirmed in the app footer (Render RENDER_GIT_COMMIT).",
            "Stripe/Supabase SQL and env vars require founder dashboard access.",
        ],
    }
    print(json.dumps(report, indent=2))
    www = next(item for item in report["results"] if item["name"] == "www_https")
    health = next(item for item in report["results"] if item["name"] == "stcore_health")
    return 0 if www.get("ok") and health.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
