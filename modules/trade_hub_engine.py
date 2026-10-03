"""Stateless Trade Hub idea generation for a single roster.

Like modules.dashboard_engine, this is a from-scratch sibling to app.py's
Trade Hub page rather than an app.py extraction — modules/ never imports
app.py (confirmed: no other module does; app.py imports modules/, not the
reverse). The actual idea-generation engine (modules.trade_ideas.build_trade_ideas,
~6500 lines) and the per-team league summary it needs
(modules.team_eval.build_league_summary) are already clean, already-shared
modules/ functions — this module calls them directly with zero duplication.

apply_strategy_age_curve (~135 lines, pandas only) and
strategy_adjusted_pick_score_multiplier (~10 lines) live here and are
imported by app.py (`from modules.trade_hub_engine import
apply_strategy_age_curve, strategy_adjusted_pick_score_multiplier`) — this
file used to carry its own byte-for-byte copy of both, ported by hand from
app.py, until that drift risk was consolidated to a single implementation.
The Trust-enforcement plumbing (build_trade_trust_context + a trivial
roster-player-map builder) that wraps modules.trust_enforcement is a
similar case: both this module and app.py used to hand-keep their own
copies in sync by inspection; both now alias modules.trade_trust's single
implementation (see modules/trade_trust.py).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Mapping

import pandas as pd

from modules import league_value_settings
from modules import player_eligibility
from modules import player_quick_view
from modules import rankings
from modules import sleeper
from modules import trade_hub_ui
from modules import trade_ideas as trade_ideas_module
from modules import trade_trust
from modules import trade_visual_language
from modules import trust_enforcement
from modules.compact_fantasy_assets import compact_package
from modules.player_tiers import assign_player_tiers
from modules.league_value_settings import format_score_columns
from modules.team_eval import build_league_summary, normalize_team_strategy

MAX_TRADE_IDEAS = 8


def _safe_text(value: object, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def apply_strategy_age_curve(df: pd.DataFrame, strategy: str, score_field: str) -> pd.DataFrame:
    """Faithful port of app.py's apply_strategy_age_curve — see module docstring.

    Applies team-strategy preference without destroying league/base values.
    Writes strategy_score/strategy_preference_multiplier. Only the active
    score_field is overwritten for Trade Hub ranking compatibility.
    """

    if df.empty:
        return df

    strategy_key = normalize_team_strategy(strategy)
    if (
        str(df.attrs.get("strategy_curve") or "") == strategy_key
        and str(df.attrs.get("strategy_curve_field") or "") == str(score_field or "")
        and "strategy_score" in df.columns
    ):
        return df

    df = df.copy()
    ages = pd.to_numeric(df.get("age", pd.Series(float("nan"), index=df.index)), errors="coerce")
    positions = df.get("position", pd.Series("", index=df.index)).fillna("").astype(str).str.upper()
    multiplier = pd.Series(1.0, index=df.index, dtype="float64")

    if strategy_key == "contender":
        multiplier = multiplier.mask(ages.ge(25) & ages.le(30), 1.04)
        multiplier = multiplier.mask(ages.le(22), 0.98)
        multiplier = multiplier.mask((positions == "RB") & ages.ge(29), 0.94)
    elif strategy_key == "fringe_contender":
        multiplier = multiplier.mask(ages.ge(24) & ages.le(29), 1.025)
        multiplier = multiplier.mask(ages.le(24), 1.01)
        multiplier = multiplier.mask((positions.isin(["RB", "WR", "TE"])) & ages.ge(31), 0.96)
    elif strategy_key == "retool":
        multiplier = multiplier.mask(ages.le(25), 1.04)
        multiplier = multiplier.mask(ages.ge(26) & ages.le(29), 1.01)
        multiplier = multiplier.mask((positions == "RB") & ages.ge(28), 0.91)
        multiplier = multiplier.mask((positions.isin(["WR", "TE"])) & ages.ge(31), 0.94)
    elif strategy_key == "rebuild":
        multiplier = multiplier.mask(ages.le(23), 1.10)
        multiplier = multiplier.mask(ages.gt(23) & ages.le(25), 1.06)
        multiplier = multiplier.mask(ages.gt(25) & ages.le(26), 1.02)
        multiplier = multiplier.mask((positions == "RB") & ages.ge(28), 0.82)
        multiplier = multiplier.mask((positions == "WR") & ages.ge(30), 0.86)
        multiplier = multiplier.mask((positions == "TE") & ages.ge(31), 0.88)
        multiplier = multiplier.mask((positions == "QB") & ages.ge(34), 0.92)
    elif strategy_key == "tank":
        multiplier = multiplier.mask(ages.le(23), 1.15)
        multiplier = multiplier.mask(ages.gt(23) & ages.le(25), 1.09)
        multiplier = multiplier.mask((positions == "RB") & ages.ge(27), 0.75)
        multiplier = multiplier.mask((positions == "WR") & ages.ge(30), 0.80)
        multiplier = multiplier.mask((positions == "TE") & ages.ge(31), 0.84)
        multiplier = multiplier.mask((positions == "QB") & ages.ge(34), 0.88)

    for column, league_column in (
        ("dynasty_score", "league_dynasty_score"),
        ("value_score", "league_value_score"),
        ("rebuild_score", "league_rebuild_score"),
    ):
        if column in df.columns and league_column not in df.columns:
            df[league_column] = pd.to_numeric(df[column], errors="coerce").fillna(0).round().astype(int)

    df["strategy_preference_multiplier"] = multiplier.round(4)
    primary = score_field if score_field in df.columns else "dynasty_score"
    if primary not in df.columns:
        primary = "league_dynasty_score" if "league_dynasty_score" in df.columns else "base_score"
    primary_scores = pd.to_numeric(df.get(primary, pd.Series(0, index=df.index)), errors="coerce").fillna(0)
    league_primary = {
        "dynasty_score": "league_dynasty_score",
        "value_score": "league_value_score",
        "rebuild_score": "league_rebuild_score",
    }.get(primary)
    if league_primary and league_primary in df.columns:
        primary_scores = pd.to_numeric(df[league_primary], errors="coerce").fillna(primary_scores)

    df["strategy_score"] = (primary_scores * multiplier).clip(lower=0).round().astype(int)
    if score_field in df.columns or score_field:
        df[score_field] = df["strategy_score"]

    for column, league_column in (
        ("dynasty_score", "league_dynasty_score"),
        ("value_score", "league_value_score"),
        ("rebuild_score", "league_rebuild_score"),
    ):
        if column == score_field:
            continue
        if league_column in df.columns:
            df[column] = df[league_column]

    if "base_score" in df.columns:
        df["base_score"] = pd.to_numeric(df["base_score"], errors="coerce").fillna(0).round().astype(int)

    df = assign_player_tiers(df, primary_score_field=score_field if score_field in df.columns else "strategy_score")
    curved = format_score_columns(df)
    curved.attrs["strategy_curve"] = strategy_key
    curved.attrs["strategy_curve_field"] = str(score_field or "")
    return curved


_PICK_STRATEGY_MULTIPLIERS = {
    "contender": 0.88,
    "fringe_contender": 0.95,
    "retool": 1.02,
    "rebuild": 1.16,
    "tank": 1.25,
}


def strategy_adjusted_pick_score_multiplier(base_multiplier: float, strategy: str) -> float:
    """Faithful port of app.py's strategy_adjusted_pick_score_multiplier."""

    strategy_key = normalize_team_strategy(strategy)
    return float(base_multiplier) * _PICK_STRATEGY_MULTIPLIERS.get(strategy_key, 1.0)


