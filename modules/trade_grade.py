"""One user-side trade valuation shared by Trade Hub and the Trade Analyzer.

Trade Hub (modules.trade_ideas, reached through modules.trade_hub_engine and
also used by Trade Finder / All Trades) used to suggest packages that the
Trade Analyzer (modules.trade_analyzer_fit + modules.trade_offer_analyzer)
then graded COUNTER or DECLINE for the same user. They priced the same trade
differently: Hub priced assets through the strategy age curve and reasoned
about consolidation, the Analyzer did neither, and the Analyzer treated a
this-week Out/IR tag as a permanent loss.

This module holds the pieces of the user-side valuation that both now share.
`modules.trade_analyzer_fit.evaluate_trade_analyzer_fit` applies them, and
`grade_trade_for_user` below is the one entry point Trade Hub calls to gate
its ideas, so a surfaced idea and an Analyzer run of the same package give
the same verdict.

Inputs contract: asset scores and roster frames are expected to be on the
caller's strategy-adjusted, league-adjusted scale already. Every production
caller builds them from `modules.trade_hub_engine.apply_strategy_age_curve`
(Trade Hub, web Trade Analyzer, mobile/web-next Trade Analyzer), with picks
scaled by `strategy_adjusted_pick_score_multiplier`. Nothing here re-applies
the curve, so it can never be applied twice.

The three adjustments, all in the same value units as the scores:

1. Consolidation premium (`user_consolidation_adjustment`). The side that
   ends up with the single best asset in an uneven-count deal is paid for
   consolidating. It uses the same formula Trade Hub already used for the
   partner side (`consolidation_premium`): best asset x (8% + 24% x the gap
   between the two sides' best assets). The user is credited when they
   consolidate into the best piece and debited when they break it up for
   depth.

2. Starter strength (`starter_strength_adjustment`). Raw value treats bench
   and starting value the same. A team's posture decides how much more a
   point of starting-lineup value is worth than a point of bench value. A
   contender values starter value at 1.5x (weight 0.50 on the starter-lineup
   delta), a fringe contender at 1.35x, retool 1.15x, rebuild 1.05x and tank
   1.0x. The delta is the change in the optimal starting lineup's value,
   computed with injured players counted as available (their absence is
   priced separately by the injury model below).

3. Injury availability (`estimate_injury_absence` / `injury_availability_cost`).
   An injury is a time-limited availability discount, not a value wipe. The
   player's healthy-equivalent value is restored first, but only when the
   valuation pipeline evidently discounted it (the row carries the
   `risk_multiplier` column rankings.py writes). Then the weeks he is
   expected to miss are charged:

       cost = healthy value x 40% current-season share / 17 fantasy weeks
              x weeks missed among the remaining regular-season + playoff weeks
              x posture weight x (1.0 if he starts for that roster, else 0.25)
              x (0.10 in the offseason)
       capped at 25% of the healthy value.

   Posture weights: contender 0.95, fringe contender 0.75, retool 0.45,
   rebuild 0.15, tank 0.05.

   Sleeper never fills `injury_start_date`, and nothing in the players table
   carries a return date. So the weeks come from documented conservative
   defaults per status, and the explanation always says it is an estimate:
   Questionable 0.25, Doubtful 1, Out 2, IR / PUP / NFI 4 (the NFL minimum
   stay), and Suspended 3 (Sleeper does not report the length). An
   `injury_body_part` or `injury_notes` that reads season-ending (ACL,
   Achilles, torn, rupture, season-ending) charges the rest of the season,
   and "surgery" raises the estimate to at least 6 weeks. "NA" stays healthy
   (#1295), and "Sus" goes through the suspension default rather than the
   generic minor bucket (#1302).

   The season week is `league_settings["current_week"]` when a caller
   provides it. Otherwise it is estimated from the calendar: week 1 starts
   the Tuesday after Labor Day. Both Hub and the Analyzer use the same rule,
   so they agree on any given day.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from modules import injury_status as injury_table
from modules import model_status
from modules.frame_records import frame_records
from modules.player_state_authority import is_suspended
from modules.rankings import (
    COMPOSITE_WEIGHT_OPPORTUNITY,
    current_availability_multiplier,
    injury_level,
    risk_multiplier,
)
from modules.team_eval import normalize_team_strategy

logger = logging.getLogger(__name__)

# --- consolidation -----------------------------------------------------------

CONSOLIDATION_BASE_RATE = 0.08
CONSOLIDATION_GAP_RATE = 0.24
# Equal-count deals only carry a premium when the headliners differ clearly.
CONSOLIDATION_EVEN_COUNT_RATIO = 0.85
# Trade Hub's partner-side check already credited each first-round pick as
# this much consolidation premium paid (see trade_ideas._explicit_* and
# _cornerstone_consolidation_premium).
CONSOLIDATION_FIRST_ROUND_CREDIT = 850


def consolidation_premium(target_score: float, headliner_ratio: float) -> int:
    """Premium owed for consolidating into `target_score`.

    `headliner_ratio` is the other side's best asset divided by the target
    (1.0 = an equal headliner comes back, so only the 8% base applies).
    """

    gap = max(0.0, 1.0 - min(1.0, float(headliner_ratio or 0.0)))
    rate = CONSOLIDATION_BASE_RATE + CONSOLIDATION_GAP_RATE * gap
    return int(round(max(0.0, float(target_score or 0)) * rate))


def cornerstone_consolidation_premium(
    *,
    target_score: int,
    headliner_ratio: float,
    first_round_count: int,
) -> tuple[int, int]:
    """Trade Hub's partner-side form: (required premium, premium still unmet)."""

    required = consolidation_premium(target_score, headliner_ratio)
    unmet = max(0, required - max(0, int(first_round_count)) * CONSOLIDATION_FIRST_ROUND_CREDIT)
    return required, unmet


