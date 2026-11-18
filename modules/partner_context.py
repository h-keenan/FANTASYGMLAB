"""Partner context for trade-idea acceptance: roster age, pick stash, trade habits.

Handshake items 3, 4 and 5 of docs/audits/2026-11-advice-handshakes.md. Three
small, bounded nudges on how likely the PARTNER is to say yes. They never
replace the existing partner checks (need, posture, age-of-return, value loss)
and they never touch the 12% fairness ceiling.

Guardrails (all constants below, all tested):

* Each factor has its own small cap (``AGE_MAX_POINTS`` / ``PICK_MAX_POINTS`` /
  ``TENDENCY_MAX_POINTS``).
* The COMBINED adjustment is clamped to ``COMBINED_MAX_POINTS`` of the 0-100
  market-realism score, in either direction.
* The partner loss cap moves at most ``CAP_SHIFT_MAX`` (one percentage point of
  the 9% max cap) and ONLY when at least two factors push the same way; a single
  signal never changes the cap, so it cannot flip a borderline idea by itself.
* A small sample shrinks the tendency toward neutral (``n / (n + SHRINK_K)``).
* Pick valuation is untouched: picks are already priced from the ORIGINAL
  owner's projected slot (``trade_ideas._pick_value_components``); this module
  only reads each pick's slot and the partner's pick counts.

Kill switch: ``DYNASTYGM_PARTNER_CONTEXT_V1`` (default ON; 0/false/off restores
the previous behaviour exactly). Sim AI GMs do not read this module."""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Sequence

from modules import age_profile, experimental_graduation

PARTNER_CONTEXT_ENV_KEY = "DYNASTYGM_PARTNER_CONTEXT_V1"

AGE_MAX_POINTS = 3.0
PICK_MAX_POINTS = 3.0
TENDENCY_MAX_POINTS = 2.0
COMBINED_MAX_POINTS = 6.0
CAP_SHIFT_MAX = 0.01
# 6 points of score = the full cap shift.
CAP_PER_POINT = CAP_SHIFT_MAX / COMBINED_MAX_POINTS
SHRINK_K = 4.0
MIN_AGED_PLAYERS = 6
AGE_FULL_SIGNAL_YEARS = 2.5
CORE_AGE_MIN_DELTA = age_profile.TEAM_OLDER_RETOOL_DELTA_YEARS
EARLY_SLOT_SHARE = 1.0 / 3.0
NOTE_MIN_POINTS = 1.5


def enabled() -> bool:
    return experimental_graduation.graduated_kill_switch_enabled(PARTNER_CONTEXT_ENV_KEY, default=True)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _is_early(round_num: Any, slot: Any, team_count: int) -> bool:
    try:
        slot_n = int(slot)
        round_n = int(round_num or 0)
    except (TypeError, ValueError):
        return False
    return round_n == 1 and slot_n <= max(1, int(round(team_count * EARLY_SLOT_SHARE)))


def build_context(
    *,
    age_block: Mapping[str, Any] | None,
    picks_block: Mapping[str, Any] | None,
    tendency: Mapping[str, Any] | None,
    league_core_age: float | None,
    team_count: int,
) -> dict[str, Any]:
    """One partner's compact context from the shared team-profile blocks
    (``team_profile.build_age_block`` / ``build_picks_block`` and the profile's
    tendency block). Missing pieces stay empty and contribute nothing."""

    age = dict(age_block or {})
    core = age.get("core_avg")
    aged = sum(int(v) for v in (age.get("phase_counts") or {}).values())
    delta = None
    if core is not None and league_core_age is not None and aged >= MIN_AGED_PLAYERS:
        delta = float(core) - float(league_core_age)
    picks = dict(picks_block or {})
    assets = [a for a in picks.get("assets") or () if isinstance(a, Mapping)]
    early = sum(1 for a in assets if _is_early(a.get("round"), a.get("slot_number"), team_count))
    firsts = int(picks.get("firsts") or 0)
    tier = str(picks.get("tier") or "middle")
    tend = dict(tendency or {})
    return {
        "core_age": core,
        "league_core_age": league_core_age,
        "core_age_delta": delta,
        "firsts": firsts,
        "early_firsts": early,
        "pick_count": int(picks.get("count") or len(assets)),
        "pick_tier": tier,
        "pick_stash": early >= 2 or (firsts >= 3 and tier == "high"),
        "pick_short": bool(picks_block) and (firsts == 0 or tier == "low"),
        "lean": str(tend.get("lean") or ""),
        "buy_count": int(tend.get("buy_count") or 0),
        "sell_count": int(tend.get("sell_count") or 0),
    }


def league_core_age(age_blocks: Iterable[Mapping[str, Any] | None]) -> float | None:
    values = [float(b["core_avg"]) for b in age_blocks if b and b.get("core_avg") is not None]
    return round(sum(values) / len(values), 2) if values else None


def _avg_age(assets: Sequence[Mapping[str, Any]]) -> float | None:
    ages = []
    for a in assets:
        if a.get("asset_type") != "player":
            continue
        try:
            age = float(a.get("age") or 0)
        except (TypeError, ValueError):
            continue
        if 0 < age <= age_profile.MAX_KNOWN_AGE:
            ages.append(age)
    return sum(ages) / len(ages) if ages else None


def _age_gap(gives: Sequence[Mapping[str, Any]], gets: Sequence[Mapping[str, Any]]) -> float:
    """Years the partner's outgoing players are older than what they receive (0 when unknown)."""

    gives_avg, gets_avg = _avg_age(gives), _avg_age(gets)
    if gives_avg is None or gets_avg is None:
        return 0.0
    return gives_avg - gets_avg