build_roster_player_map = trade_trust.build_roster_player_map
build_trade_trust_context = trade_trust.build_trade_trust_context


def enforce_generated_trade_ideas(
    ideas: list[dict],
    *,
    df_players: pd.DataFrame,
    league_id: str,
    df_summary: pd.DataFrame,
    my_roster_id: int,
    rosters: list[dict] | None,
    untouchables: tuple[str, ...] = (),
) -> list[dict]:
    """Faithful, simplified port of app.py's enforce_cached_trade_ideas —
    the production Trust safety boundary so a stale cached idea can never
    suggest trading a player who has since been rostered elsewhere, traded,
    or dropped. Drops the explicit-player-focus/diagnostics params, which
    are for a narrower "search for a specific player" flow Trade Hub's
    general idea list doesn't use."""

    canonical_players: dict[str, dict] = {}
    player_enforcement: dict[str, Any] = {}
    candidate_player_ids = {
        _safe_text(asset.get("player_id"))
        for idea in ideas or ()
        for side in ("send_assets", "receive_assets")
        for asset in idea.get(side) or ()
        if isinstance(asset, dict)
        and _safe_text(asset.get("asset_type")).casefold() == "player"
        and _safe_text(asset.get("player_id"))
    }
    if df_players is not None and not df_players.empty:
        candidate_players = df_players[df_players["player_id"].astype(str).isin(candidate_player_ids)]
        for _, row in candidate_players.iterrows():
            player = row.to_dict()
            player_id = _safe_text(player.get("player_id"))
            if not player_id:
                continue
            canonical_players[player_id] = player
            result = trust_enforcement.enforcement_from_player_annotations(player)
            if result is not None:
                player_enforcement[player_id] = result

    roster_player_map = build_roster_player_map(rosters)
    trust_context = build_trade_trust_context(
        league_id=league_id, df_summary=df_summary, roster_player_map=roster_player_map
    )

    board = trust_enforcement.enforce_trade_board(
        ideas or (),
        canonical_players=canonical_players,
        player_enforcement=player_enforcement,
        ownership_by_player=dict(trust_context.ownership_by_player),
        valid_roster_ids=trust_context.valid_roster_ids,
        my_roster_id=int(my_roster_id),
        team_name_to_roster=dict(trust_context.team_name_to_roster),
        league_context_valid=bool(
            trust_context.league_context_valid and int(my_roster_id) in trust_context.valid_roster_ids
        ),
        untouchable_names=frozenset(_safe_text(name).casefold() for name in untouchables if _safe_text(name)),
        explicit_player_focus=False,
        focused_player_ids=(),
        explicit_acquisition_target=False,
    )
    return list(board.recommendations)



