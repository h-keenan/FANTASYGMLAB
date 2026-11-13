"""Weekly ingest of nflverse's official NFL injury reports (see
modules/nflverse_injury_reports.py). Backfills 2021..current on the first run
(any missing season file), then refreshes the in-progress season.

    python scripts/ingest_nflverse_injuries.py --dry-run     # fetch+validate, write nothing, no git
    python scripts/ingest_nflverse_injuries.py --no-push     # write files, no git
    python scripts/ingest_nflverse_injuries.py               # write + commit + push to main (CI)

Commit/push follows the other data workflows (built-in GITHUB_TOKEN, plain
fast-forward push to main, no new secrets). If the push loses a race with
another data job it re-syncs and retries (the fetch is idempotent).
Exits non-zero on any validation/fetch failure of a completed season, leaving
committed files untouched.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import nflverse_injury_reports as nir  # noqa: E402
from scripts.refresh_and_commit_players_db import DEFAULT_REPO_SLUG, _run_git, sync_to_latest_branch  # noqa: E402

AUTHOR_NAME = "FantasyDesk Injury History Bot"
AUTHOR_EMAIL = "injury-history-bot@users.noreply.github.com"
SUBJECT = "chore(data): nflverse weekly injury reports"
PUSH_ATTEMPTS = 3


def _sleeper_resolver():
    """GSIS -> Sleeper id through Sleeper's own dump (no third-party id file)."""

    try:
        from modules.gsis_crosswalk import GsisCrosswalk

        path = ROOT / "data" / "sleeper_players.json"
        players = json.loads(path.read_text(encoding="utf-8"))
        crosswalk = GsisCrosswalk(players if isinstance(players, dict) else {})

        def resolve(gsis: str, name: str = "", team: str = "", position: str = "") -> str | None:
            # Exact GSIS match first; else a unique (name, team, position) match
            # against the CURRENT dump (honest null when ambiguous/unknown).
            sid = crosswalk.sleeper_id_for_gsis(gsis)
            if sid:
                return sid
            _, sid, _ = crosswalk.lookup_canonical(name, team, position)
            return sid

        return resolve
    except Exception as exc:  # noqa: BLE001
        print(f"gsis crosswalk unavailable, sleeper_id left blank: {exc}", file=sys.stderr)
        return None


def run_ingest(*, dry_run: bool, fetch=nir.fetch_season_csv, current_season: int | None = None) -> tuple[list[dict], list[Path], list[str]]:
    current = current_season or nir.current_season_now()
    resolver = _sleeper_resolver()
    results, changed, errors = [], [], []
    for season in nir.seasons_to_sync(ROOT, current):
        try:
            stats = nir.sync_season(
                ROOT, season, current_season=current, fetch=fetch, sleeper_id_for_gsis=resolver, dry_run=dry_run
            )
        except nir.InjuryReportError as exc:
            errors.append(f"{season}: {exc}")
            continue
        results.append(stats)
        if stats["changed"]:
            changed.append(nir.report_path(ROOT, season))
    return results, changed, errors


def commit_and_push(paths: list[Path], push_url: str | None) -> int:
    rel = [str(p.relative_to(ROOT)) for p in paths]
    env = dict(os.environ)
    env.update(GIT_AUTHOR_NAME=AUTHOR_NAME, GIT_AUTHOR_EMAIL=AUTHOR_EMAIL,
               GIT_COMMITTER_NAME=AUTHOR_NAME, GIT_COMMITTER_EMAIL=AUTHOR_EMAIL)
    if _run_git(ROOT, ["add", *rel]).returncode != 0:
        print("git add failed", file=sys.stderr)
        return 1
    if _run_git(ROOT, ["diff", "--cached", "--quiet"]).returncode == 0:
        print("nothing staged; no commit")
        return 0
    message = f"{SUBJECT}\n\nAutomated by injury-history-ingest. {nir.ATTRIBUTION_TEXT}\nFiles: {', '.join(rel)}"
    if _run_git(ROOT, ["commit", "-m", message], env=env).returncode != 0:
        print("git commit failed", file=sys.stderr)
        return 1
    if not push_url:
        print("no GITHUB_PUSH_TOKEN; committed locally, cannot push", file=sys.stderr)
        return 1
    push = _run_git(ROOT, ["push", push_url, "HEAD:main"])
    if push.returncode != 0:
        # Never print push.stderr: it can echo the credentialed URL.
        print("git push failed (non-fast-forward or auth)", file=sys.stderr)
        return 1
    print("pushed injury report update")
    return 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="fetch and validate only; write nothing")
    parser.add_argument("--no-push", action="store_true", help="write files but do not run git")
    args = parser.parse_args(argv[1:])

    push_token = os.environ.get("GITHUB_PUSH_TOKEN", "").strip()
    repo_slug = os.environ.get("GITHUB_REPO_SLUG", DEFAULT_REPO_SLUG).strip()
    push_url = f"https://x-access-token:{push_token}@github.com/{repo_slug}.git" if push_token else None
    use_git = not (args.dry_run or args.no_push)

    code = 1
    for attempt in range(1, PUSH_ATTEMPTS + 1):
        if use_git and not sync_to_latest_branch(ROOT, "origin", "main"):
            print("could not sync checkout; aborting", file=sys.stderr)
            return 1
        results, changed, errors = run_ingest(dry_run=args.dry_run)
        print(json.dumps({"seasons": results, "errors": errors, "attribution": nir.ATTRIBUTION_TEXT}, indent=2))
        if errors:
            return 1
        if not use_git or not changed:
            return 0
        code = commit_and_push(changed, push_url)
        if code == 0:
            return 0
        print(f"push attempt {attempt}/{PUSH_ATTEMPTS} failed; re-syncing", file=sys.stderr)
    return code


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
