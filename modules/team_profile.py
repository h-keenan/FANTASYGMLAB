"""One shared per-league team profile: what we know about EVERY team, built once.

Assembly only, no new math and no new valuation. Each field comes from the
module that already owns it:

* posture     canonical refined classifier (``modules.league_rankings``)
* age         ``modules.age_profile`` (the one age curve) over the valued frame
* needs       ``modules.roster_value_model.league_needs`` (the one need table)
* picks       ``modules.trade_ideas._build_roster_pick_assets`` (values, projected
              slots) plus ``modules.pick_flow`` (picks bought / sold)
* tendency    ``modules.manager_tendencies`` (min-sample gated) and
              ``modules.team_trade_history`` (the simple buyer / seller lean)

Nothing consumes the profile's tendency block yet (it is attached for the
trade-idea work that follows); no endpoint exposes it, so the Pro gate on
manager-level text is untouched. Declared Team Situation is per user, not per
team, so it is not in the profile: ``trade_posture.resolve_posture`` still layers
the declared stance over ``posture.key`` for the user's own roster.

Cached like the rankings frame (``swr_cache.redis_swr_cache``, Redis single
flight, keyed by the league-state fingerprint) so every consumer in a window
shares one build. A missing input never reads as "fine": it adds a code to
``model_status`` and leaves that block empty.

Kill switch: ``DYNASTYGM_TEAM_PROFILE`` (default ON) only gates the cached
front door; the pure builder is always available."""

from __future__ import annotations

import logging
from typing import Any, Iterable, Mapping

import pandas as pd

from modules import (
    age_profile,
    experimental_graduation,
    league_rankings,
    league_value_settings,
    model_status,
    redis_cache,
    roster_value_model,
    sleeper,
    swr_cache,
)

logger = logging.getLogger("fantasygm.team_profile")

TEAM_PROFILE_ENV_KEY = "DYNASTYGM_TEAM_PROFILE"
PROFILE_VERSION = 1
FRESH_TTL_SECONDS = 120
STALE_TTL_SECONDS = 1800
LOCK_TIMEOUT_SECONDS = 20.0
# The "core" for the age-weighted average: the roster's most valuable players.
CORE_SIZE = 12
AGE_POSITIONS = ("QB", "RB", "WR", "TE")


def enabled() -> bool:
    return experimental_graduation.graduated_kill_switch_enabled(TEAM_PROFILE_ENV_KEY, default=True)


