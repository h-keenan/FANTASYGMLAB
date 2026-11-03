"""Team-need vocabulary shared by every surface, and the K/DEF shallow-room check.

The CORE_POSITIONS (QB/RB/WR/TE) need model is ``modules.roster_value_model``
and nothing else: ``assessment_from_model`` below only reshapes its output into
the ``TeamNeedsAssessment`` the Dashboard / My Team / glance / alerts already
read. The coverage-count policy that used to live here compared player values
to thresholds written for a 0-100 scale against a 0-11,000 valued frame, so it
reported "covered" for nearly every dynasty roster; it is gone, not patched
(``docs/suggested-drops-and-needs.md``).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from modules import injury_status as injury_table
from modules import model_status, runtime_trace

CORE_POSITIONS = ("QB", "RB", "WR", "TE")

# Shallow, single-starter rooms. A league only ever starts one K and one DEF,
# and a second rostered kicker has ~zero roster-construction value no matter
# how strong its raw score looks, so these positions get their own binary
# coverage check (classify_shallow_position_rooms / true_shallow_position_needs
# below) instead of the lineup/league-rank model that prices QB/RB/WR/TE.
# Omitting them from the needs model entirely was the root cause of
# kicker/defense "acquire" trade suggestions being pushed at teams that already
# have one of each and don't want another.
SHALLOW_POSITIONS = ("K", "DEF")

@dataclass(frozen=True)
class PositionNeedAssessment:
    position: str
    severity: float
    classification: str
    starter_quality: float | None
    backup_quality: float | None
    depth_quality: float | None
    future_stability: float | None
    injury_pressure: float
    replacement_gap: float | None
    required_starters: int
    reasons: tuple[str, ...]
    reason_codes: tuple[str, ...]
    data_quality: str
    true_need: bool
    relative_weakness: bool
    upgrade_opportunity: bool
    temporary_injury_pressure: bool
    future_risk: bool


@dataclass(frozen=True)
class TeamNeedsAssessment:
    positions: tuple[PositionNeedAssessment, ...]
    true_needs: tuple[str, ...]
    relative_weaknesses: tuple[str, ...]
    upgrade_opportunities: tuple[str, ...]
    temporary_injury_pressures: tuple[str, ...]
    future_risks: tuple[str, ...]
    # "Degraded" only when no model result was available for this roster
    # (``need_model_unavailable``); never a silent "everything is covered".
    model_status: Mapping[str, Any] = field(default_factory=model_status.ok)

    def for_position(self, position: str) -> PositionNeedAssessment | None:
        normalized = str(position or "").strip().upper()
        return next(
            (
                assessment
                for assessment in self.positions
                if assessment.position == normalized
            ),
            None,
        )


# Real, already-computed signal for the Next Move/Dashboard priority ladder
# (roster need > injury pressure > future risk > upgrade opportunity — see
# select_need_headline below). This is a strict step-function, not a numeric
# confidence score, so rather than fabricate a percentage the ladder doesn't
# produce, each rung gets an honest tier word describing *why* it surfaced.
# Single source of truth for app.py (web Dashboard) and modules.dashboard_engine
# (mobile "Next Move" briefing) so both agree on the wording for the identical
# category — previously two hand-kept-in-sync copies of the same dict.
NEED_TIER_LABELS: dict[str, str] = {
    "true_need": "Priority",
    "injury_pressure": "Urgent",
    "future_risk": "Watch",
    "upgrade": "Opportunity",
    "balanced": "",
}


def select_need_headline(assessment: "TeamNeedsAssessment") -> dict[str, str]:
    """Select an accurate need-category headline without collapsing semantics.

    Single source of truth for app.py's ``team_need_display`` and
    modules.dashboard_engine's ``select_need_headline`` — previously two
    hand-kept-in-sync copies of the exact same priority-ladder logic.
    """

    position_items = {item.position: item for item in assessment.positions}
    current_needs = [
        position
        for position in assessment.true_needs
        if (
            position_items.get(position) is not None
            and position_items[position].classification == "short_term_need"
            and not position_items[position].temporary_injury_pressure
        )
    ]
    if current_needs:
        return {
            "category": "true_need",
            "label": "Biggest Team Need",
            "value": current_needs[0],
            "note": "Starter and depth coverage identify this as the clearest current roster deficiency.",
            "tone": "need",
            "tier_label": NEED_TIER_LABELS["true_need"],
        }
    if assessment.temporary_injury_pressures:
        return {
            "category": "injury_pressure",
            "label": "Injury Pressure",
            "value": assessment.temporary_injury_pressures[0],
            "note": "Current availability is creating temporary pressure in this room.",
            "tone": "risk",
            "tier_label": NEED_TIER_LABELS["injury_pressure"],
        }
    if assessment.future_risks:
        return {
            "category": "future_risk",
            "label": "Future Roster Risk",
            "value": assessment.future_risks[0],
            "note": "Current coverage is playable, but future stability is limited.",
            "tone": "draft",
            "tier_label": NEED_TIER_LABELS["future_risk"],
        }
    if assessment.upgrade_opportunities:
        return {
            "category": "upgrade",
            "label": "Upgrade Opportunity",
            "value": assessment.upgrade_opportunities[0],
            "note": "This covered room trails the league baseline but is not a true roster need.",
            "tone": "need",
            "tier_label": NEED_TIER_LABELS["upgrade"],
        }
    return {
        "category": "balanced",
        "label": "Balanced Roster",
        "value": "No urgent need",
        "note": "No current roster deficiency is standing out under the canonical coverage policy.",
        "tone": "draft",
        "tier_label": NEED_TIER_LABELS["balanced"],
    }


def _text(row, *fields: str) -> str:
    return " ".join(
        str(row.get(field) or "").strip().lower()
        for field in fields
    )


def _is_unavailable(row) -> bool:
    return injury_table.is_ruled_out(row.get("status"), row.get("injury_status"))


_NEED_TIERS = {"primary": 1.0, "secondary": 0.8}


def assessment_from_model(
    model_result: Mapping[str, Any] | None,
    *,
    status: Mapping[str, Any] | None = None,
) -> TeamNeedsAssessment:
    """Reshape one ``roster_value_model.assess_needs`` result for the
    Dashboard / My Team / alerts ladder (``select_need_headline``).

    primary / secondary tier -> ``short_term_need`` (a true need); a watch room
    with aging starters and no young cover -> ``future_risk``; a room whose
    weakest starter slot trails the league -> ``upgrade_opportunity`` when it
    is not already a need; starters who are ruled out ->
    ``temporary_injury_pressure``. ``None`` (no result for this roster) is
    reported as ``need_model_unavailable``, never as a covered roster."""

    merged_status = model_status.merge(status, (model_result or {}).get("model_status"))
    available = model_result is not None
    if not available:
        model_status.add(merged_status, "need_model_unavailable")
    by_position = {str(item["position"]): item for item in ((model_result or {}).get("positions") or [])}
    ordered = [str(item["position"]) for item in ((model_result or {}).get("positions") or [])]

    assessments: list[PositionNeedAssessment] = []
    for position in CORE_POSITIONS:
        item = by_position.get(position)
        if item is None:
            assessments.append(
                PositionNeedAssessment(
                    position=position, severity=0.0, classification="covered", starter_quality=None,
                    backup_quality=None, depth_quality=None, future_stability=None, injury_pressure=0.0,
                    replacement_gap=None, required_starters=0,
                    reasons=(
                        ("The need model is unavailable for this roster.",)
                        if not available
                        else (f"{position} is not a starting slot in this league.",)
                    ),
                    reason_codes=(("need_model_unavailable",) if not available else ("not_a_lineup_slot",)),
                    data_quality="missing", true_need=False, relative_weakness=False,
                    upgrade_opportunity=False, temporary_injury_pressure=False, future_risk=False,
                )
            )
            continue
        tier = str(item["tier"])
        true_need = tier in _NEED_TIERS
        future_risk = bool(item.get("future_gap")) and not true_need
        relative_weakness = bool(item.get("relative_weakness"))
        injury = bool(item.get("injured_starters"))
        upgrade = bool(relative_weakness and not true_need)
        if true_need:
            classification, severity = "short_term_need", _NEED_TIERS[tier]
        elif future_risk:
            classification, severity = "future_risk", 0.65
        else:
            classification, severity = "covered", (0.3 if tier == "watch" else 0.0)
        codes: list[str] = []
        if true_need:
            codes.append("insufficient_active_coverage")
        if future_risk:
            codes.append("insufficient_future_stability")
        if injury:
            codes.append("temporary_injury_pressure")
        if upgrade:
            codes.append("covered_relative_weakness")
        elif relative_weakness:
            codes.append("relative_weakness")
        if not true_need and not relative_weakness:
            codes.append("room_covered")
        reasons = list(item.get("reasons") or ()) or [str(item.get("need_type") or "covered")]
        assessments.append(
            PositionNeedAssessment(
                position=position, severity=severity, classification=classification,
                starter_quality=None, backup_quality=None, depth_quality=None, future_stability=None,
                injury_pressure=1.0 if injury else 0.0, replacement_gap=None,
                required_starters=int(item.get("starters") or 0),
                reasons=tuple(dict.fromkeys(str(r) for r in reasons)),
                reason_codes=tuple(dict.fromkeys(codes)),
                data_quality="complete", true_need=true_need, relative_weakness=relative_weakness,
                upgrade_opportunity=upgrade, temporary_injury_pressure=injury, future_risk=future_risk,
            )
        )

    rank = {position: index for index, position in enumerate(ordered)}
    by_model_order = sorted(assessments, key=lambda a: rank.get(a.position, len(rank)))
    return TeamNeedsAssessment(
        positions=tuple(assessments),
        true_needs=tuple(a.position for a in by_model_order if a.true_need),
        relative_weaknesses=tuple(a.position for a in by_model_order if a.relative_weakness),
        upgrade_opportunities=tuple(a.position for a in by_model_order if a.upgrade_opportunity),
        temporary_injury_pressures=tuple(a.position for a in by_model_order if a.temporary_injury_pressure),
        future_risks=tuple(a.position for a in by_model_order if a.future_risk),
        model_status=merged_status,
    )


def room_records(model_result: Mapping[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Per-position room record for the trade copy (``need_type`` label, the
    league rank behind it) from the same model result."""

    rooms: dict[str, dict[str, Any]] = {}
    for item in (model_result or {}).get("positions") or []:
        rooms[str(item["position"])] = {
            "position": str(item["position"]),
            "required_starters": int(item.get("starters") or 0),
            "tier": str(item["tier"]),
            "true_need": str(item["tier"]) in _NEED_TIERS,
            "need_type": str(item.get("need_type") or ""),
            "surplus": bool(item.get("surplus")),
            "weakest_slot": dict(item.get("weakest_slot") or {}),
        }
    return rooms


