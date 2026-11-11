"""Multi-team trade engine: grade a 3-to-6-team trade for every team.

There is no new valuation model here. A multi-team trade is a transfer matrix
(``modules.multi_team_trade``); for each participating roster this runs the SAME
per-team pipeline the two-team Trade Analyzer runs for one seat:

* the team's own posture (``trade_hub_engine.roster_posture``; a declared
  Team Situation for the requester's own roster) and its age curve / pick price,
* the roster-full check (``drop_candidates.plan_trade_overflow``),
* ``trade_analyzer_fit.evaluate_trade_analyzer_fit`` (market delta, consolidation
  adjustment, ``trade_lineup_model`` lineup effect, posture weighting, needs),
* ``trade_offer_analyzer.decide_offer_verdict`` for the band, confidence and
  reasons,

with ``send_assets`` = what that team sends (to anyone) and ``receive_assets`` =
what it receives (from anyone). A two-team transfer matrix therefore grades each
seat exactly as the legacy endpoint would grade it.

On top, ``multi_team_trade.summarize`` reads the league level (most hurt team,
best-to-worst spread, who wins / loses) and, when asked, ``trade_veto`` gives
each team's veto risk. Counter-offer search is not part of this module.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Mapping

import pandas as pd

from modules import (
    drop_candidates,
    league_rankings,
    league_value_settings,
    model_status,
    sleeper,
    trade_analyzer_fit,
    trade_grade,
    trade_ideas as trade_ideas_module,
    trade_offer_analyzer,
    trade_veto,
)
from modules import multi_team_trade as mt
from modules import roster_value_model
from modules.trade_analyzer_assembly import pick_asset_from_mapping, player_asset_from_mapping
from modules.trade_hub_engine import (
    apply_strategy_age_curve,
    roster_posture,
    strategy_adjusted_pick_score_multiplier,
)

logger = logging.getLogger("fantasygm.multi_team_trade")

# hook(frame, transfer_player_ids) -> frame, applied to each team's strategy-adjusted
# frame (keeper surplus, IDP rows). Lets the API layer add its inputs without this
# module knowing about them.
FrameHook = Callable[[pd.DataFrame, set[str]], pd.DataFrame]


def _fail(status: str, headline: str, **extra: Any) -> dict[str, Any]:
    return {"status": status, "headline": headline, **extra}


def _asset_public(asset: Mapping[str, Any]) -> dict[str, Any]:
    is_pick = asset.get("asset_type") == "pick"
    return {
        "type": "pick" if is_pick else "player",
        "id": str(asset.get("pick_id") if is_pick else asset.get("player_id")),
        "label": str(asset.get("label") or asset.get("name") or ""),
        "position": str(asset.get("position") or ""),
        "team": str(asset.get("team") or ""),
        "age": asset.get("age"),
        "score": int(asset.get("score") or 0),
    }


def _team_names(league_id: str, roster_ids: list[str]) -> dict[str, str]:
    try:
        profiles = sleeper.get_league_roster_profiles(league_id) or {}
    except Exception:
        profiles = {}
    names: dict[str, str] = {}
    for rid in roster_ids:
        prof = profiles.get(rid) or (profiles.get(int(rid)) if rid.isdigit() else None) or {}
        names[rid] = str(prof.get("team_name") or prof.get("owner_name") or f"Team {rid}")
    return names


def _why(
    *,
    name: str,
    verdict: Mapping[str, Any],
    market_delta: int,
    ppw: float,
    sends: list[dict[str, Any]],
    receives: list[dict[str, Any]],
    overflow: Mapping[str, Any] | None,
) -> list[dict[str, str]]:
    """Multi-factor reasons for one team: where the assets go and come from, the
    market, the lineup, the roster fit, the team's direction, and the risk."""

    out: list[dict[str, str]] = []

    def add(factor: str, text: Any) -> None:
        text = str(text or "").strip()
        if text:
            out.append({"factor": factor, "text": text})

    if sends or receives:
        got = ", ".join(f"{a['label']} (from {a['from_team_name']})" for a in receives) or "nothing"
        gave = ", ".join(f"{a['label']} (to {a['to_team_name']})" for a in sends) or "nothing"
        add("flows", f"{name} receives {got} and sends {gave}.")
    add("market", verdict.get("value_summary"))
    if abs(ppw) >= 0.5:
        direction = "gains" if ppw > 0 else "loses"
        add("lineup", f"{name}'s lineup {direction} about {abs(ppw):.1f} points a week.")
    add("lineup", verdict.get("roster_summary"))
    for warning in verdict.get("lineup_warnings") or ():
        add("lineup", warning.get("message") or warning.get("text") or warning.get("title"))
    if overflow and overflow.get("need"):
        add("roster_fit", f"{name} would be over the roster limit by {overflow['need']} and has to cut to fit.")
    add("posture", verdict.get("posture_note"))
    add("posture", verdict.get("strategy_summary"))
    add("risk", verdict.get("risk_summary"))
    return out


