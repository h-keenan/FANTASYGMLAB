"""IDP (individual defensive player) projection model.

Predicts a defender's per-game stat *rates* and scores them with a league's own
``scoring_settings`` (``modules.idp_scoring``). Predicting rates per stat, not
points, is deliberate: tackle rates are stable year to year, sack rates are
partly stable, and interceptions / fumble recoveries / touchdowns are close to
noise, so each stat is regressed to its position mean by a different amount and
the league's scoring decides how much each one matters.

Layers (fit by ``scripts/idp_backtest.py`` on 2022-2024 transitions only, 2025
held out; constants in ``idp_model_params.json``):

1. Season prior: for each position (DL/LB/DB) and stat, a ridge regression of
   next-season rate on last-season rate, last-season defensive snap share and
   age (linear + quadratic). The regression coefficient on last season's rate is
   the shrinkage toward the position mean; the snap term is role stability; the
   age terms are the position's age curve.
2. In-season update: games already played this season are blended into the
   prior with a per-stat pseudo-game weight ``k`` (``(k * prior + sum) / (k + n)``).
3. Availability: ``survival`` is the probability a defender at this age still
   plays a meaningful role next season (fit on the same transitions).

Everything is point-in-time: callers pass only weekly rows from before the
week being predicted. Nothing here fabricates a value: a player with no
defensive games in the prior season and none this season gets ``None``.
"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from typing import Any, Dict, Iterable, List, Mapping, Sequence

from modules.idp_scoring import idp_slot_family

COMPONENTS = (
    "idp_tkl_solo", "idp_tkl_ast", "idp_tkl_loss", "idp_sack", "idp_qb_hit", "idp_pass_def",
    "idp_int", "idp_ff", "idp_fum_rec", "idp_def_td", "idp_safe", "idp_blk_kick",
    "idp_sack_yd", "idp_int_ret_yd", "idp_fum_ret_yd", "idp_pass_def_3p",
)
FAMILIES = ("DL", "LB", "DB")
PARAMS_PATH = os.path.join(os.path.dirname(__file__), "idp_model_params.json")
# A defender counts as having played a defensive game when the row has
# defensive snaps (rows without them are special-teams-only appearances).
MIN_ROLE_GAMES = 8
# The season before last only counts as evidence with a real sample.
MIN_PRIOR2_GAMES = 4


@lru_cache(maxsize=1)
def load_params() -> Dict[str, Any]:
    try:
        with open(PARAMS_PATH, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def defensive_games(rows: Iterable[Mapping[str, Any]] | None, *, before_week: int | None = None) -> List[Mapping[str, Any]]:
    """Weekly rows in which the player was on the field for defensive snaps."""

    out = []
    for row in rows or ():
        if not isinstance(row, Mapping):
            continue
        if before_week is not None and int(row.get("week") or 0) >= int(before_week):
            continue
        if float(row.get("defensive_snaps") or 0) > 0:
            out.append(row)
    return out


def season_summary(rows: Iterable[Mapping[str, Any]] | None, *, before_week: int | None = None) -> Dict[str, Any]:
    """Games, per-game stat rates and mean defensive snap share."""

    games = defensive_games(rows, before_week=before_week)
    n = len(games)
    if not n:
        return {"games": 0, "rates": {}, "snap_share": None}
    rates = {c: sum(float(g.get(c) or 0.0) for g in games) / n for c in COMPONENTS}
    shares = [float(g["def_snap_share"]) for g in games if g.get("def_snap_share") is not None]
    return {"games": n, "rates": rates, "snap_share": (sum(shares) / len(shares)) if shares else None}


def _age_feature(age: float | None, family: str, params: Mapping[str, Any]) -> tuple[float, float]:
    center = float((params.get("age_center") or {}).get(family, 26.0))
    a = center if age is None else float(age)
    d = a - center
    return d, d * d


def project_prior_rates(
    family: str,
    prior: Mapping[str, Any] | None,
    age: float | None,
    *,
    prior2: Mapping[str, Any] | None = None,
    params: Mapping[str, Any] | None = None,
) -> Dict[str, float] | None:
    """Season prior for next season from last season's summary (and the season
    before it when the player has one). None when the player has no defensive
    games last season (the model has nothing to go on)."""

    params = params or load_params()
    fam = idp_slot_family(family) or family
    coefs = (params.get("rate_models") or {}).get(fam)
    if not coefs or not prior or not prior.get("games"):
        return None
    d1, d2 = _age_feature(age, fam, params)
    snap = prior.get("snap_share")
    snap = float((params.get("mean_snap_share") or {}).get(fam, 0.5)) if snap is None else float(snap)
    out: Dict[str, float] = {}
    for comp in COMPONENTS:
        c = coefs.get(comp)
        if not c:
            continue
        rate = float(prior["rates"].get(comp, 0.0))
        rate2 = float(prior2["rates"].get(comp, 0.0)) if prior2 and prior2.get("games", 0) >= MIN_PRIOR2_GAMES else rate
        value = c["a"] + c["b"] * rate + c.get("b2", 0.0) * rate2 + c["snap"] * snap + c["age"] * d1 + c["age2"] * d2
        out[comp] = max(0.0, value)
    return out


def update_with_current(
    family: str,
    prior_rates: Mapping[str, float] | None,
    current: Mapping[str, Any] | None,
    *,
    params: Mapping[str, Any] | None = None,
) -> Dict[str, float] | None:
    """Blend this season's games so far into the prior. With no prior the
    position mean is the prior; with no games and no prior the result is None."""

    params = params or load_params()
    fam = idp_slot_family(family) or family
    n = int((current or {}).get("games") or 0)
    if prior_rates is None:
        if n < 1:
            return None
        base = (params.get("position_mean_rates") or {}).get(fam)
        if not base:
            return None
        prior_rates = base
    ks = params.get("k_in_season") or {}
    out: Dict[str, float] = {}
    for comp, p in prior_rates.items():
        k = float(ks.get(comp, 8.0))
        total = float((current or {}).get("rates", {}).get(comp, 0.0)) * n if n else 0.0
        out[comp] = (k * float(p) + total) / (k + n)
    return out


def rates_to_ppg(rates: Mapping[str, float] | None, weights: Mapping[str, float]) -> float | None:
    """Points per game from stat rates and a league's ``idp_scoring_weights``.
    A league scoring the combined tackle total (``idp_tkl``) credits both the
    solo and assist rates. Threshold bonuses are not modelled."""

    if rates is None:
        return None
    w_tkl = float(weights.get("idp_tkl", 0.0))
    total = 0.0
    for comp, rate in rates.items():
        weight = float(weights.get(comp, 0.0))
        if comp in ("idp_tkl_solo", "idp_tkl_ast"):
            weight += w_tkl
        total += weight * float(rate)
    return total


def survival_probability(family: str, age: float | None, *, params: Mapping[str, Any] | None = None) -> float:
    """Chance a defender of this age keeps a role (>= 8 defensive games) next season."""

    params = params or load_params()
    fam = idp_slot_family(family) or family
    table = (params.get("survival") or {}).get(fam) or {}
    if age is None or not table:
        return float((params.get("survival_default") or {}).get(fam, 0.75))
    a = str(int(max(min(age, max(int(k) for k in table)), min(int(k) for k in table))))
    return float(table.get(a, 0.75))


def project_player_ppg(
    family: str,
    prior_rows: Sequence[Mapping[str, Any]] | None,
    current_rows: Sequence[Mapping[str, Any]] | None,
    age: float | None,
    weights: Mapping[str, float],
    *,
    prior2_rows: Sequence[Mapping[str, Any]] | None = None,
    before_week: int | None = None,
    params: Mapping[str, Any] | None = None,
) -> float | None:
    """Expected PPG for the next game under the league's scoring, point-in-time."""

    prior = season_summary(prior_rows)
    prior2 = season_summary(prior2_rows) if prior2_rows else None
    prior_rates = project_prior_rates(family, prior, age, prior2=prior2, params=params)
    current = season_summary(current_rows, before_week=before_week)
    return rates_to_ppg(update_with_current(family, prior_rates, current, params=params), weights)


