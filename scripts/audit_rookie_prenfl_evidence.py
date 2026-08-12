#!/usr/bin/env python3
"""Offline rookie / pre-NFL evidence audit over existing caches.

Does not change valuation weights. Writes JSON under
/opt/cursor/artifacts/rookie-prenfl-evidence/ (or --output).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from modules import rankings, sleeper  # noqa: E402


def _rate_numeric(series: pd.Series) -> float:
    if series is None or len(series) == 0:
        return 0.0
    return float(pd.to_numeric(series, errors="coerce").notna().mean())


def _rate_text(series: pd.Series) -> float:
    if series is None or len(series) == 0:
        return 0.0
    text = series.astype(str)
    ok = series.notna() & text.ne("") & text.ne("None") & text.ne("nan") & text.ne("<NA>")
    return float(ok.mean())


def _pearson(a: pd.Series, b: pd.Series) -> float | None:
    a = pd.to_numeric(a, errors="coerce")
    b = pd.to_numeric(b, errors="coerce")
    mask = a.notna() & b.notna()
    if int(mask.sum()) < 8:
        return None
    return float(a[mask].corr(b[mask]))


def _r2(a: pd.Series, b: pd.Series) -> float | None:
    a = pd.to_numeric(a, errors="coerce")
    b = pd.to_numeric(b, errors="coerce")
    mask = a.notna() & b.notna()
    if int(mask.sum()) < 8:
        return None
    x = a[mask].to_numpy()
    y = b[mask].to_numpy()
    x = x - x.mean()
    y = y - y.mean()
    den = float((x @ x) * (y @ y))
    if den <= 0:
        return None
    return float((x @ y) ** 2 / den)


def build_valued_frame() -> tuple[pd.DataFrame, dict[str, dict]]:
    raw = sleeper.get_players(refresh=False)
    stats = sleeper.get_season_player_stats(refresh=False)
    prior = sleeper.get_prior_season_player_stats(refresh=False)
    meta: dict[str, dict] = {}
    for pid, payload in raw.items():
        if not isinstance(payload, dict):
            continue
        md = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        meta[str(pid)] = {
            "college": payload.get("college"),
            "rookie_year": md.get("rookie_year"),
            "draft_round": payload.get("draft_round"),
            "draft_pick": payload.get("draft_pick"),
            "overall_pick": payload.get("overall_pick"),
        }

    rows = []
    for pid, payload in raw.items():
        if not isinstance(payload, dict) or not payload.get("active"):
            continue
        position = str(payload.get("position") or "")
        fantasy_positions = payload.get("fantasy_positions") or []
        if position not in {"QB", "RB", "WR", "TE"} and not any(
            item in {"QB", "RB", "WR", "TE"} for item in fantasy_positions
        ):
            continue
        record = rankings.normalize_player_record(str(pid), payload)
        if record:
            rows.append(record)

    frame = pd.DataFrame(rows)
    frame = rankings.attach_player_stats(frame, stats or {}, prior_stats=prior or {})
    frame = rankings.apply_valuation_model(frame)
    for key in ("college", "rookie_year", "draft_round", "draft_pick", "overall_pick"):
        frame[key] = frame["player_id"].astype(str).map(
            lambda player_id, field=key: (meta.get(player_id) or {}).get(field)
        )
    return frame, meta


def coverage_row(frame: pd.DataFrame) -> dict:
    if frame is None or frame.empty:
        return {"n": 0}
    games = pd.to_numeric(frame.get("games_played"), errors="coerce").fillna(0)
    snaps = pd.to_numeric(frame.get("snap_share"), errors="coerce").fillna(0)
    prior = pd.to_numeric(frame.get("prior_games_played"), errors="coerce").fillna(0)
    recency = (
        pd.to_numeric(frame.get("recency_n"), errors="coerce").fillna(0)
        if "recency_n" in frame.columns
        else pd.Series(0.0, index=frame.index)
    )
    fantasycalc = pd.to_numeric(frame.get("fantasycalc_value"), errors="coerce").fillna(0)
    depth_order = pd.to_numeric(frame.get("depth_chart_order"), errors="coerce").fillna(0)
    return {
        "n": int(len(frame)),
        "age": round(_rate_numeric(frame["age"]), 3),
        "years_exp": round(_rate_numeric(frame["years_exp"]), 3),
        "college_raw": round(_rate_text(frame["college"]), 3),
        "rookie_year_raw": round(_rate_text(frame["rookie_year"]), 3),
        "depth_pos": round(_rate_text(frame["depth_chart_position"]), 3),
        "depth_ord_gt0": round(float((depth_order > 0).mean()), 3),
        "team": round(_rate_text(frame["team"]), 3),
        "search_rank": round(_rate_numeric(frame["search_rank"]), 3),
        "market": round(_rate_numeric(frame["market_score"]), 3),
        "fantasycalc_gt0": round(float((fantasycalc > 0).mean()), 3),
        "games_gt0": round(float((games > 0).mean()), 3),
        "snaps_gt0": round(float((snaps > 0).mean()), 3),
        "prior_gt0": round(float((prior > 0).mean()), 3),
        "recency_ge3": round(float((recency >= 3).mean()), 3),
        "draft_round": round(_rate_numeric(frame["draft_round"]), 3),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="/opt/cursor/artifacts/rookie-prenfl-evidence",
    )
    args = parser.parse_args()
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    frame, _meta = build_valued_frame()
    years_exp = pd.to_numeric(frame["years_exp"], errors="coerce")
    frame["cohort"] = np.select(
        [years_exp.le(0), years_exp.eq(1), years_exp.ge(2)],
        ["rookie", "year2", "veteran"],
        default="unknown",
    )
    games = pd.to_numeric(frame.get("games_played"), errors="coerce").fillna(0)
    production_confidence = pd.to_numeric(
        frame.get("production_confidence"), errors="coerce"
    ).fillna(0)
    frame["has_nfl_sample"] = games.gt(0) | production_confidence.gt(0)

    cohorts = {
        "rookie": frame["cohort"].eq("rookie"),
        "year2": frame["cohort"].eq("year2"),
        "veteran": frame["cohort"].eq("veteran"),
        "rookie_no_nfl": frame["cohort"].eq("rookie") & ~frame["has_nfl_sample"],
        "rookie_with_team": frame["cohort"].eq("rookie")
        & frame["team"].notna()
        & frame["team"].astype(str).ne(""),
        "rookie_no_team": frame["cohort"].eq("rookie")
        & (frame["team"].isna() | frame["team"].astype(str).eq("")),
    }
    for position in ("QB", "RB", "WR", "TE"):
        cohorts[f"rookie_{position}"] = frame["cohort"].eq("rookie") & frame[
            "position"
        ].eq(position)

    coverage = {name: coverage_row(frame.loc[mask]) for name, mask in cohorts.items()}

    market: dict[str, dict] = {}
    linkage = rankings.effective_market_linkage_series(frame)
    mass = rankings.composite_market_mass_series(frame)
    frame = frame.assign(effective_market_linkage=linkage, composite_market_mass=mass)
    for name in ("rookie_no_nfl", "rookie", "year2", "veteran"):
        mask = cohorts[name] if name != "rookie" else cohorts["rookie"]
        if name == "rookie_no_nfl":
            mask = cohorts["rookie_no_nfl"]
        subset = frame.loc[mask]
        market[name] = {
            "n": int(len(subset)),
            "pearson_score_market": _pearson(subset["score"], subset["market_score"]),
            "r2_score_market": _r2(subset["market_score"], subset["score"]),
            "effective_market_linkage_mean": float(subset["effective_market_linkage"].mean())
            if len(subset)
            else None,
            "composite_market_mass_mean": float(subset["composite_market_mass"].mean())
            if len(subset)
            else None,
            "production_nunique": int(
                pd.to_numeric(subset["production_score"], errors="coerce").nunique()
            )
            if "production_score" in subset and len(subset)
            else 0,
        }

    report = {
        "verdict": "ROOKIE EVIDENCE NEEDS MORE WORK",
        "provider_decision": "C",
        "draft_capital_supported": rankings.draft_capital_supported_by_available_data(),
        "valued_n": int(len(frame)),
        "normalize_drops_college_and_rookie_year": True,
        "coverage": coverage,
        "market_dependence": market,
        "notes": [
            "college and metadata.rookie_year exist on raw Sleeper but are not canonical frame fields",
            "no draft_round/overall_pick in cached player payload",
            "do not implement rookie evidence weights until draft capital is ingested",
        ],
    }
    path = out_dir / "audit-summary.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"wrote": str(path), "verdict": report["verdict"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
