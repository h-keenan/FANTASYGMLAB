"""Verify FantasyGM Lab production domain cutover gates.

Checks DNS/HTTP shape for:
  fantasygmlab.com → static landing
  app.fantasygmlab.com → Streamlit
  health on app host

Exit codes:
  0 = all required gates pass
  1 = one or more required gates fail (NOT READY)
  2 = usage / unexpected error
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


STATIC_URL = "https://fantasygmlab.com/"
WWW_URL = "https://www.fantasygmlab.com/"
APP_URL = "https://app.fantasygmlab.com/"
APP_HEALTH = "https://app.fantasygmlab.com/_stcore/health"
ONRENDER_HEALTH = "https://fantasygmlab.onrender.com/_stcore/health"
WEBHOOK_HEALTH = "https://fantasygm-lab-stripe-webhook.onrender.com/health"
STATIC_ROBOTS = "https://fantasygmlab.com/robots.txt"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _header(headers: Any, name: str) -> str:
    if not headers:
        return ""
    try:
        return str(headers.get(name) or headers.get(name.lower()) or "")
    except Exception:  # noqa: BLE001
        return ""


def _get(url: str, *, timeout: float = 30.0, method: str = "GET") -> dict[str, Any]:
    started = time.perf_counter()
    request = urllib.request.Request(
        url,
        method=method,
        headers={"User-Agent": "FantasyGMLab-DomainCutover/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(4096)
            return {
                "ok": True,
                "status": int(response.status),
                "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
                "content_type": response.headers.get("Content-Type", ""),
                "location": response.headers.get("Location", ""),
                "x_render_routing": _header(response.headers, "x-render-routing"),
                "sample": body[:120].decode("utf-8", errors="replace"),
                "bytes_read": len(body),
            }
    except urllib.error.HTTPError as exc:
        body = exc.read(4096) if exc.fp else b""
        return {
            "ok": False,
            "status": int(exc.code),
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "content_type": exc.headers.get("Content-Type", "") if exc.headers else "",
            "location": exc.headers.get("Location", "") if exc.headers else "",
            "x_render_routing": _header(exc.headers, "x-render-routing"),
            "sample": body[:120].decode("utf-8", errors="replace"),
            "error": str(exc),
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
            "error": f"{type(exc).__name__}: {exc}",
        }


def _dns(host: str) -> dict[str, Any]:
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
        addrs = sorted({item[4][0] for item in infos})
        return {"ok": True, "addresses": addrs}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def _looks_like_streamlit(sample: str, content_type: str) -> bool:
    lowered = (sample or "").casefold()
    return "streamlit" in lowered


def _looks_like_static_landing(sample: str) -> bool:
    lowered = (sample or "").casefold()
    return "data-fgl-static-landing" in lowered or (
        "fantasygm lab" in lowered
        and "founder beta" in lowered
        and "streamlit" not in lowered
    )


def evaluate() -> dict[str, Any]:
    static = _get(STATIC_URL)
    www = _get(WWW_URL)
    app = _get(APP_URL)
    health = _get(APP_HEALTH)
    onrender_health = _get(ONRENDER_HEALTH)
    webhook_health = _get(WEBHOOK_HEALTH)
    robots = _get(STATIC_ROBOTS)

    gates = {
        "static_is_marketing_html": bool(
            static.get("ok") and _looks_like_static_landing(static.get("sample", ""))
        ),
        "static_is_not_streamlit": bool(
            static.get("ok") and not _looks_like_streamlit(static.get("sample", ""), static.get("content_type", ""))
        ),
        "app_serves_streamlit": bool(
            app.get("ok") and _looks_like_streamlit(app.get("sample", ""), app.get("content_type", ""))
        ),
        "app_health_ok": bool(
            health.get("ok") and health.get("status") == 200 and "ok" in (health.get("sample") or "")
        ),
        "app_health_warm_ms": float(health.get("elapsed_ms") or 0) < 2000,
        "dns_apex": _dns("fantasygmlab.com").get("ok", False),
        "dns_app": _dns("app.fantasygmlab.com").get("ok", False),
        "onrender_still_reachable": bool(
            onrender_health.get("ok") and onrender_health.get("status") == 200
        ),
        # Informational / Ops — not required for topology READY (webhook is separate service).
        "webhook_health_ok": bool(
            webhook_health.get("ok")
            and webhook_health.get("status") == 200
            and "ok" in (webhook_health.get("sample") or "").casefold()
        ),
        # Render edge with no attached web service (Blueprint never applied).
        "webhook_no_server": (
            str(webhook_health.get("x_render_routing") or "").casefold() == "no-server"
        ),
        "static_robots_allows_crawl": bool(
            robots.get("ok")
            and "disallow: /" not in (robots.get("sample") or "").casefold()
            and "allow: /" in (robots.get("sample") or "").casefold()
        ),
        "app_is_porkbun_parking": bool(
            (not app.get("ok"))
            and int(app.get("status") or 0) == 404
            and "pixie" in (app.get("sample") or "").casefold()
        ),
        "www_serves_streamlit": bool(
            _looks_like_streamlit(www.get("sample", ""), www.get("content_type", ""))
        ),
        "apex_serves_streamlit": bool(
            _looks_like_streamlit(static.get("sample", ""), static.get("content_type", ""))
        ),
    }

    # www may redirect to apex; either static body or redirect Location is acceptable once cut over.
    www_ok = False
    if www.get("ok") and _looks_like_static_landing(www.get("sample", "")):
        www_ok = True
    if (www.get("status") in {301, 302, 307, 308}) and "fantasygmlab.com" in (
        www.get("location") or ""
    ):
        www_ok = True
    gates["www_canonical_or_static"] = www_ok

    required = [
        "static_is_marketing_html",
        "static_is_not_streamlit",
        "app_serves_streamlit",
        "app_health_ok",
        "app_health_warm_ms",
        "dns_apex",
        "dns_app",
    ]
    failed = [name for name in required if not gates[name]]
    return {
        "measured_at": _now(),
        "verdict": "PRODUCTION TOPOLOGY READY" if not failed else "NOT READY",
        "failed_gates": failed,
        "gates": gates,
        "probes": {
            "static": static,
            "www": www,
            "app": app,
            "app_health": health,
            "onrender_health": onrender_health,
            "webhook_health": webhook_health,
            "static_robots": robots,
            "dns": {
                "apex": _dns("fantasygmlab.com"),
                "www": _dns("www.fantasygmlab.com"),
                "app": _dns("app.fantasygmlab.com"),
            },
        },
        "manual_ops_still_required": [
            "Render always-on plan for fantasygm-lab",
            "Attach app.fantasygmlab.com to Streamlit; move apex/www to static marketing",
            "Supabase Site URL + redirect allowlist → https://app.fantasygmlab.com",
            "Stripe test return URLs → app host; deploy webhook /health",
            "Idle 20+ minute wake test",
            "iPhone Safari manual smoke",
            "Complete docs/production-launch-checklist.md GO gate",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-out", type=str, default="")
    args = parser.parse_args()
    report = evaluate()
    text = json.dumps(report, indent=2)
    print(text)
    if args.json_out:
        with open(args.json_out, "w", encoding="utf-8") as handle:
            handle.write(text)
    return 0 if report["verdict"] == "PRODUCTION TOPOLOGY READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
