"""Letter grades for the Fantasy Sim: what the player sees instead of a number.

A numeric overall (and any rank taken from it) is a tell: sort by it and you have the model's hidden rating.
The sim therefore shows Madden / 2K style **letter grades** only:

* an **overall grade** (12 coarse bands, A+ .. F): the player's value percentile within his position pool plus
  deterministic scouting noise, then bucketed. It is informative but not monotone-exact: two players a few places
  apart can swap bands, and a rookie's band is wider (``grade_range``).
* position **attribute grades** (``attributes``): built from observable inputs (usage shares, projection and its
  spread, age curve, injury history), never from the hidden value, each with its own independent noise, so they do
  not add up to the overall.

Everything here is PRESENTATION ONLY. It reads a frozen snapshot, draws no engine randomness (noise comes from a
sha256 of ``(save seed, player, season, tag)``) and writes no state, so every old save replays identically. The raw
number (``value``) never leaves the server: see ``tests/test_sim_grades.py`` for the leak scan.
"""

from __future__ import annotations

import hashlib
import statistics
from typing import Any, Mapping

LETTERS = ("F", "D", "D+", "C-", "C", "C+", "B-", "B", "B+", "A-", "A", "A+")  # index 0 = worst
# Lower edge of each band as a (noisy) percentile within the position pool, aligned with LETTERS.
CUTS = (0.0, 0.12, 0.22, 0.33, 0.44, 0.55, 0.66, 0.76, 0.84, 0.91, 0.955, 0.985)
MIN_POOL = 10  # a position pool thinner than this gets no grade (no fabricated rating)

SIGMA_VET = 0.08  # overall noise (percentile units) for an established player
SIGMA_ROOKIE_BASE = 0.07
SIGMA_ROOKIE_SPAN = 0.17  # extra noise at zero scouting confidence
SIGMA_ATTR = 0.10
UNCERTAIN_SIGMA = 0.12  # at or above this the grade is shown with a range and a "?"
RANGE_K = 0.9  # range half-width = RANGE_K * sigma, in percentile units

_N = statistics.NormalDist()


def band_of(percentile: float) -> int:
    """Index into LETTERS for a percentile in [0, 1]."""

    p = min(1.0, max(0.0, percentile))
    idx = 0
    for i, cut in enumerate(CUTS):
        if p >= cut:
            idx = i
    return idx


def letter_of(percentile: float) -> str:
    return LETTERS[band_of(percentile)]


def _z(seed: int, pid: str, season: int, tag: str) -> float:
    """Deterministic standard normal for (save seed, player, season, tag). Not the engine's RNG: no replay impact."""

    digest = hashlib.sha256(f"grade|{seed}|{pid}|{season}|{tag}".encode("utf-8")).digest()
    u = (int.from_bytes(digest[:8], "big") + 0.5) / 2.0 ** 64
    return _N.inv_cdf(u)


def _avg_rank_pct(values: Mapping[str, float]) -> dict[str, float]:
    """Percentile (0-1, ties share the average rank) of each id within ``values``."""

    n = len(values)
    ordered = sorted(values, key=lambda k: values[k])
    out: dict[str, float] = {}
    i = 0
    while i < n:
        j = i
        while j + 1 < n and values[ordered[j + 1]] == values[ordered[i]]:
            j += 1
        pct = ((i + 1) + (j + 1)) / 2.0 / n
        for k in range(i, j + 1):
            out[ordered[k]] = pct
        i = j + 1
    return out


# ------------------------------------------------------------------ attribute definitions