def _num(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if out == out else default


def _clean(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "item"):
        try:
            value = value.item()
        except Exception:
            pass
    if isinstance(value, float) and value != value:
        return None
    return value


def build_age_block(team_df: pd.DataFrame, score_field: str) -> dict[str, Any]:
    """Roster avg / median age, the value-weighted core age, per-position phase
    mix, and the cliff / rising player ids (all through ``age_profile``)."""

    empty = {
        "avg": None,
        "median": None,
        "core_avg": None,
        "by_position": {},
        "cliff_ids": [],
        "rising_ids": [],
        "phase_counts": {},
    }
    if team_df is None or team_df.empty or "age" not in team_df.columns:
        return empty
    frame = team_df.copy()
    frame["_age"] = pd.to_numeric(frame["age"], errors="coerce")
    frame = frame[(frame["_age"] > 0) & (frame["_age"] <= age_profile.MAX_KNOWN_AGE)]
    if frame.empty:
        return empty
    field = score_field if score_field in frame.columns else "dynasty_score"
    frame["_score"] = pd.to_numeric(frame.get(field), errors="coerce").fillna(0.0) if field in frame.columns else 0.0
    frame["_pos"] = frame["position"].astype(str).str.upper() if "position" in frame.columns else ""
    frame["_phase"] = [age_profile.phase(p, a) for p, a in zip(frame["_pos"], frame["_age"])]
    frame = frame.sort_values("_score", ascending=False)

    core = frame.head(CORE_SIZE)
    weight = float(core["_score"].clip(lower=0).sum())
    core_avg = (
        float((core["_age"] * core["_score"].clip(lower=0)).sum() / weight) if weight > 0 else float(core["_age"].mean())
    )
    by_position: dict[str, Any] = {}
    for pos in AGE_POSITIONS:
        sub = frame[frame["_pos"] == pos]
        if sub.empty:
            continue
        counts = sub["_phase"].value_counts().to_dict()
        left = [age_profile.prime_years_left(pos, a) for a in sub["_age"]]
        left = [v for v in left if v is not None]
        by_position[pos] = {
            "count": int(len(sub)),
            "avg": round(float(sub["_age"].mean()), 1),
            "phase_mix": {k: int(v) for k, v in counts.items()},
            "prime_years_left_avg": round(sum(left) / len(left), 1) if left else None,
        }
    ids = frame["player_id"].astype(str) if "player_id" in frame.columns else pd.Series([], dtype=str)
    return {
        "avg": round(float(frame["_age"].mean()), 2),
        "median": round(float(frame["_age"].median()), 2),
        "core_avg": round(core_avg, 2),
        "by_position": by_position,
        "cliff_ids": [str(i) for i in ids[frame["_phase"] == "cliff"].tolist()],
        "rising_ids": [str(i) for i in ids[frame["_phase"] == "rising"].tolist()],
        "phase_counts": {k: int(v) for k, v in frame["_phase"].value_counts().to_dict().items()},
    }


def build_picks_block(
    assets: Iterable[Mapping[str, Any]], flow: Mapping[str, Any] | None, capitals: list[int]
) -> dict[str, Any]:
    items = [
        {
            "season": a.get("season"),
            "round": a.get("round"),
            "original_roster_id": a.get("original_roster_id"),
            "slot": a.get("projected_slot_label"),
            "slot_number": a.get("projected_slot_number"),
            "value": int(a.get("score") or 0),
        }
        for a in assets or ()
        if a.get("asset_type") == "pick"
    ]
    total = sum(i["value"] for i in items)
    tier = "middle"
    if capitals:
        series = pd.Series(capitals, dtype="float64")
        if total <= float(series.quantile(0.25)):
            tier = "low"
        elif total >= float(series.quantile(0.75)):
            tier = "high"
    return {
        "assets": items,
        "capital": total,
        "tier": tier,
        "count": len(items),
        "firsts": sum(1 for i in items if int(i.get("round") or 0) == 1),
        "flow": dict(flow or {}),
    }


def build_team_profiles(
    *,
    league_id: str,
    lens: str,
    valued: pd.DataFrame,
    rosters: list[Mapping[str, Any]],
    rankings_frame: pd.DataFrame,
    league_needs: "roster_value_model.LeagueNeeds | None",
    pick_assets_by_owner: Mapping[int, list[Mapping[str, Any]]] | None,
    pick_flow: Mapping[Any, Mapping[str, Any]] | None,
    trade_leans: Mapping[Any, Mapping[str, Any]] | None,
    manager_profile: Mapping[str, Any] | None,
    score_field: str,
    status: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Pure assembly of the league's team profiles from already-built inputs."""

    league_status = model_status.merge(status)
    frame_rows: dict[str, Mapping[str, Any]] = {}
    if rankings_frame is not None and not rankings_frame.empty:
        for _, row in rankings_frame.iterrows():
            frame_rows[str(row.get("roster_id"))] = row.to_dict()
    else:
        model_status.merge_into(league_status, model_status.from_codes(["team_profile_rankings_missing"]))

    players = valued
    if players is not None and not players.empty and "player_id" in players.columns:
        players = players.assign(_pid=players["player_id"].astype(str))
    capitals = [
        sum(int(a.get("score") or 0) for a in (assets or ()) if a.get("asset_type") == "pick")
        for assets in (pick_assets_by_owner or {}).values()
    ]
    managers = (manager_profile or {}).get("managers") or {}

    teams: dict[str, Any] = {}
    avgs: list[float] = []
    for roster in rosters:
        rid = str(roster.get("roster_id"))
        owned = {str(p) for p in (roster.get("players") or []) if p is not None}
        team_df = (
            players[players["_pid"].isin(owned)] if players is not None and not players.empty and "_pid" in players else pd.DataFrame()
        )
        row = frame_rows.get(rid, {})
        age = build_age_block(team_df, score_field)
        if age["avg"] is not None:
            avgs.append(float(age["avg"]))
        needs_row = league_needs.for_roster(rid) if league_needs is not None else None
        needs_status = model_status.ok()
        if needs_row is None:
            needs_status = model_status.from_codes(["team_profile_needs_missing"])
        need_list: list[str] = []
        surplus: dict[str, list[str]] = {}
        coverage: Any = {}
        if needs_row:
            from modules.roster_needs import assessment_from_model, room_records

            assessment = assessment_from_model(needs_row, status=league_needs.status if league_needs else None)
            need_list = [str(p).upper() for p in assessment.true_needs]
            coverage = room_records(needs_row)
            surplus = {
                str(item["position"]): [str(pid) for pid in item.get("surplus_player_ids") or ()]
                for item in (needs_row.get("positions") or ())
                if item.get("surplus_player_ids")
            }
        try:
            rid_int = int(rid)
        except ValueError:
            rid_int = -1
        manager = managers.get(rid_int) or managers.get(rid) or {}
        lean = (trade_leans or {}).get(rid_int) or {}
        teams[rid] = {
            "roster_id": rid,
            "team_name": _clean(row.get("team_name")),
            "posture": {
                "key": _clean(row.get("strategy")) or None,
                "label": _clean(row.get("strategy_label")) or None,
                "archetype": _clean(row.get("archetype_label")) or None,
                "power_rank": _clean(row.get("power_rank")),
                "source": "auto_canonical" if league_rankings.canonical_posture_enabled() else "auto_legacy",
            },
            "age": age,
            "needs": {"needs": need_list, "surplus_ids": surplus, "room_coverage": coverage, "model_status": needs_status},
            "picks": build_picks_block((pick_assets_by_owner or {}).get(rid_int), (pick_flow or {}).get(rid_int), capitals),
            "tendency": {
                "lean": _clean(lean.get("tendency")),
                "buy_count": int(lean.get("buy_count") or 0),
                "sell_count": int(lean.get("sell_count") or 0),
                "manager_status": _clean(manager.get("status")),
                "sample": _clean(manager.get("sample")),
                "labels": {k: v.get("label") for k, v in (manager.get("signals") or {}).items()} if manager else {},
            },
        }
    league_age = {
        "mean": round(sum(avgs) / len(avgs), 2) if avgs else None,
        "median": round(float(pd.Series(avgs).median()), 2) if avgs else None,
    }
    for rid, team in teams.items():
        avg = team["age"]["avg"]
        team["age"]["league_rank"] = (
            1 + sum(1 for other in avgs if avg is not None and other < avg) if avg is not None else None
        )
    return {
        "version": PROFILE_VERSION,
        "league_id": league_id,
        "lens": lens,
        "league": {"age": league_age, "team_count": len(teams)},
        "teams": teams,
        "model_status": league_status,
    }


def _compute(league_id: str, lens: str, players_db_path: str, _fingerprint: str) -> dict[str, Any]:
    """Gather the cached inputs (each already shared and cached elsewhere) and assemble."""

    from modules import manager_tendencies, pick_flow, team_trade_history, trade_ideas

    league = sleeper.get_league(league_id) or {}
    settings = league_value_settings.detect_league_value_settings_from_payload(league)
    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=lens, players_db_path=players_db_path
    )
    rosters = sleeper.get_rosters(league_id) or []
    if valued.empty or not rosters:
        return {
            "version": PROFILE_VERSION,
            "league_id": league_id,
            "lens": lens,
            "league": {},
            "teams": {},
            "model_status": model_status.from_codes(["team_profile_inputs_missing"]),
        }
    score_field = league_value_settings.valuation_score_field(lens)
    status = model_status.ok()
    rankings_frame = league_rankings.build_league_rankings_frame_cached(
        league_id=league_id, lens=lens, players_db_path=players_db_path
    )
    df_summary, _capital = league_rankings.build_league_summary_and_draft_capital_cached(
        league_id=league_id, lens=lens, players_db_path=players_db_path
    )
    needs = roster_value_model.league_needs(
        valued=valued, rosters=rosters, league=league, settings=settings, score_field=score_field, status=status
    )

    def guarded(code: str, fn, default):
        try:
            return fn()
        except Exception:
            logger.warning("team profile input %s unavailable (league=%s)", code, league_id, exc_info=True)
            model_status.merge_into(status, model_status.from_codes([code]))
            return default

    picks = guarded(
        "team_profile_picks_unavailable",
        lambda: trade_ideas._build_roster_pick_assets(league_id, rosters, df_summary, league_settings=settings),
        {},
    )
    flow = guarded("team_profile_pick_flow_unavailable", lambda: pick_flow.league_pick_flow_counts_cached(league_id), {})
    leans = guarded(
        "team_profile_trade_leans_unavailable",
        lambda: team_trade_history.league_trade_tendencies_cached(league_id, players_db_path),
        {},
    )
    managers = guarded(
        "team_profile_manager_tendencies_unavailable", lambda: manager_tendencies.league_tendencies_cached(league_id), {}
    )
    return build_team_profiles(
        league_id=league_id,
        lens=lens,
        valued=valued,
        rosters=rosters,
        rankings_frame=rankings_frame,
        league_needs=needs,
        pick_assets_by_owner=picks,
        pick_flow=flow,
        trade_leans=leans,
        manager_profile=managers,
        score_field=score_field,
        status=status,
    )


def league_team_profiles_cached(*, league_id: str, lens: str, players_db_path: str) -> dict[str, Any]:
    """The league's team profiles, built once per (league, lens, league state) and shared.

    Returns ``{"teams": {}, ...}`` with a ``model_status`` code when the switch
    is off or the build fails: callers fall back to today's behaviour."""

    if not enabled():
        return {"version": PROFILE_VERSION, "league_id": league_id, "lens": lens, "teams": {},
                "model_status": model_status.from_codes(["team_profile_disabled"])}
    fingerprint = (
        f"{league_value_settings.league_state_fingerprint(league_id, players_db_path)}"
        f"|posture={int(league_rankings.canonical_posture_enabled())}|age={int(age_profile.enabled())}|v={PROFILE_VERSION}"
    )
    key = (league_id, lens, players_db_path, fingerprint)
    try:
        return swr_cache.redis_swr_cache(
            cache_key=redis_cache.build_cache_key("league_team_profiles", *key),
            fresh_ttl_seconds=FRESH_TTL_SECONDS,
            stale_ttl_seconds=STALE_TTL_SECONDS,
            compute=lambda: _compute(*key),
            lock_timeout_seconds=LOCK_TIMEOUT_SECONDS,
        )
    except Exception:
        logger.warning("team profile build failed (league=%s)", league_id, exc_info=True)
        return {"version": PROFILE_VERSION, "league_id": league_id, "lens": lens, "teams": {},
                "model_status": model_status.from_codes(["team_profile_failed"])}
