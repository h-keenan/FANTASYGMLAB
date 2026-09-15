"""Trade Analyzer fit engine: roster-specific accept/decline/counter inputs.

Extracted from `app.py` so the mobile API can share the exact same fit
computation as the web app instead of re-deriving it — see the repository's
existing "share one engine" precedent in `services/mobile_api_service.py`
and `modules/league_value_settings.py`. This is a pure code move: no
scoring thresholds, component weights, or guardrails changed. `app.py`
re-exports every name here unchanged.

`evaluate_trade_analyzer_fit` is the entry point: given a roster, the full
player pool, a proposed send/receive package, and league/lineup settings,
it returns the `fit` mapping that `modules.trade_offer_analyzer.
decide_offer_verdict` consumes to produce the accept/decline/counter
verdict. Does not invent a new fit formula or retune anything — same rule
as `modules/canonical_player_ranking.py` and `modules/league_value_settings.py`.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from modules import runtime_trace
from modules import trade_visual_language
from modules.league_value_settings import DEFAULT_LEAGUE_VALUE_SETTINGS, _safe_float
from modules.league_workspace_ui import _format_score
from modules.rankings import injury_level, is_injury_status, summarize_team_injuries
from modules.roster_needs import TeamNeedsAssessment, assess_team_needs
from modules.team_eval import (
    normalize_team_strategy,
    suggest_optimal_lineup,
    team_strategy_label,
)


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except Exception:
        pass
    return str(value)


@runtime_trace.traced("roster_normalization", phase="roster_normalization")
def normalize_player_ids(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "player_id" not in df.columns:
        return df
    df = df.copy()
    df["player_id"] = df["player_id"].astype(str)
    return df


def score_asset_value(asset) -> int:
    try:
        return int(asset.get("score", asset.get("value_score", 0)) or 0)
    except Exception:
        return 0


def strategy_trade_result_note(strategy: str) -> str:
    strategy_key = normalize_team_strategy(strategy)
    if strategy_key == "contender":
        return "Contender lens: prioritizes current points, elite starters, and useful consolidation while discounting future picks slightly."
    if strategy_key == "fringe_contender":
        return "Fringe contender lens: favors lineup upgrades, but keeps enough future flexibility to avoid getting trapped in the middle."
    if strategy_key == "rebuild":
        return "Rebuild lens: prioritizes youth and draft capital, and discounts aging veterans unless the value gap is strong."
    if strategy_key == "tank":
        return "Tank/Rebuild lens: heavily prioritizes picks, young players, and future value over short-term production."
    return "Retool lens: balances current production with future value, so picks and young starters keep meaningful weight."


def trade_value_verdict(score: int) -> str:
    return trade_visual_language.trade_value_band(score)


def _lineup_depth_thresholds(league_settings: dict | None = None) -> dict[str, int]:
    settings = dict(DEFAULT_LEAGUE_VALUE_SETTINGS)
    settings.update(league_settings or {})
    qb_count = max(1, int(settings.get("qb_count") or 1))
    superflex_count = max(0, int(settings.get("superflex_count") or 0))
    flex_count = max(0, int(settings.get("flex_count") or 0))
    return {
        "QB": qb_count + (1 if superflex_count > 0 else 0),
        "RB": max(2, int(settings.get("rb_count") or 2) + (1 if flex_count > 0 else 0)),
        "WR": max(3, int(settings.get("wr_count") or 3) + (1 if flex_count > 0 else 0)),
        "TE": max(1, int(settings.get("te_count") or 1)),
    }


def _team_position_counts(df_team: pd.DataFrame) -> dict[str, int]:
    if df_team is None or df_team.empty or "position" not in df_team.columns:
        return {pos: 0 for pos in ["QB", "RB", "WR", "TE"]}
    counts = (
        df_team["position"]
        .fillna("")
        .astype(str)
        .str.upper()
        .value_counts()
        .to_dict()
    )
    return {pos: int(counts.get(pos, 0)) for pos in ["QB", "RB", "WR", "TE"]}


def _starter_lineup_snapshot(
    team_df: pd.DataFrame,
    score_field: str,
    lineup_settings: dict | None = None,
) -> dict | None:
    if team_df is None or team_df.empty:
        return {
            "lineup_df": pd.DataFrame(),
            "starter_score": 0.0,
            "starter_count": 0,
            "position_scores": {pos: 0.0 for pos in ["QB", "RB", "WR", "TE", "K"]},
        }

    if score_field in team_df.columns:
        resolved_score_field = score_field
    elif "value_score" in team_df.columns:
        resolved_score_field = "value_score"
    elif "dynasty_score" in team_df.columns:
        resolved_score_field = "dynasty_score"
    else:
        return None

    lineup_df = suggest_optimal_lineup(
        team_df.copy(), lineup_settings, score_field=resolved_score_field
    )
    if lineup_df.empty or "suggested_starter" not in lineup_df.columns:
        return None

    starters = lineup_df[lineup_df["suggested_starter"].fillna(False)].copy()
    starter_scores = pd.to_numeric(starters[resolved_score_field], errors="coerce").fillna(0)
    position_scores: dict[str, float] = {}
    for pos in ["QB", "RB", "WR", "TE", "K"]:
        pos_scores = starter_scores[starters["position"].astype(str).str.upper() == pos]
        position_scores[pos] = float(pos_scores.sum()) if not pos_scores.empty else 0.0

    return {
        "lineup_df": lineup_df,
        "starter_score": float(starter_scores.sum()),
        "starter_count": int(len(starters)),
        "position_scores": position_scores,
        "score_field": resolved_score_field,
    }


def _simulate_post_trade_roster(
    my_team_df: pd.DataFrame,
    all_players_df: pd.DataFrame,
    send_assets: list[dict],
    receive_assets: list[dict],
) -> pd.DataFrame:
    if my_team_df is None:
        return pd.DataFrame()

    current = normalize_player_ids(my_team_df.copy())
    if "player_id" not in current.columns:
        return current
    current["player_id"] = current["player_id"].astype(str)

    send_ids = {
        str(asset.get("player_id") or "")
        for asset in send_assets or []
        if asset.get("asset_type") == "player" and asset.get("player_id")
    }
    receive_ids = {
        str(asset.get("player_id") or "")
        for asset in receive_assets or []
        if asset.get("asset_type") == "player" and asset.get("player_id")
    }

    post_df = current[~current["player_id"].isin(send_ids)].copy()
    if not receive_ids:
        return post_df.reset_index(drop=True)

    player_pool = normalize_player_ids(all_players_df.copy()) if all_players_df is not None else pd.DataFrame()
    if not player_pool.empty and "player_id" in player_pool.columns:
        player_pool["player_id"] = player_pool["player_id"].astype(str)
        receive_df = player_pool[player_pool["player_id"].isin(receive_ids)].copy()
    else:
        receive_df = pd.DataFrame()

    if receive_df.empty:
        fallback_rows = []
        template_columns = list(post_df.columns)
        for asset in receive_assets or []:
            if asset.get("asset_type") != "player":
                continue
            row = {column: None for column in template_columns}
            row.update(
                {
                    "player_id": str(asset.get("player_id") or ""),
                    "name": _safe_text(asset.get("name") or asset.get("label"), "Player"),
                    "position": _safe_text(asset.get("position")).upper(),
                    "team": _safe_text(asset.get("team")),
                    "status": _safe_text(asset.get("status")),
                    "injury_status": _safe_text(asset.get("injury_status")),
                    "age": asset.get("age"),
                    "value_score": _safe_float(asset.get("value_score"), 0),
                    "dynasty_score": _safe_float(asset.get("score"), 0),
                    "rebuild_score": _safe_float(asset.get("score"), 0),
                    "score": _safe_float(asset.get("score"), 0),
                }
            )
            fallback_rows.append(row)
        receive_df = pd.DataFrame(fallback_rows)

    if receive_df.empty:
        return post_df.reset_index(drop=True)

    post_df = pd.concat([post_df, receive_df], ignore_index=True, sort=False)
    post_df["player_id"] = post_df["player_id"].astype(str)
    post_df = post_df.drop_duplicates(subset=["player_id"], keep="last")
    return post_df.reset_index(drop=True)


def roster_injury_context(
    roster_df: pd.DataFrame,
    lineup_df: pd.DataFrame | None = None,
) -> dict:
    return summarize_team_injuries(roster_df, lineup_df)


def build_team_needs_assessment(
    roster_df: pd.DataFrame,
    metrics: dict | None,
    league_settings: dict | None = None,
    *,
    lineup_df: pd.DataFrame | None = None,
    score_field: str | None = None,
) -> TeamNeedsAssessment:
    """Build one immutable assessment from an already-loaded roster context."""

    settings = dict(DEFAULT_LEAGUE_VALUE_SETTINGS)
    settings.update(league_settings or {})
    resolved_lineup = (
        lineup_df
        if lineup_df is not None
        else suggest_optimal_lineup(roster_df, settings, score_field=score_field)
    )
    return assess_team_needs(
        roster_df,
        resolved_lineup,
        settings,
        relative_weaknesses=list((metrics or {}).get("weaknesses", []) or []),
    )


def get_needed_positions(
    my_team_df: pd.DataFrame,
    metrics: dict | None,
    league_settings: dict | None = None,
    *,
    include_fallback: bool = True,
    assessment: TeamNeedsAssessment | None = None,
    lineup_df: pd.DataFrame | None = None,
) -> list[str]:
    """Return the legacy position list derived from a canonical assessment."""

    resolved_assessment = assessment or build_team_needs_assessment(
        my_team_df,
        metrics,
        league_settings,
        lineup_df=lineup_df,
    )
    ordered_positions = list(resolved_assessment.true_needs)
    if include_fallback:
        ordered_positions.extend(resolved_assessment.upgrade_opportunities)
        ordered_positions.extend(resolved_assessment.future_risks)
    return list(dict.fromkeys(ordered_positions))[:4]


def evaluate_trade_analyzer_fit(
    my_team_df: pd.DataFrame,
    all_players_df: pd.DataFrame,
    send_assets: list[dict],
    receive_assets: list[dict],
    metrics: dict | None,
    strategy: str,
    lineup_settings: dict | None,
    score_field: str,
) -> dict | None:
    if my_team_df is None or my_team_df.empty:
        return None
    if not send_assets and not receive_assets:
        return None

    score_column = (
        "value_score"
        if "value_score" in my_team_df.columns
        else score_field
        if score_field in my_team_df.columns
        else "dynasty_score"
    )
    if score_column not in my_team_df.columns:
        return None

    current_snapshot = _starter_lineup_snapshot(my_team_df, score_column, lineup_settings)
    post_team_df = _simulate_post_trade_roster(my_team_df, all_players_df, send_assets, receive_assets)
    post_snapshot = _starter_lineup_snapshot(post_team_df, score_column, lineup_settings)
    if not current_snapshot or not post_snapshot:
        return None

    value_delta = int(sum(score_asset_value(asset) for asset in receive_assets) - sum(score_asset_value(asset) for asset in send_assets))
    lineup_delta = int(round(float(post_snapshot["starter_score"]) - float(current_snapshot["starter_score"])))

    strategy_key = normalize_team_strategy(strategy)
    current_needs = get_needed_positions(
        my_team_df,
        metrics,
        lineup_settings,
        include_fallback=False,
    )
    need_set = {str(pos).upper() for pos in current_needs}
    strength_set = {str(pos).upper() for pos in (metrics or {}).get("strengths", []) or []}

    send_positions = {
        str(asset.get("position") or "").upper()
        for asset in send_assets or []
        if asset.get("asset_type") == "player"
    }
    receive_positions = {
        str(asset.get("position") or "").upper()
        for asset in receive_assets or []
        if asset.get("asset_type") == "player"
    }
    filled_needs = sorted(pos for pos in receive_positions & need_set if pos)
    exposed_needs = sorted(pos for pos in (send_positions & need_set) - receive_positions if pos)
    surplus_moves = sorted(pos for pos in send_positions & strength_set if pos)

    current_counts = _team_position_counts(my_team_df)
    post_counts = _team_position_counts(post_team_df)
    depth_thresholds = _lineup_depth_thresholds(lineup_settings)
    depth_losses = [
        pos
        for pos in ["QB", "RB", "WR", "TE"]
        if post_counts.get(pos, 0) < current_counts.get(pos, 0)
        and post_counts.get(pos, 0) < depth_thresholds.get(pos, 0)
    ]

    position_deltas = {}
    for pos in ["QB", "RB", "WR", "TE", "K"]:
        before = float(current_snapshot["position_scores"].get(pos, 0.0))
        after = float(post_snapshot["position_scores"].get(pos, 0.0))
        position_deltas[pos] = int(round(after - before))
    improved_positions = [
        pos
        for pos, delta in sorted(position_deltas.items(), key=lambda item: item[1], reverse=True)
        if delta >= 120
    ]
    weakened_positions = [
        pos
        for pos, delta in sorted(position_deltas.items(), key=lambda item: item[1])
        if delta <= -120
    ]

    current_avg_age = pd.to_numeric(my_team_df.get("age", pd.Series(dtype="float64")), errors="coerce").dropna()
    post_avg_age = pd.to_numeric(post_team_df.get("age", pd.Series(dtype="float64")), errors="coerce").dropna()
    current_age = float(current_avg_age.mean()) if not current_avg_age.empty else None
    new_age = float(post_avg_age.mean()) if not post_avg_age.empty else None
    age_delta = (new_age - current_age) if current_age is not None and new_age is not None else None

    current_lineup_df = current_snapshot.get("lineup_df", pd.DataFrame())
    post_lineup_df = post_snapshot.get("lineup_df", pd.DataFrame())
    current_starters = (
        current_lineup_df[current_lineup_df["suggested_starter"].fillna(False)].copy()
        if not current_lineup_df.empty and "suggested_starter" in current_lineup_df.columns
        else pd.DataFrame()
    )
    post_starters = (
        post_lineup_df[post_lineup_df["suggested_starter"].fillna(False)].copy()
        if not post_lineup_df.empty and "suggested_starter" in post_lineup_df.columns
        else pd.DataFrame()
    )
    current_health_ctx = roster_injury_context(my_team_df, current_lineup_df)
    post_health_ctx = roster_injury_context(post_team_df, post_lineup_df)
    current_injured_starters = int(current_health_ctx.get("injured_starters") or 0)
    post_injured_starters = int(post_health_ctx.get("injured_starters") or 0)
    current_injury_burden = float(current_health_ctx.get("injury_burden") or 0.0)
    post_injury_burden = float(post_health_ctx.get("injury_burden") or 0.0)
    current_health_flag = _safe_text(current_health_ctx.get("health_flag"), "Stable")
    post_health_flag = _safe_text(post_health_ctx.get("health_flag"), "Stable")
    current_injury_positions = (
        {
            str(pos).upper()
            for pos in (current_health_ctx.get("injured_positions") or [])
            if str(pos).upper()
        }
    )
    send_healthy_positions = {
        str(asset.get("position") or "").upper()
        for asset in send_assets or []
        if asset.get("asset_type") == "player" and not is_injury_status(asset)
    }
    receive_healthy_positions = {
        str(asset.get("position") or "").upper()
        for asset in receive_assets or []
        if asset.get("asset_type") == "player" and not is_injury_status(asset)
    }
    receive_injury_levels = [
        injury_level(asset.get("status"), asset.get("injury_status"))
        for asset in receive_assets or []
        if asset.get("asset_type") == "player"
    ]
    incoming_major_injuries = sum(1 for level in receive_injury_levels if level == "major")
    incoming_moderate_injuries = sum(1 for level in receive_injury_levels if level == "moderate")
    injury_reinforcements = sorted(pos for pos in receive_healthy_positions & current_injury_positions if pos)
    injury_exposure = sorted(pos for pos in send_healthy_positions & current_injury_positions if pos)

    send_pick_value = int(sum(score_asset_value(asset) for asset in send_assets if asset.get("asset_type") == "pick"))
    receive_pick_value = int(sum(score_asset_value(asset) for asset in receive_assets if asset.get("asset_type") == "pick"))
    send_pick_count = sum(1 for asset in send_assets if asset.get("asset_type") == "pick")
    receive_pick_count = sum(1 for asset in receive_assets if asset.get("asset_type") == "pick")

    value_component = 2 if value_delta >= 700 else 1 if value_delta >= 150 else 0 if value_delta > -250 else -1 if value_delta > -1000 else -2
    lineup_component = 2 if lineup_delta >= 500 else 1 if lineup_delta >= 120 else 0 if lineup_delta > -120 else -1 if lineup_delta > -500 else -2
    need_component = min(2, len(filled_needs)) - min(2, len(exposed_needs) + len(depth_losses))
    if surplus_moves:
        need_component = min(2, need_component + 1)

    age_component = 0
    if age_delta is not None:
        if strategy_key in {"rebuild", "tank"}:
            if age_delta <= -0.4:
                age_component = 2
            elif age_delta < 0:
                age_component = 1
            elif age_delta >= 0.5:
                age_component = -2
            elif age_delta > 0:
                age_component = -1
        elif strategy_key in {"contender", "fringe_contender"}:
            if lineup_delta >= 120 and age_delta <= 0.6:
                age_component = 1
            elif age_delta >= 0.8 and lineup_delta <= 0:
                age_component = -1
        else:
            if age_delta <= -0.35:
                age_component = 1
            elif age_delta >= 0.75 and lineup_delta <= 0:
                age_component = -1

    draft_component = 0
    if send_pick_count or receive_pick_count:
        pick_delta = receive_pick_value - send_pick_value
        if strategy_key in {"rebuild", "tank"}:
            if pick_delta > 0:
                draft_component = 2
            elif pick_delta < 0:
                draft_component = -2
        elif strategy_key in {"contender", "fringe_contender"}:
            if send_pick_value > 0 and lineup_delta >= 120:
                draft_component = 1
            elif receive_pick_value > send_pick_value and lineup_delta <= 0:
                draft_component = -1
        else:
            if pick_delta > 0:
                draft_component = 1
            elif pick_delta < 0 and lineup_delta <= 0:
                draft_component = -1

    strategy_component = 0
    if strategy_key in {"contender", "fringe_contender"}:
        if lineup_delta >= 120:
            strategy_component += 2
        if filled_needs:
            strategy_component += 1
        if depth_losses or exposed_needs:
            strategy_component -= 2
        if receive_pick_count > send_pick_count and lineup_delta <= 0:
            strategy_component -= 1
    elif strategy_key in {"rebuild", "tank"}:
        if receive_pick_value > send_pick_value:
            strategy_component += 2
        if age_delta is not None and age_delta < 0:
            strategy_component += 1
        if send_pick_value > receive_pick_value:
            strategy_component -= 2
        if lineup_delta <= -500 and receive_pick_value <= send_pick_value:
            strategy_component -= 1
    else:
        if filled_needs:
            strategy_component += 1
        if lineup_delta >= 120:
            strategy_component += 1
        if age_delta is not None and age_delta < 0:
            strategy_component += 1
        if depth_losses:
            strategy_component -= 1

    injury_component = 0
    if post_injured_starters < current_injured_starters:
        injury_component += min(2, current_injured_starters - post_injured_starters)
    elif post_injured_starters > current_injured_starters:
        injury_component -= min(2, post_injured_starters - current_injured_starters)
    if injury_reinforcements:
        injury_component += 1
    if injury_exposure:
        injury_component -= 1
    if strategy_key in {"contender", "fringe_contender"}:
        injury_component -= (incoming_major_injuries * 2) + incoming_moderate_injuries
    elif strategy_key == "retool":
        injury_component -= incoming_major_injuries
    else:
        injury_component -= max(0, incoming_major_injuries - 1)
    injury_burden_delta = post_injury_burden - current_injury_burden

    fit_total = (
        value_component
        + lineup_component
        + need_component
        + age_component
        + draft_component
        + strategy_component
        + injury_component
    )
    if fit_total >= 5:
        roster_fit_verdict = "Strong Fit"
    elif fit_total >= 2:
        roster_fit_verdict = "Helpful Fit"
    elif fit_total >= 0:
        roster_fit_verdict = "Mixed Fit"
    elif fit_total >= -2:
        roster_fit_verdict = "Risky Fit"
    else:
        roster_fit_verdict = "Poor Fit"

    if not send_positions and not receive_positions:
        lineup_summary = "No direct starter-lineup change because only draft capital moves."
    else:
        if lineup_delta >= 120:
            lineup_summary = f"Starter lineup improves by +{_format_score(lineup_delta)}."
        elif lineup_delta <= -120:
            lineup_summary = f"Starter lineup drops by {_format_score(abs(lineup_delta))}."
        else:
            lineup_summary = "Starter lineup stays close to neutral."
        if improved_positions:
            lineup_summary += f" Biggest lift: {' / '.join(improved_positions[:2])}."
        if weakened_positions:
            lineup_summary += f" Weakest hit: {' / '.join(weakened_positions[:2])}."
        if depth_losses:
            lineup_summary += f" Depth gets thinner at {' / '.join(depth_losses[:2])}."
        if current_injured_starters > post_injured_starters:
            lineup_summary += f" Injury pressure eases from {current_injured_starters} to {post_injured_starters} injured starters."
        elif post_injured_starters > current_injured_starters:
            lineup_summary += f" Injury pressure rises to {post_injured_starters} injured starters."
        elif injury_reinforcements:
            lineup_summary += f" Adds healthy cover at {' / '.join(injury_reinforcements[:2])}."

    strategy_parts = []
    if strategy_key in {"contender", "fringe_contender"}:
        strategy_parts.append("Contender-friendly" if strategy_component >= 1 else "Mixed contender fit" if strategy_component >= 0 else "Poor contender fit")
        if filled_needs:
            strategy_parts.append(f"fills {' / '.join(filled_needs[:2])} need")
        if send_pick_value > 0 and lineup_delta >= 120:
            strategy_parts.append("uses future capital to improve now")
        elif receive_pick_value > send_pick_value:
            strategy_parts.append("keeps more future flexibility")
        if injury_reinforcements:
            strategy_parts.append(f"adds healthy cover at {' / '.join(injury_reinforcements[:2])}")
        elif incoming_major_injuries:
            strategy_parts.append("takes on injured production")
    elif strategy_key in {"rebuild", "tank"}:
        strategy_parts.append("Rebuild-friendly" if strategy_component >= 1 else "Mixed rebuild fit" if strategy_component >= 0 else "Poor rebuild fit")
        if receive_pick_value > send_pick_value:
            strategy_parts.append("adds future draft capital")
        if age_delta is not None and age_delta < 0:
            strategy_parts.append("gets the roster younger")
        elif age_delta is not None and age_delta > 0.4:
            strategy_parts.append("pushes the roster older")
        if incoming_major_injuries and receive_pick_value > send_pick_value:
            strategy_parts.append("can absorb a longer injury timeline")
    else:
        strategy_parts.append("Retool-friendly" if strategy_component >= 1 else "Mixed retool fit" if strategy_component >= 0 else "Poor retool fit")
        if filled_needs:
            strategy_parts.append(f"addresses {' / '.join(filled_needs[:2])}")
        if age_delta is not None and age_delta < 0:
            strategy_parts.append("keeps the future outlook healthier")
        if injury_reinforcements:
            strategy_parts.append("stabilizes injury depth")
    strategy_fit_label = strategy_parts[0] if strategy_parts else team_strategy_label(strategy)
    strategy_summary = ". ".join(
        part[:1].upper() + part[1:] if idx == 0 and part else part
        for idx, part in enumerate(strategy_parts)
        if part
    )
    if strategy_summary and not strategy_summary.endswith("."):
        strategy_summary += "."
    if not strategy_summary:
        strategy_summary = strategy_trade_result_note(strategy)

    positives = []
    negatives = []
    if value_delta > 0:
        positives.append("wins on raw value")
    if lineup_delta > 0:
        positives.append("improves the starting lineup")
    if filled_needs:
        positives.append(f"helps at {' / '.join(filled_needs[:2])}")
    if receive_pick_value > send_pick_value:
        positives.append("adds future capital")
    if age_delta is not None and age_delta < 0:
        positives.append("gets a bit younger")
    if injury_reinforcements or post_injured_starters < current_injured_starters:
        positives.append("improves injury cover")

    if value_delta < 0:
        negatives.append("pays a raw-value premium")
    if lineup_delta < 0:
        negatives.append("costs starter strength")
    if exposed_needs:
        negatives.append(f"moves from a weak {' / '.join(exposed_needs[:2])} room")
    if depth_losses:
        negatives.append(f"thins {' / '.join(depth_losses[:2])} depth")
    if send_pick_value > receive_pick_value:
        negatives.append("spends future draft capital")
    if age_delta is not None and age_delta > 0.6:
        negatives.append("ages the roster up")
    if incoming_major_injuries or incoming_moderate_injuries:
        negatives.append("brings back injured production")
    if injury_exposure:
        negatives.append(f"removes healthy cover at {' / '.join(injury_exposure[:2])}")

    if positives and negatives:
        explanation = f"Helps because it {', '.join(positives[:2])}, but it also {', '.join(negatives[:2])}."
    elif positives:
        explanation = f"Helps because it {', '.join(positives[:3])}."
    elif negatives:
        explanation = f"Hurts because it {', '.join(negatives[:3])}."
    else:
        explanation = "This is mostly a value-level reshuffle without a strong roster-fit swing."

    injury_summary_parts = []
    if injury_reinforcements:
        injury_summary_parts.append(f"adds healthy cover at {' / '.join(injury_reinforcements[:2])}")
    if injury_exposure:
        injury_summary_parts.append(f"removes healthy cover at {' / '.join(injury_exposure[:2])}")
    if incoming_major_injuries:
        injury_summary_parts.append(
            f"acquires {incoming_major_injuries} major injury risk{'s' if incoming_major_injuries != 1 else ''}"
        )
    elif incoming_moderate_injuries:
        injury_summary_parts.append(
            f"acquires {incoming_moderate_injuries} shorter-term injury risk{'s' if incoming_moderate_injuries != 1 else ''}"
        )
    if post_injury_burden <= current_injury_burden - 1.0:
        injury_summary = (
            f"Injury risk improves from {current_health_flag} to {post_health_flag}. "
            + (", ".join(injury_summary_parts) if injury_summary_parts else "The roster comes out healthier overall.")
            + "."
        )
    elif post_injury_burden >= current_injury_burden + 1.0:
        injury_summary = (
            f"Injury risk rises from {current_health_flag} to {post_health_flag}. "
            + (", ".join(injury_summary_parts) if injury_summary_parts else "The return adds more health volatility than it removes.")
            + "."
        )
    elif injury_summary_parts:
        injury_summary = (
            "Health context: "
            + ", ".join(injury_summary_parts)
            + "."
        )
    else:
        injury_summary = "Health context stays close to neutral."

    return {
        "available": True,
        "value_delta": value_delta,
        "value_verdict": trade_value_verdict(value_delta),
        "roster_fit_verdict": roster_fit_verdict,
        "lineup_delta": lineup_delta,
        "lineup_summary": lineup_summary,
        "strategy_fit_label": strategy_fit_label,
        "strategy_summary": strategy_summary,
        "injury_summary": injury_summary,
        "explanation": explanation,
        "component_scores": {
            "value": value_component,
            "lineup": lineup_component,
            "needs": need_component,
            "age": age_component,
            "draft": draft_component,
            "strategy": strategy_component,
            "injury": injury_component,
        },
        "injury_burden_delta": injury_burden_delta,
    }