def _asset_value(asset: Mapping[str, Any], values: Mapping[int, float] | None = None) -> float:
    if values is not None and id(asset) in values:
        return float(values[id(asset)])
    try:
        return float(asset.get("score", asset.get("value_score", 0)) or 0)
    except (TypeError, ValueError):
        return 0.0


def user_consolidation_adjustment(
    send_assets: Sequence[Mapping[str, Any]],
    receive_assets: Sequence[Mapping[str, Any]],
    *,
    values: Mapping[int, float] | None = None,
) -> tuple[int, str]:
    """Signed consolidation premium for the user's side, plus a short note.

    Only the side that ends up with the best single asset carries one. With
    uneven counts the user is credited when they send more pieces for the best
    asset, and debited when they break it up into more pieces; with even
    counts a (gap-only) premium applies only when the headliners clearly
    differ. `values` optionally overrides each asset's score (keyed
    by id(asset)), so the healthy-equivalent injury values are what get
    compared.
    """

    send = [asset for asset in send_assets or () if isinstance(asset, Mapping)]
    receive = [asset for asset in receive_assets or () if isinstance(asset, Mapping)]
    if not send or not receive:
        return 0, ""
    best_in = max(_asset_value(asset, values) for asset in receive)
    best_out = max(_asset_value(asset, values) for asset in send)
    if len(send) == len(receive):
        # Even counts can still concentrate value: the side that lands the
        # clearly better headliner is paid for it (gap premium only; there is
        # no piece-count consolidation to price).
        if best_in > best_out and best_out / best_in <= CONSOLIDATION_EVEN_COUNT_RATIO:
            gap = 1.0 - best_out / best_in
            premium = int(round(best_in * CONSOLIDATION_GAP_RATE * gap))
            return premium, f"lands the best asset in the deal (+{premium:,})"
        if best_out > best_in and best_in / best_out <= CONSOLIDATION_EVEN_COUNT_RATIO:
            gap = 1.0 - best_in / best_out
            premium = int(round(best_out * CONSOLIDATION_GAP_RATE * gap))
            return -premium, f"gives up the best asset in the deal (-{premium:,})"
        return 0, ""
    if len(send) > len(receive) and best_in > best_out:
        premium = consolidation_premium(best_in, best_out / best_in if best_in else 0.0)
        return premium, f"consolidates {len(send)} pieces into the best asset in the deal (+{premium:,})"
    if len(receive) > len(send) and best_out > best_in:
        premium = consolidation_premium(best_out, best_in / best_out if best_out else 0.0)
        return -premium, f"breaks up the best asset in the deal into {len(receive)} pieces (-{premium:,})"
    return 0, ""


