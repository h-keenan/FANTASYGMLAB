"""External health check for the live FantasyDesk stack (stdlib only).

Run by .github/workflows/ops-health-check.yml on a schedule and by hand:

    python scripts/ops_health_check.py            # human summary, exit 1 on failure
    python scripts/ops_health_check.py --json     # machine-readable

What it covers (each check is independent; one failure never hides another):

* public surfaces: API /health, web home, /trade-analyzer, legal pages,
  robots/sitemap, the marketing apex, the public values API
* deploy drift: the live ``build`` SHA from /health versus the newest ``main``
  commit (a release blocked for review, or a stuck autopull timer, shows here)
* TLS certificate expiry for the app and api hosts
* Supabase reachability and the billing-plans Edge Function
* data freshness: news ingest, rating snapshots, and the age of the last
  successful run of every scheduled GitHub workflow

Secrets: ``SUPABASE_URL`` / ``SUPABASE_SERVICE_ROLE_KEY`` (optional; the
Supabase checks are reported as "skipped" without them) and
``GITHUB_TOKEN`` (optional; workflow and drift checks skip without it). No
value from the environment is ever printed or included in output.

Honest limits: GitHub-hosted schedules are best effort and are often delayed
by hours, so the freshness thresholds below are deliberately wider than the
nominal cron intervals. This is a second pair of eyes, not a replacement for
an external uptime monitor with SMS/push paging.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

API_BASE = os.environ.get("OPS_API_BASE", "https://api.fantasygmlab.com")
APP_BASE = os.environ.get("OPS_APP_BASE", "https://app.fantasygmlab.com")
APEX_BASE = os.environ.get("OPS_APEX_BASE", "https://fantasygmlab.com")
USER_AGENT = "Mozilla/5.0 (compatible; FantasyDeskOpsCheck/1.0)"
TIMEOUT_SECONDS = 20

# Scheduled workflow name -> max age (hours) of its newest successful run
# before it is reported stale. Wider than the cron because GitHub throttles
# scheduled runs (observed 4-6 hours between "*/15" and "*/30" runs).
WORKFLOW_MAX_AGE_HOURS: dict[str, float] = {
    "News Ingest": 9,
    "Push Trigger Sweep": 9,
    "Injury Status Sync": 4,
    "Players DB Refresh": 14,
    "Player Rating Snapshot": 36,
    "Trade Outcome Result Sweep": 36,
}
NEWS_MAX_AGE_HOURS = 9
RATING_SNAPSHOT_MAX_AGE_HOURS = 48
PUBLIC_VALUES_MAX_AGE_HOURS = 36
TLS_MIN_DAYS = 14
DEPLOY_DRIFT_GRACE_MINUTES = 30

Result = dict[str, Any]


def result(name: str, status: str, detail: str = "") -> Result:
    """status is one of ok / fail / skip."""
    return {"name": name, "status": status, "detail": detail}


# ---------------------------------------------------------------------------
# Pure helpers (unit tested)
# ---------------------------------------------------------------------------


def parse_ts(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) == 10:  # a bare date
        text += "T00:00:00+00:00"
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def age_hours(value: Any, now: datetime) -> float | None:
    parsed = parse_ts(value)
    if parsed is None:
        return None
    return (now - parsed).total_seconds() / 3600.0


def check_freshness(name: str, value: Any, max_hours: float, now: datetime) -> Result:
    age = age_hours(value, now)
    if age is None:
        return result(name, "fail", "no timestamp available")
    if age > max_hours:
        return result(name, "fail", f"{age:.1f}h old (limit {max_hours:g}h)")
    return result(name, "ok", f"{age:.1f}h old")


def check_drift(build: str, main_sha: str, main_time: Any, now: datetime) -> Result:
    """Live build SHA vs newest main commit, with a grace window for deploys."""
    name = "deploy_drift"
    build = (build or "").strip()
    main_sha = (main_sha or "").strip()
    if not build or build == "local" or not main_sha:
        return result(name, "skip", "build or main SHA unavailable")
    if main_sha.startswith(build) or build.startswith(main_sha[: len(build)]):
        return result(name, "ok", f"live build {build[:12]} is current")
    age = age_hours(main_time, now)
    if age is not None and age * 60 < DEPLOY_DRIFT_GRACE_MINUTES:
        return result(name, "ok", f"main moved {age * 60:.0f} min ago; within deploy grace")
    return result(
        name,
        "fail",
        f"live build {build[:12]} is behind main {main_sha[:12]} "
        "(blocked release or stuck autopull: run `fgl-release status` on the box)",
    )


def failing_signature(results: list[Result]) -> str:
    names = sorted(r["name"] for r in results if r["status"] == "fail")
    return ", ".join(names)


def render_markdown(results: list[Result], now: datetime) -> str:
    lines = [f"Ops health check, {now.strftime('%Y-%m-%dT%H:%M:%SZ')}", ""]
    for r in results:
        mark = {"ok": "PASS", "fail": "FAIL", "skip": "SKIP"}[r["status"]]
        detail = f" - {r['detail']}" if r["detail"] else ""
        lines.append(f"- {mark} `{r['name']}`{detail}")
    failing = failing_signature(results)
    lines.append("")
    lines.append(f"Failing: {failing}" if failing else "Failing: none")
    return "\n".join(lines)


def cert_days_left(not_after: str, now: datetime) -> float | None:
    """not_after in ssl's 'Jun  1 12:00:00 2027 GMT' form."""
    try:
        expires = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return (expires - now).total_seconds() / 86400.0