# Opportunity labels (modules.rankings' real opportunity-tier
# classification, already on every player asset via _player_asset) that
# mean "role trending up, price probably hasn't caught up yet" — the same
# labels rankings.py maps to workload_trend "Rising" for these tiers.
_BUY_LOW_OPPORTUNITY_LABELS = frozenset({"Backup With Upside", "Committee Back"})
# "Starter At Risk" is rankings.py's own workload_trend="Fragile" tier —
# established trade value from a starter reputation, but the opportunity
# signal underneath is already softening.
_SELL_HIGH_OPPORTUNITY_LABELS = frozenset({"Starter At Risk"})


def _classify_impact_tag(idea: Mapping[str, Any], confidence_label: str) -> str:
    """high_impact / buy_low / sell_high, or "" — real signals already on
    every idea (confidence_label, and each asset's opportunity_label), not
    new modeling. Priority order matches the concept sheet: a high-
    confidence idea is flagged as such first, then buy/sell opportunity."""

    if confidence_label == "High":
        return "high_impact"
    receive_labels = {
        str(asset.get("opportunity_label") or "")
        for asset in (idea.get("receive_assets") or [])
        if isinstance(asset, Mapping)
    }
    if receive_labels & _BUY_LOW_OPPORTUNITY_LABELS:
        return "buy_low"
    send_labels = {
        str(asset.get("opportunity_label") or "")
        for asset in (idea.get("send_assets") or [])
        if isinstance(asset, Mapping)
    }
    if send_labels & _SELL_HIGH_OPPORTUNITY_LABELS:
        return "sell_high"
    return ""


