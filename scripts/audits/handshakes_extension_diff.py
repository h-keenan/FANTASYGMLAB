"""Before/after diff for the handshakes 3-5 EXTENSION flags (flag off vs on).

SYNTHETIC seeded leagues (same generator as partner_context_diff.py). Each team
takes a turn as "me" in every seed.

Surfaces compared (off = today's output, on = flag default):
  finder     DYNASTYGM_PARTNER_CONTEXT_FINDER_V1     Trade Finder reads the partner team profile
  dashboard  DYNASTYGM_PARTNER_CONTEXT_DASHBOARD_V1  dashboard direct path reads the profile
  search     DYNASTYGM_PARTNER_CONTEXT_SEARCH_V1     player search ("get this player") reads the profile
  ask_pick   DYNASTYGM_ASK_PICK_IDEA_V1              new "Ask for their pick" idea type

For the three profile surfaces the flag decides whether the surface passes the
cached league team profile to the engine (``partner_context.team_profiles_for_surface``);
the harness patches the profile loader with the synthetic profiles and calls the
same engine entry points each surface uses.

    .venv313/bin/python scripts/audits/handshakes_extension_diff.py OUT.md
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from partner_context_diff import SEEDS, TEAMS, card, key, make_league  # noqa: E402

from modules import partner_context, team_profile, trade_ideas  # noqa: E402

SETTINGS = {"league_type": "dynasty", "type": 2}
SURFACES = {
    "finder": partner_context.FINDER_ENV_KEY,
    "dashboard": partner_context.DASHBOARD_ENV_KEY,
    "search": partner_context.SEARCH_ENV_KEY,
    "ask_pick": partner_context.ASK_PICK_ENV_KEY,
}


def _profiles(surface: str, profiles, on: bool):
    """What the surface hands the engine for its flag state."""

    env = SURFACES[surface]
    os.environ[env] = "1" if on else "0"
    with patch.object(team_profile, "league_team_profiles_cached", lambda **_k: profiles):
        return partner_context.team_profiles_for_surface(env, league_id="x", lens="dynasty", players_db_path="x")


def _build(seed, rid, players, summary, adapter, profiles, block=(), **extra):
    with patch.object(trade_ideas._UserSideAnalyzerGate, "passes", lambda self, idea: True):
        return trade_ideas.build_trade_ideas(
            players, f"synthetic-{seed}", summary, rid, list(block), [], {}, max_ideas=40, score_field="value_score",
            league_settings=SETTINGS, adapter=adapter, team_profiles=profiles, _pipeline_cache_enabled=False,
            **extra,
        )


def run_surface(surface: str, seed: int, rid: int, on: bool):
    players, summary, adapter, profiles = make_league(seed)
    # Other flags stay at their default so only this surface's flag differs.
    for env in SURFACES.values():
        os.environ.pop(env, None)
    os.environ.pop(partner_context.PARTNER_CONTEXT_ENV_KEY, None)
    handed = _profiles(surface, profiles, on)
    if surface == "ask_pick":
        # Ask-pick reads age/picks/tendency; the tendency comes from the
        # Trade Hub path, so hand the profile in both runs.
        handed = profiles
        os.environ[SURFACES["ask_pick"]] = "1" if on else "0"
    extra = {}
    if surface == "finder":
        mine = players[players["player_id"].isin(next(r for r in adapter.get_rosters("x") if r["roster_id"] == rid)["players"])]
        top = mine.sort_values("value_score", ascending=False).iloc[1]
        extra = {"block": [top["name"]], "trade_block_player_ids": [top["player_id"]]}
    if surface == "search":
        return _search(seed, rid, players, summary, adapter, handed)
    return _build(seed, rid, players, summary, adapter, handed, **extra)


def _search(seed, rid, players, summary, adapter, handed):
    rosters = adapter.get_rosters("x")
    other = next(r for r in rosters if r["roster_id"] != rid)
    target = sorted(
        (p for p in players.to_dict("records") if p["player_id"] in set(other["players"])),
        key=lambda p: -p["value_score"],
    )[0]
    roster_map = {r["roster_id"]: r["players"] for r in rosters}
    with patch.object(trade_ideas._UserSideAnalyzerGate, "passes", lambda self, idea: True):
        result = trade_ideas.build_player_trade_hub_ideas(
            players, f"synthetic-{seed}", summary, rid, {}, [], mode="target_player",
            selected_player_id=target["player_id"], max_ideas=12, score_field="value_score",
            league_settings=SETTINGS, adapter=adapter, prefetched_roster_map=roster_map,
            priced_search=True, team_profiles=handed,
        )
    return list(result.get("ideas") or [])


def compare(surface: str):
    same = changed = added = removed = 0
    shifts, samples = [], []
    ask_cards = []
    total_off = total_on = 0
    for seed in SEEDS:
        for rid in range(1, TEAMS + 1):
            try:
                off, on = run_surface(surface, seed, rid, False), run_surface(surface, seed, rid, True)
            except Exception as exc:  # a synthetic miss must not hide the rest
                print(f"skip {surface} seed={seed} rid={rid}: {type(exc).__name__}: {exc}", file=sys.stderr)
                continue
            total_off += len(off)
            total_on += len(on)
            off_by, on_by = {key(i): i for i in off}, {key(i): i for i in on}
            for k, a in off_by.items():
                b = on_by.get(k)
                if b is None:
                    removed += 1
                    continue
                delta = (b["market_realism_score"] - a["market_realism_score"])
                shifts.append(delta)
                if (a["market_realism_score"], a.get("partner_fit_reason")) != (
                    b["market_realism_score"], b.get("partner_fit_reason")):
                    changed += 1
                    if len(samples) < 3 and delta:
                        samples.append((seed, rid, card(a), card(b)))
                else:
                    same += 1
            for k, b in on_by.items():
                if k not in off_by:
                    added += 1
                    if b.get("ask_pick_reasons"):
                        if len(ask_cards) < 6:
                            ask_cards.append((seed, rid, card(b), "; ".join(b.get("ask_pick_reasons") or [])))
    return {
        "surface": surface, "off": total_off, "on": total_on, "same": same, "changed": changed,
        "added": added, "removed": removed,
        "avg_shift": round(sum(shifts) / len(shifts), 3) if shifts else 0.0,
        "max_abs_shift": max((abs(s) for s in shifts), default=0),
        "samples": samples, "ask_cards": ask_cards,
    }


def main(out: str) -> None:
    lines = [
        "# Handshakes 3-5 extension: before / after",
        "",
        f"SYNTHETIC seeded 12-team leagues (seeds {list(SEEDS)}; every team as 'me'). Off = flag 0 (today's output).",
        "",
    ]
    for surface in SURFACES:
        r = compare(surface)
        lines += [
            f"## {surface} ({SURFACES[surface]})",
            f"- Ideas off {r['off']} -> on {r['on']}; unchanged {r['same']}, changed {r['changed']}, "
            f"added {r['added']}, removed {r['removed']}",
            f"- Realism shift on shared ideas: avg {r['avg_shift']}, max abs {r['max_abs_shift']} "
            f"(combined cap +/-{partner_context.COMBINED_MAX_POINTS})",
        ]
        for seed, rid, before, after in r["samples"]:
            lines += [f"- seed {seed}, me={rid}", f"  - before: {before}", f"  - after: {after}"]
        for seed, rid, c, why in r["ask_cards"]:
            lines += [f"- NEW seed {seed}, me={rid}: {c}", f"  - why: {why}"]
        lines.append("")
    Path(out).write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "handshakes_extension_diff.md")
