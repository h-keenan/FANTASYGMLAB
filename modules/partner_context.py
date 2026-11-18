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
# Extension flags (each default ON, 0/false/off restores the previous output
# exactly). The first three decide whether a surface hands the shared league
# team profile (partner trade tendency) to the idea engine; with the flag off the
# surface reads tendency neutral exactly as before. All of them also require the
# master flag above.
FINDER_ENV_KEY = "DYNASTYGM_PARTNER_CONTEXT_FINDER_V1"
DASHBOARD_ENV_KEY = "DYNASTYGM_PARTNER_CONTEXT_DASHBOARD_V1"
SEARCH_ENV_KEY = "DYNASTYGM_PARTNER_CONTEXT_SEARCH_V1"
# Surfaces that default OFF until their realism shift is proven inside
# COMBINED_MAX_POINTS (player search overshot it; explicit "1" opts in).
SURFACE_DEFAULT_ON = {SEARCH_ENV_KEY: False}
ASK_PICK_ENV_KEY = "DYNASTYGM_ASK_PICK_IDEA_V1"
ASK_PICK_TITLE = "Ask for their pick"
ASK_PICK_MAX_PER_PARTNER = 2
ASK_PICK_MIN_FACTORS = 2

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


def surface_enabled(env_key: str) -> bool:
    """A surface flag counts only while the master flag is on too."""

    return enabled() and experimental_graduation.graduated_kill_switch_enabled(
        env_key, default=SURFACE_DEFAULT_ON.get(env_key, True)
    )


def team_profiles_for_surface(
    env_key: str, *, league_id: str, lens: str, players_db_path: str
) -> Mapping[str, Any] | None:
    """The cached league team profile for a surface, or None (neutral tendency,
    today's output) when the surface flag is off or the profile is unavailable."""

    if not surface_enabled(env_key):
        return None
    try:
        from modules import team_profile

        return team_profile.league_team_profiles_cached(
            league_id=league_id, lens=lens, players_db_path=players_db_path
        )
    except Exception:
        return None


def ask_pick_enabled() -> bool:
    return surface_enabled(ASK_PICK_ENV_KEY)


def _short_name(label: Any) -> str:
    parts = str(label or "").split()
    return f"{parts[0][0]}. {' '.join(parts[1:])}" if len(parts) > 1 else str(label or "")


def ask_pick_plan(
    ctx: Mapping[str, Any] | None,
    *,
    partner_strategy: str,
    partner_needs: Iterable[str],
    send_assets: Sequence[Mapping[str, Any]],
) -> dict[str, Any] | None:
    """Should we propose asking this partner for a pick, and why?

    Needs real surplus pick capital (a stash of early firsts, or 2+ firsts and
    not short on picks) AND at least ``ASK_PICK_MIN_FACTORS`` plausibility
    factors: the partner is contending, the player we send fills a position they
    need, their core is older than the league's (picks are the currency an older
    core spends), or they lean buyer lately. One signal alone never proposes the
    idea. Pricing is not done here: the pick's value is the shared pick price
    already on the asset (``trade_ideas.pick_value_components``)."""

    if not ctx or not ask_pick_enabled():
        return None
    if ctx.get("pick_short"):
        return None
    firsts = int(ctx.get("firsts") or 0)
    if not (ctx.get("pick_stash") or firsts >= 2):
        return None
    needs = {str(p).upper() for p in partner_needs or ()}
    players = [a for a in send_assets if a.get("asset_type") == "player"]
    if not players:
        return None
    reasons: list[str] = []
    if str(partner_strategy or "").lower() in {"contender", "fringe_contender"}:
        reasons.append("they are contending")
    fills = [a for a in players if str(a.get("position") or "").upper() in needs]
    if fills:
        who = _short_name(fills[0].get("label") or fills[0].get("name"))
        reasons.append(f"{who} fills a {str(fills[0].get('position')).upper()} need")
    delta = ctx.get("core_age_delta")
    if delta is not None and float(delta) >= CORE_AGE_MIN_DELTA:
        reasons.append("their core runs older")
    if str(ctx.get("lean") or "").lower() == "buyer" and int(ctx.get("buy_count") or 0) >= 2:
        reasons.append("they have been buying")
    if len(reasons) < ASK_PICK_MIN_FACTORS:
        return None
    capital = "are deep in early picks" if ctx.get("pick_stash") else f"hold {firsts} firsts"
    return {"reasons": reasons, "capital": capital, "rationale": f"They {capital}; " + ", ".join(reasons) + "."}


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