# --- starter strength --------------------------------------------------------

STARTER_STRENGTH_WEIGHTS: dict[str, float] = {
    "contender": 0.50,
    "fringe_contender": 0.35,
    "retool": 0.15,
    "rebuild": 0.05,
    "tank": 0.0,
}


def starter_strength_weight(strategy: str) -> float:
    return STARTER_STRENGTH_WEIGHTS.get(normalize_team_strategy(strategy), 0.15)


def starter_strength_adjustment(lineup_delta: float, strategy: str) -> int:
    return int(round(float(lineup_delta or 0) * starter_strength_weight(strategy)))


# --- season window -----------------------------------------------------------

FANTASY_SEASON_WEEKS = 17
OFFSEASON_INJURY_FACTOR = 0.10


@dataclass(frozen=True)
class SeasonWindow:
    current_week: int
    remaining_weeks: int
    in_season: bool
    source: str  # "league" | "calendar"


def _labor_day(year: int) -> date:
    first = date(year, 9, 1)
    return first + timedelta(days=(7 - first.weekday()) % 7)


def estimate_nfl_week(today: date | None = None) -> int:
    """Calendar estimate of the NFL week (0 = offseason/preseason)."""

    today = today or datetime.now(timezone.utc).date()
    start = _labor_day(today.year) + timedelta(days=1)
    if today < start:
        # January playoffs belong to the previous season, past every
        # fantasy week, so they read as offseason too.
        return 0
    week = (today - start).days // 7 + 1
    return week if week <= FANTASY_SEASON_WEEKS else 0


def season_window(
    league_settings: Mapping[str, Any] | None = None,
    *,
    today: date | None = None,
) -> SeasonWindow:
    settings = league_settings or {}
    raw_week = settings.get("current_week") if isinstance(settings, Mapping) else None
    source = "league"
    try:
        week = int(raw_week) if raw_week is not None and str(raw_week).strip() != "" else None
    except (TypeError, ValueError):
        week = None
    if week is None:
        week = estimate_nfl_week(today)
        source = "calendar"
    if week <= 0 or week > FANTASY_SEASON_WEEKS:
        return SeasonWindow(0, FANTASY_SEASON_WEEKS, False, source)
    return SeasonWindow(week, FANTASY_SEASON_WEEKS - week + 1, True, source)


# --- injury availability -----------------------------------------------------

# Default weeks out per designation come from the one injury table
# (modules.injury_status): none of these are return dates (Sleeper's
# injury_start_date is empty for every rostered player and no return estimate
# exists in the players table). For a single-game designation the weeks are
# 1 - P(plays), the same fact the projections use as a play probability.
INJURY_STATUS_DEFAULT_WEEKS: dict[str, float] = injury_table.default_weeks_by_key()
SURGERY_MIN_WEEKS = 6.0
SEASON_ENDING_TERMS = (
    "acl",
    "achilles",
    "season-ending",
    "season ending",
    "out for season",
    "out for the season",
    "torn",
    "rupture",
)

INJURY_POSTURE_WEIGHTS: dict[str, float] = {
    "contender": 0.95,
    "fringe_contender": 0.75,
    "retool": 0.45,
    "rebuild": 0.15,
    "tank": 0.05,
}
CURRENT_SEASON_VALUE_SHARE = 0.40
NON_STARTER_AVAILABILITY_WEIGHT = 0.25
INJURY_COST_CAP_SHARE = 0.25


@dataclass(frozen=True)
class InjuryAbsence:
    status_label: str
    weeks: float
    season_ending: bool
    basis: str


