from modules.rankings import injury_level


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


from modules import runtime_trace


@runtime_trace.traced("waiver_generation", phase="waiver_generation")
def recommend_faab(player_score: int,
                   position: str,
                   is_starter: bool = False,
                   budget: int = 100,
                   league_settings: dict | None = None,
                   status: str = "",
                   injury_status: str = "",
                   injury_need_match: bool = False,
                   team_injury_pressure: int = 0) -> int:
    """
    Very simple deterministic FAAB rule-of-thumb for a 100-FAAB league.
    You can refine these later.
    """
    if player_score <= 0:
        return 0

    # Baseline % by position, loosely inspired by typical FAAB strategy ranges [web:64][web:68]
    base_pct = 0.03  # 3%

    pos = (position or "").upper()
    if pos == "RB":
        base_pct = 0.10  # up to ~10% on impact RBs
    elif pos == "WR":
        base_pct = 0.07
    elif pos == "TE":
        base_pct = 0.05
    elif pos == "QB":
        base_pct = 0.02

    # Boost if you expect them to start
    if is_starter:
        base_pct *= 1.5

    settings = dict(league_settings or {})
    league_format = str(settings.get("league_format") or "Dynasty")
    scoring_format = str(settings.get("scoring_format") or "PPR")
    qb_format = str(settings.get("qb_format") or "1QB")
    te_premium = bool(settings.get("te_premium"))
    league_size = max(8, min(18, _safe_int(settings.get("league_size"), 12) or 12))
    starter_count = max(6, _safe_int(settings.get("starter_count"), 9) or 9)
    flex_count = max(0, _safe_int(settings.get("flex_count"), 2))
    bench_count = max(0, _safe_int(settings.get("bench_count"), 0))
    taxi_count = max(0, _safe_int(settings.get("taxi_count"), 0))
    ir_count = max(0, _safe_int(settings.get("ir_count"), 0))
    reserve_depth = bench_count + taxi_count + ir_count

    if pos == "QB":
        if qb_format == "2QB":
            base_pct *= 2.25
        elif qb_format == "Superflex":
            base_pct *= 1.85

    if scoring_format == "Standard":
        if pos == "RB":
            base_pct *= 1.08
        elif pos in {"WR", "TE"}:
            base_pct *= 0.95
    elif scoring_format == "Half-PPR":
        if pos == "RB":
            base_pct *= 1.03
        elif pos == "WR":
            base_pct *= 0.99
    elif scoring_format == "PPR":
        if pos == "WR":
            base_pct *= 1.03
        elif pos == "TE":
            base_pct *= 1.02

    if te_premium and pos == "TE":
        base_pct *= 1.12

    if league_format == "Redraft" and not is_starter:
        base_pct *= 0.88
    elif league_format == "Dynasty" and not is_starter and pos in {"RB", "WR", "TE"}:
        base_pct *= 1.05

    base_pct *= 1 + max(-3, min(6, league_size - 12)) * 0.04
    lineup_pressure = max(-3, min(6, (starter_count - 9) + (flex_count - 2)))
    if pos in {"RB", "WR", "TE"}:
        base_pct *= 1 + (lineup_pressure * 0.015)
    elif pos == "QB" and qb_format in {"Superflex", "2QB"}:
        base_pct *= 1 + max(0, lineup_pressure) * 0.010
    if reserve_depth >= 12:
        base_pct *= 1.12
    elif reserve_depth >= 8:
        base_pct *= 1.06

    injury_key = injury_level(status, injury_status)
    injury_discount = {
        "healthy": 1.0,
        "minor": 0.88,
        "moderate": 0.66,
        "major": 0.48,
    }.get(injury_key, 1.0)
    if league_format == "Dynasty" and not is_starter and injury_key in {"moderate", "major"}:
        injury_discount *= 1.12
    base_pct *= injury_discount

    if injury_need_match and injury_key == "healthy":
        base_pct *= 1.15
        if _safe_int(team_injury_pressure, 0) >= 2:
            base_pct *= 1.08

    # Modulate by player_score scale (higher score -> more aggressive)
    # Assume scores can range roughly from 0 to 10,000
    score_factor = min(max(player_score / 5000.0, 0.5), 2.0)

    pct = base_pct * score_factor
    faab = int(round(budget * pct))

    # Clamp to a reasonable range
    if faab < 0:
        faab = 0
    if faab > budget:
        faab = budget

    return faab
