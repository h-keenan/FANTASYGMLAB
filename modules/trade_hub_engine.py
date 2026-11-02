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

import time
from dataclasses import dataclass
from typing import Any, Mapping

import pandas as pd

from modules import keepers as keepers_module
from modules import league_rankings
from modules import league_value_settings
from modules import player_quick_view
from modules import redis_cache
from modules import sleeper
from modules import team_stance as team_stance_module
from modules import trade_hub_presentation
from modules import trade_posture as trade_posture_module
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


# The neutral posture every "no team context" valuation uses: the signed-in
# Analyzer's default (POST .../trade-analyzer `strategy`), the bot's interesting
# trades and the public Analyzer's board. One name so they cannot drift apart.
DEFAULT_ANALYZER_STRATEGY = "retool"


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

    sd = league_value_settings.smooth_decline
    sy = league_value_settings.smooth_youth_bonus

    def decline(pos_list, start, floor):
        return sd(ages, start, floor).where(positions.isin(pos_list), 1.0)

    if strategy_key == "contender":
        multiplier = sy(ages, ((22.0, 0.98), (25.0, 1.04), (30.0, 1.04), (32.0, 1.0)))
        multiplier = multiplier * decline(["RB"], 29, 0.94)
    elif strategy_key == "fringe_contender":
        multiplier = sy(ages, ((22.0, 1.01), (24.0, 1.01), (25.0, 1.025), (29.0, 1.025), (31.0, 1.0)))
        multiplier = multiplier * decline(["RB", "WR", "TE"], 31, 0.96)
    elif strategy_key == "retool":
        multiplier = sy(ages, ((22.0, 1.04), (25.0, 1.04), (26.0, 1.01), (29.0, 1.01), (31.0, 1.0)))
        multiplier = multiplier * decline(["RB"], 28, 0.91) * decline(["WR", "TE"], 31, 0.94)
    elif strategy_key == "rebuild":
        multiplier = sy(ages, ((23.0, 1.10), (25.0, 1.06), (26.0, 1.02), (28.0, 1.0)))
        multiplier = (
            multiplier
            * decline(["RB"], 28, 0.82)
            * decline(["WR"], 30, 0.86)
            * decline(["TE"], 31, 0.88)
            * decline(["QB"], 34, 0.92)
        )
    elif strategy_key == "tank":
        multiplier = sy(ages, ((23.0, 1.15), (25.0, 1.09), (26.0, 1.0)))
        multiplier = (
            multiplier
            * decline(["RB"], 27, 0.75)
            * decline(["WR"], 30, 0.80)
            * decline(["TE"], 31, 0.84)
            * decline(["QB"], 34, 0.88)
        )

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
# workload_trend="Cooling" is rankings.py's weekly-recency read: a real,
# multi-week usage decline (>=4 played games, display-grade confidence),
# never a one-bad-week blip (see compute_recency_features/
# recency_trend_display's own gating). It fires across every opportunity
# tier (an "Elite Opportunity" starter can still be cooling off), so without
# this check a player whose role is genuinely shrinking never got flagged
# sell_high unless they also happened to carry the separate "Starter At
# Risk" label.
_SELL_HIGH_WORKLOAD_TRENDS = frozenset({"Cooling"})


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
    send_assets = [asset for asset in (idea.get("send_assets") or []) if isinstance(asset, Mapping)]
    send_labels = {str(asset.get("opportunity_label") or "") for asset in send_assets}
    send_trends = {str(asset.get("workload_trend") or "") for asset in send_assets}
    if (send_labels & _SELL_HIGH_OPPORTUNITY_LABELS) or (send_trends & _SELL_HIGH_WORKLOAD_TRENDS):
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
    # Full, untruncated per-side totals the idea's own trade_gain is derived
    # from (modules.trade_ideas' my_score/their_score) — added for web-next's
    # Trade Hub port (Revision 3), which renders modules.trade_visual_language.
    # value_edge_lean_bar_html's "who has the edge" bar from these same two
    # numbers, exactly like the Streamlit page does. `package["send"/"receive"]`
    # is truncated to MAX_SIDE_ASSETS and can't be re-summed for this: a trade
    # with more assets than that per side would silently misrepresent the
    # lean. Additive-only field; existing mobile/web consumers that don't
    # read it are unaffected.
    send_score: int = 0
    receive_score: int = 0
    # Stable identity for this exact idea (modules.trade_hub_presentation.
    # idea_recommendation_id — the same canonical hash Trade Hub's own
    # session-state handoff/focus plumbing already keys on), added so a
    # client can ask GET .../trade-hub/{recommendation_id}/share-card.png
    # for a branded PNG of precisely this idea without re-posting its
    # contents (the server re-derives the idea from its own cached search
    # instead of trusting a client payload — see that endpoint's docstring).
    recommendation_id: str = ""
    # Team posture the idea was graded and ranked under (modules.trade_posture):
    # the user's resolved posture, the Analyzer's honest label when it is a
    # trade-off ("GOOD VALUE, COSTS YOUR LINEUP"), the one-line note, whether
    # the idea fits the posture, and the lineup points it moves. Additive.
    posture: dict[str, Any] | None = None
    posture_label: str = ""
    posture_note: str = ""
    posture_alignment: str = ""
    lineup_points: float | None = None

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
            "send_score": self.send_score,
            "receive_score": self.receive_score,
            "recommendation_id": self.recommendation_id,
            "posture": self.posture,
            "posture_label": self.posture_label,
            "posture_note": self.posture_note,
            "posture_alignment": self.posture_alignment,
            "lineup_points": self.lineup_points,
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
    category = "Headline Recommendation" if is_headline else trade_hub_presentation.trade_hub_display_section(dict(idea))
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
        send_score=int(idea.get("my_score") or 0),
        receive_score=int(idea.get("their_score") or 0),
        recommendation_id=trade_hub_presentation.idea_recommendation_id(idea),
        posture=dict(idea["posture"]) if isinstance(idea.get("posture"), Mapping) else None,
        posture_label=_safe_text(idea.get("posture_label")),
        posture_note=_safe_text(idea.get("posture_note")),
        posture_alignment=_safe_text(idea.get("posture_alignment")),
        lineup_points=idea.get("posture_lineup_points"),
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