def _text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def estimate_injury_absence(
    status: Any,
    injury_status: Any,
    *,
    body_part: Any = "",
    notes: Any = "",
    window: SeasonWindow | None = None,
) -> InjuryAbsence | None:
    """Estimated weeks out from the Sleeper fields we actually have, or None."""

    status_text = _text(status)
    injury_text = _text(injury_status)
    cls = injury_table.classify(status_text, injury_text)
    if cls.category == "healthy":
        return None
    if cls.weeks_out is None:
        # A bare roster status such as "Inactive" or "Practice Squad" is an
        # indefinite, non-medical absence with no recovery window to price;
        # the existing valuation handles it.
        return None
    suspended = cls.suspended
    # Show Sleeper's own wording for the field that decided the row.
    label = "Suspended" if suspended else (
        (injury_text if cls.source == "injury_status" else status_text) or cls.row.label
    )
    weeks = cls.weeks_out
    basis = f"default for {label}"
    detail = " ".join(_text(part).casefold() for part in (body_part, notes, injury_text))
    window = window or season_window()
    season_ending = not suspended and any(term in detail for term in SEASON_ENDING_TERMS)
    if season_ending:
        weeks = float(window.remaining_weeks)
        basis = f"{_text(body_part) or 'injury'} reads season-ending"
    elif "surgery" in detail and weeks < SURGERY_MIN_WEEKS:
        weeks = SURGERY_MIN_WEEKS
        basis = "surgery noted"
    return InjuryAbsence(status_label=label, weeks=float(weeks), season_ending=season_ending, basis=basis)


