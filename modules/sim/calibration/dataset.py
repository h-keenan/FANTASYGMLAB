"""Build the real-history panel the player model is calibrated against.

Input: a directory of Sleeper public weekly payloads (the same files
``scripts/projection_calibration_backtest.py fetch`` writes):
``stats_{season}_{week}.json`` (actual box scores) and ``proj_{season}_{week}.json``
(weekly projections; the week-1 file carries the preseason ADP and a preseason
points-per-game projection). Output: one compact gzipped JSON panel, committed
at ``data/panel.json.gz`` so the backtest and tests run without the raw cache.

One row per (season, player) in the relevant fantasy pool (QB/RB/WR/TE/K with a
preseason ADP or a usable preseason projection)::

    {"season", "pid", "pos", "age", "rookie", "team", "adp", "proj_ppg",
     "weeks": [[played, pts_ppr, pass_att, pass_cmp, pass_yd, pass_td, pass_int,
                rush_att, rush_yd, rush_td, tgt, rec, rec_yd, rec_td, fum_lost,
                fgm, xpm] x 17 or None for the NFL bye / no row]}

``played`` is 1 when the player logged a game. ``None`` is a week the player's NFL
team did not play (bye). Everything else is the real number (0 = real zero).

Run: ``python -m modules.sim.calibration.dataset build --cache DIR --players data/sleeper_players.json``
Nothing here touches ``data/players.db`` or any real module (pure stdlib).
"""

from __future__ import annotations

import argparse
import datetime as _dt
import gzip
import json
from pathlib import Path
from typing import Any

POSITIONS = ("QB", "RB", "WR", "TE", "K")
STAT_FIELDS = (
    "pts_ppr", "pass_att", "pass_cmp", "pass_yd", "pass_td", "pass_int",
    "rush_att", "rush_yd", "rush_td", "rec_tgt", "rec", "rec_yd", "rec_td", "fum_lost",
    "fgm", "xpm",
)
PANEL_PATH = Path(__file__).resolve().parent / "data" / "panel.json.gz"
SEASON_WEEKS = 17


def _load(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
    except ValueError:
        return []
    return data if isinstance(data, list) else []


def _age_on(birth_date: str | None, season: int) -> float | None:
    if not birth_date:
        return None
    try:
        born = _dt.date.fromisoformat(str(birth_date)[:10])
    except ValueError:
        return None
    return round((_dt.date(season, 9, 1) - born).days / 365.25, 2)


def build_panel(cache: Path, players_json: Path, seasons: list[int], pool_ppg_floor: float = 6.0) -> list[dict[str, Any]]:
    directory = json.loads(players_json.read_text())
    rows_out: list[dict[str, Any]] = []
    for season in seasons:
        proj1 = _load(cache / f"proj_{season}_1.json")
        if not proj1:
            continue
        stats_by_week: dict[int, dict[str, dict[str, Any]]] = {}
        team_played: dict[int, set[str]] = {}
        for week in range(1, SEASON_WEEKS + 1):
            rows = _load(cache / f"stats_{season}_{week}.json")
            stats_by_week[week] = {str(r["player_id"]): r for r in rows}
            team_played[week] = {r.get("team") for r in rows if (r.get("stats") or {}).get("gp") and r.get("team")}
        for row in proj1:
            player = row.get("player") or {}
            pos = player.get("position")
            if pos not in POSITIONS:
                continue
            stats = row.get("stats") or {}
            adp = stats.get("adp_dd_ppr")
            adp = float(adp) if adp is not None and float(adp) < 999 else None  # 999/1000 = unranked
            ppg = float(stats.get("pts_ppr") or 0.0)
            if adp is None and ppg < pool_ppg_floor:
                continue
            pid = str(row["player_id"])
            info = directory.get(pid) or {}
            ry_raw = (player.get("metadata") or {}).get("rookie_year")
            rookie_year = int(ry_raw) if str(ry_raw or "").isdigit() else None
            if rookie_year is None and info.get("years_exp") is not None:
                rookie_year = 2026 - int(info["years_exp"])  # directory is current as of 2026
            weeks: list[Any] = []
            team = row.get("team")
            for week in range(1, SEASON_WEEKS + 1):
                srow = stats_by_week[week].get(pid)
                s = (srow or {}).get("stats") or {}
                wteam = (srow or {}).get("team") or team
                if wteam and wteam not in team_played[week] and not s.get("gp"):
                    weeks.append(None)  # the NFL team did not play: bye
                    continue
                weeks.append([int(bool(s.get("gp")))] + [round(float(s.get(f) or 0.0), 2) for f in STAT_FIELDS])
            if all(w is None or not w[0] for w in weeks) and adp is None:
                continue
            rows_out.append({
                "season": season, "pid": pid, "pos": pos,
                "age": _age_on(info.get("birth_date"), season) or (float(info["age"]) - (2026 - season) if info.get("age") else None),
                "rookie": bool(rookie_year is not None and rookie_year == season),
                "years_exp": None if rookie_year is None else max(0, season - rookie_year),
                "team": team, "adp": adp, "proj_ppg": round(ppg, 2), "weeks": weeks,
            })
    return rows_out


def save_panel(rows: list[dict[str, Any]], path: Path = PANEL_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", compresslevel=9) as fh:
        json.dump({"stat_fields": STAT_FIELDS, "rows": rows}, fh, separators=(",", ":"))


def load_panel(path: Path = PANEL_PATH) -> list[dict[str, Any]]:
    with gzip.open(path, "rt") as fh:
        return json.load(fh)["rows"]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("--cache", required=True, type=Path)
    ap.add_argument("--players", required=True, type=Path)
    ap.add_argument("--seasons", nargs="*", type=int, default=[2021, 2022, 2023, 2024, 2025])
    ap.add_argument("--out", type=Path, default=PANEL_PATH)
    args = ap.parse_args(argv)
    rows = build_panel(args.cache, args.players, args.seasons)
    save_panel(rows, args.out)
    print(f"{len(rows)} player-seasons -> {args.out} ({args.out.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()


def player_mapping(row: dict[str, Any], *, rank_in_pos: int | None = None) -> dict[str, Any]:
    """The ``player`` mapping the model takes, built from a panel row. The bye
    week is the real one for that player's team and season, so simulated
    availability is comparable to the real thing."""

    bye = next((i + 1 for i, w in enumerate(row["weeks"]) if w is None), 0)
    return {
        "player_id": f"{row['season']}:{row['pid']}", "pos": row["pos"], "age": row["age"] or 26.0,
        "years_exp": row.get("years_exp"), "is_rookie": row["rookie"], "team": row.get("team") or "",
        "projection_mean_ppg": row["proj_ppg"], "adp": row["adp"], "bye_week": bye,
        "value_rank": rank_in_pos,
    }


def season_summary(row: dict[str, Any]) -> dict[str, Any]:
    """Real outcome of one player-season: games available / played, PPG over games
    played, weekly points of played games (PPR)."""

    avail = [w for w in row["weeks"] if w is not None]
    played = [w for w in avail if w[0]]
    pts = [w[1] for w in played]
    return {
        "available": len(avail), "played": len(played), "missed": len(avail) - len(played),
        "pts": pts, "ppg": (sum(pts) / len(pts)) if pts else 0.0, "total": sum(pts),
    }