@dataclass(frozen=True)
class TradeIdeaCard:
    partner_team_name: str
    rationale: str
    trade_gain: int
    confidence_label: str
    market_realism_label: str
    reasoning_tags: tuple[str, ...]
    package: dict[str, Any]
    category: str
    value_edge_band: str
    impact_tag: str = ""
    landed_gm_target_player_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "partner_team_name": self.partner_team_name,
            "rationale": self.rationale,
            "trade_gain": self.trade_gain,
            "confidence_label": self.confidence_label,
            "market_realism_label": self.market_realism_label,
            "reasoning_tags": list(self.reasoning_tags),
            "package": self.package,
            "category": self.category,
            "value_edge_band": self.value_edge_band,
            "impact_tag": self.impact_tag,
            "landed_gm_target_player_ids": list(self.landed_gm_target_player_ids),
        }


def project_trade_idea_card(idea: Mapping[str, Any], *, is_headline: bool = False) -> TradeIdeaCard:
    gain = int(idea.get("trade_gain") or 0)
    edge_label = f"+{gain}" if gain > 0 else (f"-{abs(gain)}" if gain < 0 else "")
    package = compact_package(
        idea.get("send_assets"),
        idea.get("receive_assets"),
        value_edge=edge_label,
        confidence=_safe_text(idea.get("trade_confidence_label")),
    )
    # Headline placement is presentation order, not a property on the idea
    # itself — web's select_trade_hub_headline_idea is literally
    # order_trade_hub_visible_ideas(ideas)[0] (app.py), so the caller (which
    # already computes that same ordering) tells us via is_headline rather
    # than this function re-deriving rank from a Mapping with no board
    # context. modules/ can't import app.py to reuse that helper directly.
    category = "Headline Recommendation" if is_headline else trade_hub_ui.trade_hub_display_section(dict(idea))
    confidence_label = _safe_text(idea.get("trade_confidence_label"), "Low")
    return TradeIdeaCard(
        partner_team_name=_safe_text(idea.get("partner_team_name"), "Trade partner"),
        rationale=_safe_text(idea.get("rationale")),
        trade_gain=gain,
        confidence_label=confidence_label,
        market_realism_label=_safe_text(idea.get("market_realism_label"), "Thin"),
        reasoning_tags=tuple(str(tag) for tag in (idea.get("reasoning_tags") or ())),
        package=package,
        category=category,
        value_edge_band=trade_visual_language.trade_value_band(edge_label),
        impact_tag=_classify_impact_tag(idea, confidence_label),
        landed_gm_target_player_ids=tuple(
            str(pid) for pid in (idea.get("landed_gm_target_player_ids") or ())
        ),
    )


def _tag_landed_gm_targets(
    ideas: list[dict[str, Any]],
    *,
    gm_target_player_ids: frozenset[str],
) -> list[dict[str, Any]]:
    """Mark ideas that would land the user a GM Target (receive side only).

    Presentation-only tag — never changes ranking, score, or which ideas are
    generated. Comes from the same durable GM Targets watchlist the mobile
    GM Targets screen reads (modules.gm_targets), not an invented signal.
    """

    if not gm_target_player_ids:
        return ideas
    for idea in ideas:
        landed = sorted(
            {
                str(asset.get("player_id"))
                for asset in idea.get("receive_assets") or ()
                if isinstance(asset, dict)
                and str(asset.get("asset_type") or "") == "player"
                and str(asset.get("player_id") or "") in gm_target_player_ids
            }
        )
        idea["landed_gm_target_player_ids"] = landed
    return ideas