def _apply_keeper_context(
    frame: pd.DataFrame, score_field: str, keeper_context: Mapping[str, Any] | None
) -> pd.DataFrame:
    """Fold keeper surplus into player values (same adjustment the Trade
    Analyzer uses, applied after the strategy age curve). Unknown cost or any
    failure silently keeps the normal values."""

    if not keeper_context:
        return frame
    try:
        adjusted = keepers_module.keeper_adjusted_values(
            valued=frame,
            score_field=score_field,
            num_teams=int(keeper_context.get("num_teams") or 12),
            current_picks=list(keeper_context.get("current_picks") or []),
            previous_picks=list(keeper_context.get("previous_picks") or []),
            round_penalty=int(keeper_context.get("round_penalty") or 0),
        )
        return keepers_module.apply_keeper_values(frame, score_field, adjusted) if adjusted else frame
    except Exception:
        return frame


def _keeper_context_for_league(league: Mapping[str, Any], league_id: str, round_penalty: int) -> dict[str, Any] | None:
    try:
        current_picks = keepers_module.latest_draft_picks(sleeper.get_league_drafts(league_id), sleeper.get_draft_picks)
        previous_id = str(league.get("previous_league_id") or "")
        previous_picks = (
            keepers_module.latest_draft_picks(sleeper.get_league_drafts(previous_id), sleeper.get_draft_picks)
            if previous_id and previous_id != "0"
            else []
        )
        return {
            "num_teams": int(league.get("total_rosters") or (league.get("settings") or {}).get("num_teams") or 12),
            "current_picks": current_picks,
            "previous_picks": previous_picks,
            "round_penalty": int(round_penalty or 0),
        }
    except Exception:
        return None


_IDP_FAMILIES = frozenset({"DL", "LB", "DB", "DE", "DT", "NT", "OLB", "ILB", "MLB", "CB", "S", "SS", "FS"})


