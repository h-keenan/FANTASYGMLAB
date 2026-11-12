"""Structured caution tags for a Trade Analyzer verdict.

Owner report (2026-11): a REBUILDING team (#11 of 12, 3-6) that already held
five 1st-round picks across the next two drafts was shown SMASH ACCEPT for
sending P. Washington (WR, 24, value 6,037) + a 2027 R3 and receiving Josh
Downs (WR, 25, 3,921) + a 2027 R1. The value balance (+1,873) is honest; what
the ladder cannot see is that the 6th first is worth less *to this team* than
its sticker price, while ~2,100 of present value left the roster.

Rule (``pick_glut``), derived from facts, not from one player or one team:

* direction: the team does not want present value over future value
  (``trade_posture.ORIENTATION`` <= 0: retool, rebuild, tank). Contenders pay
  for lost lineup through the window term already.
* picks held: premium picks (R1 = 1.0, R2 = 0.5) in the next two drafts
  already total ``GLUT_UNITS`` or more, and the trade adds more of them.
* share: picks are at least ``PICK_SHARE_MIN`` of the incoming value, so the
  deal really is "value for picks", not a player swap with a pick sweetener.
* outflow: real current value goes out: players sent out beat players coming
  back by ``CURRENT_OUT_MIN`` value units, or the lineup model says the team
  loses lineup points. A sold player past ``AGING_AGE`` is the textbook
  rebuild sale and never trips it.
* roster room: when the roster limit is known and the open spots after the
  trade can absorb every pick the team would hold, the picks are not crowding
  anything and the caution stays quiet. Unknown room never blocks it.

Effect (and the only one): a tag with a one-line explanation in ``cautions``
and, when the verdict was SMASH ACCEPT, a ONE-step softening to ACCEPT.
Value numbers, trade score, confidence and counter search are never touched.
Wording lives here; web and mobile render these strings verbatim
(web-next/src/lib/tradeCautions.ts is the identical twin of the mobile one).
"""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from modules import trade_posture, trade_value_bands as bands

CAUTION_PICK_GLUT = "pick_glut"
PICK_GLUT_TAG = "Trading proven value for picks you may not need"

# Premium-pick weights: what one pick adds toward "already holds a lot".
PICK_UNITS = {1: 1.0, 2: 0.5}
# ~2 firsts + 2 seconds per two drafts is a normal haul (3.0). Four or more is
# a team that already has more premium picks than a rebuild can use.
GLUT_UNITS = 4.0
# The trade must add at least half a unit (one R2) of premium picks.
MIN_NET_UNITS = 0.5
PICK_SHARE_MIN = 0.25
CURRENT_OUT_MIN = 1500.0
LINEUP_OUT_MIN = 5.0
AGING_AGE = 28

# Verdict labels the caution may sit next to; only the top rung softens.
_ELIGIBLE_VERDICTS = {bands.VERDICT_SMASH_ACCEPT, bands.VERDICT_ACCEPT, bands.VERDICT_FAIR}


