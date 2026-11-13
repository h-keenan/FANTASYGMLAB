"""Scouting profiles and development curves for generated rookie classes (dynasty mode).

Pure and deterministic: stdlib + numpy, no real data. Every generated rookie carries a few
numbers in his player record (``extra``: a scouting seed, his class rank and size, his talent z
and a hidden development archetype with its per-year progression ratios). Everything shown to
the user is a pure function of those numbers plus his position, age and name, so the profile a
user sees at the rookie draft, in the rookie's first season and years later is one consistent
story, and a replayed game shows the same prospect.

Two halves:

* ``develop`` / ``expected_curve``: the hidden development archetype (early bloomer, steady,
  late bloomer, star trajectory, bust risk). The step ratios stored in ``extra`` (``dev_r1`` ..
  ``dev_r4``) are what ``game_dynasty.season_snapshot`` multiplies a rookie's projection by each
  offseason (in place of the plain age curve), so the curve shown to the user and the curve the
  sim plays are the same numbers. What the user sees is a scouting estimate that starts close to
  the plain age curve and converges to the truth as confidence grows (years in the league, games).
* ``build_profile``: the generated scouting report (draft capital proxy, measurables, college
  production, analytics percentiles vs the position class, scouting tags, a blurb). The payload
  is shaped so real college stats can slot in unchanged: ``college.columns`` names the stats and
  ``college.seasons[].stats`` holds the values; a real feed only has to fill those and set
  ``source`` to something other than ``"generated"``.

Everything here is a simulation. The UI labels it "Generated prospect".
"""

from __future__ import annotations

import math
import statistics
from typing import Any, Mapping, Sequence

import numpy as np

from modules.sim import aging

SCOUT_VERSION = 1
CURVE_YEARS = 5

ARCHETYPES = ("early", "steady", "late", "star", "bust")
ARCHETYPE_LABELS = {
    "early": "Early bloomer",
    "steady": "Steady grower",
    "late": "Late bloomer",
    "star": "Star trajectory",
    "bust": "Bust risk",
}
# Multiplier on the plain age curve for offseason k = 1..4 (rookie -> year 2, ... year 4 -> year 5).
# Weighted by the class mix the average is about 1.0, so the calibrated age curve still describes the
# population; the archetype only decides who beats it and who falls behind it, and when.
ARCHETYPE_REL = {
    "early": (1.06, 0.97, 0.95, 0.96),
    "steady": (1.00, 1.01, 1.01, 1.00),
    "late": (0.95, 1.06, 1.09, 1.05),
    "star": (1.15, 1.10, 1.05, 1.02),
    "bust": (0.90, 0.90, 0.93, 0.95),
}
# The tag a scout would put on each archetype (EA-style, deliberately vague).
ARCHETYPE_TAG = {"early": "Polished", "steady": "Reliable floor", "late": "Raw", "star": "High upside", "bust": "Boom/bust"}
# When scouts are wrong they mistake a prospect for a neighbour on this ring.
_NEIGHBOURS = {"early": ("steady", "star"), "steady": ("early", "late"), "late": ("steady", "bust"), "star": ("early", "steady"), "bust": ("late", "steady")}
REVEAL_CONFIDENCE = 0.75
AGE_GROWTH_SCALE = {21: 1.0, 22: 1.0, 23: 1.0, 24: 1.0, 25: 1.0}  # age is already inside the age curve

_N = statistics.NormalDist()


def _clamp(x: float, lo: float, hi: float) -> float:
    return lo if x < lo else hi if x > hi else x


def _phi(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _pct(z: float) -> int:
    """Percentile (1-99) of a z-score against the position class."""

    return int(_clamp(round(_phi(z) * 100.0), 1, 99))


def _gen(seed: int) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(entropy=int(seed))))


# ------------------------------------------------------------------ talent and archetype


