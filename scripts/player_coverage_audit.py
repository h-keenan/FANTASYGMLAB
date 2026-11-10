#!/usr/bin/env python3
"""Player coverage audit: which real NFL players can a user NOT find?

Compares every real NFL player in the Sleeper universe (active/IR/practice
squad/rookie, with a team, fantasy or IDP position) against what each
player-facing lookup path actually returns, and prints the missing players
grouped by the reason they are excluded.

Lookup paths modelled (all share one backend pool):

  players_db      row present in data/players.db (the valuation table)
  eligibility     passes player_eligibility.filter_current_fantasy_players
  full_pool       present in the full league-valued pool (/rankings pool,
                  /rankings/search, /players/{id}/rank) -- the "can be found"
                  bar every surface should meet
  top_n_window    inside the /rankings?limit=N window. Every client search box
                  (Players, Compare, Trade Analyzer, GM orb, Veto) used to
                  filter ONLY this window client-side, so anyone below rank N
                  was unsearchable. Reported as "beyond_rankings_window".

IDP positions are not in players.db by design (served by /idp/values for
leagues that start defenders); they are counted separately, not as missing.

Read-only: pass COPIES of the data. The script refuses to run against the
repo's live data/players.db or data/sleeper_players.json.

  python scripts/player_coverage_audit.py --db /tmp/copy/players.db \
      --sleeper /tmp/copy/sleeper_players.json [--window 300] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OFFENSE_POSITIONS = {"QB", "RB", "WR", "TE", "K", "FB", "DEF"}
IDP_POSITIONS = {"DL", "DE", "DT", "LB", "OLB", "ILB", "MLB", "DB", "CB", "S", "SS", "FS"}
# Sleeper statuses for a real, currently-rostered player (incl. IR/PUP/PS).
CURRENT_SLEEPER_STATUSES = {
    "active", "injured reserve", "practice squad", "pup", "nfi",
    "physically unable to perform", "non football injury", "reserve/injured",
    "suspended", "questionable", "doubtful", "out", "ir",
}
DEFAULT_WINDOW = 300


def _refuse_live_paths(*paths: Path) -> None:
    live = {(REPO_ROOT / "data" / "players.db").resolve(), (REPO_ROOT / "data" / "sleeper_players.json").resolve()}
    for path in paths:
        if path.resolve() in live:
            raise SystemExit(f"Refusing to read live {path}: pass a copy (the loaders can write back).")


def sleeper_universe(sleeper: dict[str, Any]) -> list[dict[str, Any]]:
    """Real NFL players a user would expect to find: a team plus a current status."""

    out: list[dict[str, Any]] = []
    for pid, p in sleeper.items():
        if not isinstance(p, dict) or str(p.get("sport") or "nfl").lower() != "nfl":
            continue
        team = str(p.get("team") or "").strip()
        if not team:
            continue
        status = str(p.get("status") or "").strip().lower()
        injury = str(p.get("injury_status") or "").strip().lower()
        if status not in CURRENT_SLEEPER_STATUSES and injury not in {"ir", "pup", "nfi", "out"}:
            continue
        positions = {str(x).upper() for x in (p.get("fantasy_positions") or []) if x}
        if p.get("position"):
            positions.add(str(p["position"]).upper())
        if not positions & (OFFENSE_POSITIONS | IDP_POSITIONS):
            continue
        name = p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
        if not name:
            continue
        out.append(
            {
                "player_id": str(p.get("player_id") or pid),
                "name": name,
                "position": str(p.get("position") or sorted(positions)[0]).upper(),
                "positions": positions,
                "team": team,
                "status": p.get("status"),
                "years_exp": p.get("years_exp"),
                "raw": p,
                "is_idp": not (positions & OFFENSE_POSITIONS),
            }
        )
    return out


def build_pools(db_copy: str, window: int) -> dict[str, Any]:
    from modules import canonical_player_ranking, league_value_settings, player_eligibility, rankings

    raw = rankings.load_players(db_copy)
    if raw is None or raw.empty:
        raise SystemExit("players.db copy produced an empty frame.")
    raw_ids = {str(x) for x in raw["player_id"]}
    annotated = player_eligibility.annotate_player_eligibility(raw)
    reasons = {
        str(r.player_id): str(getattr(r, "player_eligibility_reason", ""))
        for r in annotated.itertuples()
    }
    eligible = player_eligibility.filter_current_fantasy_players(annotated, surface="coverage_audit")
    settings = dict(league_value_settings.DEFAULT_LEAGUE_VALUE_SETTINGS)
    valued = league_value_settings.apply_valuation_lens(eligible, "Dynasty", settings)
    ctx = canonical_player_ranking.resolve_scoring_rank_context(settings)
    ranked = canonical_player_ranking.attach_canonical_ranks(
        valued, scoring_format=ctx.scoring_format, score_field="dynasty_score", context=ctx
    )
    ranked = ranked.sort_values("dynasty_score", ascending=False)
    ordered_ids = [str(x) for x in ranked["player_id"]]
    return {
        "raw_ids": raw_ids,
        "reasons": reasons,
        "eligible_ids": {str(x) for x in eligible["player_id"]},
        "full_pool_ids": set(ordered_ids),
        "window_ids": set(ordered_ids[:window]),
        "pool_rank": {pid: i + 1 for i, pid in enumerate(ordered_ids)},
    }


def classify(player: dict[str, Any], pools: dict[str, Any]) -> tuple[str, str]:
    """(path_that_drops_them, reason). Reason 'found' == fully covered."""

    pid = player["player_id"]
    if player["is_idp"]:
        return "idp_separate_surface", "idp_position_served_by_idp_values_only"
    if pid not in pools["raw_ids"]:
        # Re-run the canonical predicate on the raw Sleeper record: a failure means a
        # stale provider listing (correctly excluded); a pass means a real gap.
        from modules import player_eligibility

        verdict = player_eligibility.player_eligibility(player["raw"])
        if verdict["eligible"]:
            return "players_db", "not_in_players_db_but_eligible_GAP"
        return "players_db", "not_in_players_db_stale_provider_record:" + str(verdict["reason"])
    if pid not in pools["eligible_ids"]:
        return "eligibility", "ineligible:" + (pools["reasons"].get(pid) or "unknown")
    if pid not in pools["full_pool_ids"]:
        return "full_pool", "dropped_after_eligibility"
    if pid not in pools["window_ids"]:
        return "top_n_window", "beyond_rankings_window"
    return "found", "found"


def run_audit(sleeper: dict[str, Any], db_copy: str, window: int = DEFAULT_WINDOW) -> dict[str, Any]:
    universe = sleeper_universe(sleeper)
    pools = build_pools(db_copy, window)
    by_reason: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for player in universe:
        path, reason = classify(player, pools)
        player["rank"] = pools["pool_rank"].get(player["player_id"])
        by_reason[f"{path}|{reason}"].append(player)
    return {"universe": len(universe), "window": window, "by_reason": by_reason}


def render(result: dict[str, Any], examples: int = 12) -> str:
    lines = [f"Universe: {result['universe']} real NFL players (team + current status + supported position)"]
    lines.append(f"Rankings window used by client search boxes: top {result['window']}")
    found = len(result["by_reason"].get("found|found", []))
    lines.append(f"Found everywhere: {found}")
    lines.append("")
    for key, players in sorted(result["by_reason"].items(), key=lambda kv: -len(kv[1])):
        if key == "found|found":
            continue
        path, reason = key.split("|", 1)
        lines.append(f"[{path}] {reason}: {len(players)}")
        ranked = sorted(players, key=lambda p: (p["rank"] is None, p["rank"] or 0))
        for p in ranked[:examples]:
            rank = f" rank~{p['rank']}" if p["rank"] else ""
            lines.append(f"    {p['name']} ({p['position']}, {p['team']}, {p['status']}){rank}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", required=True, help="COPY of data/players.db")
    ap.add_argument("--sleeper", required=True, help="COPY of data/sleeper_players.json")
    ap.add_argument("--window", type=int, default=DEFAULT_WINDOW)
    ap.add_argument("--examples", type=int, default=12)
    ap.add_argument("--json", help="write full machine-readable result here")
    args = ap.parse_args(argv)
    db, sl = Path(args.db), Path(args.sleeper)
    _refuse_live_paths(db, sl)
    sleeper_payload = json.loads(sl.read_text())
    # The loaders resolve ``data/...`` relative to the cwd and may write caches
    # back there, so run from a throwaway sandbox holding private copies.
    import os

    original_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "data").mkdir()
        shutil.copy2(db, Path(tmp) / "data" / "players.db")
        shutil.copy2(sl, Path(tmp) / "data" / "sleeper_players.json")
        os.chdir(tmp)
        try:
            result = run_audit(sleeper_payload, "data/players.db", args.window)
        finally:
            os.chdir(original_cwd)
    print(render(result, args.examples))
    if args.json:
        Path(args.json).write_text(
            json.dumps(
                {k: [{**{k2: v2 for k2, v2 in p.items() if k2 != "raw"}, "positions": sorted(p["positions"])} for p in v] for k, v in result["by_reason"].items()},
                indent=1,
                default=str,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