# (key, label) per position, in display order. Names say what the input really is: usage and production
# percentiles, not made-up skill ratings (the sim has no route-running or hands data).
ATTRIBUTES: dict[str, tuple[tuple[str, str], ...]] = {
    "QB": (("production", "Production"), ("efficiency", "Efficiency"), ("volume", "Volume"), ("consistency", "Consistency"), ("durability", "Durability"), ("prime", "Prime")),
    "RB": (("volume", "Workload"), ("production", "Production"), ("efficiency", "Efficiency"), ("consistency", "Consistency"), ("durability", "Durability"), ("prime", "Prime")),
    "WR": (("volume", "Targets"), ("production", "Production"), ("efficiency", "Efficiency"), ("consistency", "Consistency"), ("durability", "Durability"), ("prime", "Prime")),
    "TE": (("volume", "Targets"), ("production", "Production"), ("efficiency", "Efficiency"), ("consistency", "Consistency"), ("durability", "Durability"), ("prime", "Prime")),
    "K": (("production", "Scoring"), ("consistency", "Accuracy"), ("role", "Role"), ("durability", "Durability"), ("prime", "Prime")),
    "DEF": (("production", "Scoring"), ("consistency", "Consistency")),
}
# Age at which a position peaks and how many years either side before it is a clear mismatch.
_PEAK = {"QB": (29.0, 8.0), "RB": (24.5, 5.0), "WR": (26.0, 6.0), "TE": (27.0, 6.0), "K": (30.0, 10.0), "DEF": (26.0, 99.0)}


def _share(extra: Mapping[str, float]) -> float | None:
    for key in ("opportunity_share", "target_share", "rush_share", "snap_share"):
        v = extra.get(key)
        if v is not None and v > 0:
            return float(v)
    return None


def _metrics(p: Any) -> dict[str, float | None]:
    """The raw observable behind each attribute (higher = better). None when the data is not there."""

    ex = p.extra
    mean = float(p.mean)
    cv = float(p.sd) / mean if mean > 0 and p.sd else None
    peak, spread = _PEAK.get(p.pos, (27.0, 6.0))
    prime = 1.0 - min(1.0, abs(float(p.age) - peak) / spread)
    risk = ex.get("injury_risk_score")
    played = ex.get("games_played")
    prior = ex.get("prior_games_played")
    dur: float | None = None
    parts = []
    if risk is not None:
        parts.append(-float(risk))
    gp = [g for g in (played, prior) if g is not None and g > 0]
    if gp:
        parts.append(min(17.0, sum(gp) / len(gp)) / 17.0 * 10.0)
    if parts:
        dur = sum(parts) / len(parts)
    depth = ex.get("depth_chart_order")
    return {
        "production": mean,
        "volume": _share(ex),
        "consistency": -cv if cv is not None else None,
        "durability": dur,
        "prime": prime,
        "role": -float(depth) if depth else None,
        "_market": float(p.market),
    }


def _pool_tables(snap: Any) -> dict[str, Any]:
    """Per-snapshot, cached: each player's value percentile within position and each attribute metric's percentile."""

    cached = getattr(snap, "_grade_tables", None)
    if cached is not None:
        return cached
    by_pos: dict[str, list[str]] = {}
    for pid in snap.pids:
        by_pos.setdefault(snap.players[pid].pos, []).append(pid)
    overall: dict[str, float] = {}
    attrs: dict[str, dict[str, float]] = {}
    for pos, pids in by_pos.items():
        if len(pids) < MIN_POOL:
            continue
        overall.update(_avg_rank_pct({pid: float(snap.players[pid].value) for pid in pids}))
        raw = {pid: _metrics(snap.players[pid]) for pid in pids}
        pct_by_metric: dict[str, dict[str, float]] = {}
        for key in ("production", "volume", "consistency", "durability", "prime", "role"):
            have = {pid: m[key] for pid, m in raw.items() if m[key] is not None}
            if len(have) >= MIN_POOL:
                pct_by_metric[key] = _avg_rank_pct(have)
        mkt = _avg_rank_pct({pid: m["_market"] for pid, m in raw.items()})
        prod = pct_by_metric.get("production", {})
        for pid in pids:
            row: dict[str, float] = {k: v[pid] for k, v in pct_by_metric.items() if pid in v}
            if pid in prod:  # outproducing what the market expects of him
                row["efficiency"] = min(1.0, max(0.0, 0.5 + 0.55 * (prod[pid] - mkt[pid])))
            attrs[pid] = row
    cached = {"overall": overall, "attrs": attrs}
    object.__setattr__(snap, "_grade_tables", cached)
    return cached