def talent_z(mean: float, ref12: float) -> float:
    """Talent as a z-score against the position class, from the rookie's projection relative to the
    position's 12th-best veteran (class rank 1 ~ +1.2, a 0.3 ratio ~ 0, the deep tail ~ -1.5)."""

    ratio = max(0.02, float(mean) / max(0.1, float(ref12)))
    return _clamp((math.log(ratio) - math.log(0.30)) / 0.9, -2.2, 2.2)


def archetype_weights(z: float) -> dict[str, float]:
    t = _phi(z)  # 0 (deep tail) .. 1 (top of the class)
    w = {
        "star": 0.03 + 0.20 * t * t,
        "early": 0.20,
        "steady": 0.36 - 0.08 * t,
        "late": 0.16 + 0.06 * (1.0 - t),
        "bust": 0.05 + 0.26 * (1.0 - t) ** 2,
    }
    total = sum(w.values())
    return {k: v / total for k, v in w.items()}


def draw_archetype(z: float, u: float) -> str:
    acc = 0.0
    weights = archetype_weights(z)
    for name in ARCHETYPES:
        acc += weights[name]
        if u <= acc:
            return name
    return ARCHETYPES[-1]


def dev_steps(pos: str, age: float, arch: str, jitters: Sequence[float]) -> tuple[float, float, float, float]:
    """The four offseason ratios a rookie of ``age`` (during his rookie season) follows: the plain age curve
    times his archetype, with a little per-player wobble."""

    rel = ARCHETYPE_REL[arch]
    return tuple(  # type: ignore[return-value]
        round(aging.age_mult(pos, age + k) * rel[k] * math.exp(0.025 * float(jitters[k])), 4) for k in range(4)
    )


def rookie_dev_fields(pos: str, age: float, z: float, seed: int, class_rank: int, class_size: int) -> dict[str, float]:
    """The numeric fields stored in a generated rookie's ``extra`` (version-gated by the caller)."""

    g = _gen(seed)
    u = float(g.random())
    jit = [float(g.standard_normal()) for _ in range(4)]
    arch = draw_archetype(z, u)
    r1, r2, r3, r4 = dev_steps(pos, age, arch, jit)
    return {
        "scout_seed": float(seed), "class_rank": float(class_rank), "class_size": float(class_size), "talent_z": round(z, 4),
        "dev_arch": float(ARCHETYPES.index(arch)), "dev_r1": r1, "dev_r2": r2, "dev_r3": r3, "dev_r4": r4,
    }


def has_curve(extra: Mapping[str, float]) -> bool:
    return "dev_arch" in extra and "dev_r1" in extra


def archetype_of(extra: Mapping[str, float]) -> str:
    return ARCHETYPES[int(extra["dev_arch"]) % len(ARCHETYPES)]


def step_ratio(extra: Mapping[str, float], years_exp: float) -> float | None:
    """The stored ratio for the offseason after a player's ``years_exp``-th season (0 = after his rookie
    season), or None when the curve is over (year 5 on: the plain age curve takes over) or he has none."""

    if not has_curve(extra):
        return None
    k = int(years_exp)
    if k < 0 or k >= 4:
        return None
    return float(extra[f"dev_r{k + 1}"])


# ------------------------------------------------------------------ the displayed curve


def confidence(extra: Mapping[str, float], years_exp: float = 0.0, games: int = 0) -> float:
    """How well scouts know this player: a per-player starting clarity that grows with years in the league and games played."""

    seed = int(extra.get("scout_seed", 0))
    c0 = 0.30 + 0.25 * float(_gen(seed ^ 0x5CA1AB1E).random())
    return round(min(0.98, c0 + 0.20 * float(years_exp) + 0.12 * min(max(games, 0), 17) / 17.0), 3)


def confidence_label(c: float) -> str:
    return "High" if c >= 0.70 else "Medium" if c >= 0.40 else "Low"


