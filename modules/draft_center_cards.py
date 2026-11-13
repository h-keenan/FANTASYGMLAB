import pandas as pd
from modules import league_display
from modules import team_eval as team_eval_module

_safe_text = league_display._safe_text


_safe_positive_int = league_display._safe_positive_int


_format_rank = league_display._format_rank


tidy_label = league_display.tidy_label


def _recommendation_reason_text(value: str, limit: int = 120) -> str:
    text = " ".join(_safe_text(value).split())
    return league_display._truncate_text(text, limit) if text else ""


def _draft_rank_cutoffs(league_size: int) -> tuple[int, int]:
    top_cut = max(2, league_size // 3)
    bottom_cut = max(top_cut + 1, league_size - top_cut + 1)
    return top_cut, bottom_cut


def _draft_posture_profile(
    team_row: pd.Series | dict | None,
    league_size: int,
) -> dict:
    team = team_row if isinstance(team_row, (pd.Series, dict)) else {}
    strategy_key = team_eval_module.normalize_team_strategy(
        team.get("strategy") or team.get("mode") or team.get("strategy_key")
    )
    draft_rank = _safe_positive_int(
        team.get("draft_capital_rank"),
        league_size or 99,
    )
    future_rank = _safe_positive_int(
        team.get("future_draft_capital_rank"),
        draft_rank or league_size or 99,
    )
    power_rank = _safe_positive_int(
        team.get("power_rank"),
        league_size or 99,
    )
    first_rounders = _safe_positive_int(team.get("first_rounders"), 0)
    top_cut, bottom_cut = _draft_rank_cutoffs(max(league_size, 1))

    if strategy_key in {"contender", "fringe_contender"}:
        if draft_rank <= top_cut and future_rank <= top_cut:
            return {
                "label": "Aggressive Contender",
                "note": f"Contending build with top-tier draft leverage. {_safe_positive_int(team.get('first_rounders'), 0)} tracked first-rounders gives this roster room to spend for starters without emptying the cupboard.",
                "tone": "power",
            }
        if draft_rank >= bottom_cut and future_rank >= bottom_cut:
            return {
                "label": "Capital-Constrained Contender",
                "note": "Current strength is ahead of future flexibility. Any win-now move should protect remaining premium outs unless the starter upgrade is obvious.",
                "tone": "weakness",
            }
        return {
            "label": "Balanced Contender",
            "note": "Competitive roster with usable draft flexibility. This team can buy selectively, but each future pick has to produce a clear current-lineup payoff.",
            "tone": "strategy",
        }

    if strategy_key in {"rebuild", "tank"}:
        if draft_rank <= top_cut and future_rank <= top_cut:
            return {
                "label": "Pick-Rich Rebuilder",
                "note": f"Rebuild path already has strong pick insulation with {first_rounders} tracked first-rounders. The leverage here is patience, or using surplus capital to tier up instead of chasing points.",
                "tone": "opportunity",
            }
        if future_rank <= top_cut or first_rounders >= 2:
            return {
                "label": "Future-Focused Rebuilder",
                "note": "Future capital is the main leverage point. Preserving premium picks and moving short-window veterans for more insulation should shape draft decisions first.",
                "tone": "opportunity",
            }
        return {
            "label": "Capital-Light Rebuilder",
            "note": "The rebuild label is there, but the pick cushion is not. This roster should treat veterans and movable depth as the fastest path to more draft insulation.",
            "tone": "risk",
        }

    if draft_rank >= bottom_cut and future_rank >= bottom_cut:
        return {
            "label": "Capital-Constrained Pivot",
            "note": "This roster has not picked a final direction and also lacks strong draft insulation. Creating optionality matters more than spending future picks right now.",
            "tone": "risk",
        }

    if power_rank <= top_cut and draft_rank <= top_cut:
        return {
            "label": "Balanced Contender",
            "note": "The team is competitive enough to buy, but still has enough capital to stay flexible. Draft moves should be selective rather than all-in.",
            "tone": "strategy",
        }

    return {
        "label": "Middle-Tier Pivot Candidate",
        "note": "This roster sits between a push and a reset. Draft decisions should prioritize preserving optionality until the market offers a clear buy or sell lane.",
        "tone": "strategy",
    }


# Public alias — same pure function render_your_draft_posture uses
# internally, exposed under a non-underscore name for callers outside this
# module (e.g. services/mobile_api_service.py).
draft_posture_profile = _draft_posture_profile


def _classification_reason(row, mode: str, implication: str) -> str:
    strategy = _safe_text(
        row.get("strategy_display"),
        tidy_label(row.get("mode", "unknown")),
    )
    draft_rank = _format_rank(row.get("draft_capital_rank"), tied=bool(row.get("draft_capital_rank_tied")))
    future_rank = _format_rank(row.get("future_draft_capital_rank"), tied=bool(row.get("future_draft_capital_rank_tied")))
    power_rank = _format_rank(row.get("power_rank"), tied=bool(row.get("power_rank_tied")))
    firsts = _safe_positive_int(row.get("first_rounders"), 0)

    if mode in {"pick_buyer", "buy_picks"}:
        if team_eval_module.normalize_team_strategy(
            row.get("strategy_key")
            or row.get("strategy")
            or row.get("mode")
        ) in {"rebuild", "tank"}:
            return f"{strategy} timeline, but draft rank {draft_rank} says this roster still needs more future capital."
        return f"Draft rank {draft_rank} leaves too little flexibility for a {strategy.lower()} build."
    if mode in {"pick_seller", "sell_picks"}:
        return f"Roster Power rank {power_rank} gives this roster a real reason to spend picks for points now."
    if mode == "pivot":
        return "Middle-tier Roster Power and franchise ranks leave this roster needing optionality before it picks a direction."
    if mode == "pick_rich":
        return f"{firsts} first-rounder{'s' if firsts != 1 else ''} and future rank {future_rank} keep the board open."
    if mode == "pick_poor":
        return f"Draft rank {draft_rank} and future rank {future_rank} leave this roster with very little pick leverage."
    if mode == "move_veterans":
        return f"{strategy} posture plus an older roster base makes veteran-for-pick moves easier to justify."
    if mode == "spend_future":
        return f"Contender pressure plus future rank {future_rank} makes this one of the cleaner all-in teams."
    return implication


def _draft_workspace_team_lines(
    df: pd.DataFrame,
    *,
    limit: int = 3,
    include_strategy: bool = False,
    include_draft: bool = False,
    include_future: bool = False,
    include_implication: bool = False,
    classification: str = "",
) -> list[str]:
    if df is None or df.empty:
        return ["No clear team cluster is standing out yet."]

    items: list[str] = []
    for _, row in df.head(limit).iterrows():
        team_name = _safe_text(row.get("team_name"), "Team")
        details: list[str] = []
        if include_strategy:
            details.append(
                _safe_text(
                    row.get("strategy_display"),
                    tidy_label(row.get("mode", "unknown")),
                )
            )
        if include_draft:
            details.append(
                f"Draft {_format_rank(row.get('draft_capital_rank'), tied=bool(row.get('draft_capital_rank_tied')))}"
            )
        if include_future:
            details.append(
                f"Future {_format_rank(row.get('future_draft_capital_rank'), tied=bool(row.get('future_draft_capital_rank_tied')))}"
            )
        implication = (
            _recommendation_reason_text(
                _safe_text(row.get("manager_trade_implication")),
                92,
            )
            if include_implication
            else ""
        )
        rationale = _recommendation_reason_text(
            _classification_reason(row, classification, implication),
            112,
        )
        if rationale:
            details.append(rationale)
        items.append(
            team_name + (f" | {' | '.join(details)}" if details else "")
        )
    return items


# ---------------------------------------------------------------------------
# Structured rows (card schema 2)
#
# The legacy `items` strings ("Team | Retool | Draft #10 | Future #10 | long
# sentence") are kept for one release because the iOS build in App Store review
# and older Android builds still render them. New clients render `rows`.
# Rule (docs/audits/2026-11-convolution-audit.md section 6): the API returns
# fields, never a joined string; `reason_short` is at most 60 characters and
# the long sentence lives only in `reason_long`.
# ---------------------------------------------------------------------------

CARD_SCHEMA_VERSION = 2
# Teams kept per card for `rows`. The legacy `items` strings stay at the top 3;
# clients show 3 rows and offer "See all" for the rest.
CARD_ROW_POOL = 6
REASON_SHORT_MAX = 60


def _short_reason(text: str) -> str:
    text = " ".join(_safe_text(text).split())
    if len(text) <= REASON_SHORT_MAX:
        return text
    return text[: REASON_SHORT_MAX - 1].rstrip() + "\u2026"


def _optional_rank(value) -> int | None:
    rank = _safe_positive_int(value, 0)
    return rank if rank > 0 else None


def _row_reason(row, mode: str, strategy: str, long_text: str) -> tuple[str, str]:
    """(reason_code, reason_short) for a card row. The short line never repeats
    the rank numbers already shown as pills."""
    strategy_key = team_eval_module.normalize_team_strategy(
        row.get("strategy_key") or row.get("strategy") or row.get("mode")
    )
    firsts = _safe_positive_int(row.get("first_rounders"), 0)
    if mode in {"pick_buyer", "buy_picks"}:
        if mode == "buy_picks":
            return "buys_picks", "Likely to add future picks"
        if strategy_key in {"rebuild", "tank"}:
            return "rebuild_needs_capital", "Rebuild timeline, pick base still thin"
        return "too_few_picks", f"Too few picks for a {strategy.lower()}"
    if mode in {"pick_seller", "sell_picks"}:
        if mode == "sell_picks":
            return "sells_picks", "Likely to move picks for help now"
        return "strong_roster_spends", "Strong roster, ready to spend picks now"
    if mode == "pivot":
        return "no_direction", "Mid-tier roster with no clear direction"
    if mode == "pick_rich":
        return "pick_rich", f"{firsts} first-rounder{'s' if firsts != 1 else ''} and a deep future board"
    if mode == "pick_poor":
        return "pick_poor", "Very little pick leverage"
    if mode == "move_veterans":
        return "moves_veterans", f"{strategy} with an older base: vets for picks"
    if mode == "spend_future":
        return "spends_future", "Contender with the picks to push now"
    return "signal", _short_reason(long_text)


_IMPLICATION_CLASSIFICATIONS = frozenset({"buy_picks", "sell_picks", "move_veterans", "spend_future"})


def _draft_workspace_team_rows(
    df: pd.DataFrame,
    *,
    limit: int = CARD_ROW_POOL,
    classification: str = "",
) -> list[dict]:
    """Structured twin of `_draft_workspace_team_lines`: same teams, same order,
    same long sentence, as fields."""
    if df is None or df.empty:
        return []
    include_implication = classification in _IMPLICATION_CLASSIFICATIONS
    rows: list[dict] = []
    for _, row in df.head(limit).iterrows():
        strategy = _safe_text(row.get("strategy_display"), tidy_label(row.get("mode", "unknown")))
        draft_rank = _optional_rank(row.get("draft_capital_rank"))
        future_rank = _optional_rank(row.get("future_draft_capital_rank"))
        power_rank = _optional_rank(row.get("power_rank"))
        franchise_rank = _optional_rank(row.get("franchise_rank"))
        draft_tied = bool(row.get("draft_capital_rank_tied"))
        future_tied = bool(row.get("future_draft_capital_rank_tied"))
        implication = (
            _recommendation_reason_text(_safe_text(row.get("manager_trade_implication")), 92)
            if include_implication
            else ""
        )
        # Same call the legacy `items` string uses, so the two can never drift.
        reason_long = _recommendation_reason_text(_classification_reason(row, classification, implication), 112)
        reason_code, reason_short = _row_reason(row, classification, strategy, reason_long)
        evidence = []
        if draft_rank is not None:
            evidence.append({"key": "draft_rank", "label": "Draft capital rank", "value": _format_rank(draft_rank, tied=draft_tied)})
        if future_rank is not None:
            evidence.append({"key": "future_rank", "label": "Future capital rank", "value": _format_rank(future_rank, tied=future_tied)})
        if power_rank is not None:
            evidence.append({"key": "power_rank", "label": "Roster Power rank", "value": _format_rank(power_rank, tied=bool(row.get("power_rank_tied")))})
        if franchise_rank is not None:
            evidence.append({"key": "franchise_rank", "label": "Franchise rank", "value": _format_rank(franchise_rank, tied=bool(row.get("franchise_rank_tied")))})
        evidence.append({"key": "firsts", "label": "First-round picks", "value": str(_safe_positive_int(row.get("first_rounders"), 0))})
        avatar = row.get("avatar_url")
        rows.append(
            {
                "team_id": _safe_text(row.get("roster_id")),
                "team_name": _safe_text(row.get("team_name"), "Team"),
                "avatar_url": avatar if isinstance(avatar, str) and avatar else None,
                "strategy": team_eval_module.normalize_team_strategy(
                    row.get("strategy_key") or row.get("strategy") or row.get("mode")
                ),
                "strategy_display": strategy,
                "draft_rank": draft_rank,
                "draft_rank_tied": draft_tied,
                "future_rank": future_rank,
                "future_rank_tied": future_tied,
                "firsts": _safe_positive_int(row.get("first_rounders"), 0),
                "reason_code": reason_code,
                "reason_short": reason_short,
                "reason_long": reason_long,
                "evidence": evidence,
            }
        )
    return rows


def _signal_card(
    label: str,
    title: str,
    tone: str,
    df: pd.DataFrame,
    classification: str,
    **line_options,
) -> dict:
    """One card: legacy `items` strings + schema-2 `rows` from the same frame."""
    return {
        "label": label,
        "title": title,
        "tone": tone,
        "schema": CARD_SCHEMA_VERSION,
        "items": _draft_workspace_team_lines(df, classification=classification, **line_options),
        "rows": _draft_workspace_team_rows(df, classification=classification),
    }


def build_draft_decision_cards(
    draft_workspace: pd.DataFrame,
) -> list[dict]:
    if draft_workspace is None or draft_workspace.empty:
        return []

    working = draft_workspace.copy()
    league_size = len(working)
    _draft_rank_cutoffs(league_size)
    midpoint = (league_size + 1) / 2.0
    middle_low = max(1, int(midpoint) - 1)
    middle_high = min(league_size, int(midpoint) + 1)

    for column, default in {
        "power_rank": league_size,
        "franchise_rank": league_size,
        "draft_capital_rank": league_size,
        "future_draft_capital_rank": league_size,
        "draft_capital": 0.0,
        "future_draft_capital": 0.0,
        "pick_count": 0.0,
        "first_rounders": 0.0,
    }.items():
        working[column] = pd.to_numeric(
            working.get(column),
            errors="coerce",
        ).fillna(default)

    working["strategy_key"] = working.apply(
        lambda row: team_eval_module.normalize_team_strategy(
            row.get("strategy")
            or row.get("mode")
            or row.get("strategy_key")
        ),
        axis=1,
    )
    working["pivot_distance"] = (
        (working["power_rank"] - midpoint).abs()
        + (working["franchise_rank"] - midpoint).abs()
        + ((working["draft_capital_rank"] - midpoint).abs() * 0.55)
    )

    pick_buyers = working[
        working["strategy_key"].isin({"rebuild", "tank", "retool"})
    ].sort_values(
        [
            "draft_capital_rank",
            "future_draft_capital_rank",
            "power_rank",
            "team_name",
        ],
        ascending=[False, False, False, True],
    ).head(CARD_ROW_POOL)
    if pick_buyers.empty:
        pick_buyers = working.sort_values(
            [
                "draft_capital_rank",
                "future_draft_capital_rank",
                "team_name",
            ],
            ascending=[False, False, True],
        ).head(CARD_ROW_POOL)

    pick_sellers = working[
        working["strategy_key"].isin({"contender", "fringe_contender"})
    ].sort_values(
        [
            "power_rank",
            "draft_capital_rank",
            "future_draft_capital_rank",
            "team_name",
        ],
        ascending=[True, True, True, True],
    ).head(CARD_ROW_POOL)
    if pick_sellers.empty:
        pick_sellers = working.sort_values(
            ["power_rank", "draft_capital_rank", "team_name"],
            ascending=[True, True, True],
        ).head(CARD_ROW_POOL)

    pivot_candidates = working[
        working["power_rank"].between(middle_low, middle_high)
        & working["franchise_rank"].between(middle_low, middle_high)
        & ~working["strategy_key"].isin({"contender", "rebuild", "tank"})
    ].sort_values(
        ["pivot_distance", "team_name"],
        ascending=[True, True],
    ).head(CARD_ROW_POOL)
    if pivot_candidates.empty:
        pivot_candidates = working[
            ~working["strategy_key"].isin(
                {"contender", "rebuild", "tank"}
            )
        ].sort_values(
            ["pivot_distance", "team_name"],
            ascending=[True, True],
        ).head(CARD_ROW_POOL)

    pick_rich = working.sort_values(
        [
            "draft_capital",
            "future_draft_capital",
            "first_rounders",
            "team_name",
        ],
        ascending=[False, False, False, True],
    ).head(CARD_ROW_POOL)
    pick_poor = working.sort_values(
        [
            "draft_capital",
            "future_draft_capital",
            "pick_count",
            "team_name",
        ],
        ascending=[True, True, True, True],
    ).head(CARD_ROW_POOL)

    return [
        _signal_card(
            "Best Pick Buyers",
            "Teams that should be acquiring more picks",
            "opportunity",
            pick_buyers,
            "pick_buyer",
            include_strategy=True,
            include_draft=True,
            include_future=True,
        ),
        _signal_card(
            "Best Pick Sellers",
            "Teams best positioned to spend picks for points now",
            "power",
            pick_sellers,
            "pick_seller",
            include_strategy=True,
            include_draft=True,
            include_future=True,
        ),
        _signal_card(
            "Pivot Candidates",
            "Middle teams that still need a draft direction",
            "strategy",
            pivot_candidates,
            "pivot",
            include_strategy=True,
            include_draft=True,
            include_future=True,
        ),
        _signal_card(
            "Pick-Rich Teams",
            "The strongest future capital bases in the league",
            "strength",
            pick_rich,
            "pick_rich",
            include_strategy=True,
            include_draft=True,
            include_future=True,
        ),
        _signal_card(
            "Pick-Poor Teams",
            "The thinnest future cupboards right now",
            "weakness",
            pick_poor,
            "pick_poor",
            include_strategy=True,
            include_draft=True,
            include_future=True,
        ),
    ]


def build_draft_partner_cards(
    draft_workspace: pd.DataFrame,
) -> list[dict]:
    if draft_workspace is None or draft_workspace.empty:
        return []

    working = draft_workspace.copy()
    league_size = len(working)
    top_cut, _ = _draft_rank_cutoffs(league_size)
    midpoint = (league_size + 1) / 2.0

    for column, default in {
        "power_rank": league_size,
        "franchise_rank": league_size,
        "draft_capital_rank": league_size,
        "future_draft_capital_rank": league_size,
        "age_rank": league_size,
    }.items():
        working[column] = pd.to_numeric(
            working.get(column),
            errors="coerce",
        ).fillna(default)

    working["strategy_key"] = working.apply(
        lambda row: team_eval_module.normalize_team_strategy(
            row.get("strategy")
            or row.get("mode")
            or row.get("strategy_key")
        ),
        axis=1,
    )

    likely_buy_picks = working[
        working["strategy_key"].isin({"rebuild", "tank", "retool"})
    ].sort_values(
        [
            "draft_capital_rank",
            "future_draft_capital_rank",
            "age_rank",
            "team_name",
        ],
        ascending=[False, False, False, True],
    ).head(CARD_ROW_POOL)

    likely_sell_picks = working[
        working["strategy_key"].isin({"contender", "fringe_contender"})
    ].sort_values(
        [
            "power_rank",
            "draft_capital_rank",
            "future_draft_capital_rank",
            "team_name",
        ],
        ascending=[True, True, True, True],
    ).head(CARD_ROW_POOL)

    likely_move_veterans = working[
        working["strategy_key"].isin({"rebuild", "tank", "retool"})
        & working["age_rank"].ge(midpoint)
    ].sort_values(
        ["age_rank", "power_rank", "draft_capital_rank", "team_name"],
        ascending=[False, False, False, True],
    ).head(CARD_ROW_POOL)
    if likely_move_veterans.empty:
        likely_move_veterans = working[
            working["strategy_key"].isin({"rebuild", "tank", "retool"})
        ].sort_values(
            ["power_rank", "age_rank", "team_name"],
            ascending=[False, False, True],
        ).head(CARD_ROW_POOL)

    likely_spend_future = working[
        working["strategy_key"].isin({"contender", "fringe_contender"})
        & working["future_draft_capital_rank"].le(max(top_cut, 3))
    ].sort_values(
        ["future_draft_capital_rank", "power_rank", "team_name"],
        ascending=[True, True, True],
    ).head(CARD_ROW_POOL)
    if likely_spend_future.empty:
        likely_spend_future = likely_sell_picks.head(CARD_ROW_POOL)

    return [
        _signal_card(
            "Likely To Buy Picks",
            "Teams most likely to add future capital",
            "opportunity",
            likely_buy_picks,
            "buy_picks",
            include_strategy=True,
            include_draft=True,
            include_implication=True,
        ),
        _signal_card(
            "Likely To Sell Picks",
            "Teams most likely to move picks for current help",
            "power",
            likely_sell_picks,
            "sell_picks",
            include_strategy=True,
            include_draft=True,
            include_implication=True,
        ),
        _signal_card(
            "Move Veterans For Picks",
            "Teams most likely to trade short-window assets for future outs",
            "strategy",
            likely_move_veterans,
            "move_veterans",
            include_strategy=True,
            include_future=True,
            include_implication=True,
        ),
        _signal_card(
            "Spend Future Capital",
            "Teams with both the reason and the ammo to push now",
            "franchise",
            likely_spend_future,
            "spend_future",
            include_strategy=True,
            include_future=True,
            include_implication=True,
        ),
    ]