def age_on(birth_date: Any, season: int) -> float | None:
    """Age in years on Sept 1 of ``season`` from a Sleeper ``YYYY-MM-DD`` birth date."""

    try:
        from datetime import date

        y, m, d = (int(part) for part in str(birth_date).split("-"))
        return (date(int(season), 9, 1) - date(y, m, d)).days / 365.25
    except Exception:
        return None


def value_from_vor(vor_points: float, *, params: Mapping[str, Any] | None = None) -> float:
    """Offensive-scale value (0-10,000, FantasyCalc units) for a season's points
    over replacement, via the curve fit on offense (``scripts/idp_value_curve.py``)."""

    params = params or load_params()
    curve = params.get("value_curve") or {}
    if not curve or vor_points <= 0:
        return 0.0
    return float(min(float(curve.get("cap", 9000)), float(curve["a"]) * float(vor_points) ** float(curve["p"])))


def replacement_ranks(slots: Mapping[str, int], teams: int) -> Dict[str, int]:
    """How many defenders of each family a league starts (IDP_FLEX split evenly
    across DL/LB/DB); the next one down is replacement level. DE/DT count toward
    DL, CB/S toward DB."""

    counts = {"DL": 0.0, "LB": 0.0, "DB": 0.0}
    for slot, n in slots.items():
        fam = idp_slot_family(slot)
        if fam:
            counts[fam] += float(n)
    flex = float(slots.get("IDP_FLEX", 0)) / 3.0
    return {fam: int(round(float(teams) * (counts[fam] + flex))) for fam in counts}