def generate_trade_idea_records(
    *,
    league_id: str,
    my_roster_id: int,
    players_df: pd.DataFrame,
    rosters: list[dict],
    league_settings: Mapping[str, Any] | None,
    score_field: str,
    team_strategy: str = "retool",
    max_ideas: int = MAX_TRADE_IDEAS,
    untouchable_player_ids: tuple[str, ...] = (),
    gm_target_player_ids: tuple[str, ...] = (),
    trade_block_player_ids: tuple[str, ...] = (),
    team_stance: str = "",
) -> list[dict[str, Any]]:
    """The full, Trust-enforced idea dicts — same shape modules.trade_ideas
    and modules.trade_hub_ui already work with (trade_confidence_label,
    send_assets/receive_assets, fit_grade, hub_* reason fields, etc.).

    `untouchable_player_ids` hard-blocks those players from every outgoing
    (send) package — sourced from the caller's GM Targets untouchable flag,
    resolved here to names because modules.trade_ideas.build_trade_ideas'
    protection list is name-keyed (matches the web app's own untouchables
    contract). `gm_target_player_ids` never changes what's generated — it
    only tags ideas that would land one of those players (see
    _tag_landed_gm_targets) so the UI can call it out.

    `trade_block_player_ids` is the Trade Finder feature: when non-empty,
    every outgoing package is built ONLY from these specific players (the
    ones the caller explicitly chose to shop) instead of the passive
    board's normal "anything not protected" pool — modules.trade_ideas.
    build_trade_ideas' own `trade_block_names` parameter already supports
    this restriction, it just wasn't wired up outside the web app before.
    Resolved to names for the same reason untouchables are.

    `team_stance` is the caller's OWN declared Team Situation
    (modules.team_stance: "rebuilding"/"competing"/"balanced", or "" for
    none set) — applied last, via modules.trade_ideas.apply_team_stance_framing,
    which only appends a short clause to each idea's rationale text. It
    never changes which ideas are generated, their scores, or their order.

    `generate_trade_ideas` narrows these to TradeIdeaCard for the mobile
    Trade Hub card UI; callers that need the raw engine fields — ranking via
    modules.trade_hub_ui.order_trade_hub_visible_ideas, or narrative
    building via modules.canonical_recommendation_narrative.build_trade_narrative
    (the Dashboard's Top Trade Opportunity tile) — should call this instead."""

    # OVR for every asset's PlayerIdentityRow badge (coridian_, Trade Hub
    # card screenshot: the colored tier ring alone doesn't say how good two
    # similarly-tiered players actually are relative to each other).
    # Computed once here, on the pool as handed in — BEFORE
    # apply_strategy_age_curve below touches `score_field` — so a player's
    # OVR matches the same percentile-against-the-full-ranked-pool contract
    # every other surface already uses (see
    # player_quick_view.overall_ratings_for_pool's docstring and
    # services/mobile_api_service.py's /rankings endpoint), not a number that
    # shifts with this request's team-strategy age curve. `_player_asset`
    # reads it straight off the row as "overall_rating"; callers whose pool
    # lacks `position`/`score_field` simply get no column, and
    # `_player_asset` already treats a missing value as "no rating" (None).
    if "position" in players_df.columns and score_field in players_df.columns:
        players_df = players_df.copy()
        players_df["overall_rating"] = player_quick_view.overall_ratings_for_pool(
            players_df, score_column=score_field
        )

    df_summary = build_league_summary(
        players_df,
        league_id,
        score_field=score_field,
        current_score_field="value_score",
        lineup_settings=dict(league_settings or {}),
    )
    if df_summary.empty:
        return []

    strategy_df = apply_strategy_age_curve(players_df, team_strategy, score_field)
    roster_owner_items = tuple(
        sorted(
            (str(roster.get("roster_id")), tuple(str(pid) for pid in (roster.get("players") or []) if pid is not None))
            for roster in rosters or []
        )
    )
    prefetched_rosters = [
        {"roster_id": roster_id, "players": list(player_ids), "platform": "sleeper"}
        for roster_id, player_ids in roster_owner_items
    ]

    untouchable_ids = {str(pid) for pid in untouchable_player_ids if str(pid)}
    untouchable_names: list[str] = []
    if untouchable_ids and "player_id" in strategy_df.columns and "name" in strategy_df.columns:
        matches = strategy_df[strategy_df["player_id"].astype(str).isin(untouchable_ids)]
        untouchable_names = [str(name) for name in matches["name"].tolist() if str(name)]

    trade_block_ids = {str(pid) for pid in trade_block_player_ids if str(pid)}
    trade_block_names: list[str] = []
    if trade_block_ids and "player_id" in strategy_df.columns and "name" in strategy_df.columns:
        matches = strategy_df[strategy_df["player_id"].astype(str).isin(trade_block_ids)]
        trade_block_names = [str(name) for name in matches["name"].tolist() if str(name)]

    raw_ideas = trade_ideas_module.build_trade_ideas(
        df_players=strategy_df,
        league_id=league_id,
        df_summary=df_summary,
        my_roster_id=my_roster_id,
        trade_block_names=trade_block_names,
        untouchable_names=untouchable_names,
        role_map={},
        max_ideas=max_ideas,
        score_field=score_field,
        pick_score_multiplier=strategy_adjusted_pick_score_multiplier(1.0, team_strategy),
        team_strategy=team_strategy,
        # A Trade Finder selection IS the "intentional player-focused search"
        # build_trade_ideas' own docstring describes — without this, picking
        # any core/protected starter (a QB1, a locked-in WR1) silently empties
        # the trade-block pool and the search returns zero ideas no matter
        # what's selected, which is exactly what it looked like from outside.
        allow_protected_focus=bool(trade_block_names),
        league_settings=dict(league_settings or {}),
        draft_status=None,
        search_budget="",
        prefetched_rosters=prefetched_rosters or None,
    )
    enforced = enforce_generated_trade_ideas(
        raw_ideas,
        df_players=strategy_df,
        league_id=league_id,
        df_summary=df_summary,
        my_roster_id=my_roster_id,
        rosters=rosters,
        untouchables=tuple(untouchable_names),
    )
    tagged = _tag_landed_gm_targets(
        list(enforced),
        gm_target_player_ids=frozenset(str(pid) for pid in gm_target_player_ids if str(pid)),
    )
    return trade_ideas_module.apply_team_stance_framing(tagged, team_stance)


