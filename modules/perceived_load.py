"""Perceived-load / concurrency harness contracts (#231).

Bounded, safe diagnostics for how the product feels under imperfect network
and multi-session conditions. Does not hammer production by default.
"""

from __future__ import annotations

import os
from typing import Any, Mapping


PRODUCTION_OPT_IN_ENV = "DYNASTYGM_ALLOW_PRODUCTION_LOAD"
MAX_LOCAL_CONCURRENCY = 10
MAX_PRODUCTION_CONCURRENCY = 2

# Approximate browser throttle presets (Chromium DevTools-style). Not exact 4G/5G.
THROTTLE_PRESETS: dict[str, dict[str, Any]] = {
    "FAST": {
        "label": "normal broadband/Wi-Fi",
        "latency_ms": 20,
        "download_kbps": 40_000,
        "upload_kbps": 10_000,
        "cpu_slowdown": 1,
    },
    "MID": {
        "label": "moderate mobile / constrained Wi-Fi",
        "latency_ms": 150,
        "download_kbps": 1_600,
        "upload_kbps": 750,
        "cpu_slowdown": 4,
    },
    "SLOW": {
        "label": "high-latency mobile-like",
        "latency_ms": 400,
        "download_kbps": 400,
        "upload_kbps": 200,
        "cpu_slowdown": 6,
    },
}

PERCEIVED_MILESTONES = (
    "shell_visible",
    "loading_dismissed",
    "first_useful",
    "game_plan_ready",
    "interactive_stable",
)

TIMELINE_SECONDS = (0, 1, 2, 3, 5, 8, 12)


def production_load_allowed(*, environ: Mapping[str, str] | None = None) -> bool:
    env = environ if environ is not None else os.environ
    return str(env.get(PRODUCTION_OPT_IN_ENV) or "").strip() in {"1", "true", "TRUE", "yes"}


def bounded_concurrency(requested: int, *, production: bool = False) -> int:
    """Clamp concurrency; production requires explicit opt-in and stays tiny."""

    n = max(1, int(requested))
    if production:
        if not production_load_allowed():
            raise PermissionError(
                f"Production load probes require {PRODUCTION_OPT_IN_ENV}=1"
            )
        return min(n, MAX_PRODUCTION_CONCURRENCY)
    return min(n, MAX_LOCAL_CONCURRENCY)


def throttle_preset(name: str) -> dict[str, Any]:
    key = str(name or "").strip().upper()
    if key not in THROTTLE_PRESETS:
        raise KeyError(f"Unknown throttle preset: {name}")
    return dict(THROTTLE_PRESETS[key])


def sanitize_load_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Drop secrets / PII-looking fields from load reports."""

    banned = {
        "email",
        "password",
        "token",
        "access_token",
        "refresh_token",
        "authorization",
        "cookie",
        "username",
        "league_name",
        "player_name",
    }
    out: dict[str, Any] = {}
    for key, value in row.items():
        k = str(key).casefold()
        if k in banned or any(part in k for part in ("secret", "token", "password")):
            continue
        if isinstance(value, str) and "@" in value:
            continue
        out[str(key)[:64]] = value
    return out


def summarize_failure_rate(*, successes: int, failures: int) -> dict[str, Any]:
    total = max(0, int(successes)) + max(0, int(failures))
    rate = (float(failures) / float(total)) if total else 0.0
    return {
        "successes": int(successes),
        "failures": int(failures),
        "total": total,
        "failure_rate": round(rate, 4),
    }


def stampede_report(
    *,
    signature: str,
    build_count: int,
    concurrent_sessions: int,
) -> dict[str, Any]:
    """Detect same-signature redundant builds under concurrency."""

    builds = max(0, int(build_count))
    sessions = max(1, int(concurrent_sessions))
    redundant = max(0, builds - 1)
    return {
        "signature_prefix": str(signature or "")[:8],
        "build_count": builds,
        "concurrent_sessions": sessions,
        "redundant_builds": redundant,
        "stampede": builds > 1 and sessions > 1,
    }


def perceived_timeline_schema() -> dict[str, Any]:
    return {
        "milestones": list(PERCEIVED_MILESTONES),
        "sample_seconds": list(TIMELINE_SECONDS),
        "throttle_presets": sorted(THROTTLE_PRESETS),
        "max_local_concurrency": MAX_LOCAL_CONCURRENCY,
        "max_production_concurrency": MAX_PRODUCTION_CONCURRENCY,
        "production_opt_in_env": PRODUCTION_OPT_IN_ENV,
    }