def _num(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _score(asset: Mapping[str, Any]) -> float:
    return _num(asset.get("score", asset.get("value_score")))


def _round(asset: Mapping[str, Any]) -> int:
    return int(_num(asset.get("round")))


def _season(asset: Mapping[str, Any]) -> int:
    return int(_num(asset.get("season")))


def pick_units(picks: Sequence[Mapping[str, Any]], seasons: Sequence[int]) -> float:
    return sum(PICK_UNITS.get(_round(p), 0.0) for p in picks if _season(p) in set(seasons))


def build_pick_context(
    all_picks: Sequence[Mapping[str, Any]] | None,
    my_roster_id: Any,
    *,
    open_roster_spots: int | None = None,
) -> dict[str, Any] | None:
    """What the team holds, from the league's pick table (before the trade).

    ``open_roster_spots``: active roster slots still free (None = unknown)."""

    picks = [p for p in (all_picks or ()) if isinstance(p, Mapping) and _season(p) > 0]
    if not picks:
        return None
    seasons = sorted({_season(p) for p in picks})[:2]
    mine = [p for p in picks if str(p.get("owner_roster_id")) == str(my_roster_id)]
    return {
        "seasons": seasons,
        "held_units": round(pick_units(mine, seasons), 2),
        "held_firsts": sum(1 for p in mine if _round(p) == 1 and _season(p) in seasons),
        "held_premium": sum(1 for p in mine if _round(p) in PICK_UNITS and _season(p) in seasons),
        "open_roster_spots": open_roster_spots,
    }


def open_roster_spots(league: Mapping[str, Any] | None, roster: Mapping[str, Any] | None) -> int | None:
    from modules import roster_value_model as rvm

    limits = rvm.roster_limits(league, roster)
    if limits.active_limit is None:
        return None
    return max(0, limits.active_limit - len(limits.active_ids))


def pick_glut(
    posture: Mapping[str, Any] | None,
    send_assets: Sequence[Mapping[str, Any]] | None,
    receive_assets: Sequence[Mapping[str, Any]] | None,
    pick_context: Mapping[str, Any] | None,
    assessment: Mapping[str, Any] | None = None,
) -> dict[str, Any] | None:
    """The caution (a dict of facts) or None. See the module docstring."""

    if not pick_context:
        return None
    key = trade_posture.normalize_team_strategy(str((posture or {}).get("key") or ""))
    if not (posture or {}).get("key") or trade_posture.ORIENTATION.get(key, 0.0) > 0:
        return None
    sent = [a for a in send_assets or () if isinstance(a, Mapping)]
    got = [a for a in receive_assets or () if isinstance(a, Mapping)]
    seasons = list(pick_context.get("seasons") or [])
    sent_picks = [a for a in sent if a.get("asset_type") == "pick"]
    got_picks = [a for a in got if a.get("asset_type") == "pick"]
    sent_players = [a for a in sent if a.get("asset_type") != "pick"]
    got_players = [a for a in got if a.get("asset_type") != "pick"]

    incoming_units = pick_units(got_picks, seasons)
    net_units = incoming_units - pick_units(sent_picks, seasons)
    held = _num(pick_context.get("held_units"))
    if incoming_units <= 0 or net_units < MIN_NET_UNITS or held < GLUT_UNITS:
        return None

    incoming_value = sum(_score(a) for a in got)
    pick_value = sum(_score(a) for a in got_picks)
    share = pick_value / incoming_value if incoming_value > 0 else 0.0
    if share < PICK_SHARE_MIN:
        return None

    current_out = sum(_score(a) for a in sent_players) - sum(_score(a) for a in got_players)
    lineup_points = _num((assessment or {}).get("lineup_points"))
    if current_out < CURRENT_OUT_MIN and lineup_points > -LINEUP_OUT_MIN:
        return None
    if sent_players:
        top = max(sent_players, key=_score)
        if _num(top.get("age")) >= AGING_AGE:
            return None

    open_spots = pick_context.get("open_roster_spots")
    if open_spots is not None:
        after = int(open_spots) - (len(got_players) - len(sent_players))
        if after >= int(held + net_units + 0.999):
            return None

    new_picks = [a for a in got_picks if _season(a) in seasons and _round(a) in PICK_UNITS]
    return {
        "code": CAUTION_PICK_GLUT,
        "tag": PICK_GLUT_TAG,
        "explanation": explanation(int(pick_context.get("held_premium") or 0), len(new_picks)),
        "facts": {
            "held_premium_picks": int(pick_context.get("held_premium") or 0),
            "held_firsts": int(pick_context.get("held_firsts") or 0),
            "incoming_premium_picks": len(new_picks),
            "pick_share_of_incoming": round(share, 2),
            "current_value_out": round(current_out),
            "lineup_points": round(lineup_points, 1),
            "open_roster_spots": open_spots,
        },
        "softened": False,
        "softened_from": "",
    }


def explanation(held: int, incoming: int) -> str:
    more = "another pick" if incoming == 1 else f"{incoming} more picks"
    return (
        f"You already hold {held} first- and second-round picks in the next two drafts, so {more} "
        "adds less to your team than its listed value. The value balance is unchanged."
    )


def apply_cautions(
    verdict: str, caution: dict[str, Any] | None
) -> tuple[list[dict[str, Any]], bool]:
    """(cautions, soften). The caution only shows on a verdict that still reads
    positive or close (a decline needs no extra warning); it softens exactly
    one rung, SMASH ACCEPT -> ACCEPT, and nothing else."""

    if not caution or verdict not in _ELIGIBLE_VERDICTS:
        return [], False
    soften = verdict == bands.VERDICT_SMASH_ACCEPT
    out = dict(caution)
    if soften:
        out["softened"] = True
        out["softened_from"] = bands.VERDICT_SMASH_ACCEPT
    return [out], soften