# Idea generation re-applies the valuation lens across the whole players
# table and searches every roster for partner fits — real work, redone from
# scratch on every call even though a given (league, roster, strategy,
# lens) combo can't change faster than the underlying Sleeper roster data
# does. Same live-time-bucket idiom modules.sleeper uses for its own
# endpoint caches. Lives here (not in services/mobile_api_service.py, where
# it first shipped) so modules.dashboard_engine's Top Trade Opportunity
# tile — which calls this exact function with the exact same arguments to
# pull one headline idea — shares the same cache instead of independently
# recomputing the identical search Trade Hub may have just cached moments
# earlier for the same user.
TRADE_HUB_IDEAS_TTL_SECONDS = 30


def _trade_hub_ideas_cache_bucket() -> int:
    return int(time.time() // TRADE_HUB_IDEAS_TTL_SECONDS)


@lru_cache(maxsize=256)
def _generate_trade_idea_records_cached(
    league_id: str,
    roster_id: int,
    strategy: str,
    lens: str,
    players_db_path: str,
    untouchable_player_ids: tuple[str, ...],
    gm_target_player_ids: tuple[str, ...],
    _bucket: int,
) -> list[dict[str, Any]]:
    league = sleeper.get_league(league_id)
    if not league:
        return []
    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    players_df = rankings.load_players(players_db_path)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(players_db_path)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="trade_hub_ideas_cache", league=league
    )
    if players_df.empty:
        return []

    valued = league_value_settings.apply_valuation_lens(players_df, lens, settings)
    score_field = league_value_settings.valuation_score_field(lens)
    rosters = sleeper.get_rosters(league_id)
    return generate_trade_idea_records(
        league_id=league_id,
        my_roster_id=roster_id,
        players_df=valued,
        rosters=rosters,
        untouchable_player_ids=untouchable_player_ids,
        gm_target_player_ids=gm_target_player_ids,
        league_settings=settings,
        score_field=score_field,
        team_strategy=strategy,
    )