def exclude_idp_rows(players_df: pd.DataFrame) -> pd.DataFrame:
    """Trade Hub never builds ideas around defenders: their IDP-model values
    are not part of this engine's trusted pricing. Offense-only frames (every
    frame today) pass through untouched; silently, with no message."""

    if players_df is None or players_df.empty or "position" not in players_df.columns:
        return players_df
    is_idp = players_df["position"].astype(str).str.upper().isin(_IDP_FAMILIES)
    return players_df[~is_idp] if bool(is_idp.any()) else players_df


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
    df_summary: pd.DataFrame | None = None,
    trade_block_pick_ids: tuple[str, ...] = (),
    require_receive_picks: bool = False,
    keeper_context: Mapping[str, Any] | None = None,
    finder_trace: "trade_ideas_module.FinderSearchTrace | None" = None,
) -> list[dict[str, Any]]:
    """The full, Trust-enforced idea dicts — same shape modules.trade_ideas
    and modules.trade_hub_presentation already work with (trade_confidence_label,
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

    `trade_block_pick_ids` / `require_receive_picks` are Trade Finder's pick
    controls: the caller's own picks to offer (GET .../draft-picks pick_id
    format, "season:round:original_roster_id"), resolved inside
    build_trade_ideas against only the picks this roster really owns per
    Sleeper's traded-picks data, and a "must get picks back" filter on the
    return side. Both default off, leaving the passive board unchanged.

    `team_stance` is the caller's OWN declared Team Situation
    (modules.team_stance: "rebuilding"/"competing"/"balanced", or "" for
    none set) — applied last, via modules.trade_ideas.apply_team_stance_framing,
    which only appends a short clause to each idea's rationale text. It
    never changes which ideas are generated, their scores, or their order.

    `generate_trade_ideas` narrows these to TradeIdeaCard for the mobile
    Trade Hub card UI; callers that need the raw engine fields — ranking via
    modules.trade_hub_presentation.order_trade_hub_visible_ideas, or narrative
    building via modules.canonical_recommendation_narrative.build_trade_narrative
    (the Dashboard's Top Trade Opportunity tile) — should call this instead.

    `df_summary` is an optional precomputed override for the per-roster
    league summary below (modules.team_eval.build_league_summary) — the
    same "accept it precomputed, else compute fresh" contract
    modules.dashboard_engine.compose_next_move_briefing already uses for
    its own roster_df/lineup_df/injury_context. `_generate_trade_idea_records_cached`
    passes the ALREADY-CACHED result of modules.league_rankings.
    build_league_summary_and_draft_capital_cached here instead of letting
    this function redo that same full-league-wide pass from scratch on
    every cache miss (coridian_, 2026-10-18: "it still takes too long to
    load" — this exact recomputation, not a missing cache, was the real
    cost behind Dashboard's ~11s cold load). Omitting it (every existing
    test/caller) falls back to the original fresh computation, unchanged."""

    players_df = exclude_idp_rows(players_df)

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

    if df_summary is None:
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
    strategy_df = _apply_keeper_context(strategy_df, score_field, keeper_context)
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
        trade_block_pick_ids=[str(pid) for pid in trade_block_pick_ids if str(pid)],
        require_receive_picks=bool(require_receive_picks),
        finder_trace=finder_trace,
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
    if finder_trace is not None:
        # Trust enforcement is the last word on realistic trades: an idea it
        # drops is not realistic. Count that honestly, then (only when nothing
        # realistic survived) run the closest non-realistic packages through
        # the SAME enforcement so a "closest option" is never something Trust
        # would have refused outright.
        dropped = len(raw_ideas) - len(enforced)
        if dropped > 0:
            finder_trace.count("trust", dropped)
        if not enforced:
            near = finder_trace.closest_ideas(limit=6)
            kept = enforce_generated_trade_ideas(
                near,
                df_players=strategy_df,
                league_id=league_id,
                df_summary=df_summary,
                my_roster_id=my_roster_id,
                rosters=rosters,
                untouchables=tuple(untouchable_names),
            ) if near else []
            finder_trace.enforced_closest = list(kept)[:3]
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
# coridian_, 2026-10-19, performance audit: widened from the original 30s
# to 2 minutes, alongside the same change in modules.league_value_settings/
# modules.league_rankings/modules.waivers_logic — a real league's roster
# doesn't change faster than every couple minutes in practice.
TRADE_HUB_IDEAS_TTL_SECONDS = 120