def analyze_multi_team_trade(
    *,
    league_id: str,
    transfers: list[Mapping[str, Any]],
    lens: str,
    players_db_path: str,
    perspective_roster_id: str = "",
    min_teams: int = mt.MIN_TEAMS,
    max_teams: int = mt.MAX_TEAMS,
    frame_hook: FrameHook | None = None,
    posture_override: Callable[[Mapping[str, Any]], dict[str, Any] | None] | None = None,
    untouchable_provider: Callable[[str], Callable[[], set[str] | None]] | None = None,
    usage_provider: Callable[[Any], Mapping[str, Mapping[str, Any]]] | None = None,
    crowd_class_strength_by_year: Mapping[Any, Any] | None = None,
    include_veto: bool = False,
    status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Grade a multi-team trade for every participant (see module docstring).

    Returns ``{"status": "ok", "teams": [...], "summary": {...}, "flows": [...]}``
    or ``{"status": <invalid|unavailable>, "headline", "errors"?}`` for every
    non-verdict outcome (never raises for a bad request).

    Hooks (all optional): ``frame_hook`` adds keeper/IDP inputs to each team's
    frame; ``posture_override(roster)`` returns the posture for rosters the
    caller knows better than the auto classification (the requester's declared
    Team Situation); ``untouchable_provider(roster_id)`` returns the protected
    player ids for that roster's forced-cut plan (only the requester has any);
    ``usage_provider`` feeds the forced-cut plan's usage guard."""

    status = status if status is not None else model_status.ok()
    parsed, shape_errors = mt.parse_transfers(transfers)
    if shape_errors:
        return _fail("invalid", shape_errors[0]["message"], errors=shape_errors)
    teams_in_trade = mt.participants(parsed)
    # Cheap structural checks first: nothing is fetched for a request that can
    # never be valid (too many teams / assets, empty).
    early = [
        e for e in mt.validate_transfers(
            parsed, roster_players={r: () for r in teams_in_trade}, pick_owners=None,
            min_teams=min_teams, max_teams=max_teams,
        )
        if e["code"] in {mt.ERR_EMPTY, mt.ERR_TOO_FEW, mt.ERR_TOO_MANY, mt.ERR_TOO_MANY_TRANSFERS,
                         mt.ERR_SAME_TEAM, mt.ERR_DUPLICATE}
    ]
    if early:
        return _fail("invalid", early[0]["message"], errors=early)

    league = sleeper.get_league(league_id)
    if not league:
        return _fail("unavailable", "League not found.")
    settings = league_value_settings.detect_league_value_settings_from_payload(league)
    rosters = sleeper.get_rosters(league_id) or []
    by_rid = {str(r.get("roster_id")): r for r in rosters}
    if perspective_roster_id and str(perspective_roster_id) not in by_rid:
        return _fail("invalid", "The perspective team is not in this league.")

    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=lens, players_db_path=players_db_path
    )
    if valued.empty:
        return _fail("unavailable", "Player values are not ready yet.")
    score_field = league_value_settings.valuation_score_field(lens)

    # Ownership (players from the rosters; picks from the league's pick table).
    pick_transfers = [t for t in parsed if t.asset_type == mt.ASSET_PICK]
    pick_by_id: dict[str, Mapping[str, Any]] = {}
    if pick_transfers:
        df_summary, _capital = league_rankings.build_league_summary_and_draft_capital_cached(
            league_id=league_id, lens=lens, players_db_path=players_db_path
        )
        if df_summary.empty:
            return _fail("unavailable", "Draft pick data is not ready yet.")
        picks = trade_ideas_module.list_draft_pick_assets(
            league_id, df_summary, league_settings=dict(settings),
            **({"crowd_class_strength_by_year": crowd_class_strength_by_year} if crowd_class_strength_by_year else {}),
        )
        pick_by_id = {f"{p.get('season')}:{p.get('round')}:{p.get('original_roster_id')}": p for p in picks}
    errors = mt.validate_transfers(
        parsed,
        roster_players={rid: r.get("players") or () for rid, r in by_rid.items()},
        pick_owners={pid: str(p.get("owner_roster_id")) for pid, p in pick_by_id.items()} if pick_transfers else None,
        min_teams=min_teams, max_teams=max_teams,
    )
    if errors:
        return _fail("invalid", errors[0]["message"], errors=errors)

    transfer_player_ids = {t.asset_id for t in parsed if t.asset_type == mt.ASSET_PLAYER}
    names = _team_names(league_id, teams_in_trade)
    rankings_frame = league_rankings.build_league_rankings_frame_cached(
        league_id=league_id, lens=lens, players_db_path=players_db_path
    )
    postures: dict[str, dict[str, Any]] = {}
    for rid in teams_in_trade:
        override = posture_override(by_rid[rid]) if posture_override else None
        postures[rid] = override or roster_posture(
            league_id=league_id, roster=by_rid[rid], lens=lens, players_db_path=players_db_path,
            rankings_frame=rankings_frame,
        )
    strategies = {rid: str(p.get("key") or "retool") for rid, p in postures.items()}

    # One need / surplus model over the neutral league frame (as the Analyzer does).
    base_frame = frame_hook(valued, transfer_player_ids) if frame_hook else valued
    needs = roster_value_model.league_needs(
        valued=base_frame, rosters=rosters, league=league, settings=settings, score_field=score_field, status=status,
    )
    model_status.merge_into(status, needs.status)
    window = trade_grade.season_window(settings)
    rostered_ids = {str(pid) for r in rosters for pid in (r.get("players") or []) if pid is not None}

    team_rows: list[dict[str, Any]] = []
    for rid in teams_in_trade:
        strategy = strategies[rid]
        frame = apply_strategy_age_curve(valued, strategy, score_field)
        if frame_hook:
            frame = frame_hook(frame, transfer_player_ids)
        try:
            pool = trade_grade.league_waiver_pool(rosters, frame)
        except Exception:
            pool = None
        my_ids = {str(p) for p in (by_rid[rid].get("players") or []) if p is not None}
        frame, pool = trade_grade.attach_projection_baselines(
            frame, pool, my_ids | transfer_player_ids, score_field, lineup_settings=settings
        )
        team_df = frame[frame["player_id"].astype(str).isin(my_ids)].copy()
        if team_df.empty:
            return _fail("unavailable", f"{names[rid]}'s roster could not be read.")

        pick_mult = strategy_adjusted_pick_score_multiplier(1.0, strategy)
        out_edges, in_edges = mt.outgoing(parsed, rid), mt.incoming(parsed, rid)

        def build(edges: list[mt.Transfer], *, side: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
            assets: list[dict[str, Any]] = []
            annotated: list[dict[str, Any]] = []
            for edge in edges:
                if edge.asset_type == mt.ASSET_PLAYER:
                    rows = frame[frame["player_id"].astype(str) == edge.asset_id]
                    if rows.empty:
                        return [], []
                    asset = player_asset_from_mapping(rows.iloc[0], score_field=score_field)
                else:
                    asset = pick_asset_from_mapping(pick_by_id[edge.asset_id], pick_score_multiplier=pick_mult)
                assets.append(asset)
                other = edge.to_roster if side == "out" else edge.from_roster
                annotated.append({
                    **_asset_public(asset),
                    ("to_roster_id" if side == "out" else "from_roster_id"): other,
                    ("to_team_name" if side == "out" else "from_team_name"): names[other],
                })
            return assets, annotated

        send_assets, sends_public = build(out_edges, side="out")
        receive_assets, receives_public = build(in_edges, side="in")
        if len(send_assets) != len(out_edges) or len(receive_assets) != len(in_edges):
            return _fail("unavailable", "A player in the trade has no value data yet.")

        send_ids = [a["player_id"] for a in send_assets if a.get("asset_type") == "player"]
        receive_ids = [a["player_id"] for a in receive_assets if a.get("asset_type") == "player"]
        values = pd.to_numeric(
            frame[frame["player_id"].astype(str).isin(rostered_ids)][score_field], errors="coerce"
        ).dropna().tolist()
        overflow = None
        try:
            overflow = drop_candidates.plan_trade_overflow(
                my_team_df=team_df, all_players_df=frame, waiver_df=pool, my_roster=by_rid[rid], league=league,
                settings=settings, score_field=score_field, strategy=strategy, window=window,
                league_rostered_values=values, send_player_ids=send_ids, receive_player_ids=receive_ids,
                untouchable_provider=(untouchable_provider(rid) if untouchable_provider else (lambda: set())),
                usage_provider=usage_provider or (lambda _rvc: {}),
                status=status,
            )
        except model_status.LOOKUP_ERRORS:
            logger.warning("roster-full check failed (league=%s roster=%s)", league_id, rid, exc_info=True)
            model_status.add(status, "drop_model_failed")

        fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
            my_team_df=team_df, all_players_df=frame, send_assets=send_assets, receive_assets=receive_assets,
            metrics=None, strategy=strategy, lineup_settings=settings, score_field=score_field, waiver_df=pool,
            posture=postures[rid], forced_drop_assets=(overflow or {}).get("forced_assets") or None,
            team_needs=needs.for_roster(rid),
        )
        if not fit or not fit.get("available"):
            return _fail("unavailable", f"{names[rid]}'s side of the trade could not be graded.")
        model_status.merge_into(status, fit.get("model_status"))
        verdict = trade_offer_analyzer.decide_offer_verdict(
            fit, send_assets=send_assets, receive_assets=receive_assets, partner_assets=[], waiver_options={}
        ).to_public_dict()

        lineup = verdict.get("lineup_model") or {}
        points = lineup.get("points") or {}
        ppw = float(points.get("per_week_delta") or 0.0)
        market = int(verdict.get("value_delta") or 0)
        positions = lineup.get("positions") or {}
        worst = min(positions.items(), key=lambda kv: kv[1].get("per_week_delta", 0.0), default=None)
        posture = postures[rid]
        team_rows.append({
            "roster_id": rid,
            "team_name": names[rid],
            "is_perspective": rid == str(perspective_roster_id),
            "sends": sends_public,
            "receives": receives_public,
            "verdict": verdict,
            "trade_score": int(verdict.get("trade_score") or 0),
            "market_delta": market,
            "lineup_delta": {
                "per_week": ppw,
                "ros": points.get("ros_delta"),
                "worst_position": lineup.get("worst_position"),
            },
            "tone": verdict.get("tone"),
            "color_token": trade_value_color(verdict.get("tone")),
            "outcome": mt.outcome_for_tone(verdict.get("tone")),
            "posture": {
                "key": strategy,
                "group": posture.get("group") or "retool",
                "label": posture.get("label") or "",
                "source": posture.get("source") or "",
                "record": posture.get("record") or "",
                "standing": posture.get("standing") or "",
            },
            "roster_overflow": drop_candidates.public_overflow(overflow),
            "why": _why(
                name=names[rid], verdict=verdict, market_delta=market, ppw=ppw,
                sends=sends_public, receives=receives_public, overflow=overflow,
            ),
            # internal: feeds the veto read below, removed before returning
            "_veto_side": {
                "roster_id": rid, "team_name": names[rid], "market_delta": market,
                "team_score": int(verdict.get("trade_score") or 0), "points_per_week": ppw,
                "posture": strategy, "posture_group": posture.get("group") or "retool",
                "worst_position": (
                    {"position": worst[0], "per_week_delta": float(worst[1].get("per_week_delta", 0.0))}
                    if worst else None
                ),
            },
        })

    veto_sides = [t["_veto_side"] for t in team_rows]
    veto = trade_veto.assess_each(veto_sides) if include_veto else {}
    for t in team_rows:
        t.pop("_veto_side")
        t["veto_risk"] = veto.get(t["roster_id"]) if include_veto else None
    # Requester's seat first, then the order the trade named the teams.
    team_rows.sort(key=lambda t: 0 if t["is_perspective"] else 1)

    flows = [
        {**t.to_public(), "from_team_name": names[t.from_roster], "to_team_name": names[t.to_roster]}
        for t in parsed
    ]
    return {
        "status": "ok",
        "team_count": len(team_rows),
        "teams": team_rows,
        "flows": flows,
        "summary": mt.summarize(team_rows, perspective_roster_id),
        "veto_summary": trade_veto.assess(veto_sides) if include_veto else None,
        "model_status": status,
    }


def trade_value_color(tone: Any) -> str:
    from modules import trade_value_bands

    return trade_value_bands.COLOR_TOKEN_BY_TONE.get(str(tone or "fair"), "neutral")
