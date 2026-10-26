#!/usr/bin/env python3
"""Rank Google Search Console queries into SEO "quick win" opportunities.

Reads the Search Analytics API with the operator's gcloud Application Default
Credentials (never prints or stores the token) and writes a ranked list of
queries sitting at average position 5-30 with real impressions, grouped with
the page that currently earns them.

    python scripts/seo_opportunities.py [--site https://app.fantasygmlab.com/]
                                        [--days 28] [--min-impressions 5]
                                        [--out-dir artifacts/seo]

Prerequisites: `gcloud auth application-default login` with an account that
has access to the Search Console property. Requests carry
`x-goog-user-project: fantasygmlab-prod`.

New properties legitimately have no data yet: the script then writes an empty
report that says so and exits 0 (it never invents rows).

Output is written under artifacts/seo/ by default (gitignored); it is an
input to the human-reviewed publishing loop in docs/seo-publishing-policy.md,
not something that publishes anything.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import requests

API = "https://searchconsole.googleapis.com/webmasters/v3"
QUOTA_PROJECT = "fantasygmlab-prod"
DEFAULT_SITES = ("https://app.fantasygmlab.com/", "sc-domain:fantasygmlab.com", "sc-domain:fantasydesk.app")
MIN_POSITION = 5.0
MAX_POSITION = 30.0
ROW_LIMIT = 5000
TIMEOUT = 30


def access_token() -> str:
    """gcloud ADC token. Never logged."""

    try:
        out = subprocess.run(
            ["gcloud", "auth", "application-default", "print-access-token"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SystemExit(
            "Could not get a gcloud ADC token. Run `gcloud auth application-default login` first "
            f"({type(exc).__name__})."
        )
    token = out.stdout.strip()
    if not token:
        raise SystemExit("gcloud returned an empty ADC token.")
    return token


def headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "x-goog-user-project": QUOTA_PROJECT, "Content-Type": "application/json"}


def list_sites(token: str) -> dict[str, str]:
    """{siteUrl: permissionLevel} for the properties the account can read."""

    response = requests.get(f"{API}/sites", headers=headers(token), timeout=TIMEOUT)
    response.raise_for_status()
    return {entry["siteUrl"]: entry.get("permissionLevel", "") for entry in response.json().get("siteEntry", [])}


def pick_site(requested: str | None, available: dict[str, str]) -> str:
    usable = {url for url, level in available.items() if level and level != "siteUnverifiedUser"}
    if requested:
        if requested not in usable:
            raise SystemExit(f"No verified access to {requested}. Available: {sorted(usable) or 'none'}")
        return requested
    for candidate in DEFAULT_SITES:
        if candidate in usable:
            return candidate
    raise SystemExit(f"None of the expected properties are accessible. Available: {sorted(usable) or 'none'}")


def query_rows(token: str, site: str, start: date, end: date, dimensions: list[str]) -> list[dict[str, Any]]:
    body = {
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "dimensions": dimensions,
        "rowLimit": ROW_LIMIT,
        "dataState": "final",
    }
    response = requests.post(
        f"{API}/sites/{quote(site, safe='')}/searchAnalytics/query", headers=headers(token), json=body, timeout=TIMEOUT
    )
    response.raise_for_status()
    return response.json().get("rows", [])


def rank_opportunities(
    query_page_rows: list[dict[str, Any]], *, min_impressions: int = 5, limit: int = 200
) -> list[dict[str, Any]]:
    """Pure ranking. Rows are Search Analytics rows with keys [query, page].

    Queries are aggregated across pages (impression-weighted position); the
    page earning the most impressions is reported as the target. Only queries
    averaging position 5-30 with at least `min_impressions` qualify. Score
    favours impressions and being close to page one:
        score = impressions * (1 - (position - 5) / 30)
    """

    agg: dict[str, dict[str, Any]] = {}
    for row in query_page_rows:
        keys = row.get("keys") or []
        if len(keys) < 2:
            continue
        query, page = str(keys[0]).strip(), str(keys[1])
        impressions = float(row.get("impressions") or 0)
        if not query or impressions <= 0:
            continue
        entry = agg.setdefault(query, {"impressions": 0.0, "clicks": 0.0, "pos_weighted": 0.0, "pages": {}})
        entry["impressions"] += impressions
        entry["clicks"] += float(row.get("clicks") or 0)
        entry["pos_weighted"] += float(row.get("position") or 0) * impressions
        entry["pages"][page] = entry["pages"].get(page, 0.0) + impressions

    out: list[dict[str, Any]] = []
    for query, entry in agg.items():
        impressions = entry["impressions"]
        if impressions < min_impressions:
            continue
        position = entry["pos_weighted"] / impressions
        if not MIN_POSITION <= position <= MAX_POSITION:
            continue
        top_page = max(entry["pages"].items(), key=lambda item: item[1])[0]
        out.append(
            {
                "query": query,
                "impressions": int(impressions),
                "clicks": int(entry["clicks"]),
                "ctr": round(entry["clicks"] / impressions, 4),
                "avg_position": round(position, 1),
                "top_page": top_page,
                "score": round(impressions * (1 - (position - MIN_POSITION) / 30), 2),
            }
        )
    out.sort(key=lambda item: (-item["score"], item["query"]))
    return out[:limit]


def render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# SEO opportunities",
        "",
        f"Site: `{report['site']}`  |  window: {report['start']} to {report['end']}  |  generated: {report['generated_at']}",
        "",
    ]
    if report["total_rows"] == 0:
        lines += ["No Search Console data yet for this window (new property or nothing indexed). Nothing to rank.", ""]
        return "\n".join(lines)
    lines += [
        f"{report['total_rows']} query/page rows read; {len(report['opportunities'])} queries at avg position "
        f"{MIN_POSITION:g}-{MAX_POSITION:g} with at least {report['min_impressions']} impressions.",
        "",
    ]
    if report["opportunities"]:
        lines += ["| Query | Impr. | Clicks | Avg pos | Page | Score |", "|---|---:|---:|---:|---|---:|"]
        for item in report["opportunities"]:
            lines.append(
                f"| {item['query']} | {item['impressions']} | {item['clicks']} | {item['avg_position']} | "
                f"{item['top_page']} | {item['score']} |"
            )
    else:
        lines.append("No queries currently qualify as quick wins.")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--site", help="Search Console property (default: first accessible of the known properties)")
    parser.add_argument("--days", type=int, default=28)
    parser.add_argument("--min-impressions", type=int, default=5)
    parser.add_argument("--out-dir", default="artifacts/seo")
    args = parser.parse_args(argv)

    token = access_token()
    site = pick_site(args.site, list_sites(token))
    # Search Console data lags ~2 days.
    end = date.today() - timedelta(days=2)
    start = end - timedelta(days=max(1, args.days) - 1)
    rows = query_rows(token, site, start, end, ["query", "page"])

    report = {
        "site": site,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "min_impressions": args.min_impressions,
        "total_rows": len(rows),
        "opportunities": rank_opportunities(rows, min_impressions=args.min_impressions),
    }
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "seo_opportunities.json").write_text(json.dumps(report, indent=2) + "\n")
    (out_dir / "seo_opportunities.md").write_text(render_markdown(report))
    print(f"{site}: {report['total_rows']} rows, {len(report['opportunities'])} opportunities -> {out_dir}/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
