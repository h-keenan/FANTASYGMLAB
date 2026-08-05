#!/usr/bin/env python3
"""Probe public production surfaces without secrets.

Prints JSON evidence for HTTPS, health, favicon, and known webhook host guesses.
Does not create accounts, call Stripe, or read Supabase.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

PRODUCTION_BASELINE_SHA = "3065e315c7855f2546cc700e0b70d91c9247e9a3"

TARGETS = (
    ("apex_https", "https://fantasygmlab.com/"),
    ("www_https", "https://www.fantasygmlab.com/"),
    ("stcore_health", "https://www.fantasygmlab.com/_stcore/health"),
    ("onrender_app", "https://fantasygmlab.onrender.com/"),
    ("favicon_png", "https://www.fantasygmlab.com/favicon.png"),
    ("favicon_ico", "https://www.fantasygmlab.com/favicon.ico"),
    (
        "webhook_guess_health",
        "https://fantasygm-lab-stripe-webhook.onrender.com/health",
    ),
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
            return {
                "name": name,
                "url": url,
                "ok": True,
                "status": int(response.status),
                "final_url": response.geturl(),
                "ms": round((time.perf_counter() - started) * 1000, 1),
                "body_prefix": body.decode("utf-8", "replace"),
            }
    except Exception as exc:  # noqa: BLE001 - probe must always report
        status = getattr(exc, "code", None) if isinstance(exc, urllib.error.HTTPError) else None
        return {
            "name": name,
            "url": url,
            "ok": False,
            "status": status,
            "error": f"{type(exc).__name__}: {exc}",
            "ms": round((time.perf_counter() - started) * 1000, 1),
        }


def main() -> int:
    report = {
        "probed_at_utc": datetime.now(timezone.utc).isoformat(),
        "expected_main_baseline": PRODUCTION_BASELINE_SHA,
        "results": [_probe(name, url) for name, url in TARGETS],
        "notes": [
            "Webhook host is a guess from render.yaml service name; 404 means undeployed or custom hostname.",
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