def _trade_hub_ideas_cache_bucket() -> int:
    return int(time.time() // TRADE_HUB_IDEAS_TTL_SECONDS)


def _generate_trade_idea_records_cached(
    league_id: str,
    roster_id: int,
    strategy: str,
    lens: str,
    players_db_path: str,
    untouchable_player_ids: tuple[str, ...],
    gm_target_player_ids: tuple[str, ...],
    keeper_round_penalty: int,
    _bucket: int,
) -> list[dict[str, Any]]:
    league = sleeper.get_league(league_id)
    if not league:
        return []
    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    # coridian_, 2026-10-19: "Dashboard takes too long to load" — this used
    # to run its own load -> filter -> apply_valuation_lens pass here, the
    # exact same "asker-independent, redone from scratch" cost
    # build_valued_players_frame_cached already exists to fix (same 30s
    # Redis-backed cache league_rankings/waivers_logic/playoff_simulator and
    # this same function's own df_summary call just below already share).
    # get_league_dashboard had already computed and cached this identical
    # (league_id, lens) frame moments earlier in the same request via that
    # cached front door, but this call site never reused it, so Dashboard's
    # trade tile paid the full valuation pass a second time on any cache
    # miss of trade_hub_ideas's own separate 30s bucket.
    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=lens, players_db_path=players_db_path
    )
    if valued.empty:
        return []
    score_field = league_value_settings.valuation_score_field(lens)
    rosters = sleeper.get_rosters(league_id)
    # coridian_, 2026-10-18: "it still takes too long to load" — Dashboard's
    # ~11s cold load traced to this exact per-roster league summary being
    # redone from scratch here on every cache miss, even though League
    # Rankings/Draft Center already share one cached copy of the identical
    # computation (league_rankings.build_league_summary_and_draft_capital_cached,
    # same 30s window). Reusing that cache entry here means Dashboard,
    # Trade Hub, League Rankings, and Draft Center all share one pass
    # instead of each paying it independently.
    df_summary, _draft_capital_summary = league_rankings.build_league_summary_and_draft_capital_cached(
        league_id=league_id, lens=lens, players_db_path=players_db_path
    )
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
        df_summary=df_summary,
        keeper_context=(
            _keeper_context_for_league(league, league_id, keeper_round_penalty)
            if settings.get("_keeper_mode")
            else None
        ),
    )


# Redis-backed single-flight + cache (modules.redis_cache.redis_single_flight_cache)
# — same pattern, and same reason, as modules.playoff_simulator and
# modules.league_rankings use for their own caches below: without a
# single-flight guard, N concurrent requests that all miss the same
# (league_id, roster_id, strategy, lens, untouchables, gm_targets, bucket)
# key before the first finishes would each independently pay the full
# build_trade_ideas search cost (measured at ~150-300ms of mostly
# pure-Python, GIL-held work per call for a realistic 12-14 team dynasty
# league — see scripts/profile_trade_hub.py) instead of sharing one. That
# directly contradicts this cache's own documented purpose above (one
# shared entry per 30s window across every caller).
#
# This used to be a per-process threading.Lock + functools.lru_cache pair,
# which only protected ONE uvicorn worker: under docker-compose.yml's
# multiple mobile-api workers, each worker has its own process memory, so
# that old pair would let the same expensive search run redundantly once
# per worker AND a cache hit in worker A would never help a request that
# happened to land on worker B. The Redis-backed version below fixes both:
# the distributed lock makes only one worker, cluster-wide, actually run a
# given search, and the cached result lives in Redis, not in any one
# worker's memory, so every worker serves it.
_TRADE_HUB_IDEAS_LOCK_TIMEOUT_SECONDS = 15.0


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
    keeper_round_penalty: int = 0,
    posture: Mapping[str, Any] | None = None,
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
    OUTSIDE the cache boundary — a stance-aware rationale clause is a cheap
    string append, not worth invalidating/duplicating the expensive search
    cache entry over. See modules.trade_ideas.apply_team_stance_framing.

    Single-flight + cache, now shared across every mobile-api worker via
    Redis: see modules.redis_cache.redis_single_flight_cache and this
    module's own comment above it."""

    key = (
        league_id,
        roster_id,
        strategy,
        lens,
        players_db_path,
        tuple(sorted({str(pid) for pid in untouchable_player_ids if str(pid)})),
        tuple(sorted({str(pid) for pid in gm_target_player_ids if str(pid)})),
        keepers_module.clamp_round_penalty(keeper_round_penalty),
        _trade_hub_ideas_cache_bucket(),
    )
    cache_key = redis_cache.build_cache_key("trade_hub_ideas", *key)
    records = redis_cache.redis_single_flight_cache(
        cache_key=cache_key,
        ttl_seconds=TRADE_HUB_IDEAS_TTL_SECONDS,
        compute=lambda: _generate_trade_idea_records_cached(*key),
        lock_timeout_seconds=_TRADE_HUB_IDEAS_LOCK_TIMEOUT_SECONDS,
    )
    # `posture` (the caller's resolved team posture) is stamped OUTSIDE the
    # cache boundary like the stance framing: the search itself is keyed on the
    # posture's strategy key (callers pass posture["key"] as `strategy`).
    return trade_posture_module.stamp_records(
        trade_ideas_module.apply_team_stance_framing(records, team_stance), posture
    )