def project_league_values(
    defenders: Sequence[Mapping[str, Any]],
    weights: Mapping[str, float],
    *,
    slots: Mapping[str, int],
    teams: int,
    season: int,
    before_week: int | None = None,
    params: Mapping[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    """Value every defender for one league.

    Each input dict needs ``player_id``, ``position``, ``birth_date`` (optional),
    ``prior_rows`` (last season's weekly rows), optional ``prior2_rows`` and
    ``current_rows`` (this season so far). Output rows carry projected PPG,
    projected season points (x games x survival), points over this league's
    replacement level at the player's family, and ``value`` on the offensive
    scale. Defenders with no usable history are returned with ``value`` None;
    nothing is invented for them.
    """

    params = params or load_params()
    games = float(params.get("season_games") or 17)
    scored: List[Dict[str, Any]] = []
    for d in defenders:
        fam = idp_slot_family(d.get("position"))
        if fam is None:
            continue
        age = age_on(d.get("birth_date"), season)
        ppg = project_player_ppg(
            fam, d.get("prior_rows"), d.get("current_rows"), age, weights,
            prior2_rows=d.get("prior2_rows"), before_week=before_week, params=params,
        )
        entry: Dict[str, Any] = {"player_id": str(d.get("player_id")), "family": fam, "age": age, "ppg": ppg, "value": None}
        if ppg is not None:
            surv = survival_probability(fam, age, params=params)
            entry["survival"] = surv
            entry["projected_points"] = ppg * games * surv
            evidence = season_summary(d.get("prior_rows"))["games"] + season_summary(d.get("current_rows"), before_week=before_week)["games"]
            entry["confidence"] = "high" if evidence >= 20 else "medium" if evidence >= MIN_ROLE_GAMES else "low"
        scored.append(entry)
    ranks = replacement_ranks(slots, teams)
    for fam in FAMILIES:
        pool = sorted((e for e in scored if e["family"] == fam and e.get("projected_points") is not None), key=lambda e: -e["projected_points"])
        n = ranks[fam]
        if n <= 0 or not pool:
            continue
        repl = pool[min(n, len(pool) - 1)]["projected_points"]
        for e in pool:
            e["replacement_points"] = repl
            e["vor"] = e["projected_points"] - repl
            e["value"] = round(value_from_vor(e["vor"], params=params))
    return scored
