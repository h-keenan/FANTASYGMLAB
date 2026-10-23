import time
from typing import Any, Mapping
import pandas as pd
from modules import league_maturity
from modules import league_display
from modules import player_eligibility
from modules import player_quick_view
from modules import player_state_authority
from modules import league_value_settings
from modules import rankings
from modules import redis_cache
from modules import sleeper

# Same live-time-bucket idiom modules.trade_hub_engine/modules.league_rankings/
# modules.playoff_simulator already use for their own Redis-backed caches: a
# 30s window is short enough that a fresh add/drop or injury designation
# shows up on the wire within half a minute (this data's whole point is
# "what can I act on right now"), long enough that the flood of mobile
# clients polling Waivers during a live waiver period share one computed
# pool instead of each re-running it.
# coridian_, 2026-10-19, performance audit: widened from the original 30s
# to 2 minutes, alongside the same change in modules.league_value_settings/
# modules.league_rankings/modules.trade_hub_engine — still fast enough that
# a fresh add/drop or injury designation shows up well within any
# reasonable expectation, while cutting repeat-visit recompute cost during
# a live waiver period substantially.
WAIVER_POOL_TTL_SECONDS = 120


def _waiver_pool_cache_bucket() -> int:
    return int(time.time() // WAIVER_POOL_TTL_SECONDS)


# Redis-backed single-flight + cache (modules.redis_cache.redis_single_flight_cache)
# — same pattern, and same reason, as modules.trade_hub_engine's and
# modules.league_rankings's own caches: services/mobile_api_service.py's
# `/v1/leagues/{league_id}/waivers` endpoint used to run this exact pool build
# (apply_valuation_lens over the WHOLE league-eligible pool, the overall_rating
# percentile pass, a row-wise `.apply(rankings.is_probably_stale_free_agent,
# axis=1)` over every free agent, then position/overall ranking) from scratch
# on every single request — every GM checking the wire pays the full cost
# independently, even though none of this depends on who's asking, only on
# (league_id, lens) and how recently a roster actually changed. Without a
# single-flight guard, N concurrent requests that all miss the same key before
# the first one finishes would each independently redo this pass instead of
# sharing one.
#
# Deliberately scoped to ONLY the league-wide, asker-independent part of the
# endpoint's pipeline. The per-roster work that follows it in the endpoint
# (modules.trade_analyzer_fit.build_team_needs_assessment, injury context,
# team_eval.suggest_optimal_lineup) runs over one caller's own ~15-25 man
# roster, not the full free-agent pool — cheap enough, and different enough
# per caller/roster_id, that folding it into this cache would only fragment
# the one entry every GM in the league could otherwise share. Same "outside
# the cache boundary" call modules.trade_hub_engine makes for team_stance.
_WAIVER_POOL_LOCK_TIMEOUT_SECONDS = 15.0


def _build_waiver_free_agent_pool_cached(
    league_id: str,
    lens: str,
    players_db_path: str,
    _bucket: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    league = sleeper.get_league(league_id)
    if not league:
        return pd.DataFrame(), pd.DataFrame()
    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    players_df = rankings.load_players(players_db_path)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(players_db_path)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="mobile_api_waivers", league=league
    )
    if players_df.empty:
        return pd.DataFrame(), pd.DataFrame()

    valued = league_value_settings.apply_valuation_lens(players_df, lens, settings)
    score_field = league_value_settings.valuation_score_field(lens)
    # Percentiled against the full league-eligible pool (rostered players
    # included), matching the hero ring's denominator — see
    # _project_waiver_row's overall_rating comment in
    # services/mobile_api_service.py.
    valued["_overall_rating_col"] = player_quick_view.overall_ratings_for_pool(
        valued, score_column=score_field
    )

    rosters = sleeper.get_rosters(league_id)
    roster_player_map = {
        str(roster.get("roster_id")): tuple(
            str(pid) for pid in (roster.get("players") or []) if pid is not None
        )
        for roster in rosters
        if roster.get("roster_id") is not None
    }

    free_agents = player_state_authority.waiver_actionable_player_pool(
        valued, roster_player_map, surface="mobile_api_waivers"
    )
    if free_agents.empty:
        return valued, free_agents

    free_agents = free_agents.copy()
    free_agents["stale_free_agent"] = free_agents.apply(rankings.is_probably_stale_free_agent, axis=1)
    free_agents.loc[free_agents["stale_free_agent"], ["dynasty_score", "value_score"]] = 0
    free_agents = free_agents.sort_values(["stale_free_agent", score_field], ascending=[True, False])
    # Sleeper's global trending-add signal (cross-league, last 24h — see
    # annotate_sleeper_trending_add's docstring) — folded into this cached
    # pool build too, rather than fetched once per request outside it, so a
    # cache hit skips this network call as well.
    free_agents = annotate_sleeper_trending_add(free_agents, sleeper.trending_add_rank_map())

    score_series = pd.to_numeric(free_agents.get(score_field, 0), errors="coerce").fillna(0)
    free_agents["position_rank"] = (
        free_agents.groupby("position")[score_field]
        .rank(method="first", ascending=False)
        .fillna(0)
        .astype(int)
    )
    free_agents["overall_rank"] = score_series.rank(method="first", ascending=False).fillna(0).astype(int)
    return valued, free_agents


def build_waiver_free_agent_pool_cached(
    *,
    league_id: str,
    lens: str,
    players_db_path: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Cached front door for the Waivers endpoint's league-wide free-agent
    pool build — resolves its own league/settings/players_df from just
    (league_id, lens, players_db_path) rather than accepting them as
    arguments, so every caller asking about the same league/lens combo
    within the same 30s window hits one cache entry instead of each
    independently re-running `apply_valuation_lens` over the whole eligible
    pool, the overall-rating percentile pass, the row-wise
    `is_probably_stale_free_agent` check, and position/overall ranking.

    Returns `(valued, free_agents)`: `valued` is the full league-eligible
    pool (rostered players included — the endpoint needs it to slice out
    the caller's own roster for team-needs/injury context), `free_agents`
    is the unowned subset with `stale_free_agent`, the Sleeper trending-add
    columns, and `position_rank`/`overall_rank` already attached. Both are
    returned as copies so a caller mutating either (e.g. adding
    `injury_replacement_fit`) never corrupts the cached entry.

    Single-flight + cache, shared across every mobile-api worker via Redis:
    see modules.redis_cache.redis_single_flight_cache and this module's own
    comment above `_build_waiver_free_agent_pool_cached`."""

    key = (league_id, lens, players_db_path, _waiver_pool_cache_bucket())
    cache_key = redis_cache.build_cache_key("waiver_free_agent_pool", *key)
    valued, free_agents = redis_cache.redis_single_flight_cache(
        cache_key=cache_key,
        ttl_seconds=WAIVER_POOL_TTL_SECONDS,
        compute=lambda: _build_waiver_free_agent_pool_cached(*key),
        lock_timeout_seconds=_WAIVER_POOL_LOCK_TIMEOUT_SECONDS,
    )
    return valued.copy(), free_agents.copy()


def annotate_sleeper_trending_add(
    free_agents: pd.DataFrame,
    trending_map: dict | None = None,
) -> pd.DataFrame:
    """Attach Sleeper's GLOBAL trending-add signal to each free-agent row.

    ``trending_map`` is ``modules.sleeper.trending_add_rank_map()``'s output
    (``player_id -> {"count": int, "rank": int}``) — callers fetch it once
    per request/render (one Sleeper call) and pass it in here rather than
    this function reaching the network itself, so both the web route
    (app.py) and the mobile endpoint (services/mobile_api_service.py) share
    this exact same join instead of duplicating it.

    This is deliberately labeled "sleeper_trending_add*", not just
    "trending*" — this codebase already uses "trending" for a different,
    roster-internal signal (role/usage trend, e.g. rankings.py's "Usage
    trending up/down"). Sleeper's trending-add list is a completely
    different thing: cross-league, platform-wide add velocity over the last
    24h, NOT scoped to this league. Adds three columns, all "not trending"
    when ``trending_map`` is empty/None or a given player has no entry:
      - ``sleeper_trending_add`` (bool) — currently on Sleeper's global
        trending-add list.
      - ``sleeper_trending_add_count`` (Optional[int]) — Sleeper's own
        24h add count for this player.
      - ``sleeper_trending_add_rank`` (Optional[int]) — 1-indexed rank
        within that global list (1 = most added across all of Sleeper).
    """

    if free_agents is None or free_agents.empty or "player_id" not in free_agents.columns:
        return free_agents

    annotated = free_agents.copy()
    mapping = trending_map or {}
    player_ids = annotated["player_id"].astype(str)
    if not mapping:
        annotated["sleeper_trending_add"] = False
        annotated["sleeper_trending_add_count"] = None
        annotated["sleeper_trending_add_rank"] = None
        return annotated

    annotated["sleeper_trending_add"] = player_ids.isin(set(mapping.keys()))
    # Built as plain Python lists on an object-dtype Series (not .map(), which
    # would upcast a None/int mix to float64 and silently turn "not trending"
    # into NaN instead of a real None) — downstream readers (the web badge
    # helper below, mobile's _clean_json_value) check `is None`/truthiness
    # directly.
    annotated["sleeper_trending_add_count"] = pd.Series(
        [mapping.get(pid, {}).get("count") for pid in player_ids],
        index=annotated.index,
        dtype="object",
    )
    annotated["sleeper_trending_add_rank"] = pd.Series(
        [mapping.get(pid, {}).get("rank") for pid in player_ids],
        index=annotated.index,
        dtype="object",
    )
    return annotated


def waiver_confidence_label(row, position_rank: int) -> tuple[str, str]:
    """Real recommendation-confidence signal for a Priority Adds candidate.

    Not a new score: derived directly from the same already-computed signals
    ``rank_priority_add_candidates`` uses to rank this exact row —
    ``priority_need_fit`` / ``injury_replacement_fit`` (does this fill a real
    roster need) and ``priority_value_opportunity`` (is this elite value on
    the wire regardless of need) — mirroring Trade Ideas'
    High/Medium/Low confidence language
    (``modules.trade_ideas._trade_confidence_label``) so the same badge/label
    visual pattern (``modules.trade_visual_language.confidence_indicator_html``)
    reads consistently across both surfaces.

    Rows that never went through ``rank_priority_add_candidates`` (no
    ``priority_need_fit``/``priority_value_opportunity`` columns at all —
    e.g. Stash Candidates/Watchlist Depth/FAAB Shortlist, which are sourced
    from the raw wire, not the need-fit ranker) return an empty label rather
    than fabricate one from signals that were never actually computed for
    them.
    """

    if "priority_need_fit" not in row and "priority_value_opportunity" not in row:
        return "", ""
    stale = bool(row.get("stale_free_agent"))
    try:
        score = int(round(float(row.get("score", row.get("value_score", 0)) or 0)))
    except Exception:
        score = 0
    if stale or score <= 0:
        return "Low", "Stale or low-value under the current lens."
    need_fit = bool(row.get("priority_need_fit")) or bool(row.get("injury_replacement_fit"))
    value_opportunity = bool(row.get("priority_value_opportunity"))
    if need_fit:
        return "High", "Matches a real roster need on this roster."
    if value_opportunity or int(position_rank or 99) <= 1:
        return "Medium", "Elite wire value, but not tied to a stated roster need."
    return "Low", "Depth-level add without a strong need or value signal."


_safe_text = league_display._safe_text


def waiver_recommendation_label(row, position_rank: int) -> tuple[str, str]:
    """Translate existing waiver signals into a concise presentation label."""

    if bool(row.get("stale_free_agent")):
        return "Watch", "neutral"
    if bool(row.get("injury_replacement_fit")) or position_rank <= 3:
        return "Add", "opportunity"
    opportunity = _safe_text(row.get("opportunity_label")).strip()
    try:
        age = float(row.get("age") or 0)
    except Exception:
        age = 0
    if (age and age <= 24) or opportunity in {
        "Backup With Upside",
        "Starter At Risk",
        "Committee Back",
    }:
        return "Stash", "information"
    return "Watch", "neutral"


def select_top_waiver_opportunity(
    free_agents: pd.DataFrame,
    roster_df: pd.DataFrame,
    league_settings: dict | None,
    score_field: str,
    *,
    needed_positions: list[str] | None = None,
    league: Mapping[str, Any] | None = None,
    rosters: list[Mapping[str, Any]] | None = None,
):
    if free_agents is None or free_agents.empty:
        return pd.Series(dtype="object")

    ranked = rank_priority_add_candidates(
        free_agents,
        score_field=score_field,
        needed_positions=needed_positions or [],
        league_settings=league_settings or {},
        roster_df=roster_df if roster_df is not None else pd.DataFrame(),
        max_items=1,
        league=league,
        rosters=rosters,
    )
    if ranked.empty:
        return pd.Series(dtype="object")
    selected = ranked.iloc[0].copy()
    kicker_required = int((league_settings or {}).get("k_count") or 0) > 0
    if (
        str(selected.get("position") or "").strip().upper() == "K"
        and kicker_required
        and bool(selected.get("priority_need_fit"))
    ):
        selected["kicker_need_fit"] = True
        selected["injury_replacement_note"] = (
            "Your lineup requires a kicker and the roster does not currently "
            "have a viable active option."
        )
    return selected


def _roster_has_viable_kicker(roster_df: pd.DataFrame) -> bool:
    if roster_df is None or roster_df.empty:
        return False
    positions = (
        roster_df.get("position", pd.Series(dtype="object"))
        .fillna("")
        .astype(str)
        .str.upper()
    )
    kicker_rows = roster_df[positions.eq("K")].copy()
    if kicker_rows.empty:
        return False
    team_values = kicker_rows.get(
        "team",
        pd.Series("", index=kicker_rows.index),
    ).fillna("").astype(str).str.strip().str.upper()
    status_values = (
        kicker_rows.get(
            "status",
            pd.Series("", index=kicker_rows.index),
        ).fillna("").astype(str).str.strip().str.lower()
        + " "
        + kicker_rows.get(
            "injury_status",
            pd.Series("", index=kicker_rows.index),
        ).fillna("").astype(str).str.strip().str.lower()
    )
    unavailable = status_values.str.contains(
        r"\b(?:ir|out|inactive|suspended|pup|nfi)\b",
        regex=True,
    )
    return bool(
        (
            team_values.ne("")
            & ~team_values.isin({"FA", "FREE AGENT", "NONE", "N/A"})
            & ~unavailable
        ).any()
    )


def _qb_format(league_settings: dict | None) -> str:
    settings = league_settings or {}
    raw = str(settings.get("qb_format") or "").strip().casefold()
    if "super" in raw or raw in {"sf", "superflex"}:
        return "superflex"
    if "2qb" in raw or raw == "2":
        return "2qb"
    if int(settings.get("superflex_count") or 0) > 0:
        return "superflex"
    return "1qb"


def _score_series(frame: pd.DataFrame, score_field: str) -> pd.Series:
    return pd.to_numeric(frame.get(score_field, 0), errors="coerce").fillna(0.0)


def rank_priority_add_candidates(
    free_agents: pd.DataFrame,
    *,
    score_field: str,
    needed_positions: list[str] | None,
    league_settings: dict | None,
    roster_df: pd.DataFrame | None,
    max_items: int = 6,
    league: Mapping[str, Any] | None = None,
    rosters: list[Mapping[str, Any]] | None = None,
) -> pd.DataFrame:
    """Order Priority Adds for THIS roster — not bare dynasty-score tops.

    Preserves Best Available as a separate Snapshot surface. Uses existing
    TeamNeedsAssessment outputs + score/injury flags. Does not invent a new
    opaque score.

    `league`/`rosters` (both optional, for callers that already have them —
    the real Waivers endpoint does) let this detect a pre-/mid-draft league
    via modules.league_maturity.build_league_evidence's own
    roster_population_ratio — see the kicker-suppression comment below for
    why this matters specifically for the kicker-need signal.
    """

    if free_agents is None or free_agents.empty or max_items <= 0:
        return free_agents.iloc[0:0].copy() if free_agents is not None else pd.DataFrame()

    # Production candidate builders publish this canonical decision.  Keep the
    # ranker defensive when it receives a complete raw player record, while
    # preserving small internal/test frames that intentionally contain only
    # already-vetted ranking inputs.
    if "waiver_actionable" in free_agents.columns:
        candidates = free_agents[
            free_agents["waiver_actionable"].fillna(False).astype(bool)
        ].copy()
    elif {"team", "status", "active"}.issubset(free_agents.columns):
        candidates = player_state_authority.filter_waiver_actionable_players(free_agents)
    else:
        candidates = free_agents.copy()
    if candidates.empty:
        return candidates
    settings = league_settings or {}
    needed = {
        str(pos).upper()
        for pos in (needed_positions or [])
        if str(pos).upper()
    }
    positions = (
        candidates.get("position", pd.Series("", index=candidates.index))
        .fillna("")
        .astype(str)
        .str.upper()
    )
    scores = _score_series(candidates, score_field)
    stale = candidates.get(
        "stale_free_agent",
        pd.Series(False, index=candidates.index, dtype="bool"),
    ).fillna(False)
    injury_fit = candidates.get(
        "injury_replacement_fit",
        pd.Series(False, index=candidates.index, dtype="bool"),
    ).fillna(False)
    # rankings.opportunity_profile() sets workload_trend="Blocked" as the
    # fallback tier of its own opportunity hierarchy (below Buried Depth/
    # Handcuff/Committee Back/etc.) precisely for players with no live path
    # to snaps right now — the same value the Player Detail screen renders
    # as "Role trending down — Blocked". value_score/dynasty_score are
    # long-horizon (draft capital, age curve) and can stay high for a young
    # former-high-pick player years after their real-world role has
    # collapsed; without this gate that legacy value score alone was enough
    # to clear the "elite wire value" cutoff below and surface a 0%-snap,
    # role-blocked player (e.g. Audric Estime, RB) as a Priority Add. A
    # candidate whose opportunity genuinely reopens (e.g. the player ahead
    # of them gets hurt) is re-labeled out of "Blocked" upstream in
    # rankings.py on the next refresh, so gating on this column does not
    # punish real opportunity swings — only players rankings.py itself has
    # already judged to have no current role.
    role_blocked = (
        candidates.get(
            "workload_trend",
            pd.Series("", index=candidates.index, dtype="object"),
        )
        .fillna("")
        .astype(str)
        .str.strip()
        .str.casefold()
        == "blocked"
    )

    # coridian_, 2026-10-20, screenshot: a league that "hasn't even
    # drafted" surfaced 5 kickers at the top of Priority Adds.
    # _roster_has_viable_kicker(roster_df) correctly returns False for a
    # genuinely empty roster — but a pre-/mid-draft roster is ALSO empty,
    # for a completely different reason (nothing's been picked yet, not
    # "the user forgot a kicker"). A naive roster-SIZE cutoff (tried first,
    # reverted) broke a real, intentional case: a roster that's otherwise
    # mostly filled but genuinely missing only a kicker correctly gets
    # recommended one regardless of its exact size. The real signal is
    # LEAGUE-wide, not single-roster: modules.league_maturity's own
    # roster_population_ratio (already shipped, already tested, already
    # used by the Streamlit app's own startup-mode detection — just never
    # wired into this endpoint) checks what fraction of EVERY roster in
    # the league has any players at all, which correctly tells "the whole
    # league hasn't drafted yet" apart from "my team specifically is
    # missing just a kicker" without needing per-user draft-status
    # plumbing. league/rosters are optional here so existing callers that
    # don't have full league context keep their current behavior.
    league_is_pre_draft = False
    if league is not None or rosters is not None:
        evidence = league_maturity.build_league_evidence(league=league, rosters=rosters)
        league_is_pre_draft = bool(
            evidence.get("roster_count")
        ) and evidence.get("roster_population_ratio", 1.0) < 0.5

    kicker_required = int(settings.get("k_count") or 0) > 0
    has_viable_kicker = _roster_has_viable_kicker(
        roster_df if roster_df is not None else pd.DataFrame()
    )
    suppress_kickers = not (
        kicker_required and not has_viable_kicker and not league_is_pre_draft
    )
    qb_format = _qb_format(settings)

    positive = candidates[(~stale) & (~role_blocked) & (scores > 0)].copy()
    if positive.empty:
        return candidates.iloc[0:0].copy()

    pos_scores = _score_series(positive, score_field)
    # Exceptional wire value: top overall FA or clearly above the featured pack.
    top_cutoff = float(pos_scores.quantile(0.85)) if len(pos_scores) >= 4 else float(pos_scores.max())
    overall_rank = pos_scores.rank(ascending=False, method="first")

    need_fit = []
    value_opportunity = []
    actionable = []
    skill_needs = needed - {"QB", "TE", "K"}
    for idx in positive.index:
        position = str(positive.at[idx, "position"] or "").upper()
        score = float(pos_scores.at[idx])
        injured = bool(injury_fit.at[idx] if idx in injury_fit.index else False)
        is_need = position in needed or injured
        if position == "K":
            is_need = bool(kicker_required and not has_viable_kicker)
        is_elite_value = bool(overall_rank.at[idx] <= 2 or score >= top_cutoff)
        if position in {"QB", "TE"} and position not in needed and not injured:
            is_need = False
            # Do not let covered QB/TE displace true skill-position needs.
            if skill_needs:
                is_elite_value = False
            elif position == "QB" and qb_format == "1qb":
                # Adequate 1QB rooms: ordinary QBs are not Priority Adds.
                is_elite_value = False
            elif position == "TE":
                is_elite_value = bool(overall_rank.at[idx] <= 1 and score >= top_cutoff)
            else:
                # Superflex without a true QB need: only exceptional wire QB value.
                is_elite_value = bool(overall_rank.at[idx] <= 2 and score >= top_cutoff)
        if position == "K" and suppress_kickers:
            is_need = False
            is_elite_value = False
        need_fit.append(is_need)
        value_opportunity.append(bool(is_elite_value and not is_need))
        actionable.append(bool(is_need or is_elite_value))

    positive = positive.copy()
    positive["priority_need_fit"] = need_fit
    positive["priority_value_opportunity"] = value_opportunity
    positive["priority_actionable"] = actionable
    positive["_priority_score"] = pos_scores
    positive["_injury_fit"] = injury_fit.reindex(positive.index).fillna(False)
    positive = positive[positive["priority_actionable"]].copy()
    if positive.empty:
        return positive

    positive = positive.sort_values(
        ["_injury_fit", "priority_need_fit", "priority_value_opportunity", "_priority_score"],
        ascending=[False, False, False, False],
    )

    # Soft diversity: prefer decision utility across rooms without a rigid 1-of-each rule.
    selected_indices: list = []
    position_counts: dict[str, int] = {}
    soft_cap = 2
    for idx, row in positive.iterrows():
        position = str(row.get("position") or "").upper()
        count = position_counts.get(position, 0)
        exceptional = bool(row.get("priority_need_fit")) or bool(row.get("_injury_fit"))
        if count >= soft_cap and not (
            exceptional and count < soft_cap + 1 and qb_format != "1qb" and position == "QB"
        ):
            # Allow a third same-position pick only for true need/injury, and never
            # flood 1QB boards with ordinary QBs (already demoted above).
            if count >= soft_cap and not (exceptional and position != "QB"):
                if count >= soft_cap + 1:
                    continue
                if position == "QB" and qb_format == "1qb":
                    continue
                if not exceptional:
                    continue
        selected_indices.append(idx)
        position_counts[position] = count + 1
        if len(selected_indices) >= max_items:
            break

    if len(selected_indices) < max_items:
        for idx in positive.index:
            if idx in selected_indices:
                continue
            selected_indices.append(idx)
            if len(selected_indices) >= max_items:
                break

    result = positive.loc[selected_indices].copy()
    drop_cols = [col for col in ("_priority_score", "_injury_fit") if col in result.columns]
    if drop_cols:
        result = result.drop(columns=drop_cols)
    return result.reset_index(drop=True)