def roster_posture(
    *,
    league_id: str,
    roster: Mapping[str, Any] | None,
    lens: str,
    players_db_path: str,
    declared_stance: Any = "",
    client_strategy: str = "",
    rankings_frame: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """The ONE posture for a roster, for every surface that generates, ranks or
    grades trades (Analyzer, Hub, Finder, Dashboard, GM Plan, glance, alerts).

    Declared Team Situation > the league rankings' auto classification (roster
    strength blended with the real record, age curve, draft capital) > the
    client's value (``trade_posture.resolve_posture``). Reads one already-cached
    rankings row (pass ``rankings_frame`` when the caller has it); every lookup
    fails open to the next source."""

    roster = roster or {}
    declared = ""
    if declared_stance:
        try:
            declared = team_stance_module.team_strategy_for_stance(declared_stance)
        except Exception:
            declared = ""
    auto = ""
    power_rank = None
    league_size = None
    try:
        frame = rankings_frame
        if frame is None:
            frame = league_rankings.build_league_rankings_frame_cached(
                league_id=league_id, lens=lens, players_db_path=players_db_path
            )
        if frame is not None and not frame.empty:
            league_size = len(frame)
            match = frame[frame["roster_id"].astype(str) == str(roster.get("roster_id") or "")]
            if not match.empty:
                row = match.iloc[0]
                auto = _clean_scalar(row.get("strategy"))
                power_rank = _clean_scalar(row.get("power_rank"))
    except Exception:
        pass
    return trade_posture_module.resolve_posture(
        declared_strategy=declared,
        auto_strategy=auto,
        client_strategy=client_strategy,
        power_rank=power_rank,
        league_size=league_size,
        record=roster.get("settings"),
    )


def _clean_scalar(value: Any) -> Any:
    try:
        if value is None or (isinstance(value, float) and value != value):
            return ""
    except Exception:
        return ""
    return value if not hasattr(value, "item") else value.item()


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
    trade_block_pick_ids: tuple[str, ...] = (),
    require_receive_picks: bool = False,
    finder_trace: "trade_ideas_module.FinderSearchTrace | None" = None,
    posture: Mapping[str, Any] | None = None,
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

    Picks: `trade_block_pick_ids` offers the caller's selected picks
    (players-only, picks-only, or both), and `require_receive_picks` keeps
    only packages whose return includes at least one of the partner's real
    owned picks. Pick valuation is the engine's own (_build_roster_pick_assets,
    the same per-pick model GET .../draft-picks and Trade Analyzer use) —
    see generate_trade_idea_records' docstring.
    """
    league = sleeper.get_league(league_id)
    if not league:
        return []
    settings = league_value_settings.detect_league_value_settings_from_payload(league)

    # Deliberately not routed through this module's own 30s trade-ideas
    # cache (see docstring above), but the expensive valuation-lens pass
    # itself is still worth sharing with whatever ELSE just asked about
    # this same (league_id, lens) -- Dashboard, Trade Hub, League Rankings,
    # Draft Center, Waivers all already reuse this exact cached frame
    # (league_value_settings.build_valued_players_frame_cached) rather than
    # each re-running load -> filter -> apply_valuation_lens from scratch.
    valued = league_value_settings.build_valued_players_frame_cached(
        league_id=league_id, lens=lens, players_db_path=players_db_path
    )
    if valued.empty:
        return []
    score_field = league_value_settings.valuation_score_field(lens)
    rosters = sleeper.get_rosters(league_id)
    records = generate_trade_idea_records(
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
        trade_block_pick_ids=trade_block_pick_ids,
        require_receive_picks=require_receive_picks,
        finder_trace=finder_trace,
    )
    if finder_trace is not None and posture:
        finder_trace.enforced_closest = trade_posture_module.stamp_records(
            list(finder_trace.enforced_closest), posture
        )
    return trade_posture_module.stamp_records(records, posture)


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


# ---------------------------------------------------------------------------
# Hold verdict + plain-English posture (new-user guidance audit, 2026-10)
#
# Pure, cheap functions over already-computed inputs (the projected idea
# cards, the declared stance, one already-cached rankings row, the league
# payload). Nothing here runs the idea search or any valuation; a "hold"
# is only ever built from those real inputs.

# An idea "clears the bar" when it is not a low-confidence/close-call idea and
# the value gain is at least this many points (same scale as card.trade_gain).
HOLD_MIN_ACTIONABLE_TRADE_GAIN = 200
# A top-third power rank counts as a team with little pressure to trade.
HOLD_CONTENDER_TOP_FRACTION = 1 / 3
# Below this fraction of the regular season the record is too small a sample.
HOLD_SMALL_SAMPLE_SEASON_FRACTION = 0.15

POSTURE_SENTENCES = {
    "contender": "You're competing now, so ideas favor current value.",
    "fringe_contender": "You're in the hunt, so ideas favor players who help soon.",
    "retool": "You're balancing now and later, so ideas favor younger starters.",
    "rebuild": "You're building for later, so ideas favor young players and picks.",
    "tank": "You're building for later, so ideas lean hardest toward youth and picks.",
}


def posture_sentence(strategy: object) -> str:
    """Plain-English line for the effective strategy ('' if unknown)."""

    return POSTURE_SENTENCES.get(_safe_text(strategy).strip().lower(), "")


def _idea_clears_bar(card: Mapping[str, Any]) -> bool:
    if trade_visual_language.confidence_level(_safe_text(card.get("confidence_label"))) == "low":
        return False
    try:
        return int(card.get("trade_gain") or 0) >= HOLD_MIN_ACTIONABLE_TRADE_GAIN
    except (TypeError, ValueError):
        return False


def build_hold_verdict(
    cards: list[Mapping[str, Any]],
    *,
    strategy: object = "",
    power_rank: int | None = None,
    team_count: int | None = None,
    season_progress: float = 0.0,
    in_season: bool = False,
    trade_window: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """Return a hold block, or None when trading is the better answer.

    Reasons, in priority order: deadline passed (trading closed); no ideas;
    no idea clears the bar; a top-third competing team with no high-impact
    idea; too small an in-season sample. `why` lists only facts we have.
    """

    window = trade_window or {}
    competing = _safe_text(strategy).lower() in {"contender", "fringe_contender"}
    why: list[dict[str, str]] = []

    def fact(factor: str, text: str) -> None:
        why.append({"factor": factor, "text": text})

    if window.get("trade_deadline_passed"):
        week = window.get("trade_deadline_week")
        fact("context", f"Your league's trade deadline was week {week}." if week else "Your league's trade deadline has passed.")
        fact("context", "Trades reopen after the season.")
        return {
            "verdict": "hold",
            "reason": "trade_deadline_passed",
            "headline": "Trading is closed. Hold.",
            "why": why,
            "ideas_optional": False,
        }

    clearing = [card for card in cards if _idea_clears_bar(card)]
    has_high_impact = any(_safe_text(card.get("impact_tag")) == "high_impact" for card in cards)
    top_third = bool(power_rank and team_count and power_rank <= max(1, round(team_count * HOLD_CONTENDER_TOP_FRACTION)))

    reason = ""
    if not cards:
        reason = "no_ideas"
    elif not clearing:
        reason = "none_clear_bar"
    elif competing and top_third and not has_high_impact:
        reason = "contender_no_need"
    elif in_season and 0 < season_progress < HOLD_SMALL_SAMPLE_SEASON_FRACTION and not has_high_impact:
        reason = "small_sample"
    if not reason:
        return None

    if not cards:
        fact("ideas", "No trade idea fit your roster and your league's rosters today.")
    elif not clearing:
        fact("ideas", "None of today's ideas is a clear win for you: each is a small gain or a long shot.")
    elif reason == "contender_no_need":
        fact("ideas", "No idea is a high-impact upgrade for your lineup.")
    elif reason == "small_sample":
        fact("context", "It's early in the season, so records and trends say little yet.")
    if power_rank and team_count:
        fact("competition", f"Your team ranks #{power_rank} of {team_count} for power in this league.")
    if competing and reason in {"contender_no_need", "none_clear_bar"}:
        fact("posture", "You're competing now, so a small gain rarely beats keeping your lineup intact.")
    return {
        "verdict": "hold",
        "reason": reason,
        "headline": "Holding is the best move right now.",
        "why": why,
        "ideas_optional": bool(cards),
    }