def _rookie_sigma(p: Any) -> float | None:
    """Overall noise for a player scouts do not know well yet, else None. Generated rookies carry a scouting
    confidence (``scouting.confidence``); a real incoming rookie gets a middling one."""

    ex = p.extra
    if "scout_seed" in ex:
        from modules.sim import scouting

        conf = scouting.confidence(ex, float(ex.get("years_exp", 0.0)), 0)
    elif ex.get("is_rookie") or (ex.get("years_exp") is not None and float(ex["years_exp"]) < 0.5 and ex.get("games_played", 1) in (0, None)):
        conf = 0.45
    else:
        return None
    return SIGMA_ROOKIE_BASE + SIGMA_ROOKIE_SPAN * (1.0 - conf)


def grade_of(snap: Any, pid: str, season: int = 1) -> dict[str, Any] | None:
    """``{"letter", "range": (lo, hi) | None}`` for a player, or None (pick, thin pool)."""

    p = snap.players.get(pid)
    if p is None:
        return None
    latent = _pool_tables(snap)["overall"].get(pid)
    if latent is None:
        return None
    seed = int(getattr(snap, "seed", 0))
    rs = _rookie_sigma(p)
    sigma = SIGMA_VET if rs is None else rs
    est = latent + sigma * _z(seed, pid, season, "overall")
    out: dict[str, Any] = {"letter": letter_of(est), "range": None, "index": band_of(est)}
    if sigma >= UNCERTAIN_SIGMA:
        lo, hi = letter_of(est - RANGE_K * sigma), letter_of(est + RANGE_K * sigma)
        if lo != hi:
            out["range"] = (lo, hi)
        out["uncertain"] = True
    return out


def attributes_of(snap: Any, pid: str, season: int = 1) -> list[dict[str, Any]]:
    """Attribute grades for the PQV, in display order. An attribute the data cannot support is left out."""

    p = snap.players.get(pid)
    if p is None or p.pos not in ATTRIBUTES:
        return []
    row = _pool_tables(snap)["attrs"].get(pid)
    if not row:
        return []
    seed = int(getattr(snap, "seed", 0))
    rs = _rookie_sigma(p)
    sigma = SIGMA_ATTR if rs is None else max(SIGMA_ATTR, rs)
    out = []
    for key, label in ATTRIBUTES[p.pos]:
        base = row.get(key)
        if base is None:
            continue
        est = base + sigma * _z(seed, pid, season, "attr:" + key)
        entry: dict[str, Any] = {"key": key, "label": label, "grade": letter_of(est)}
        if sigma >= UNCERTAIN_SIGMA + 0.03:
            entry["uncertain"] = True
        out.append(entry)
    return out


def grade_fields(snap: Any, pid: str, season: int = 1) -> dict[str, Any]:
    """The row fields every player carries: ``grade`` (letter or None), ``grade_range`` ([lo, hi] or None),
    ``grade_uncertain``."""

    g = grade_of(snap, pid, season)
    if g is None:
        return {"grade": None, "grade_range": None, "grade_uncertain": False}
    return {"grade": g["letter"], "grade_range": list(g["range"]) if g["range"] else None, "grade_uncertain": bool(g.get("uncertain"))}


def sort_key(snap: Any, pid: str, season: int = 1) -> int:
    """Higher = better shown grade (0 for no grade). Sorting by the displayed grade is allowed (coarse)."""

    g = grade_of(snap, pid, season)
    return 0 if g is None else g["index"] + 1


def legend() -> list[dict[str, str]]:
    """Plain-language meaning of each band for the legend sheet (the clients carry the same copy)."""

    words = {
        "A+": "Elite. A top-of-position difference maker.", "A": "Star. A clear WR1 / RB1 type.", "A-": "Very good starter.",
        "B+": "Strong starter.", "B": "Solid starter.", "B-": "Fringe starter.", "C+": "Flex or bench upside.", "C": "Depth.",
        "C-": "Deep bench.", "D+": "Roster filler.", "D": "Waiver wire.", "F": "Below replacement.",
    }
    return [{"letter": letter, "meaning": words[letter]} for letter in reversed(LETTERS)]


__all__ = ["LETTERS", "CUTS", "ATTRIBUTES", "band_of", "letter_of", "grade_of", "attributes_of", "grade_fields", "sort_key", "legend"]