# ---------------------------------------------------------------------------
# Network helpers
# ---------------------------------------------------------------------------


def http_get(url: str, headers: dict[str, str] | None = None) -> tuple[int, str, float]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8", "replace")
            return response.status, body, time.monotonic() - started
    except urllib.error.HTTPError as exc:
        return exc.code, "", time.monotonic() - started
    except Exception as exc:  # network, DNS, TLS, timeout
        return 0, f"{type(exc).__name__}", time.monotonic() - started


def tls_not_after(host: str) -> str | None:
    context = ssl.create_default_context()
    with socket.create_connection((host, 443), timeout=TIMEOUT_SECONDS) as sock:
        with context.wrap_socket(sock, server_hostname=host) as tls:
            cert = tls.getpeercert()
    return cert.get("notAfter") if cert else None


def json_or_none(text: str) -> Any:
    try:
        return json.loads(text)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def check_page(name: str, url: str, must_contain: str = "", get: Callable = http_get) -> Result:
    status, body, took = get(url)
    if status != 200:
        return result(name, "fail", f"HTTP {status or 'no response'} from {url}")
    if must_contain and must_contain not in body:
        return result(name, "fail", f"200 but missing expected text {must_contain!r}")
    return result(name, "ok", f"{took * 1000:.0f} ms")


def run_public_checks(now: datetime, get: Callable = http_get) -> tuple[list[Result], str]:
    out: list[Result] = []
    build = ""

    status, body, took = get(f"{API_BASE}/health")
    health = json_or_none(body) if status == 200 else None
    if isinstance(health, dict) and health.get("status") == "ok":
        build = str(health.get("build") or "")
        out.append(result("api_health", "ok", f"{took * 1000:.0f} ms, build {build[:12] or 'unknown'}"))
    else:
        out.append(result("api_health", "fail", f"HTTP {status or 'no response'} or unexpected body"))

    out.append(check_page("web_home", f"{APP_BASE}/", "FantasyDesk", get))
    out.append(check_page("web_trade_analyzer", f"{APP_BASE}/trade-analyzer", "Trade", get))
    out.append(check_page("legal_privacy", f"{APP_BASE}/legal/privacy", "Privacy", get))
    out.append(check_page("legal_terms", f"{APP_BASE}/legal/terms", "Terms", get))
    out.append(check_page("marketing_apex", f"{APEX_BASE}/", "FantasyDesk", get))

    status, body, _ = get(f"{APP_BASE}/robots.txt")
    out.append(result("robots", "ok" if status == 200 and "user-agent" in body.lower() else "fail", f"HTTP {status}"))

    status, body, _ = get(f"{APP_BASE}/sitemap.xml")
    locs = body.count("<loc>") if status == 200 else 0
    out.append(result("sitemap", "ok" if locs >= 100 else "fail", f"{locs} URLs"))

    status, body, _ = get(f"{API_BASE}/v1/public/dynasty-values?format=1qb")
    values = json_or_none(body) if status == 200 else None
    if isinstance(values, dict) and len(values.get("players") or []) >= 200:
        out.append(check_freshness("public_values_fresh", values.get("source_updated_at"), PUBLIC_VALUES_MAX_AGE_HOURS, now))
    else:
        out.append(result("public_values_fresh", "fail", f"HTTP {status} or fewer than 200 players"))

    status, body, _ = get(f"{APP_BASE}/api/public-trade-values")
    out.append(result("web_public_values_route", "ok" if status == 200 else "fail", f"HTTP {status}"))
    return out, build