# Per-cache-key single-flight locks — same pattern, and same reason, as
# modules.playoff_simulator's _playoff_odds_lock_for: functools.lru_cache's
# own internal lock only protects the cache dict itself during a
# lookup/insert, it does NOT serialize the wrapped function's *execution*.
# Without this, N concurrent requests that all miss the same (league_id,
# roster_id, strategy, lens, untouchables, gm_targets, bucket) key before
# the first one finishes would each independently pay the full
# build_trade_ideas search cost (measured at ~150-300ms of mostly
# pure-Python, GIL-held work per call for a realistic 12-14 team dynasty
# league — see scripts/profile_trade_hub.py) instead of sharing one. That
# directly contradicts this cache's own documented purpose above (one
# shared entry per 30s window across every caller), and on this service's
# single uvicorn worker (see docker-compose.yml's mobile-api comment),
# every one of those duplicate runs holds the one process's GIL back-to-
# back, stalling every other in-flight request for that much longer than
# necessary. A concrete trigger: the Dashboard's Top Trade Opportunity tile
# and the Trade Hub screen both cold-loading for the same user/league
# within the same request burst (a real multi-screen session, or the
# mobile client's own navigation retries) — both ask for the exact same
# cache key.
_TRADE_HUB_IDEAS_LOCK_PRUNE_THRESHOLD = 500

_trade_hub_ideas_locks: dict[tuple[Any, ...], threading.Lock] = {}
_trade_hub_ideas_locks_guard = threading.Lock()


def _trade_hub_ideas_lock_for(key: tuple[Any, ...]) -> threading.Lock:
    with _trade_hub_ideas_locks_guard:
        lock = _trade_hub_ideas_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _trade_hub_ideas_locks[key] = lock
        if len(_trade_hub_ideas_locks) > _TRADE_HUB_IDEAS_LOCK_PRUNE_THRESHOLD:
            # Safe to drop any lock from an older bucket: this function's
            # only caller always passes the *current* bucket (see
            # generate_trade_idea_records_cached below), so a key whose
            # bucket doesn't match the one we were just asked for can never
            # be requested again. Skip anything still held, just in case a
            # search genuinely spans a bucket rollover.
            current_bucket = key[-1]
            stale = [
                existing_key
                for existing_key, existing_lock in _trade_hub_ideas_locks.items()
                if existing_key[-1] != current_bucket and not existing_lock.locked()
            ]
            for existing_key in stale:
                _trade_hub_ideas_locks.pop(existing_key, None)
        return lock


def generate_trade_idea_records_cached(
    *,
    league_id: str,
    roster_id: int,
    strategy: str,
    lens: str,
    players_db_path: str,
    untouchable_player_ids: tuple[str, ...] = (),
    gm_target_player_ids: tuple[str, ...] = (),
    team_stance: str = "",
) -> list[dict[str, Any]]:
    """Cached front door for `generate_trade_idea_records` — resolves its
    own players_df/settings/rosters from just (league_id, lens) rather than
    accepting them as arguments, so two different callers (Trade Hub's own
    endpoint, Dashboard's trade tile) asking about the same league/roster/
    strategy/lens combo within the same 30s window hit one cache entry
    instead of each re-running the full search independently.

    `untouchable_player_ids`/`gm_target_player_ids` are per-user GM Targets
    state, so they're part of the cache key (sorted for a stable key
    regardless of input order) — two users sharing a roster with different
    GM Targets never see each other's untouchable/target tagging.

    `team_stance` (the caller's own declared Team Situation) is applied
    OUTSIDE the lru_cache boundary — a stance-aware rationale clause is a
    cheap string append, not worth invalidating/duplicating the expensive
    search cache entry over. See modules.trade_ideas.apply_team_stance_framing.

    Single-flight per cache key: see `_trade_hub_ideas_lock_for`'s
    docstring-comment for why this needs its own lock on top of
    `lru_cache`."""

    key = (
        league_id,
        roster_id,
        strategy,
        lens,
        players_db_path,
        tuple(sorted({str(pid) for pid in untouchable_player_ids if str(pid)})),
        tuple(sorted({str(pid) for pid in gm_target_player_ids if str(pid)})),
        _trade_hub_ideas_cache_bucket(),
    )
    with _trade_hub_ideas_lock_for(key):
        records = _generate_trade_idea_records_cached(*key)
    return trade_ideas_module.apply_team_stance_framing(records, team_stance)