def _is_shallow_position_disqualified(row) -> bool:
    """Disqualifying status for a shallow-position (K/DEF) starter.

    Reuses the shared ``_is_unavailable`` IR/out/suspended check and adds
    "retired", which never matters for depth positions (a retired RB simply
    isn't rostered) but does show up on long-tenured kickers/defenses whose
    row lingers on a roster.
    """
    if _is_unavailable(row):
        return True
    status = _text(row, "status", "injury_status")
    return "retired" in status


@runtime_trace.traced("classify_shallow_position_rooms", phase="team_needs")
def classify_shallow_position_rooms(
    roster_df: pd.DataFrame,
    league_settings: dict | None = None,
) -> dict[str, dict[str, Any]]:
    """Binary-ish coverage model for shallow, single-starter rooms (K/DEF).

    CORE_POSITIONS' coverage model is tuned for a real depth gradient --
    required starter counts greater than one, backups with standalone trade
    value, developmental/future-asset tracking, etc. None of that fits K/DEF:
    a league starts exactly one of each, a second rostered one has no
    standalone value, and "developmental kicker" isn't a real roster
    construction concept. So this is deliberately a much simpler, analogous
    room record: a position is "covered" if the team has at least one
    rostered, non-disqualified (not IR/out/suspended/retired/etc.) player
    there; otherwise it's a true, surfaceable need.
    """
    roster = roster_df.copy() if roster_df is not None else pd.DataFrame()
    settings = league_settings or {}
    # Unlike the CORE_POSITIONS required-starter counts above, a shallow
    # position's settings key can be a meaningful, explicit 0 (e.g.
    # modules.league_value_settings computes "k_count" straight from the
    # league's roster_positions, and plenty of real formats start no
    # kicker at all) -- `settings.get("k_count") or 1` would wrongly
    # collapse that explicit 0 back to 1 and flag every team in a
    # no-kicker league as missing one. Only fall back to the default when
    # the key is genuinely absent (unknown format), never when it's
    # present and zero.
    def _required_shallow_starters(*keys: str, default: int = 1) -> int:
        for key in keys:
            value = settings.get(key)
            if value is not None:
                try:
                    return max(0, int(value))
                except (TypeError, ValueError):
                    continue
        return default

    required = {
        "K": _required_shallow_starters("k_count"),
        "DEF": _required_shallow_starters("def_count", "dst_count"),
    }

    rooms: dict[str, dict[str, Any]] = {}
    for position in SHALLOW_POSITIONS:
        position_df = (
            roster[
                roster.get("position", pd.Series("", index=roster.index))
                .fillna("")
                .astype(str)
                .str.upper()
                .eq(position)
            ].copy()
            if not roster.empty
            else pd.DataFrame()
        )
        rostered_ids: list[str] = []
        startable_ids: list[str] = []
        disqualified_ids: list[str] = []
        for _, row in position_df.iterrows():
            player_id = str(row.get("player_id") or "").strip()
            rostered_ids.append(player_id)
            if _is_shallow_position_disqualified(row):
                disqualified_ids.append(player_id)
            else:
                startable_ids.append(player_id)

        startable_count = len(startable_ids)
        true_need = startable_count < required[position]
        if true_need and not rostered_ids:
            need_type = f"no rostered {position.lower()}"
        elif true_need:
            need_type = f"rostered {position.lower()} unavailable (IR/retired/etc.)"
        else:
            need_type = "covered"

        rooms[position] = {
            "position": position,
            "required_starters": required[position],
            "rostered_ids": rostered_ids,
            "startable_ids": startable_ids,
            "disqualified_ids": disqualified_ids,
            "startable_count": startable_count,
            "true_need": true_need,
            "need_type": need_type,
        }
    return rooms


@runtime_trace.traced("true_shallow_position_needs", phase="team_needs")
def true_shallow_position_needs(
    roster_df: pd.DataFrame,
    league_settings: dict | None = None,
) -> tuple[list[str], dict[str, dict[str, Any]]]:
    """``true_roster_needs``'s analog for shallow, single-starter rooms.

    Returns the K/DEF positions that are real gaps (no startable rostered
    player) alongside their room records, kept separate from
    ``true_roster_needs`` so CORE_POSITIONS' depth-gradient need policy stays
    untouched.
    """
    rooms = classify_shallow_position_rooms(roster_df, league_settings)
    needs = [position for position in SHALLOW_POSITIONS if rooms[position]["true_need"]]
    return needs, rooms
