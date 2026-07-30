from typing import Dict, Any, List, Optional

import pandas as pd

from modules import runtime_trace
from modules.sleeper import get_league_roster_profiles
from modules.platforms.sleeper import get_sleeper_adapter

STARTER_SLOTS = {
    "QB": 1,
    "RB": 2,
    "WR": 3,
    "TE": 1,
    "FLEX": 1,
    "WR/RB": 1,
    "SUPER_FLEX": 0,
    "K": 0,
}
BENCH_WEIGHT = 0.18
MAX_BENCH_PLAYERS = 4
TEAM_STRATEGY_LABELS = {
    "contender": "Contender",
    "fringe_contender": "Fringe Contender",
    "retool": "Retool",
    "rebuild": "Rebuild",
    "tank": "Tank/Rebuild",
}
TEAM_STRATEGY_MODE_MAP = {
    "contender": "contender",
    "fringe_contender": "competitive",
    "retool": "competitive",
    "rebuild": "rebuild",
    "tank": "rebuild",
}


def normalize_team_strategy(value, default: str = "retool") -> str:
    raw = str(value or "").strip().lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "auto": "",
        "competitive": "retool",
        "middle": "retool",
        "fringe": "fringe_contender",
        "fringe_contender": "fringe_contender",
        "tank_rebuild": "tank",
        "tank/rebuild": "tank",
        "tanking": "tank",
    }
    strategy = aliases.get(raw, raw)
    if strategy in TEAM_STRATEGY_LABELS:
        return strategy
    return default if default in TEAM_STRATEGY_LABELS else "retool"


def team_strategy_label(value) -> str:
    return TEAM_STRATEGY_LABELS.get(normalize_team_strategy(value), "Retool")


def team_strategy_mode(value) -> str:
    return TEAM_STRATEGY_MODE_MAP.get(normalize_team_strategy(value), "competitive")


def _safe_int(value, default: int = 0) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed


def _safe_float(value, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        return default
    return parsed


def _lineup_slots(lineup_settings: Optional[Dict[str, Any]] = None) -> Dict[str, int]:
    if not lineup_settings:
        return dict(STARTER_SLOTS)

    slots = dict(STARTER_SLOTS)
    slots["QB"] = max(1, _safe_int(lineup_settings.get("qb_count"), slots["QB"]))
    slots["RB"] = max(0, _safe_int(lineup_settings.get("rb_count"), slots["RB"]))
    slots["WR"] = max(0, _safe_int(lineup_settings.get("wr_count"), slots["WR"]))
    slots["TE"] = max(0, _safe_int(lineup_settings.get("te_count"), slots["TE"]))
    slots["FLEX"] = max(0, _safe_int(lineup_settings.get("regular_flex_count"), _safe_int(lineup_settings.get("flex_count"), slots["FLEX"])))
    slots["WR/RB"] = max(0, _safe_int(lineup_settings.get("wrrb_flex_count"), 0))
    slots["SUPER_FLEX"] = max(0, _safe_int(lineup_settings.get("superflex_count"), 0))
    if str(lineup_settings.get("qb_format") or "") == "2QB":
        slots["QB"] = max(2, slots["QB"])
    elif str(lineup_settings.get("qb_format") or "") == "Superflex":
        slots["SUPER_FLEX"] = max(1, slots["SUPER_FLEX"])
    slots["K"] = max(0, _safe_int(lineup_settings.get("k_count"), slots.get("K", 0)))
    return slots


def _bench_score_limit(lineup_settings: Optional[Dict[str, Any]] = None) -> int:
    if not lineup_settings:
        return MAX_BENCH_PLAYERS
    bench_count = _safe_int(lineup_settings.get("bench_count"), 0)
    taxi_count = _safe_int(lineup_settings.get("taxi_count"), 0)
    ir_count = _safe_int(lineup_settings.get("ir_count"), 0)
    reserve_count = bench_count + taxi_count + ir_count
    if reserve_count <= 0:
        return MAX_BENCH_PLAYERS
    return max(2, min(reserve_count, 10))


def _empty_summary_row(
    league_id: str, roster_id: int, owner_id: str, team_name: str
) -> Dict[str, Any]:
    return {
        "league_id": league_id,
        "roster_id": roster_id,
        "owner_id": owner_id,
        "team_name": team_name,
        "owner_name": team_name,
        "avatar_url": "",
        "total_score": 0.0,
        "starter_score": 0.0,
        "bench_score": 0.0,
        "current_roster_score": 0.0,
        "raw_roster_score": 0.0,
        "avg_age": None,
        "qb_score": 0.0,
        "rb_score": 0.0,
        "wr_score": 0.0,
        "te_score": 0.0,
        "mode": "unknown",
        "strategy": "retool",
        "strategy_label": "Retool",
    }


def _classify_team_strategy(score_percentile: float, avg_age, age_median) -> str:
    try:
        pct = float(score_percentile)
    except Exception:
        pct = 0.5

    age_delta = 0.0
    try:
        if pd.notna(avg_age) and pd.notna(age_median):
            age_delta = float(avg_age) - float(age_median)
    except Exception:
        age_delta = 0.0

    if pct >= 0.82:
        return "contender"
    if pct >= 0.62:
        return "retool" if age_delta >= 1.25 else "fringe_contender"
    if pct >= 0.38:
        return "retool"
    if pct >= 0.18:
        return "tank" if age_delta >= 1.0 else "rebuild"
    return "tank"


def _score_starter_weighted_roster(
    df_team: pd.DataFrame,
    score_field: str = "dynasty_score",
    lineup_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    if df_team.empty:
        return {
            "total_score": 0.0,
            "starter_score": 0.0,
            "bench_score": 0.0,
            "raw_roster_score": 0.0,
            "qb_score": 0.0,
            "rb_score": 0.0,
            "wr_score": 0.0,
            "te_score": 0.0,
        }

    df = df_team.copy()
    score_field = score_field if score_field in df.columns else "dynasty_score"
    df[score_field] = pd.to_numeric(df[score_field], errors="coerce").fillna(0)
    df = df.sort_values(score_field, ascending=False).reset_index(drop=True)
    slots = _lineup_slots(lineup_settings)
    used_idx = set()
    starter_idx = []

    def pick_for_pos(pos: str, limit: int) -> None:
        for idx in df.index[df["position"] == pos].tolist():
            if len([i for i in starter_idx if df.loc[i, "position"] == pos]) >= limit:
                break
            if idx not in used_idx:
                used_idx.add(idx)
                starter_idx.append(idx)

    pick_for_pos("QB", slots["QB"])
    pick_for_pos("RB", slots["RB"])
    pick_for_pos("WR", slots["WR"])
    pick_for_pos("TE", slots["TE"])
    pick_for_pos("K", slots.get("K", 0))

    flex_candidates = [
        idx
        for idx in df.index
        if df.loc[idx, "position"] in ["RB", "WR", "TE"] and idx not in used_idx
    ]
    for idx in flex_candidates[: slots["FLEX"]]:
        used_idx.add(idx)
        starter_idx.append(idx)

    superflex_candidates = [
        idx
        for idx in df.index
        if df.loc[idx, "position"] in ["QB", "RB", "WR", "TE"] and idx not in used_idx
    ]
    for idx in superflex_candidates[: slots.get("SUPER_FLEX", 0)]:
        used_idx.add(idx)
        starter_idx.append(idx)

    wrrb_candidates = [
        idx
        for idx in df.index
        if df.loc[idx, "position"] in ["RB", "WR"] and idx not in used_idx
    ]
    for idx in wrrb_candidates[: slots["WR/RB"]]:
        used_idx.add(idx)
        starter_idx.append(idx)

    starter_mask = df.index.isin(starter_idx)
    bench_mask = ~starter_mask
    starter_score = float(df.loc[starter_mask, score_field].sum())
    bench_scores = df.loc[bench_mask, score_field].nlargest(_bench_score_limit(lineup_settings))
    raw_bench_score = float(df.loc[bench_mask, score_field].sum())
    bench_score = float(bench_scores.sum()) * BENCH_WEIGHT

    weighted_scores = df[score_field].where(starter_mask, df[score_field] * BENCH_WEIGHT)

    def pos_score(pos: str) -> float:
        mask = df["position"] == pos
        if not mask.any():
            return 0.0
        return float(weighted_scores.loc[mask].sum())

    return {
        "total_score": starter_score + bench_score,
        "starter_score": starter_score,
        "bench_score": bench_score,
        "raw_roster_score": float(df[score_field].sum()),
        "qb_score": pos_score("QB"),
        "rb_score": pos_score("RB"),
        "wr_score": pos_score("WR"),
        "te_score": pos_score("TE"),
    }


@runtime_trace.traced("suggest_optimal_lineup", phase="lineup_generation")
def suggest_optimal_lineup(
    df_team: pd.DataFrame,
    lineup_settings: Optional[Dict[str, Any]] = None,
) -> pd.DataFrame:
    if df_team.empty:
        return df_team.assign(slot="BENCH", suggested_starter=False)

    df = df_team.copy()
    df["sort_score"] = df["value_score"] if "value_score" in df.columns else df["dynasty_score"]
    df["sort_score"] = pd.to_numeric(df["sort_score"], errors="coerce").fillna(0)
    df = df.sort_values("sort_score", ascending=False).reset_index(drop=True)

    slots = _lineup_slots(lineup_settings)

    used_idx = set()

    def pick_for_pos(pos, limit):
        idxs = df.index[df["position"] == pos].tolist()
        chosen = []
        for i in idxs:
            if len(chosen) >= limit:
                break
            if i not in used_idx:
                chosen.append(i)
                used_idx.add(i)
        return chosen

    qb_idx = pick_for_pos("QB", slots["QB"])
    rb_idx = pick_for_pos("RB", slots["RB"])
    wr_idx = pick_for_pos("WR", slots["WR"])
    te_idx = pick_for_pos("TE", slots["TE"])
    k_idx = pick_for_pos("K", slots["K"])

    flex_candidates = [
        i
        for i in df.index
        if df.loc[i, "position"] in ["RB", "WR", "TE"] and i not in used_idx
    ]
    flex_idx = []
    for i in flex_candidates:
        if len(flex_idx) >= slots["FLEX"]:
            break
        flex_idx.append(i)
        used_idx.add(i)

    superflex_candidates = [
        i
        for i in df.index
        if df.loc[i, "position"] in ["QB", "RB", "WR", "TE"] and i not in used_idx
    ]
    superflex_idx = []
    for i in superflex_candidates:
        if len(superflex_idx) >= slots.get("SUPER_FLEX", 0):
            break
        superflex_idx.append(i)
        used_idx.add(i)

    wrrb_candidates = [
        i
        for i in df.index
        if df.loc[i, "position"] in ["RB", "WR"] and i not in used_idx
    ]
    wrrb_idx = []
    for i in wrrb_candidates:
        if len(wrrb_idx) >= slots["WR/RB"]:
            break
        wrrb_idx.append(i)
        used_idx.add(i)

    df["slot"] = "BENCH"
    df.loc[qb_idx, "slot"] = "QB"
    df.loc[rb_idx, "slot"] = "RB"
    df.loc[wr_idx, "slot"] = "WR"
    df.loc[te_idx, "slot"] = "TE"
    df.loc[flex_idx, "slot"] = "FLEX"
    df.loc[superflex_idx, "slot"] = "SUPER_FLEX"
    df.loc[wrrb_idx, "slot"] = "WR/RB"
    df.loc[k_idx, "slot"] = "K"

    df["suggested_starter"] = df["slot"] != "BENCH"
    return df


@runtime_trace.traced("build_league_summary", phase="league_summary")
def build_league_summary(
    df_players: pd.DataFrame,
    league_id: str,
    score_field: str = "dynasty_score",
    current_score_field: str = "value_score",
    lineup_settings: Optional[Dict[str, Any]] = None,
    adapter=None,
) -> pd.DataFrame:
    """
    Build a per-team summary for a Sleeper league.
    """
    df_players = df_players.copy()
    if "player_id" in df_players.columns:
        df_players["player_id"] = df_players["player_id"].astype(str)

    platform_adapter = adapter or get_sleeper_adapter()
    rosters = platform_adapter.get_rosters(league_id)
    users = platform_adapter.get_users(league_id)

    if not rosters or not users:
        return pd.DataFrame()

    user_map: Dict[str, str] = {}
    for u in users:
        name = u.get("display_name") or u.get("username") or "Unknown"
        user_map[u.get("user_id")] = name
    roster_profiles = get_league_roster_profiles(league_id)

    rows: List[Dict[str, Any]] = []
    players_by_id = df_players.set_index("player_id")

    # First pass: build rows with a starter-weighted total score and raw depth.
    for r in rosters:
        roster_id = r.get("roster_id")
        owner_id = r.get("owner_id")
        profile = roster_profiles.get(str(roster_id), {})
        team_name = profile.get("team_name") or user_map.get(owner_id, f"Team {roster_id}")
        owner_name = profile.get("owner_name") or user_map.get(owner_id, f"Team {roster_id}")
        avatar_url = profile.get("avatar_url", "")

        player_ids = r.get("players") or []
        if not isinstance(player_ids, list):
            player_ids = []
        player_ids = [str(pid) for pid in player_ids]

        if not player_ids:
            rows.append(_empty_summary_row(league_id, roster_id, owner_id, team_name))
            continue

        df_team = players_by_id.loc[
            players_by_id.index.isin(player_ids)
        ].copy()

        if df_team.empty:
            rows.append(_empty_summary_row(league_id, roster_id, owner_id, team_name))
            continue

        current_scores = _score_starter_weighted_roster(df_team, current_score_field, lineup_settings)
        long_term_scores = _score_starter_weighted_roster(df_team, score_field, lineup_settings)
        avg_age = float(df_team["age"].mean()) if df_team["age"].notna().any() else None

        rows.append(
            {
                "league_id": league_id,
                "roster_id": roster_id,
                "owner_id": owner_id,
                "team_name": team_name,
                "owner_name": owner_name,
                "avatar_url": avatar_url,
                "total_score": current_scores["total_score"],
                "starter_score": current_scores["starter_score"],
                "bench_score": current_scores["bench_score"],
                "current_roster_score": current_scores["raw_roster_score"],
                "raw_roster_score": long_term_scores["raw_roster_score"],
                "avg_age": avg_age,
                "qb_score": current_scores["qb_score"],
                "rb_score": current_scores["rb_score"],
                "wr_score": current_scores["wr_score"],
                "te_score": current_scores["te_score"],
                "mode": "unknown",  # filled later
                "strategy": "retool",
                "strategy_label": "Retool",
            }
        )

    df_summary = pd.DataFrame.from_records(rows)

    if df_summary.empty:
        return df_summary

    # Second pass: classify strategy using score percentile with age as a tie-breaker.
    score_percentiles = df_summary["total_score"].rank(pct=True, method="average")
    age_median = df_summary["avg_age"].median(skipna=True)

    modes = []
    strategies = []
    strategy_labels = []
    for idx, row in df_summary.iterrows():
        strategy = _classify_team_strategy(
            float(score_percentiles.loc[idx]),
            row.get("avg_age"),
            age_median,
        )
        strategies.append(strategy)
        strategy_labels.append(team_strategy_label(strategy))
        modes.append(team_strategy_mode(strategy))

    df_summary["mode"] = modes
    df_summary["strategy"] = strategies
    df_summary["strategy_label"] = strategy_labels

    df_summary = _assign_team_rankings(df_summary)
    return df_summary


def _assign_team_rankings(df_summary: pd.DataFrame) -> pd.DataFrame:
    if df_summary.empty:
        return df_summary

    df_summary = df_summary.copy()
    df_summary["rank"] = (
        df_summary["total_score"]
        .rank(method="dense", ascending=False)
        .astype(int)
    )
    if len(df_summary) > 1:
        max_rank = int(df_summary["rank"].max())
        df_summary["percentile"] = (
            ((max_rank - df_summary["rank"]) / max_rank) * 100
        ).round(1)
    else:
        df_summary["percentile"] = 100.0

    return df_summary


@runtime_trace.traced("get_team_vs_league", phase="league_summary")
def get_team_vs_league(
    df_summary: pd.DataFrame, my_roster_id: int
) -> Optional[Dict[str, Any]]:
    if df_summary.empty:
        return None

    roster_ids = pd.to_numeric(df_summary["roster_id"], errors="coerce")
    target_roster_id = pd.to_numeric(pd.Series([my_roster_id]), errors="coerce").iloc[0]
    if pd.notna(target_roster_id):
        team_row = df_summary[roster_ids == target_roster_id]
    else:
        team_row = df_summary[df_summary["roster_id"].astype(str) == str(my_roster_id)]
    if team_row.empty:
        return None

    t = team_row.iloc[0]

    league_score_mean = float(df_summary["total_score"].mean())
    raw_league_age_mean = df_summary["avg_age"].mean(skipna=True)
    league_age_mean = (
        float(raw_league_age_mean) if pd.notna(raw_league_age_mean) else None
    )
    raw_avg_age = t["avg_age"]

    metrics: Dict[str, Any] = {
        "total_score": float(t["total_score"]),
        "avg_age": float(raw_avg_age) if pd.notna(raw_avg_age) else None,
        "league_score_mean": league_score_mean,
        "league_age_mean": league_age_mean,
        "mode": t["mode"],
        "strategy": normalize_team_strategy(t.get("strategy", t["mode"])),
        "strategy_label": t.get(
            "strategy_label",
            team_strategy_label(t.get("strategy", t["mode"])),
        ),
        "strengths": [],
        "weaknesses": [],
    }

    for field, default in {
        "injured_count": 0,
        "major_absences": 0,
        "injured_starters": 0,
        "injured_bench_players": 0,
        "major_injury_count": 0,
        "major_injured_starters": 0,
        "injury_risk_total": 0.0,
        "injury_burden": 0.0,
        "injury_impact_score": 0.0,
        "injury_value_impact": 0.0,
        "injury_impact_flag": "Health Status Uncertain",
        "injury_data_quality": "uncertain",
        "injury_data_note": "Injury data quality could not be confirmed.",
        "health_flag": "Stable",
        "key_injuries_summary": "",
        "top_injury_impact_summary": "",
        "top_injury_impact_players": [],
        "top_heavy_ratio": 0.0,
        "archetype": "",
        "archetype_label": "",
        "archetype_explanation": "",
        "archetype_strengths": [],
        "archetype_risks": [],
        "archetype_recommendations": [],
        "starter_rank": None,
        "bench_rank": None,
        "roster_value_rank": None,
        "age_rank": None,
        "draft_capital_rank": None,
    }.items():
        if field not in t.index:
            metrics[field] = default
            continue
        value = t.get(field)
        if isinstance(value, list):
            metrics[field] = value
            continue
        if pd.isna(value):
            metrics[field] = default
        else:
            metrics[field] = value

    for pos in ["qb", "rb", "wr", "te"]:
        col = f"{pos}_score"
        team_pos = float(t[col])
        league_pos = float(df_summary[col].mean())
        delta = team_pos - league_pos
        threshold = max(500.0, abs(league_pos) * 0.12)
        if delta >= threshold:
            metrics["strengths"].append(pos.upper())
        elif delta <= -threshold:
            metrics["weaknesses"].append(pos.upper())

    return metrics


def _normalized_rank_strength(series: pd.Series, ascending: bool = False) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if numeric.empty:
        return pd.Series(dtype="float64")

    valid = numeric.notna()
    if not valid.any():
        return pd.Series(0.5, index=numeric.index, dtype="float64")

    ranked = numeric[valid].rank(method="dense", ascending=ascending)
    max_rank = float(ranked.max() or 1.0)
    if max_rank <= 1:
        strengths = pd.Series(1.0, index=ranked.index, dtype="float64")
    else:
        strengths = ((max_rank - ranked) / (max_rank - 1.0)).clip(lower=0.0, upper=1.0)

    result = pd.Series(0.5, index=numeric.index, dtype="float64")
    result.loc[valid] = strengths
    return result


def _rank_strength(
    df: pd.DataFrame,
    rank_col: str,
    raw_col: str,
    *,
    raw_ascending: bool = False,
) -> pd.Series:
    if rank_col in df.columns:
        # League rank columns are created with 1 = best / strongest, so lower
        # numeric ranks should map to stronger normalized signals.
        return _normalized_rank_strength(df[rank_col], ascending=True)
    if raw_col in df.columns:
        return _normalized_rank_strength(df[raw_col], ascending=raw_ascending)
    return pd.Series(0.5, index=df.index, dtype="float64")


def _archetype_cutoffs(league_size: int) -> dict:
    league_size = max(int(league_size or 0), 1)
    top_cut = max(2, int(round(league_size * 0.33)))
    young_cut = max(2, int(round(league_size * 0.33)))
    bottom_cut = max(top_cut + 1, int(round(league_size * 0.67)))
    return {
        "top": top_cut,
        "young": young_cut,
        "old": bottom_cut,
        "bottom": bottom_cut,
    }


def _archetype_profile(archetype: str, row: pd.Series, cutoffs: dict) -> dict:
    power_rank = _safe_int(row.get("power_rank"), 99)
    franchise_rank = _safe_int(row.get("franchise_rank"), 99)
    draft_rank = _safe_int(row.get("draft_capital_rank"), 99)
    bench_rank = _safe_int(row.get("bench_rank"), 99)
    injury_burden = _safe_float(row.get("injury_burden"), 0.0)
    injured_starters = _safe_int(row.get("injured_starters"), 0)
    health_flag = str(row.get("health_flag") or "Stable")
    top_heavy_ratio = _safe_float(row.get("top_heavy_ratio"), 0.0)
    impact_tier_starters = _safe_int(row.get("impact_tier_starters"), 0)
    elite_tier_count = _safe_int(row.get("elite_tier_count"), 0)

    profiles = {
        "Juggernaut": {
            "explanation": "This roster has the cleanest mix of weekly lineup punch and depth in the league.",
            "strengths": [
                "Top-tier starter strength drives weekly ceilings.",
                "Depth profile is strong enough to absorb normal injuries.",
                "The current title window is already open without forcing a rebuild tradeoff.",
            ],
            "risks": [
                "League attention and trade-tax pressure will be high.",
                "A top-heavy roster can still feel thinner than it looks if multiple starters go down.",
            ],
            "recommendations": [
                "Protect starter depth before making luxury upgrades.",
                "Only spend premium picks for difference-making weekly starters.",
            ],
        },
        "Win-Now": {
            "explanation": "This team is built to maximize current weekly points more than long-term flexibility.",
            "strengths": [
                "Current power is stronger than the long-term asset base.",
                "The starting lineup is already good enough to justify aggressive weekly upgrades.",
            ],
            "risks": [
                "Future flexibility is thinner if the current season stalls.",
                "Depth losses can hit harder once premium picks are gone.",
            ],
            "recommendations": [
                "Spend selectively on weekly starter upgrades, not on luxury bench pieces.",
                "Avoid emptying the last meaningful future assets for marginal gains.",
            ],
        },
        "Aging Contender": {
            "explanation": "The current window is real, but the roster is older and needs careful value timing.",
            "strengths": [
                "Veteran production still supports a contender profile right now.",
                "The roster can push for points without another full build-up cycle.",
            ],
            "risks": [
                "Age-related value cliffs can arrive quickly.",
                "A thin draft cupboard makes it harder to reload on the fly.",
            ],
            "recommendations": [
                "Shop non-core veterans before their market turns.",
                "Prioritize younger return pieces when value is otherwise equal.",
            ],
        },
        "Balanced Contender": {
            "explanation": "This contender has enough current strength and enough future insulation to stay flexible.",
            "strengths": [
                "Current power, bench depth, and franchise value are reasonably aligned.",
                "The roster can buy, hold, or pivot without forcing one extreme path.",
            ],
            "risks": [
                "Without one elite edge, the team can drift into the playoff middle.",
                "Depth can get overvalued if it never converts into a real starter upgrade.",
            ],
            "recommendations": [
                "Turn surplus depth into one cleaner weekly advantage.",
                "Protect enough future capital to avoid a hard aging curve later.",
            ],
        },
        "Retool Candidate": {
            "explanation": "This team sits in the middle and needs a cleaner direction instead of more neutral moves.",
            "strengths": [
                "There is enough roster value here to move in either direction.",
                "The team is not forced into a tear-down unless value dictates it.",
            ],
            "risks": [
                "Standing still can trap the roster in the competitive middle.",
                "Short-term patches can hide the need for a bigger structural decision.",
            ],
            "recommendations": [
                "Decide whether to buy current starter points or recycle value into younger pieces.",
                "Use weak position rooms to guide the next trade cycle.",
            ],
        },
        "Asset Consolidator": {
            "explanation": "This roster has enough depth or future value to package into stronger, cleaner starters.",
            "strengths": [
                "The asset base is broader than the weekly lineup edge.",
                "Depth and draft flexibility create multiple trade paths.",
            ],
            "risks": [
                "Too much value may be living on the bench instead of in the starting lineup.",
                "Holding every extra piece can leave the roster underpowered on Sundays.",
            ],
            "recommendations": [
                "Package depth plus picks into one better starter.",
                "Trade from surplus instead of chipping away at core positions.",
            ],
        },
        "Young Competitive Team": {
            "explanation": "This roster is already competitive while still leaning young enough to build forward.",
            "strengths": [
                "Youth and franchise value give the team a wider runway than most middle-tier rosters.",
                "The current roster can still justify targeted weekly upgrades.",
            ],
            "risks": [
                "It is easy to buy too early and shorten the long-term advantage.",
                "A young roster can still be one position short of real contention.",
            ],
            "recommendations": [
                "Buy veterans only when the cost is depth rather than core future pieces.",
                "Keep building around long-term starters instead of chasing every weekly patch.",
            ],
        },
        "One Move Away": {
            "explanation": "The starting core is close enough that one targeted move could change the season outlook.",
            "strengths": [
                "The top of the roster already looks competitive.",
                "A focused trade can move this team from the middle into the real race.",
            ],
            "risks": [
                "Thin depth or one weak room can still cap weekly upside.",
                "Overpaying for the wrong upgrade can leave the roster stuck in place.",
            ],
            "recommendations": [
                "Target the clearest lineup weakness instead of buying general depth.",
                "Use two-for-one offers where the outgoing value is mostly bench or extra picks.",
            ],
        },
        "Productive Struggle": {
            "explanation": "This team is rebuilding, but it still has enough current lineup punch to avoid a total crater.",
            "strengths": [
                "There is enough present value here to create useful trade liquidity.",
                "The roster can keep some weekly credibility while shifting toward the future.",
            ],
            "risks": [
                "Short-term competence can create false-buy signals.",
                "Holding productive veterans too long can waste peak market value.",
            ],
            "recommendations": [
                "Sell productive pieces into future value when the return includes youth or picks.",
                "Do not let a few weekly wins distract from the larger rebuild path.",
            ],
        },
        "Youth Movement": {
            "explanation": "The defining edge here is a young roster that should gain value if the build stays disciplined.",
            "strengths": [
                "Age profile gives the roster time to compound value.",
                "The future core is more important than short-term weekly scoring.",
            ],
            "risks": [
                "Young rosters can still be light on immediate starter reliability.",
                "Patience is required because the current weekly floor can stay low.",
            ],
            "recommendations": [
                "Prioritize long-term starter traits over short-term patch pieces.",
                "Move older production for younger insulation when the market allows it.",
            ],
        },
        "Pick Hoarder": {
            "explanation": "This franchise is leaning into future flexibility and owns enough draft capital to shape multiple paths.",
            "strengths": [
                "Draft capital creates leverage for trades, rookie picks, or future pivots.",
                "The roster does not need to win immediately to be gaining value.",
            ],
            "risks": [
                "Too much future value can leave the current lineup underpowered for too long.",
                "Pick-heavy builds still need to convert assets into real starters at some point.",
            ],
            "recommendations": [
                "Protect premium picks until the market offers a real tier jump.",
                "Use extra picks to buy undervalued young starters before the roster turns the corner.",
            ],
        },
        "Full Rebuild": {
            "explanation": "This roster needs a longer runway and should optimize future value over short-term lineup fixes.",
            "strengths": [
                "A clean rebuild can reset the franchise timeline if the value discipline holds.",
                "There is little reason to spend assets on marginal current-season improvement.",
            ],
            "risks": [
                "Weak current power can make value extraction harder if veterans get stale.",
                "Without enough picks or youth, the rebuild can drift without a clear core.",
            ],
            "recommendations": [
                "Accumulate future picks and younger pieces before buying current production.",
                "Be willing to turn short-term value into a broader asset base.",
            ],
        },
    }
    profile = profiles.get(archetype, profiles["Retool Candidate"]).copy()
    profile["strengths"] = list(profile.get("strengths", []))
    profile["risks"] = list(profile.get("risks", []))
    profile["recommendations"] = list(profile.get("recommendations", []))

    if injury_burden >= 4 or injured_starters >= 2:
        profile["risks"].insert(0, f"{health_flag} is dragging more weekly value than this archetype usually wants.")
        profile["recommendations"].append("Add healthy cover before consolidating more depth away.")
    if draft_rank <= cutoffs["top"] and archetype in {"Juggernaut", "Balanced Contender", "Young Competitive Team", "Pick Hoarder"}:
        profile["strengths"].append("Above-average draft capital gives the roster more optionality than the label alone suggests.")
    if impact_tier_starters >= 4 and archetype in {"Juggernaut", "Balanced Contender", "Win-Now"}:
        profile["strengths"].append("Multiple impact-tier starters give the lineup more true weekly difference-makers.")
    if elite_tier_count <= 1 and archetype in {"One Move Away", "Productive Struggle", "Retool Candidate"}:
        profile["risks"].append("The roster may be short on true top-tier players even if the broader value base is workable.")
    if draft_rank >= cutoffs["old"] and archetype in {"Win-Now", "Aging Contender", "One Move Away"}:
        profile["risks"].append("Draft flexibility is light, so the margin for a failed buy is smaller.")
    if bench_rank >= cutoffs["bottom"] and archetype in {"Juggernaut", "Win-Now", "Aging Contender", "Balanced Contender", "One Move Away"}:
        profile["risks"].append("Bench depth is weaker than the current-team label implies.")
    if top_heavy_ratio >= 2.1 and archetype in {"Juggernaut", "Win-Now", "Aging Contender", "Balanced Contender", "One Move Away"}:
        profile["risks"].append("Too much weekly value is concentrated in the starting lineup.")
    if franchise_rank <= power_rank - 2 and archetype in {"Young Competitive Team", "Pick Hoarder", "Productive Struggle"}:
        profile["strengths"].append("Franchise value is running ahead of current power, which is useful for a longer build.")

    profile["strengths"] = profile["strengths"][:3]
    profile["risks"] = profile["risks"][:3]
    profile["recommendations"] = profile["recommendations"][:3]
    return profile


def _assign_team_archetype(row: pd.Series, league_size: int) -> dict:
    cutoffs = _archetype_cutoffs(league_size)
    strategy = normalize_team_strategy(row.get("strategy") or row.get("mode"))
    power_rank = _safe_int(row.get("power_rank"), 99)
    franchise_rank = _safe_int(row.get("franchise_rank"), 99)
    starter_rank = _safe_int(row.get("starter_rank"), 99)
    bench_rank = _safe_int(row.get("bench_rank"), 99)
    age_rank = _safe_int(row.get("age_rank"), 99)
    draft_rank = _safe_int(row.get("draft_capital_rank"), 99)
    current = _safe_float(row.get("_current_strength"), 0.5)
    future = _safe_float(row.get("_future_strength"), 0.5)
    youth = _safe_float(row.get("_youth_strength"), 0.5)
    draft = _safe_float(row.get("_draft_strength"), 0.5)
    fragility = _safe_float(row.get("_fragility"), 0.5)
    injury_burden = _safe_float(row.get("injury_burden"), 0.0)
    impact_tier_starters = _safe_int(row.get("impact_tier_starters"), 0)
    elite_tier_count = _safe_int(row.get("elite_tier_count"), 0)

    contender_like = strategy in {"contender", "fringe_contender"}

    if strategy == "contender":
        if power_rank <= max(2, cutoffs["top"] - 1) and starter_rank <= max(2, cutoffs["top"] - 1) and bench_rank <= cutoffs["top"] and injury_burden < 4 and impact_tier_starters >= 3:
            archetype = "Juggernaut"
        elif age_rank >= cutoffs["old"] and (draft_rank >= cutoffs["old"] or future < 0.45):
            archetype = "Aging Contender"
        elif franchise_rank - power_rank >= 2 or draft_rank >= cutoffs["old"]:
            archetype = "Win-Now"
        else:
            archetype = "Balanced Contender"
    elif strategy == "fringe_contender":
        if youth >= 0.68 and age_rank <= cutoffs["young"] and franchise_rank <= cutoffs["top"] + 2:
            archetype = "Young Competitive Team"
        elif starter_rank <= cutoffs["top"] + 1 and (bench_rank >= cutoffs["bottom"] or fragility >= 0.62 or injury_burden >= 4):
            archetype = "One Move Away"
        elif bench_rank <= cutoffs["top"] + 1 and (draft_rank <= cutoffs["top"] + 1 or franchise_rank <= power_rank):
            archetype = "Asset Consolidator"
        else:
            archetype = "Balanced Contender" if current >= 0.70 else "One Move Away"
    elif strategy == "retool":
        if youth >= 0.70 and age_rank <= cutoffs["young"] and power_rank <= cutoffs["top"] + 2:
            archetype = "Young Competitive Team"
        elif bench_rank <= cutoffs["top"] + 1 and (draft_rank <= cutoffs["top"] + 1 or franchise_rank <= power_rank):
            archetype = "Asset Consolidator"
        elif starter_rank <= cutoffs["top"] + 1 and (bench_rank >= cutoffs["bottom"] or fragility >= 0.62):
            archetype = "One Move Away"
        else:
            archetype = "Retool Candidate"
    else:
        if draft_rank <= cutoffs["top"] and (franchise_rank + 1 < power_rank or future >= 0.62 or draft >= 0.72):
            archetype = "Pick Hoarder"
        elif youth >= 0.68 and age_rank <= cutoffs["young"]:
            archetype = "Youth Movement"
        elif power_rank <= cutoffs["top"] + 3 or current >= 0.44 or impact_tier_starters >= 2 or elite_tier_count >= 2 or contender_like:
            archetype = "Productive Struggle"
        else:
            archetype = "Full Rebuild"

    profile = _archetype_profile(archetype, row, cutoffs)
    return {
        "archetype": archetype,
        "archetype_label": archetype,
        "archetype_explanation": profile["explanation"],
        "archetype_strengths": profile["strengths"],
        "archetype_risks": profile["risks"],
        "archetype_recommendations": profile["recommendations"],
    }


def refine_team_directions(df_summary: pd.DataFrame) -> pd.DataFrame:
    """
    Reclassify team direction using any richer league-context inputs that are available.
    Falls back gracefully to the existing score-percentile + age baseline when those
    inputs are missing.
    """
    if df_summary.empty:
        return df_summary

    refined = df_summary.copy()

    total_strength = _rank_strength(refined, "rank", "total_score", raw_ascending=False)
    roster_strength = _rank_strength(refined, "current_roster_rank", "current_roster_score", raw_ascending=False)
    starter_strength = _rank_strength(refined, "starter_rank", "starter_score", raw_ascending=False)
    bench_strength = _rank_strength(refined, "bench_rank", "bench_score", raw_ascending=False)
    youth_strength = _rank_strength(refined, "age_rank", "avg_age", raw_ascending=True)
    draft_strength = _rank_strength(refined, "draft_capital_rank", "draft_capital", raw_ascending=False)
    health_strength = _rank_strength(refined, "__health_rank__", "injury_burden", raw_ascending=True)
    balance_strength = _rank_strength(refined, "__balance_rank__", "top_heavy_ratio", raw_ascending=True)

    current_strength = (
        starter_strength * 0.42
        + roster_strength * 0.22
        + bench_strength * 0.14
        + total_strength * 0.12
        + health_strength * 0.10
    )
    future_strength = (
        draft_strength * 0.40
        + youth_strength * 0.30
        + bench_strength * 0.18
        + roster_strength * 0.12
    )
    fragility = (((1.0 - balance_strength) * 0.6) + ((1.0 - bench_strength) * 0.4)).clip(0.0, 1.0)

    order = ["tank", "rebuild", "retool", "fringe_contender", "contender"]
    order_index = {label: idx for idx, label in enumerate(order)}

    def choose_strategy(row) -> str:
        baseline = normalize_team_strategy(row.get("strategy") or row.get("mode"))
        current = _safe_float(row.get("_current_strength"), 0.5)
        future = _safe_float(row.get("_future_strength"), 0.5)
        starter = _safe_float(row.get("_starter_strength"), 0.5)
        bench = _safe_float(row.get("_bench_strength"), 0.5)
        youth = _safe_float(row.get("_youth_strength"), 0.5)
        draft = _safe_float(row.get("_draft_strength"), 0.5)
        health = _safe_float(row.get("_health_strength"), 0.5)
        fragility_score = _safe_float(row.get("_fragility"), 0.5)

        # Health is already part of current_strength, so this gate should only
        # screen out truly injury-cratered contenders instead of blocking an
        # otherwise elite roster twice.
        if current >= 0.80 and starter >= 0.72 and health >= 0.10:
            target = "contender"
            if future < 0.28 and bench < 0.25 and fragility_score > 0.65:
                target = "fringe_contender"
        elif current >= 0.64 and starter >= 0.56:
            target = "fringe_contender"
            if future < 0.36 and bench < 0.30 and (health < 0.25 or fragility_score > 0.72):
                target = "retool"
        elif current <= 0.26:
            target = "rebuild" if (future >= 0.54 or draft >= 0.60 or youth >= 0.60) else "tank"
        elif current <= 0.42:
            if future >= 0.58:
                target = "rebuild"
            elif draft < 0.35 and youth < 0.35 and health < 0.30:
                target = "tank"
            else:
                target = "retool"
        else:
            target = "retool"

        baseline_idx = order_index.get(baseline, order_index["retool"])
        target_idx = order_index.get(target, baseline_idx)
        max_shift = 1
        if (
            (current >= 0.86 and starter >= 0.78)
            or (current <= 0.20 and future <= 0.40)
            or (current <= 0.28 and future >= 0.68)
        ):
            max_shift = 2
        if target_idx > baseline_idx + max_shift:
            target_idx = baseline_idx + max_shift
        elif target_idx < baseline_idx - max_shift:
            target_idx = baseline_idx - max_shift
        return order[target_idx]

    refined["_total_strength"] = total_strength
    refined["_roster_strength"] = roster_strength
    refined["_starter_strength"] = starter_strength
    refined["_bench_strength"] = bench_strength
    refined["_youth_strength"] = youth_strength
    refined["_draft_strength"] = draft_strength
    refined["_health_strength"] = health_strength
    refined["_balance_strength"] = balance_strength
    refined["_current_strength"] = current_strength
    refined["_future_strength"] = future_strength
    refined["_fragility"] = fragility

    refined["strategy"] = refined.apply(choose_strategy, axis=1)
    refined["strategy_label"] = refined["strategy"].map(team_strategy_label)
    refined["mode"] = refined["strategy"].map(team_strategy_mode)
    league_size = len(refined)
    archetype_profiles = refined.apply(lambda row: _assign_team_archetype(row, league_size), axis=1)
    refined["archetype"] = archetype_profiles.apply(lambda item: item.get("archetype"))
    refined["archetype_label"] = archetype_profiles.apply(lambda item: item.get("archetype_label"))
    refined["archetype_explanation"] = archetype_profiles.apply(lambda item: item.get("archetype_explanation"))
    refined["archetype_strengths"] = archetype_profiles.apply(lambda item: item.get("archetype_strengths"))
    refined["archetype_risks"] = archetype_profiles.apply(lambda item: item.get("archetype_risks"))
    refined["archetype_recommendations"] = archetype_profiles.apply(lambda item: item.get("archetype_recommendations"))

    return refined.drop(
        columns=[
            "_total_strength",
            "_roster_strength",
            "_starter_strength",
            "_bench_strength",
            "_youth_strength",
            "_draft_strength",
            "_health_strength",
            "_balance_strength",
            "_current_strength",
            "_future_strength",
            "_fragility",
        ],
        errors="ignore",
    )