def _has_pick(assets: Sequence[Mapping[str, Any]]) -> bool:
    return any(a.get("asset_type") == "pick" for a in assets)


def _age_factor(
    ctx: Mapping[str, Any], gets: Sequence, gives: Sequence, incoming_band: str, existing_age_fit: str
) -> tuple[float, str]:
    delta = ctx.get("core_age_delta")
    if delta is None or abs(delta) < CORE_AGE_MIN_DELTA:
        return 0.0, ""
    strength = _clamp(abs(delta) / AGE_FULL_SIGNAL_YEARS, 0.0, 1.0)
    fit = 0.0
    if delta > 0:  # older core: wants picks and youth
        if _has_pick(gets):
            fit += 0.5
        if incoming_band == "young":
            fit += 0.5
        elif incoming_band == "old":
            fit -= 1.0
        if _age_gap(gives, gets) >= age_profile.YOUNGER_RETURN_YEARS:
            fit += 0.5
        note = "older core"
    else:  # younger core: does not want declining vets
        if incoming_band == "old":
            fit -= 1.0
        elif incoming_band in {"young", "prime"}:
            fit += 0.5
        note = "younger core"
    fit = _clamp(fit, -1.0, 1.0)
    # The posture age fit already moved the cap for this very package: halve
    # this factor when it agrees so one fact is not counted twice.
    if (existing_age_fit == "good" and fit > 0) or (existing_age_fit == "poor" and fit < 0):
        fit *= 0.5
    return AGE_MAX_POINTS * strength * fit, (note if fit else "")


def _pick_factor(ctx: Mapping[str, Any], gets: Sequence, gives: Sequence, team_count: int) -> tuple[float, str]:
    gives_picks = [a for a in gives if a.get("asset_type") == "pick"]
    points = 0.0
    note = ""
    if gives_picks:
        early = any(_is_early(a.get("round"), a.get("projected_slot_number"), team_count) for a in gives_picks)
        if ctx.get("pick_stash"):
            points += PICK_MAX_POINTS if early else PICK_MAX_POINTS / 2
            note = "deep in early picks"
        elif ctx.get("pick_short"):
            points -= PICK_MAX_POINTS
            note = "short on picks"
    if _has_pick(gets):
        if ctx.get("pick_short"):
            points += PICK_MAX_POINTS
            note = "short on picks"
        elif ctx.get("pick_stash"):
            points -= PICK_MAX_POINTS / 3
    points = _clamp(points, -PICK_MAX_POINTS, PICK_MAX_POINTS)
    return points, (note if points else "")


def _tendency_factor(ctx: Mapping[str, Any], gets: Sequence, gives: Sequence) -> tuple[float, str]:
    lean = str(ctx.get("lean") or "").strip().lower()
    buys, sells = int(ctx.get("buy_count") or 0), int(ctx.get("sell_count") or 0)
    n = buys + sells
    if lean not in {"seller", "buyer"} or n <= 0:
        return 0.0, ""
    lopsided = abs(sells - buys) / n
    shrink = n / (n + SHRINK_K)
    gap = _age_gap(gives, gets)
    partner_sells = gap >= age_profile.YOUNGER_RETURN_YEARS or (_has_pick(gets) and not _has_pick(gives))
    partner_buys = gap <= -age_profile.YOUNGER_RETURN_YEARS or (_has_pick(gives) and not _has_pick(gets))
    if lean == "seller":
        match = 1.0 if partner_sells else (-0.5 if partner_buys else 0.0)
    else:
        match = 1.0 if partner_buys else (-0.5 if partner_sells else 0.0)
    points = TENDENCY_MAX_POINTS * lopsided * shrink * match
    note = ("sells vets lately" if lean == "seller" else "buys vets lately") if match > 0 else ""
    return points, note


def adjustment(
    *,
    ctx: Mapping[str, Any] | None,
    send_assets: Sequence[Mapping[str, Any]],
    receive_assets: Sequence[Mapping[str, Any]],
    incoming_age_band: str,
    existing_age_fit: str,
    team_count: int,
) -> dict[str, Any]:
    """Bounded acceptance nudge. ``send_assets`` is what the USER sends (the
    partner receives); ``receive_assets`` is what the partner gives up."""

    empty = {"points": 0.0, "cap_shift": 0.0, "factors": {}, "note": ""}
    if not ctx or not enabled():
        return empty
    age_pts, age_note = _age_factor(ctx, send_assets, receive_assets, incoming_age_band, existing_age_fit)
    pick_pts, pick_note = _pick_factor(ctx, send_assets, receive_assets, team_count)
    tend_pts, tend_note = _tendency_factor(ctx, send_assets, receive_assets)
    parts = (age_pts, pick_pts, tend_pts)
    points = _clamp(sum(parts), -COMBINED_MAX_POINTS, COMBINED_MAX_POINTS)
    pos = sum(1 for v in parts if v > 0.25)
    neg = sum(1 for v in parts if v < -0.25)
    cap_shift = 0.0
    if (pos >= 2 and neg == 0) or (neg >= 2 and pos == 0):
        cap_shift = _clamp(points * CAP_PER_POINT, -CAP_SHIFT_MAX, CAP_SHIFT_MAX)
    strongest = max(((abs(age_pts), age_note), (abs(pick_pts), pick_note), (abs(tend_pts), tend_note)), key=lambda p: p[0])
    return {
        "points": round(points, 2),
        "cap_shift": round(cap_shift, 4),
        "factors": {"age": round(age_pts, 2), "picks": round(pick_pts, 2), "tendency": round(tend_pts, 2)},
        "note": strongest[1] if strongest[0] >= NOTE_MIN_POINTS else "",
    }