def expected_curve(pos: str, age: float, mean: float, extra: Mapping[str, float], *, years_exp: float = 0.0, games: int = 0) -> dict[str, Any]:
    """The expected development curve from the player's CURRENT per-game mean: year ``years_exp + 1`` (now) through year 5.

    ``mean`` is the sim's own projection, so the first point is exactly what the sim plays this season. The
    steps beyond it blend the plain age curve with the hidden archetype curve by ``confidence``; at full
    confidence they are the stored ratios the offseason multiplies by (modulo the zero-mean progression noise)."""

    c = confidence(extra, years_exp, games)
    base_year = int(years_exp) + 1
    points: list[dict[str, Any]] = []
    level = float(mean)
    var = 0.0
    for year in range(base_year, CURVE_YEARS + 1):
        step = year - base_year  # offseasons since now
        if step > 0:
            k = year - 2  # offseason index (0-based from the rookie season)
            plain = aging.age_mult(pos, age + step - 1)
            true = step_ratio(extra, k) or plain
            ratio = math.exp(math.log(plain) + c * (math.log(true) - math.log(plain)))
            level *= ratio
            var += 0.10 ** 2 + ((1.0 - c) * 0.07) ** 2  # progression noise plus scouting doubt per offseason
        sd = math.sqrt(var)
        points.append({
            "year": year, "mean": round(level, 1), "lo": round(max(0.0, level * math.exp(-1.28 * sd)), 1),
            "hi": round(level * math.exp(1.28 * sd), 1),
        })
    arch = archetype_of(extra) if has_curve(extra) else None
    revealed = arch is not None and c >= REVEAL_CONFIDENCE
    return {
        "base_year": base_year, "points": points, "confidence": c, "confidence_label": confidence_label(c),
        "archetype": arch if revealed else None, "archetype_label": ARCHETYPE_LABELS[arch] if revealed and arch else None,
        "revealed": revealed,
        "note": "Scouting estimate. The true curve is revealed over time." if not revealed else "Scouts have a firm read on this player.",
    }


def hint_tag(extra: Mapping[str, float], c: float) -> tuple[str, float]:
    """The vague development tag scouts attach: the true archetype's tag with probability that grows with confidence, else a neighbour's."""

    seed = int(extra.get("scout_seed", 0))
    g = _gen(seed ^ 0x7A6)
    u, pick = float(g.random()), int(g.integers(0, 2))
    arch = archetype_of(extra)
    p_true = 0.50 + 0.50 * c
    shown = arch if u < p_true else _NEIGHBOURS[arch][pick]
    return ARCHETYPE_TAG[shown], round(_clamp(0.30 + 0.55 * c, 0.2, 0.95), 2)


# ------------------------------------------------------------------ scouting report

_POS_WORD = {"QB": "quarterback", "RB": "running back", "WR": "wide receiver", "TE": "tight end"}
# (mean, sd): height in, weight lb, 40-yard dash s
_MEAS = {
    "QB": ((74.8, 1.5), (222.0, 11.0), (4.82, 0.17)),
    "RB": ((70.6, 1.6), (212.0, 11.0), (4.53, 0.10)),
    "WR": ((72.6, 2.0), (200.0, 14.0), (4.50, 0.11)),
    "TE": ((76.5, 1.4), (249.0, 11.0), (4.73, 0.13)),
}
_SCHOOL_A = ("North", "South", "East", "West", "Central", "Lakeshore", "Mountain", "Prairie", "Coastal", "Valley", "Summit", "Harbor", "Pine", "Red River", "Iron")
_SCHOOL_B = ("State", "Tech", "A&M", "University", "College", "Poly")
_MASCOT = ("Hawks", "Rams", "Bears", "Wolves", "Pioneers", "Comets", "Falcons", "Miners")


def _ft_in(inches: float) -> str:
    total = int(round(inches))
    return f"{total // 12}'{total % 12}\""


def speed_score(weight: float, forty: float) -> float:
    return weight * 200.0 / (forty ** 4)