def _number(value: Any, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed == parsed else default


def healthy_restore_factor(row: Mapping[str, Any] | None, score_field: str) -> float:
    """How much of `score_field` the valuation pipeline took off for injury.

    Returns the multiplier the injured value carries (1.0 = no discount).
    Only rows that came through rankings' risk model (they carry
    `risk_multiplier`) are restored: a value nobody discounted is never
    inflated. Recomputed with the same rankings functions the valuation
    used, comparing the player's real status with an "Active", no-injury
    twin on the same team and search rank:

    - dynasty_score / score: injury risk scales every composite factor but
      opportunity (COMPOSITE_WEIGHT_OPPORTUNITY), so
      factor = (1 - w_opp) x risk ratio + w_opp.
    - value_score: the current-season lens scales the whole score by
      current_availability_multiplier.
    - rebuild_score: league_value_settings blends 82% dynasty + 18% current.

    The last two only hold on a lens-adjusted frame (it carries
    `league_settings_multiplier`); on a raw players-table frame every score
    column is the composite, so the dynasty factor applies to all of them.
    """

    if not row or "risk_multiplier" not in row:
        return 1.0
    status = _text(row.get("status"))
    injury_status = _text(row.get("injury_status"))
    team = _text(row.get("team"))
    if not team:
        return 1.0
    rank = row.get("search_rank")
    rank = 1 if _number(rank, 0) <= 0 else rank
    healthy_risk = risk_multiplier("active", team, rank, "")
    healthy_current = current_availability_multiplier("active", team, rank, "")
    dyn_ratio = risk_multiplier(status, team, rank, injury_status) / healthy_risk if healthy_risk else 1.0
    cur_ratio = (
        current_availability_multiplier(status, team, rank, injury_status) / healthy_current
        if healthy_current
        else 1.0
    )
    dyn_ratio = min(1.0, max(0.05, dyn_ratio))
    cur_ratio = min(1.0, max(0.05, cur_ratio))
    opportunity_share = float(COMPOSITE_WEIGHT_OPPORTUNITY)
    dynasty_factor = (1.0 - opportunity_share) * dyn_ratio + opportunity_share
    field = str(score_field or "").strip()
    if "league_settings_multiplier" not in row:
        # Not through league_value_settings.apply_valuation_lens: every score
        # column is still rankings' composite, discounted the dynasty way.
        return dynasty_factor
    if field == "value_score":
        return cur_ratio
    if field == "rebuild_score":
        return 0.82 * dynasty_factor + 0.18 * cur_ratio
    return dynasty_factor


def injury_posture_weight(strategy: str) -> float:
    return INJURY_POSTURE_WEIGHTS.get(normalize_team_strategy(strategy), 0.45)


def injury_availability_cost(
    healthy_value: float,
    absence: InjuryAbsence | None,
    *,
    strategy: str,
    window: SeasonWindow,
    starts: bool,
) -> int:
    if absence is None or healthy_value <= 0:
        return 0
    weeks_missed = min(float(absence.weeks), float(window.remaining_weeks))
    weekly_value = float(healthy_value) * CURRENT_SEASON_VALUE_SHARE / FANTASY_SEASON_WEEKS
    cost = weekly_value * weeks_missed * injury_posture_weight(strategy)
    cost *= 1.0 if starts else NON_STARTER_AVAILABILITY_WEIGHT
    if not window.in_season:
        cost *= OFFSEASON_INJURY_FACTOR
    return int(round(min(cost, float(healthy_value) * INJURY_COST_CAP_SHARE)))


def _weeks_text(weeks: float) -> str:
    if weeks < 1:
        return "part of a week"
    rounded = int(round(weeks))
    return f"~{rounded} week{'s' if rounded != 1 else ''}"


@dataclass(frozen=True)
class InjuryLine:
    player_id: str
    name: str
    side: str  # "receive" | "send"
    listed_value: int
    healthy_value: int
    cost: int
    absence: InjuryAbsence

    @property
    def adjusted_value(self) -> int:
        return self.healthy_value - self.cost

    def note(self, strategy: str, window: SeasonWindow) -> str:
        timing = (
            f"{_weeks_text(self.absence.weeks)} estimated"
            if not self.absence.season_ending
            else "likely out for the rest of the season"
        )
        when = (
            f"{window.remaining_weeks} fantasy weeks left"
            if window.in_season
            else "offseason, so it barely touches this season"
        )
        return (
            f"{self.name} ({self.absence.status_label}): {timing} "
            f"({self.absence.basis}; no return date in the data), {when}. "
            f"Priced as a {self.cost:,}-point availability cost for a "
            f"{normalize_team_strategy(strategy).replace('_', ' ')}, not a permanent loss."
        )


def price_injured_assets(
    assets: Iterable[Mapping[str, Any]],
    *,
    side: str,
    rows_by_id: Mapping[str, Mapping[str, Any]],
    starter_ids: set[str],
    score_field: str,
    strategy: str,
    window: SeasonWindow,
) -> tuple[dict[int, float], list[InjuryLine]]:
    """Healthy-minus-availability-cost value for each injured player asset."""

    values: dict[int, float] = {}
    lines: list[InjuryLine] = []
    for asset in assets or ():
        if not isinstance(asset, Mapping) or asset.get("asset_type") != "player":
            continue
        player_id = _text(asset.get("player_id"))
        row = rows_by_id.get(player_id) or {}
        status = row.get("status", asset.get("status"))
        injury_status = row.get("injury_status", asset.get("injury_status"))
        absence = estimate_injury_absence(
            status,
            injury_status,
            body_part=row.get("injury_body_part", asset.get("injury_body_part")),
            notes=row.get("injury_notes", asset.get("injury_notes")),
            window=window,
        )
        if absence is None:
            continue
        listed = _asset_value(asset)
        factor = healthy_restore_factor(row, score_field)
        healthy = listed / factor if factor > 0 else listed
        cost = injury_availability_cost(
            healthy, absence, strategy=strategy, window=window, starts=player_id in starter_ids
        )
        values[id(asset)] = healthy - cost
        lines.append(
            InjuryLine(
                player_id=player_id,
                name=_text(asset.get("name") or asset.get("label")) or "Player",
                side=side,
                listed_value=int(round(listed)),
                healthy_value=int(round(healthy)),
                cost=int(cost),
                absence=absence,
            )
        )
    return values, lines


def healthy_equivalent_roster(
    df: pd.DataFrame,
    *,
    score_column: str,
    window: SeasonWindow,
) -> pd.DataFrame:
    """Roster frame for starter-strength math with injuries priced separately.

    A ruled-out player would otherwise drop out of the optimal lineup as if
    he never plays again. Here his status is cleared and his score restored
    to its healthy equivalent, so the lineup delta measures the roster's
    strength and the injury model charges only the weeks he misses.
    """

    if df is None or df.empty or "player_id" not in df.columns:
        return df
    status = df["status"] if "status" in df.columns else pd.Series("", index=df.index)
    injury = df["injury_status"] if "injury_status" in df.columns else pd.Series("", index=df.index)
    body = df["injury_body_part"] if "injury_body_part" in df.columns else pd.Series("", index=df.index)
    notes = df["injury_notes"] if "injury_notes" in df.columns else pd.Series("", index=df.index)
    mask = []
    for s, i, b, n in zip(status.tolist(), injury.tolist(), body.tolist(), notes.tolist()):
        mask.append(estimate_injury_absence(s, i, body_part=b, notes=n, window=window) is not None)
    if not any(mask):
        return df
    out = df.copy()
    flagged = pd.Series(mask, index=out.index)
    if score_column in out.columns:
        restored = []
        # One bulk conversion of the flagged rows instead of a Series per row
        # (``iterrows`` + ``to_dict`` was most of this function's cost).
        for row in frame_records(out.loc[flagged]):
            factor = healthy_restore_factor(row, score_column)
            value = _number(row.get(score_column), 0.0)
            restored.append(value / factor if factor > 0 else value)
        out[score_column] = pd.to_numeric(out[score_column], errors="coerce").astype("float64")
        out.loc[flagged, score_column] = restored
    if "status" in out.columns:
        out.loc[flagged, "status"] = "Active"
    if "injury_status" in out.columns:
        out.loc[flagged, "injury_status"] = ""
    return out


# --- the shared grade ----------------------------------------------------------

PASSING_UI_VERDICTS = frozenset({"FAIR", "ACCEPT"})


def clears_suggestion_bar(verdict) -> bool:
    """Whether the Analyzer's verdict is good enough to SUGGEST this trade.

    ``PASSING_UI_VERDICTS`` is "not a loss in the Analyzer's UI wording", but the
    FAIR UI verdict spans trade scores -400..+500, including the "Slight value
    edge to them" band (-400..-150): a package the Analyzer itself words as
    giving up value. A suggestion is a recommendation to act, so it must also
    sit at or above the "essentially even" rung of the one score ladder
    (modules.trade_value_bands.EDGE) whenever the verdict was decided on that ladder
    (a lineup model exists). Scored on the same ``trade_score`` the
    verdict itself is decided on, so Hub/Finder and the Analyzer cannot diverge.
    """

    from modules import trade_value_bands

    if verdict is None:
        return True
    if not getattr(verdict, "lineup_model", None):
        # No lineup model (offseason / no weekly data): the verdict was decided by
        # the legacy value + fit rules, not the score ladder, so the ladder's
        # "essentially even" rung is not the yardstick for it.
        return verdict.ui_verdict in PASSING_UI_VERDICTS
    # The score is the single yardstick: the verdict's band, UI verdict and tone
    # are the rung this same number lands in (the window and direction cost are
    # terms of it), so no separate label check is needed or possible.
    try:
        score = float(verdict.trade_score)
    except (TypeError, ValueError):
        return False
    return score >= -trade_value_bands.EDGE


def league_waiver_pool(rosters, valued: pd.DataFrame) -> pd.DataFrame | None:
    """The league's real free agents (unrostered, waiver-actionable), valued like
    ``valued``. None when rosters cannot be read, so the lineup model falls back
    to the market replacement level rather than assuming an empty pool. The one
    implementation behind the Analyzer and the commissioner veto calculator."""

    rosters = rosters or []
    if not rosters:
        return None
    roster_map = {str(r.get("roster_id")): list(r.get("players") or []) for r in rosters}
    rostered = {str(pid) for players in roster_map.values() for pid in players}
    pool = valued[~valued["player_id"].astype(str).isin(rostered)]
    if pool.empty:
        return pool
    from modules.player_state_authority import waiver_actionable_player_pool

    return waiver_actionable_player_pool(pool, roster_map, surface="trade_analyzer_lineup_hole")


def attach_projection_baselines(
    valued: pd.DataFrame,
    pool: pd.DataFrame | None,
    player_ids,
    score_field: str,
    lineup_settings: Mapping[str, Any] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame | None]:
    """Attach the walk-forward weekly baseline (``proj_ppg``/``proj_sd``, in the
    league's own scoring when ``lineup_settings`` carries it, else PPR; flagged
    by ``proj_scoring_applied``; availability not applied) to the players the lineup model will look at:
    ``player_ids`` and the top free agents per position. Players with no usable
    weekly history simply get no column value; the model then labels its
    fallback basis. A lookup failure (not mere absence) is logged and marks the
    returned frames (``modules.model_status``) so the verdict reports it.

    The ONE place this happens, for the Trade Analyzer endpoint AND the Hub /
    Finder gate. Grading on a frame without it priced the same package off a
    value-derived estimate instead of real weekly production, so the gate could
    pass a package (lineup -15 pts, score -21) the Analyzer then graded as a
    loss (lineup -13 pts, score -357).
    """

    try:
        from modules import player_projections

        ids = {str(pid) for pid in player_ids}
        if pool is not None and not pool.empty and score_field in pool.columns:
            top = pool.sort_values(score_field, ascending=False).groupby(
                pool["position"].astype(str).str.upper(), sort=False
            ).head(25)
            ids |= {str(pid) for pid in top["player_id"].astype(str)}
        wanted = valued[valued["player_id"].astype(str).isin(ids)]
        baselines = player_projections.baseline_weekly_points(
            [{"player_id": str(r["player_id"]), "position": r.get("position")} for _, r in wanted.iterrows()],
            scoring_settings=(lineup_settings or {}).get("_scoring_settings") or None,
        )
        if not baselines:
            return valued, pool

        def apply(frame: pd.DataFrame | None) -> pd.DataFrame | None:
            if frame is None or frame.empty:
                return frame
            frame = frame.copy()
            pids = frame["player_id"].astype(str)
            frame["proj_ppg"] = pids.map(lambda p: (baselines.get(p) or {}).get("ppg"))
            frame["proj_sd"] = pids.map(lambda p: (baselines.get(p) or {}).get("sd"))
            frame["proj_scoring_applied"] = pids.map(lambda p: bool((baselines.get(p) or {}).get("scoring_applied")))
            return frame

        return apply(valued), apply(pool)
    except model_status.LOOKUP_ERRORS:
        # "No weekly history" is handled above (empty baselines -> frames
        # unchanged, and the model labels its value-estimate basis). A
        # *failure* here is different: grading without baselines recreates the
        # Hub-gate vs Analyzer divergence this helper exists to prevent, so it
        # is logged and the returned frames are marked for the lineup model
        # to report. Non-data errors are bugs and propagate.
        logger.warning("projection baselines unavailable; lineup model will use value estimates", exc_info=True)
        return (
            model_status.mark_frame(valued.copy(), "projection_baselines_failed"),
            model_status.mark_frame(pool.copy() if pool is not None else None, "projection_baselines_failed"),
        )


def grade_trade_for_user(
    *,
    my_team_df: pd.DataFrame,
    all_players_df: pd.DataFrame,
    send_assets: list[dict],
    receive_assets: list[dict],
    strategy: str,
    lineup_settings: dict | None,
    score_field: str,
    metrics: dict | None = None,
    current_context: dict | None = None,
    waiver_df: pd.DataFrame | None = None,
    forced_drop_assets: list[dict] | None = None,
    team_needs: dict | None = None,
    pick_context: Mapping[str, Any] | None = None,
):
    """The Trade Analyzer's own verdict for this package, from the user's side.

    Exactly the Analyzer pipeline (evaluate_trade_analyzer_fit followed by
    decide_offer_verdict), so Trade Hub can drop ideas the Analyzer would
    not grade at least FAIR. Returns (fit, verdict); both are None when the
    fit cannot be computed.

    ``pick_context`` (modules.trade_cautions.build_pick_context) is the picks
    the team already holds. The Analyzer always passes it, so a caller that
    leaves it out can grade SMASH ACCEPT where the Analyzer says ACCEPT (the
    pick-glut caution softens exactly that rung): Hub and Finder pass it.
    """

    from modules import trade_analyzer_fit, trade_offer_analyzer

    fit = trade_analyzer_fit.evaluate_trade_analyzer_fit(
        my_team_df=my_team_df,
        all_players_df=all_players_df,
        send_assets=send_assets,
        receive_assets=receive_assets,
        metrics=metrics,
        strategy=strategy,
        lineup_settings=lineup_settings,
        score_field=score_field,
        current_context=current_context,
        waiver_df=waiver_df,
        forced_drop_assets=forced_drop_assets,
        team_needs=team_needs,
    )
    if not fit or not fit.get("available"):
        return fit, None
    verdict = trade_offer_analyzer.decide_offer_verdict(
        fit, send_assets=send_assets, receive_assets=receive_assets, pick_context=pick_context
    )
    return fit, verdict