def generate_trade_finder_records(
    *,
    league_id: str,
    roster_id: int,
    strategy: str,
    lens: str,
    players_db_path: str,
    trade_block_player_ids: tuple[str, ...],
    untouchable_player_ids: tuple[str, ...] = (),
    gm_target_player_ids: tuple[str, ...] = (),
    team_stance: str = "",
) -> list[dict[str, Any]]:
    """Trade Finder: "select these specific players/picks, find who'd want
    them" — the same idea-generation engine as the passive Trade Hub board
    (modules.trade_ideas.build_trade_ideas), but with the outgoing package
    pool restricted to exactly the caller's chosen players via that
    function's own `trade_block_names` parameter (see
    generate_trade_idea_records' docstring). Deliberately NOT the cached
    front door above: an on-demand, user-initiated search over an
    arbitrary player selection isn't the kind of repeated-within-30s call
    the passive board's cache bucket exists to dedupe, and caching it would
    mean one more dimension (the selection itself) in the cache key for no
    real benefit.

    Picks aren't handled here (build_trade_ideas' trade_block_names is
    player-name-keyed only) — a selected pick simply doesn't narrow the
    search the way a selected player does yet.
    """
    league = sleeper.get_league(league_id)
    if not league:
        return []
    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    players_df = rankings.load_players(players_db_path)
    if players_df is None or players_df.empty:
        players_df = rankings.build_players_table(players_db_path)
    players_df = player_eligibility.filter_current_fantasy_players(
        players_df, surface="trade_finder", league=league
    )
    if players_df.empty:
        return []

    valued = league_value_settings.apply_valuation_lens(players_df, lens, settings)
    score_field = league_value_settings.valuation_score_field(lens)
    rosters = sleeper.get_rosters(league_id)
    return generate_trade_idea_records(
        league_id=league_id,
        my_roster_id=roster_id,
        players_df=valued,
        rosters=rosters,
        untouchable_player_ids=untouchable_player_ids,
        gm_target_player_ids=gm_target_player_ids,
        trade_block_player_ids=trade_block_player_ids,
        league_settings=settings,
        score_field=score_field,
        team_strategy=strategy,
        team_stance=team_stance,
    )


def generate_trade_ideas(
    *,
    league_id: str,
    my_roster_id: int,
    players_df: pd.DataFrame,
    rosters: list[dict],
    league_settings: Mapping[str, Any] | None,
    score_field: str,
    team_strategy: str = "retool",
    max_ideas: int = MAX_TRADE_IDEAS,
    team_stance: str = "",
) -> list[TradeIdeaCard]:
    """The mobile Trade Hub board — same engine call as the web app's Trade
    Hub (modules.trade_ideas.build_trade_ideas) and the same production
    Trust enforcement boundary, fed by a fresh per-request league summary
    (modules.team_eval.build_league_summary) rather than app.py's
    Streamlit-session-cached version — see module docstring for why.

    `team_stance` is the caller's declared Team Situation; see
    generate_trade_idea_records' docstring — presentation-only rationale bias."""

    enforced = generate_trade_idea_records(
        league_id=league_id,
        my_roster_id=my_roster_id,
        players_df=players_df,
        rosters=rosters,
        league_settings=league_settings,
        score_field=score_field,
        team_strategy=team_strategy,
        max_ideas=max_ideas,
        team_stance=team_stance,
    )
    return [project_trade_idea_card(idea) for idea in enforced]
