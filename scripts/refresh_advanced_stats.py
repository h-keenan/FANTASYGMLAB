"""Scheduled job: rebuild data/nflverse_advanced_stats_<season>.json and push it.

Reuses the commit/push plumbing of ``scripts/refresh_and_commit_players_db.py``
(same safety contract: only a genuinely successful, validated, *changed*
result is committed; anything else leaves the committed file untouched).

Failure behaviour (explicit, never silent): if nflverse is down, a download
is truncated/oversized, or the parsed result fails validation, this exits
non-zero, the committed file stays as it was, and the workflow's failure step
opens/updates a tracking issue. Readers keep serving the previous file and
report its ``as_of``/``through_week``, so users see "through week N", not a
guess.

Usage: python scripts/refresh_advanced_stats.py [season]
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from modules import nflverse_advanced_stats as adv  # noqa: E402
from scripts.refresh_and_commit_players_db import DEFAULT_REPO_SLUG, refresh_and_commit  # noqa: E402

COMMIT_AUTHOR_NAME = "FantasyDesk Advanced Stats Bot"
COMMIT_AUTHOR_EMAIL = "advanced-stats-bot@users.noreply.github.com"


def build_payload(season: int) -> dict:
    from modules import sleeper
    from modules.gsis_crosswalk import GsisCrosswalk

    players = sleeper.get_players()
    if not isinstance(players, dict) or not players:
        raise adv.AdvancedStatsError("Sleeper player dump unavailable; cannot map GSIS ids")
    stats = adv.fetch_stats_player_week(season)
    pbp = adv.fetch_pbp(season)
    pbp_players, pbp_teams = adv.aggregate_pbp(pbp)
    return adv.build_season_payload(season, stats, pbp_players, pbp_teams, GsisCrosswalk(players))


def make_runner(season: int):
    def run(output_path: Path) -> int:
        try:
            payload = build_payload(season)
        except adv.AdvancedStatsError as error:
            print(f"advanced stats fetch failed: {error}", file=sys.stderr)
            return 1
        problems = adv.validate_payload(payload)
        if problems:
            print(f"advanced stats payload rejected: {problems}", file=sys.stderr)
            return 1
        changed = adv.write_if_changed(payload, str(output_path))
        print(
            f"season {season}: {payload['meta']['players']} players, "
            f"{payload['meta']['mapped_to_sleeper']} mapped, through week {payload['through_week']}, "
            f"{'updated' if changed else 'unchanged'}"
        )
        print(json.dumps(payload["meta"]["unmapped_by_reason"]))
        return 0

    return run


def main(argv: list[str]) -> int:
    from modules import sleeper

    season = int(argv[1]) if len(argv) > 1 else int(sleeper.default_player_stats_season())
    output = ROOT / adv.DATA_PATH_TEMPLATE.format(season=season)
    push_token = os.environ.get("GITHUB_PUSH_TOKEN", "").strip()
    repo_slug = os.environ.get("GITHUB_REPO_SLUG", DEFAULT_REPO_SLUG).strip()
    push_url = f"https://x-access-token:{push_token}@github.com/{repo_slug}.git" if push_token else None
    return refresh_and_commit(
        repo_root=ROOT,
        db_path=output,
        sibling_paths=(),
        push_url=push_url,
        refresh_runner=make_runner(season),
        commit_author_name=COMMIT_AUTHOR_NAME,
        commit_author_email=COMMIT_AUTHOR_EMAIL,
        commit_message_subject="chore(data): scheduled nflverse advanced stats refresh",
        commit_message_note="Automated by the advanced-stats-refresh workflow. Source: nflverse (CC BY 4.0).",
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
