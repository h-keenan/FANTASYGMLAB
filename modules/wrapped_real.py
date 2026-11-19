"""Season Wrapped for a real (Sleeper) league, from the weekly matchup payloads the app already reads.

Same card ids and shapes as the Sim deck (the Fantasy Sim deck builder) so one client component draws both. Only the cards the
real data can honestly support are built: record, MVP, best/worst week, points left on the table, luck, rank journey.
Projection history, draft, trade and waiver grading are not stored for real leagues yet, so those cards (bust, steal, trades,
consistency, grade) are left out rather than invented. Nothing here is Pro-locked for that reason.

``partial`` is True while the season is still being played: the deck is the "so far" version and says so.
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from modules.wrapped_real_data import roster_season

MIN_WEEKS = 2


def _num(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _ord(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _player(pid: str, lookup: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    info = lookup.get(pid) or {}
    return {"id": pid, "headshot_id": pid if pid.isdigit() else None, "name": info.get("name") or "Unavailable player",
            "pos": info.get("position") or "", "team": info.get("team") or ""}


def build_real_wrapped(
    weeks: Sequence[Sequence[Mapping[str, Any]]], my_roster_id: int, *, season: str, team_name: str,
    profiles: Mapping[str, Mapping[str, Any]], lookup: Mapping[str, Mapping[str, Any]], partial: bool,
) -> dict[str, Any]:
    """``weeks[i]`` is Sleeper's ``/matchups/{i+1}`` list; weeks with no points for anyone (not played yet) are skipped."""

    played = [(i + 1, rows) for i, rows in enumerate(weeks) if any(_num(r.get("points")) for r in rows)]
    deck: dict[str, Any] = {"kind": "real", "partial": partial, "season_label": f"{season} season" if season else "Season",
                            "team_name": team_name, "cards": []}
    if len(played) < MIN_WEEKS:
        return deck
    teams = len({r.get("roster_id") for _, rows in played for r in rows})
    wins: dict[Any, float] = {}
    pf: dict[Any, float] = {}
    journey: list[int] = []
    wk_rows: list[dict[str, Any]] = []
    for wk, rows in played:
        by_matchup: dict[Any, list[Mapping[str, Any]]] = {}
        for r in rows:
            by_matchup.setdefault(r.get("matchup_id"), []).append(r)
        for r in rows:
            pf[r.get("roster_id")] = pf.get(r.get("roster_id"), 0.0) + _num(r.get("points"))
            wins.setdefault(r.get("roster_id"), 0.0)
        mine = next((r for r in rows if r.get("roster_id") == my_roster_id), None)
        for group in by_matchup.values():
            if len(group) == 2:
                a, b = group
                pa, pb = _num(a.get("points")), _num(b.get("points"))
                if pa != pb:
                    wins[(a if pa > pb else b).get("roster_id")] += 1.0
                else:
                    wins[a.get("roster_id")] += 0.5
                    wins[b.get("roster_id")] += 0.5
        order = sorted(wins, key=lambda k: (-wins[k], -pf.get(k, 0.0), str(k)))
        if my_roster_id in order:
            journey.append(order.index(my_roster_id) + 1)
        if mine is not None:
            opp = next((r for r in by_matchup.get(mine.get("matchup_id"), []) if r.get("roster_id") != my_roster_id), None)
            wk_rows.append({"week": wk, "pts": round(_num(mine.get("points")), 2),
                            "opp_pts": None if opp is None else round(_num(opp.get("points")), 2),
                            "opponent": (profiles.get(str(opp.get("roster_id"))) or {}).get("team_name") if opp else None})
    if len(wk_rows) < MIN_WEEKS:
        return deck
    season_stats = roster_season([rows for _, rows in played], my_roster_id)
    losses = sum(1 for w in wk_rows if w["opp_pts"] is not None and w["pts"] < w["opp_pts"])
    win_n = sum(1 for w in wk_rows if w["opp_pts"] is not None and w["pts"] > w["opp_pts"])
    ties = sum(1 for w in wk_rows if w["opp_pts"] is not None and w["pts"] == w["opp_pts"])
    record = f"{win_n}-{losses}" + (f"-{ties}" if ties else "")
    cards: list[dict[str, Any]] = []

    def add(cid: str, eyebrow: str, title: str, sub: str | None, data: dict[str, Any]) -> None:
        cards.append({"id": cid, "eyebrow": eyebrow, "title": title, "sub": sub, "pro": False, "locked": False, "data": data})

    so_far = "Through the week so far" if partial else None
    rank = journey[-1] if journey else None
    add("intro", "SEASON SO FAR" if partial else deck["season_label"].upper(), "Your season, wrapped", team_name,
        {"record": record, "outcome": f"Rank {rank} of {teams}" if rank else None, "rank": rank, "weeks": len(wk_rows)})

    totals: dict[str, list[float]] = {}
    for _, rows in played:
        row = next((r for r in rows if r.get("roster_id") == my_roster_id), None)
        pp = (row or {}).get("players_points")
        if isinstance(pp, Mapping):
            for pid in (row.get("starters") or ()):
                if pid in pp and pid != "0":
                    totals.setdefault(pid, []).append(_num(pp[pid]))
    if totals:
        pid, vals = max(totals.items(), key=lambda kv: (sum(kv[1]), kv[0]))
        mine_total = sum(sum(v) for v in totals.values()) or 1.0
        add("mvp", "MVP", "Your most valuable player", so_far or "Points in your lineup",
            {"player": _player(pid, lookup), "pts": round(sum(vals), 1), "over_proj": None, "ppg": round(sum(vals) / len(vals), 1),
             "best": {"week": None, "pts": round(max(vals), 1)}, "share": round(100.0 * sum(vals) / mine_total)})

    best = max(wk_rows, key=lambda w: (w["pts"], -w["week"]))
    worst = min(wk_rows, key=lambda w: (w["pts"], w["week"]))
    add("weeks", "BEST AND WORST WEEK", "Peak and valley", so_far, {"best": best, "worst": worst})

    lost = [w for w in wk_rows if w["opp_pts"] is not None and w["pts"] < w["opp_pts"]]
    won = [w for w in wk_rows if w["opp_pts"] is not None and w["pts"] > w["opp_pts"]]
    bench = season_stats["bench"]
    if bench["available"]:
        miss = bench["best"]
        add("close", "CLOSE CALLS", "Points left on the table", so_far,
            {"lost_by": min(({"margin": round(w["opp_pts"] - w["pts"], 1), "week": w["week"]} for w in lost), key=lambda m: m["margin"], default=None),
             "won_by": min(({"margin": round(w["pts"] - w["opp_pts"], 1), "week": w["week"]} for w in won), key=lambda m: m["margin"], default=None),
             "bench_pts": bench["total"], "left_on_bench": None, "complete": True,
             "miss": None if not miss else {"player": _player(miss["player_id"], lookup), "week": miss["week"], "pts": miss["pts"], "proj": None}})

    add("luck", "LUCK", "You deserved better" if season_stats["diff"] < -0.4 else "How the season fell", None,
        {"actual_wins": season_stats["actual_wins"], "expected_wins": season_stats["expected_wins"], "diff": season_stats["diff"], "games": season_stats["games"]})

    if len(journey) >= MIN_WEEKS:
        add("journey", "RANK JOURNEY", f"{_ord(journey[0])} to {_ord(journey[-1])}", f"Peaked at {_ord(min(journey))}",
            {"ranks": journey, "weeks": [wk for wk, _ in played][: len(journey)], "teams": teams})

    deck["cards"] = cards
    return deck


__all__ = ["build_real_wrapped"]