def _draft_slot(class_rank: int) -> tuple[int, int]:
    """A rookie's class rank as a rough NFL draft slot: (round, overall pick). A proxy, not a real draft."""

    pick = int(_clamp(round(2 + (class_rank - 1) * 2.4), 1, 250))
    return min(7, (pick - 1) // 32 + 1), pick


def _stat_pack(pos: str, g: np.random.Generator, zp: float) -> tuple[dict[str, float], dict[str, float], dict[str, Any]]:
    """Final-season stat line, the z-scores behind it, and its tile metadata. All draws happen in a fixed order."""

    e = [float(g.standard_normal()) for _ in range(14)]

    def z(i: int, w: float) -> float:
        return w * zp + math.sqrt(max(0.0, 1.0 - w * w)) * e[i]

    s: dict[str, float] = {}
    zs: dict[str, float] = {}
    if pos == "QB":
        zs.update(comp=z(0, 0.6), ypa=z(1, 0.75), td=z(2, 0.55), ints=z(3, -0.35), rush=z(4, 0.1), expl=z(5, 0.6), dom=z(6, 0.55))
        att = int(_clamp(round(360 + 70 * z(7, 0.1)), 190, 560))
        comp_pct = _clamp(64.0 + 4.2 * zs["comp"], 52.0, 78.0)
        ypa = _clamp(8.3 + 1.1 * zs["ypa"], 6.0, 11.2)
        s.update(
            pass_att=att, pass_cmp=int(round(att * comp_pct / 100.0)), comp_pct=round(comp_pct, 1), ypa=round(ypa, 1),
            pass_yd=int(round(att * ypa)), pass_td=int(_clamp(round(att * (0.058 + 0.014 * zs["td"])), 6, 55)),
            pass_int=int(_clamp(round(att * (0.021 - 0.007 * zs["ints"])), 2, 20)),
            rush_att=int(_clamp(round(70 + 35 * zs["rush"]), 10, 190)),
        )
        s["rush_yd"] = int(round(s["rush_att"] * _clamp(4.0 + 0.7 * zs["rush"], 2.0, 7.0)))
        s["rush_td"] = int(_clamp(round(s["rush_att"] * 0.06), 0, 16))
    elif pos == "RB":
        zs.update(att=z(0, 0.55), ypc=z(1, 0.7), td=z(2, 0.5), rec=z(3, 0.35), ypr=z(4, 0.3), yprr=z(5, 0.55), share=z(6, 0.4), expl=z(7, 0.65), dom=z(8, 0.65))
        att = int(_clamp(round(185 + 55 * zs["att"]), 80, 340))
        ypc = _clamp(5.7 + 0.75 * zs["ypc"], 3.8, 8.0)
        rec = int(_clamp(round(24 + 13 * zs["rec"]), 4, 75))
        s.update(
            yprr=round(_clamp(1.5 + 0.45 * zs["yprr"], 0.5, 3.0), 2), share=round(_clamp(9.0 + 3.5 * zs["share"], 2.0, 20.0), 1),
            rush_att=att, ypc=round(ypc, 1), rush_yd=int(round(att * ypc)), rush_td=int(_clamp(round(att * (0.050 + 0.012 * zs["td"])), 1, 28)),
            rec=rec, rec_yd=int(round(rec * _clamp(7.8 + 1.6 * zs["ypr"], 4.5, 13.0))), rec_td=int(_clamp(round(rec * 0.05), 0, 7)),
        )
    elif pos == "WR":
        zs.update(rec=z(0, 0.65), ypr=z(1, 0.55), td=z(2, 0.55), yprr=z(3, 0.8), share=z(4, 0.7), expl=z(5, 0.6), dom=z(6, 0.8), adot=z(7, 0.2))
        rec = int(_clamp(round(58 + 20 * zs["rec"]), 22, 130))
        ypr = _clamp(14.4 + 2.0 * zs["ypr"], 9.5, 21.0)
        s.update(
            yprr=round(_clamp(2.3 + 0.55 * zs["yprr"], 0.8, 4.5), 2), share=round(_clamp(24.0 + 7.0 * zs["share"], 6.0, 42.0), 1),
            rec=rec, ypr=round(ypr, 1), rec_yd=int(round(rec * ypr)), rec_td=int(_clamp(round(rec * (0.115 + 0.03 * zs["td"])), 1, 22)),
        )
    else:  # TE
        zs.update(rec=z(0, 0.65), ypr=z(1, 0.5), td=z(2, 0.5), yprr=z(3, 0.8), share=z(4, 0.7), expl=z(5, 0.55), dom=z(6, 0.75), adot=z(7, 0.1))
        rec = int(_clamp(round(38 + 14 * zs["rec"]), 10, 90))
        ypr = _clamp(12.6 + 1.7 * zs["ypr"], 8.0, 18.0)
        s.update(
            yprr=round(_clamp(1.7 + 0.5 * zs["yprr"], 0.5, 3.4), 2), share=round(_clamp(16.0 + 5.0 * zs["share"], 4.0, 30.0), 1),
            rec=rec, ypr=round(ypr, 1), rec_yd=int(round(rec * ypr)), rec_td=int(_clamp(round(rec * (0.10 + 0.03 * zs["td"])), 0, 14)),
        )
    return s, zs, {}


_COLLEGE_COLUMNS = {
    "QB": (("comp_pct", "Comp %", "pct1"), ("ypa", "Yds/att", "num1"), ("pass_yd", "Pass yds", "int"), ("pass_td", "Pass TD", "int"), ("pass_int", "INT", "int"), ("rush_yd", "Rush yds", "int")),
    "RB": (("rush_att", "Rush att", "int"), ("rush_yd", "Rush yds", "int"), ("ypc", "Yds/carry", "num1"), ("rush_td", "Rush TD", "int"), ("rec", "Rec", "int"), ("rec_yd", "Rec yds", "int")),
    "WR": (("rec", "Rec", "int"), ("rec_yd", "Rec yds", "int"), ("ypr", "Yds/rec", "num1"), ("rec_td", "Rec TD", "int"), ("yprr", "Yds/route", "num2"), ("share", "Target share", "pct1")),
    "TE": (("rec", "Rec", "int"), ("rec_yd", "Rec yds", "int"), ("ypr", "Yds/rec", "num1"), ("rec_td", "Rec TD", "int"), ("yprr", "Yds/route", "num2"), ("share", "Target share", "pct1")),
}
_VOLUME_KEYS = {"pass_att", "pass_cmp", "pass_yd", "pass_td", "pass_int", "rush_att", "rush_yd", "rush_td", "rec", "rec_yd", "rec_td"}
# analytics: key, label, mean, sd, higher_is_better, fmt  (value = mean + sd * z; percentile vs the position class)
_ANALYTICS = {
    "QB": (("adj_ypa", "Adj. yards/att", 8.2, 1.2, True, "num1"), ("expl", "Explosive pass rate", 11.0, 3.0, True, "pct1"),
           ("rush", "Dual-threat (rush yds/g)", 22.0, 14.0, True, "int"), ("breakout", "Breakout age", 20.6, 1.0, False, "age"), ("athletic", "Athletic score", 6.4, 2.0, True, "num1")),
    "RB": (("dominator", "Dominator rating", 24.0, 8.0, True, "pct1"), ("yprr", "Yards/route run", 1.5, 0.45, True, "num2"), ("share", "Target share", 9.0, 3.5, True, "pct1"),
           ("expl", "Explosive run rate", 13.0, 3.5, True, "pct1"), ("breakout", "Breakout age", 20.4, 0.9, False, "age"), ("athletic", "Athletic score", 6.6, 2.0, True, "num1")),
    "WR": (("dominator", "Dominator rating", 28.0, 9.0, True, "pct1"), ("yprr", "Yards/route run", 2.3, 0.55, True, "num2"), ("share", "Target share", 24.0, 7.0, True, "pct1"),
           ("expl", "Explosive play rate", 14.0, 4.0, True, "pct1"), ("breakout", "Breakout age", 20.0, 1.0, False, "age"), ("athletic", "Athletic score", 6.5, 2.0, True, "num1")),
    "TE": (("dominator", "Dominator rating", 18.0, 7.0, True, "pct1"), ("yprr", "Yards/route run", 1.7, 0.5, True, "num2"), ("share", "Target share", 16.0, 5.0, True, "pct1"),
           ("expl", "Explosive play rate", 11.0, 3.5, True, "pct1"), ("breakout", "Breakout age", 20.8, 1.0, False, "age"), ("athletic", "Athletic score", 6.4, 2.0, True, "num1")),
}


def _fmt(value: float, fmt: str) -> str:
    if fmt == "int":
        return f"{int(round(value)):,}"
    if fmt == "num1":
        return f"{value:.1f}"
    if fmt == "num2":
        return f"{value:.2f}"
    if fmt == "pct1":
        return f"{value:.1f}%"
    if fmt == "age":
        return f"{value:.1f}"
    return str(value)


def _school(g: np.random.Generator) -> str:
    return f"{_SCHOOL_A[int(g.integers(0, len(_SCHOOL_A)))]} {_SCHOOL_B[int(g.integers(0, len(_SCHOOL_B)))]}"


def build_profile(
    *, pos: str, age: float, name: str, extra: Mapping[str, float], mean: float, draft_year: int | None = None,
    years_exp: float = 0.0, games: int = 0,
) -> dict[str, Any] | None:
    """The full generated scouting report for one rookie (any position QB/RB/WR/TE), or None for a position with no profile."""

    if pos not in _MEAS or "scout_seed" not in extra:
        return None
    seed = int(extra["scout_seed"])
    zt = float(extra.get("talent_z", 0.0))
    rank, size = int(extra.get("class_rank", 1)), int(extra.get("class_size", 60))
    g = _gen(seed)
    # fixed draw order (never conditional) keeps every value stable
    school = _school(g)
    zp = 0.78 * zt + 0.63 * float(g.standard_normal())
    z_ath = 0.35 * zt + 0.94 * float(g.standard_normal())
    z_h, z_w = float(g.standard_normal()), float(g.standard_normal())
    z_break = 0.7 * zp + 0.71 * float(g.standard_normal())
    injury_u, games_u = float(g.random()), float(g.random())
    stats, zs, _ = _stat_pack(pos, g, zp)
    zs["athletic"], zs["breakout"] = z_ath, z_break
    zs.setdefault("adj_ypa", zs.get("ypa", 0.0))
    zs.setdefault("rush", zs.get("rush", 0.0))
    variant = int(g.integers(0, 3))

    # ---- measurables
    (hm, hs), (wm, ws), (fm, fs) = _MEAS[pos]
    height = round(hm + hs * z_h)
    weight = round(wm + ws * (0.7 * z_w + 0.3 * z_h))
    z_wt = (weight - wm) / ws
    forty = round(_clamp(fm - fs * 0.85 * z_ath + fs * 0.30 * z_wt, fm - 3.0 * fs, fm + 3.0 * fs), 2)
    z_forty = (fm - forty) / fs  # faster = higher
    spd = speed_score(weight, forty)
    spd_mean = speed_score(wm, fm)
    z_spd = (spd - spd_mean) / (spd_mean * 0.075)
    ras = round(_clamp(6.5 + 2.0 * z_ath, 0.5, 9.9), 1)
    measurables = [
        {"key": "height", "label": "Height", "display": _ft_in(height), "percentile": _pct((height - hm) / hs)},
        {"key": "weight", "label": "Weight", "display": f"{int(weight)} lb", "percentile": _pct(z_wt)},
        {"key": "forty", "label": "40-yard dash", "display": f"{forty:.2f}s", "percentile": _pct(z_forty)},
        {"key": "speed_score", "label": "Speed score", "display": f"{spd:.0f}", "percentile": _pct(z_spd)},
        {"key": "athletic", "label": "Athletic score", "display": f"{ras:.1f}", "percentile": _pct((ras - 6.5) / 2.0)},
    ]

    # ---- college
    n_seasons = int(_clamp(round(age) - 19, 2, 4))
    final_year = (int(draft_year) - 1) if draft_year else 2026
    classes = ("FR", "SO", "JR", "SR")[4 - n_seasons:]
    games_final = 13 if games_u > 0.15 else int(_clamp(round(9 + 3 * games_u / 0.15), 8, 12))
    seasons = []
    for i in range(n_seasons):
        frac = (1.0, 0.75, 0.5, 0.35)[n_seasons - 1 - i]  # volume stats ramp up to the final season; rates stay
        line = {k: (round(v * frac) if k in _VOLUME_KEYS else v) for k, v in stats.items()}
        seasons.append({"season": final_year - (n_seasons - 1 - i), "team": school, "class": classes[i], "games": games_final if i == n_seasons - 1 else 12, "stats": line})
    career = {k: int(sum(s["stats"][k] for s in seasons if k in s["stats"])) for k in _VOLUME_KEYS if k in stats}
    cols = _COLLEGE_COLUMNS[pos]
    # a tile's percentile comes from the z behind it
    z_for = {"comp_pct": zs.get("comp"), "ypa": zs.get("ypa"), "pass_yd": zp * 0.7, "pass_td": zs.get("td"), "pass_int": zs.get("ints"), "rush_yd": zs.get("rush", zp * 0.5) if pos == "QB" else zs.get("att", zp) * 0.6 + zs.get("ypc", zp) * 0.4,
             "rush_att": zs.get("att"), "ypc": zs.get("ypc"), "rush_td": zs.get("td"), "rec": zs.get("rec"), "rec_yd": 0.6 * zs.get("rec", 0.0) + 0.4 * zs.get("ypr", 0.0), "ypr": zs.get("ypr"),
             "rec_td": zs.get("td"), "yprr": zs.get("yprr"), "share": zs.get("share")}
    final_pcts = {k: _pct(z_for[k]) for k, _l, _f in cols if z_for.get(k) is not None}
    college = {
        "columns": [{"key": k, "label": lab, "fmt": f} for k, lab, f in cols],
        "seasons": seasons, "career": career, "percentiles": final_pcts,
        "final": {"season": seasons[-1]["season"], "team": school, "games": seasons[-1]["games"], "stats": {k: stats[k] for k, _l, _f in cols if k in stats}},
    }

    # ---- analytics vs the position class
    analytics = []
    for key, label, m, s, hib, fmt in _ANALYTICS[pos]:
        zk = {"adj_ypa": zs.get("ypa", 0.0), "dominator": zs.get("dom", zp), "yprr": zs.get("yprr", zp), "share": zs.get("share", zp), "expl": zs.get("expl", zp), "rush": zs.get("rush", 0.0),
              "breakout": z_break, "athletic": z_ath}[key]
        value = m + s * zk if hib else m - s * zk
        if key == "athletic":
            value = ras
        elif key == "breakout":
            value = _clamp(value, 18.5, 23.5)
        elif fmt in ("pct1", "num1", "num2", "int"):
            value = max(0.0, value)
        analytics.append({"key": key, "label": label, "value": round(value, 2), "display": _fmt(value, fmt), "percentile": _pct(zk), "higher_is_better": hib})
    # keep the college tiles and the analytics bars telling one story
    for a in analytics:
        if a["key"] == "yprr" and "yprr" in stats:
            a["value"], a["display"] = stats["yprr"], _fmt(stats["yprr"], "num2")
        if a["key"] == "share" and "share" in stats:
            a["value"], a["display"] = stats["share"], _fmt(stats["share"], "pct1")

    # ---- draft capital proxy
    rnd, pick = _draft_slot(rank)
    draft = {"round": rnd, "pick": pick, "class_rank": rank, "class_size": size, "basis": "class-rank proxy (generated class, no real draft)"}

    # ---- development: tags, curve
    curve = expected_curve(pos, age, mean, extra, years_exp=years_exp, games=games)
    c = curve["confidence"]
    tag, tag_conf = hint_tag(extra, c) if has_curve(extra) else (None, 0.0)
    tags: list[dict[str, Any]] = []
    if tag:
        tags.append({"tag": tag, "confidence": tag_conf})
    if _pct(z_ath) >= 90:
        tags.append({"tag": "Elite athlete", "confidence": 0.9})
    if injury_u < 0.10:
        tags.append({"tag": "Injury history", "confidence": 0.6})
    if _pct(zp) >= 92:
        tags.append({"tag": "Production machine", "confidence": 0.8})

    return {
        "version": SCOUT_VERSION, "source": "generated", "label": "Generated prospect", "school": school, "class_year": draft_year,
        "position_word": _POS_WORD[pos], "draft": draft, "measurables": measurables, "college": college, "analytics": analytics,
        "tags": tags, "blurb": _blurb(name, pos, height, weight, school, rnd, college, analytics, forty, z_ath, tag, variant),
        "development": curve,
    }


def _blurb(name: str, pos: str, height: float, weight: float, school: str, rnd: int, college: dict[str, Any], analytics: Sequence[Mapping[str, Any]], forty: float, z_ath: float, hint: str | None, variant: int) -> str:
    last = name.split()[-1] if name else "He"
    st = college["final"]["stats"]
    rnd_text = {1: "a first-round", 2: "a second-round", 3: "a third-round"}.get(rnd, f"a round {rnd}" if rnd < 7 else "a late-round")
    a = {x["key"]: x for x in analytics}
    opening = (
        f"{name} is a {_ft_in(height)}, {int(weight)} lb {_POS_WORD[pos]} from {school}, projected as {rnd_text} pick.",
        f"A {_ft_in(height)}, {int(weight)} lb {_POS_WORD[pos]} out of {school}, {last} profiles as {rnd_text} talent.",
        f"{name} ({school}) is a {int(weight)} lb {_POS_WORD[pos]} who stands {_ft_in(height)} and projects as {rnd_text} pick.",
    )[variant % 3]
    if pos == "QB":
        prod = f"Last season: {st['comp_pct']:.1f}% completions, {st['ypa']:.1f} yards per attempt, {st['pass_td']} TD to {st['pass_int']} INT, plus {st['rush_yd']} rushing yards."
    elif pos == "RB":
        prod = f"Last season: {st['rush_yd']:,} rushing yards at {st['ypc']:.1f} per carry with {st['rush_td']} TD, and {st['rec']} catches for {st['rec_yd']} yards."
    else:
        prod = f"Last season: {st['rec']} catches for {st['rec_yd']:,} yards and {st['rec_td']} TD ({st['yprr']:.2f} yards per route run)."
    br = a.get("breakout")
    dom = a.get("dominator")
    if dom and dom["percentile"] >= 80:
        trait = f"His {dom['display']} dominator rating ranks in the {dom['percentile']}th percentile of the class."
    elif br and br["percentile"] >= 75:
        trait = f"He broke out at {br['display']}, earlier than most of the class."
    elif br and br["percentile"] <= 30:
        trait = f"He broke out late ({br['display']}), which tempers the numbers."
    else:
        trait = "His production is solid without a standout trait."
    ath = f"A {forty:.2f} forty and {'elite' if z_ath > 1.3 else 'plus' if z_ath > 0.4 else 'average' if z_ath > -0.6 else 'below-average'} athletic testing."
    dev = {
        "High upside": "Scouts see a high ceiling.",
        "Polished": "Scouts call him polished and ready to contribute early.",
        "Reliable floor": "Scouts expect steady, dependable growth.",
        "Raw": "Scouts call him raw: the tools are there, the polish is not.",
        "Boom/bust": "Scouts split on him: big upside, real bust risk.",
    }.get(hint or "", "")
    return " ".join(x for x in (opening, prod, trait, ath, dev) if x)


__all__ = [
    "ARCHETYPES", "ARCHETYPE_LABELS", "SCOUT_VERSION", "build_profile", "confidence", "dev_steps", "draw_archetype", "expected_curve",
    "has_curve", "archetype_of", "rookie_dev_fields", "step_ratio", "talent_z", "archetype_weights", "speed_score",
]
