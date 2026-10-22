"""Live projection scoreboard: replay the projection model against this season's results.

Projections are deterministic given point-in-time data, so for every completed
week we can rebuild what ``modules.player_projections`` would have projected
(only that player's games from *earlier* weeks are visible), then score it
against what actually happened. Nothing here touches a database: it reads
Sleeper's public stats/projections endpoints and writes one markdown file,
``docs/projection-scoreboard.md``.

Compared on the same player-weeks:

- ``model``: the shipped v3 estimator (usage-based empirical Bayes) and its
  68% interval;
- ``season avg``: plain average of the player's earlier games this season;
- ``Sleeper``: Sleeper's own pre-game projection (benchmark only, never an
  input to our model).

Two pools, matching ``docs/projections-v3-walkforward.md``: the "relevant"
pool (Sleeper's top N per position-week among players who played: QB 24, RB 48,
WR 60, TE 24, K 16) and every player-week that has a Sleeper projection.
Availability (injury) multipliers are not replayed: Sleeper keeps no
point-in-time injury history, so only the usage estimator is scored.

Usage::

    python scripts/projection_scoreboard.py            # write docs/projection-scoreboard.md
    python scripts/projection_scoreboard.py --commit   # also commit+push it (CI)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from modules import player_projections as pp  # noqa: E402

OUTPUT_PATH = ROOT / "docs" / "projection-scoreboard.md"
POSITIONS = ("QB", "RB", "WR", "TE", "K")
POOL_N = {"QB": 24, "RB": 48, "WR": 60, "TE": 24, "K": 16}
MAX_WEEK = 18
FIRST_SCORED_WEEK = 2  # needs at least one earlier game
_POS_QUERY = "&".join(f"position[]={p}" for p in POSITIONS)
_STATS_URL = "https://api.sleeper.com/stats/nfl/{season}/{week}?season_type=regular&" + _POS_QUERY
_PROJ_URL = "https://api.sleeper.com/projections/nfl/{season}/{week}?season_type=regular&" + _POS_QUERY
# A week counts as complete once most of the usual number of players have logged a game.
_COMPLETE_FRACTION = 0.8
_MIN_PLAYED_FOR_FIRST_WEEK = 200


def default_season(now: Optional[time.struct_time] = None) -> int:
    current = now or time.localtime()
    return int(current.tm_year if current.tm_mon >= 9 else current.tm_year - 1)


def _fetch(url: str) -> List[Dict[str, Any]]:
    last: Optional[Exception] = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "FantasyDesk-scoreboard/1.0"})
            with urllib.request.urlopen(request, timeout=90) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return payload if isinstance(payload, list) else []
        except Exception as exc:  # network flake: retry, then surface
            last = exc
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"could not fetch {url}: {last}")


def fetch_season(season: int) -> tuple[Dict[int, List[Dict[str, Any]]], Dict[int, List[Dict[str, Any]]]]:
    """Weekly stats and Sleeper projections for every week that has stats."""

    stats: Dict[int, List[Dict[str, Any]]] = {}
    projections: Dict[int, List[Dict[str, Any]]] = {}
    for week in range(1, MAX_WEEK + 1):
        rows = _fetch(_STATS_URL.format(season=season, week=week))
        if not any(float((r.get("stats") or {}).get("gp") or 0) > 0 for r in rows):
            break
        stats[week] = rows
        projections[week] = _fetch(_PROJ_URL.format(season=season, week=week))
    return stats, projections


def _played_count(rows: List[Dict[str, Any]]) -> int:
    return sum(1 for r in rows if float((r.get("stats") or {}).get("gp") or 0) > 0)


def completed_weeks(stats: Dict[int, List[Dict[str, Any]]]) -> List[int]:
    counts = {week: _played_count(rows) for week, rows in stats.items()}
    done: List[int] = []
    for week in sorted(counts):
        if not done:
            if counts[week] >= _MIN_PLAYED_FOR_FIRST_WEEK:
                done.append(week)
            continue
        typical = float(np.median([counts[w] for w in done]))
        if counts[week] >= _COMPLETE_FRACTION * typical:
            done.append(week)
    return done


def _game_row(week: int, record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    st = record.get("stats") or {}
    if not float(st.get("gp") or 0) > 0:
        return None
    return {
        "week": week,
        "fantasy_points_ppr": float(st.get("pts_ppr") or 0.0),
        "pass_attempts": float(st.get("pass_att") or 0.0),
        "rush_attempts": float(st.get("rush_att") or 0.0),
        "targets": float(st.get("rec_tgt") or 0.0),
    }


def build_rows(
    stats: Dict[int, List[Dict[str, Any]]],
    projections: Dict[int, List[Dict[str, Any]]],
    weeks: List[int],
) -> pd.DataFrame:
    """One row per (week, player) the model could have projected and who played."""

    history: Dict[str, List[Dict[str, Any]]] = {}
    position_of: Dict[str, str] = {}
    name_of: Dict[str, str] = {}
    for week in sorted(stats):
        for record in stats[week]:
            pid = str(record.get("player_id"))
            player = record.get("player") or {}
            pos = str(player.get("position") or "").upper()
            if pos in POSITIONS:
                position_of[pid] = pos
                name_of[pid] = f"{player.get('first_name') or ''} {player.get('last_name') or ''}".strip()
    out: List[Dict[str, Any]] = []
    for week in sorted(stats):
        sleeper_proj = {
            str(r.get("player_id")): (r.get("stats") or {}).get("pts_ppr") for r in projections.get(week, [])
        }
        this_week: Dict[str, Dict[str, Any]] = {}
        for record in stats[week]:
            pid = str(record.get("player_id"))
            if pid not in position_of:
                continue
            game = _game_row(week, record)
            if game:
                this_week[pid] = game
        if week in weeks and week >= FIRST_SCORED_WEEK:
            for pid, game in this_week.items():
                prior = history.get(pid)
                if not prior:
                    continue
                pos = position_of[pid]
                as_of = max(r["week"] for r in prior)
                trend = pp._player_usage_trend(prior, position=pos, upto_week=as_of)
                if trend is None:
                    continue
                estimate = max(0.0, float(trend["baseline_ppr"]))
                confidence = pp._v2_confidence(trend["games_played"])
                low, high = pp._v2_range(estimate, pos, confidence)
                proj = sleeper_proj.get(pid)
                out.append(
                    {
                        "week": week,
                        "pid": pid,
                        "name": name_of.get(pid, pid),
                        "pos": pos,
                        "actual": game["fantasy_points_ppr"],
                        "est": estimate,
                        "low": low,
                        "high": high,
                        "avg": float(trend["simple_avg_ppr"]),
                        "sleeper": float(proj) if proj is not None else np.nan,
                    }
                )
        for pid, game in this_week.items():
            history.setdefault(pid, []).append(game)
    frame = pd.DataFrame(out)
    if frame.empty:
        return frame
    frame["pool"] = False
    for (_, pos), group in frame.groupby(["week", "pos"]):
        top = group[group.sleeper.notna()].sort_values("sleeper", ascending=False).head(POOL_N[pos])
        frame.loc[top.index, "pool"] = True
    return frame


def _pairwise(frame: pd.DataFrame, column: str) -> float:
    hit = total = 0.0
    for _, group in frame.groupby(["week", "pos"]):
        actual = group.actual.values
        guess = group[column].values
        diff_a = actual[:, None] - actual[None, :]
        diff_g = guess[:, None] - guess[None, :]
        mask = diff_a > 0
        total += mask.sum()
        hit += ((diff_g > 0) & mask).sum() + 0.5 * ((diff_g == 0) & mask).sum()
    return float(hit / total) if total else float("nan")


def _metrics(frame: pd.DataFrame, column: str, *, interval: bool = False) -> Dict[str, float]:
    if frame.empty:
        return {"n": 0, "mae": float("nan"), "bias": float("nan"), "hit": float("nan"), "cov": float("nan")}
    error = frame[column] - frame.actual
    result = {
        "n": int(len(frame)),
        "mae": float(error.abs().mean()),
        "bias": float(error.mean()),
        "hit": _pairwise(frame, column),
        "cov": float("nan"),
    }
    if interval:
        result["cov"] = float(((frame.actual >= frame.low) & (frame.actual <= frame.high)).mean())
    return result


def summarize(frame: pd.DataFrame) -> Dict[str, Any]:
    pool = frame[frame.pool] if not frame.empty else frame
    with_sleeper = frame[frame.sleeper.notna()] if not frame.empty else frame
    overall = {}
    for label, group in (("pool", pool), ("all", with_sleeper)):
        overall[label] = {
            "model": _metrics(group, "est", interval=True),
            "avg": _metrics(group, "avg"),
            "sleeper": _metrics(group, "sleeper"),
        }
    by_pos = {}
    for pos in POSITIONS:
        group = pool[pool.pos == pos] if not pool.empty else pool
        by_pos[pos] = {
            "model": _metrics(group, "est", interval=True),
            "avg": _metrics(group, "avg"),
            "sleeper": _metrics(group, "sleeper"),
        }
    by_week = {}
    for week in sorted(pool.week.unique()) if not pool.empty else []:
        group = pool[pool.week == week]
        by_week[int(week)] = {
            "model": _metrics(group, "est", interval=True),
            "avg": _metrics(group, "avg"),
            "sleeper": _metrics(group, "sleeper"),
        }
    return {"overall": overall, "by_pos": by_pos, "by_week": by_week}


def _f(value: float, digits: int = 2) -> str:
    return "n/a" if value != value else f"{value:.{digits}f}"


def _pct(value: float) -> str:
    return "n/a" if value != value else f"{value * 100:.1f}%"


def render_markdown(season: int, weeks: List[int], summary: Dict[str, Any]) -> str:
    scored = [w for w in weeks if w >= FIRST_SCORED_WEEK]
    lines = [
        f"# Projection scoreboard: {season}",
        "",
        "Generated by `scripts/projection_scoreboard.py` (weekly GitHub Actions run, see",
        "`.github/workflows/projection-scoreboard.yml`). Do not edit by hand.",
        "",
    ]
    if not scored:
        lines += [f"No completed week of {season} has an earlier game to project from yet. Nothing to score.", ""]
        return "\n".join(lines)
    lines += [
        f"Scored weeks: {scored[0]}-{scored[-1]} ({len(scored)} week{'s' if len(scored) != 1 else ''}). "
        f"Model version: `{pp.PROJECTION_MODEL_VERSION}`.",
        "",
        "Every projection is rebuilt point-in-time: only the player's games from earlier weeks are visible.",
        "No database is read or written. Availability (injury) adjustments are not replayed because Sleeper keeps",
        "no point-in-time injury history; this scores the usage estimator and its 68% interval.",
        "",
        "Lower MAE is better; bias is projection minus actual (negative = under-projecting); hit rate is the",
        "share of same-position, same-week player pairs ordered correctly (start/sit); coverage is how often",
        "the actual landed inside the model's 68% interval (target 68%).",
        "",
    ]
    names = {"pool": "Relevant players (Sleeper top N per position-week)", "all": "Every played player-week with a Sleeper projection"}
    for key in ("pool", "all"):
        block = summary["overall"][key]
        lines += [f"## {names[key]}", "", "| Model | n | MAE | Bias | Start/sit hit rate | 68% coverage |", "| --- | ---: | ---: | ---: | ---: | ---: |"]
        for label, col in (("Our model", "model"), ("Season average", "avg"), ("Sleeper", "sleeper")):
            m = block[col]
            lines.append(
                f"| {label} | {m['n']:,} | {_f(m['mae'])} | {_f(m['bias'])} | {_pct(m['hit'])} | {_pct(m['cov']) if col == 'model' else '-'} |"
            )
        lines.append("")
    lines += ["## By position (relevant players)", "", "| Position | n | Model MAE | Season avg MAE | Sleeper MAE | Model bias | Model hit rate | Coverage |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |"]
    for pos in POSITIONS:
        b = summary["by_pos"][pos]
        lines.append(
            f"| {pos} | {b['model']['n']:,} | {_f(b['model']['mae'])} | {_f(b['avg']['mae'])} | {_f(b['sleeper']['mae'])} | "
            f"{_f(b['model']['bias'])} | {_pct(b['model']['hit'])} | {_pct(b['model']['cov'])} |"
        )
    lines += ["", "## By week (relevant players)", "", "| Week | n | Model MAE | Season avg MAE | Sleeper MAE | Coverage |", "| ---: | ---: | ---: | ---: | ---: | ---: |"]
    for week, b in summary["by_week"].items():
        lines.append(
            f"| {week} | {b['model']['n']:,} | {_f(b['model']['mae'])} | {_f(b['avg']['mae'])} | {_f(b['sleeper']['mae'])} | {_pct(b['model']['cov'])} |"
        )
    lines += [
        "",
        "## How to read this",
        "",
        "Fantasy scoring is partly random: a player's weekly points depend on touchdowns, game script and",
        "injuries that nobody can see in advance. In the 2022-2025 walk-forward backtest",
        "(`docs/projections-v3-walkforward.md`) the model's MAE on relevant players was about 5.7 points,",
        "against about 5.9 for the season average and about 5.6 for Sleeper's own projections, and the start/sit",
        "hit rate sat between 62% and 65% for every method. A few weeks is a small sample, so",
        "week-to-week movement in these numbers is mostly noise: judge the model on the full-season figures.",
        "",
    ]
    return "\n".join(lines)


def generate(season: int) -> str:
    stats, projections = fetch_season(season)
    weeks = completed_weeks(stats)
    frame = build_rows(stats, projections, weeks)
    summary = summarize(frame)
    return render_markdown(season, weeks, summary)


def write_scoreboard(season: int, output: Path = OUTPUT_PATH) -> int:
    text = generate(season)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text.rstrip("\n") + "\n", encoding="utf-8")
    print(f"wrote {output}")
    return 0


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--season", type=int, default=default_season())
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    parser.add_argument("--commit", action="store_true", help="commit and push the refreshed doc to main (CI)")
    args = parser.parse_args(argv)
    if not args.commit:
        return write_scoreboard(args.season, args.output)

    from scripts.refresh_and_commit_players_db import DEFAULT_REPO_SLUG, refresh_and_commit

    token = os.environ.get("GITHUB_PUSH_TOKEN", "").strip()
    slug = os.environ.get("GITHUB_REPO_SLUG", DEFAULT_REPO_SLUG).strip()
    push_url = f"https://x-access-token:{token}@github.com/{slug}.git" if token else None
    return refresh_and_commit(
        repo_root=ROOT,
        db_path=args.output,
        push_url=push_url,
        refresh_runner=lambda path: write_scoreboard(args.season, path),
        commit_author_name="FantasyDesk Projection Scoreboard Bot",
        commit_author_email="projection-scoreboard-bot@users.noreply.github.com",
        commit_message_subject="chore(docs): scheduled projection scoreboard refresh",
        commit_message_note="Automated by the projection-scoreboard workflow.",
    )


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