def run_tls_checks(now: datetime, cert_fn: Callable[[str], str | None] = tls_not_after) -> list[Result]:
    out: list[Result] = []
    for base in (APP_BASE, API_BASE):
        host = base.split("://", 1)[-1].split("/", 1)[0]
        name = f"tls_{host}"
        try:
            days = cert_days_left(cert_fn(host) or "", now)
        except Exception as exc:
            out.append(result(name, "fail", type(exc).__name__))
            continue
        if days is None:
            out.append(result(name, "fail", "could not read certificate expiry"))
        elif days < TLS_MIN_DAYS:
            out.append(result(name, "fail", f"expires in {days:.0f} days"))
        else:
            out.append(result(name, "ok", f"{days:.0f} days left"))
    return out


def run_supabase_checks(now: datetime, get: Callable = http_get) -> list[Result]:
    url = os.environ.get("SUPABASE_URL", "").strip().rstrip("/")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
    if not url or not key:
        return [result(n, "skip", "Supabase secrets not configured") for n in ("supabase_rest", "billing_plans", "news_fresh", "rating_snapshot_fresh")]
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    out: list[Result] = []

    status, body, took = get(f"{url}/rest/v1/news_source_health?select=last_success_at&order=last_success_at.desc&limit=1", headers)
    rows = json_or_none(body) if status == 200 else None
    out.append(result("supabase_rest", "ok" if status == 200 else "fail", f"HTTP {status}, {took * 1000:.0f} ms"))

    status, body, _ = get(f"{url}/functions/v1/billing-plans")
    plans = json_or_none(body) if status == 200 else None
    plan_count = len(plans.get("plans") or []) if isinstance(plans, dict) and plans.get("ok") else 0
    out.append(result("billing_plans", "ok" if plan_count >= 2 else "fail", f"HTTP {status}, {plan_count} plans"))

    newest_news = rows[0].get("last_success_at") if isinstance(rows, list) and rows else None
    out.append(check_freshness("news_fresh", newest_news, NEWS_MAX_AGE_HOURS, now))

    status, body, _ = get(f"{url}/rest/v1/player_rating_snapshots?select=snapshot_date&order=snapshot_date.desc&limit=1", headers)
    snap = json_or_none(body) if status == 200 else None
    newest_snap = snap[0].get("snapshot_date") if isinstance(snap, list) and snap else None
    out.append(check_freshness("rating_snapshot_fresh", newest_snap, RATING_SNAPSHOT_MAX_AGE_HOURS, now))
    return out


def run_github_checks(now: datetime, build: str, get: Callable = http_get) -> list[Result]:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not token or not repo:
        names = ["deploy_drift"] + [f"workflow_{n.lower().replace(' ', '_')}" for n in WORKFLOW_MAX_AGE_HOURS]
        return [result(n, "skip", "GitHub token not configured") for n in names]
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    out: list[Result] = []

    status, body, _ = get(f"https://api.github.com/repos/{repo}/commits/main", headers)
    commit = json_or_none(body) if status == 200 else None
    if isinstance(commit, dict):
        when = ((commit.get("commit") or {}).get("committer") or {}).get("date")
        out.append(check_drift(build, str(commit.get("sha") or ""), when, now))
    else:
        out.append(result("deploy_drift", "skip", f"could not read main (HTTP {status})"))

    status, body, _ = get(
        f"https://api.github.com/repos/{repo}/actions/runs?status=success&per_page=100&exclude_pull_requests=true",
        headers,
    )
    runs = (json_or_none(body) or {}).get("workflow_runs", []) if status == 200 else []
    for workflow, max_hours in WORKFLOW_MAX_AGE_HOURS.items():
        name = f"workflow_{workflow.lower().replace(' ', '_')}"
        times = [r.get("updated_at") for r in runs if r.get("name") == workflow]
        newest = max(times) if times else None
        if newest is None:
            out.append(result(name, "fail", "no recent successful run found"))
        else:
            out.append(check_freshness(name, newest, max_hours, now))
    return out


def run_all(now: datetime | None = None) -> list[Result]:
    now = now or datetime.now(timezone.utc)
    results, build = run_public_checks(now)
    results += run_tls_checks(now)
    results += run_supabase_checks(now)
    results += run_github_checks(now, build)
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--json", action="store_true", help="print JSON instead of markdown")
    args = parser.parse_args(argv)
    now = datetime.now(timezone.utc)
    results = run_all(now)
    if args.json:
        print(json.dumps({"checked_at": now.isoformat(), "results": results, "failing": failing_signature(results)}, indent=2))
    else:
        print(render_markdown(results, now))
    return 1 if any(r["status"] == "fail" for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
