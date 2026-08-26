from modules.faab import format_faab_block_html, recommend_faab, recommend_faab_guidance


BASE = {
    "league_format": "Dynasty",
    "scoring_format": "PPR",
    "qb_format": "1QB",
    "league_size": 12,
    "starter_count": 9,
    "flex_count": 2,
    "bench_count": 6,
}


def test_recommend_faab_returns_guidance_point_bid():
    bid = recommend_faab(6000, "RB", is_starter=True, budget=100, league_settings=BASE)
    guidance = recommend_faab_guidance(
        6000, "RB", is_starter=True, budget=100, league_settings=BASE
    )
    assert bid == guidance.point_bid
    assert 0 <= bid <= 100


def test_elite_waiver_is_not_a_token_bid():
    elite = recommend_faab(
        9500, "RB", is_starter=True, budget=100, league_settings=BASE
    )
    fringe = recommend_faab(
        250, "WR", is_starter=False, budget=100, league_settings=BASE
    )
    assert elite >= 15
    assert fringe <= 8
    assert elite > fringe


def test_remaining_budget_changes_dollar_amount_and_never_exceeds_pool():
    rich = recommend_faab_guidance(
        9000, "RB", is_starter=True, budget=100, remaining_budget=150, league_settings=BASE
    )
    poor = recommend_faab_guidance(
        9000, "RB", is_starter=True, budget=100, remaining_budget=12, league_settings=BASE
    )
    assert rich.dollars_known is True
    assert rich.high_bid <= 150
    assert poor.high_bid <= 12
    assert poor.point_bid <= 12
    assert rich.point_bid != poor.point_bid


def test_small_bids_still_show_an_integer_range():
    guidance = recommend_faab_guidance(4000, "QB", budget=100, league_settings=BASE)
    assert guidance.point_bid > 0
    assert guidance.pct_high > guidance.pct_low
    guidance = recommend_faab_guidance(5000, "WR", budget=100, league_settings=BASE)
    assert guidance.dollars_known is False
    html = format_faab_block_html(guidance)
    assert "FAAB BID" in html
    assert "remaining FAAB" in html
    assert "12.37" not in html
    compact = format_faab_block_html(guidance, compact=True)
    assert "FAAB BID" in compact
    assert "waiver-faab-block--compact" in compact
    assert "remaining FAAB" not in compact
    assert guidance.rationale not in compact


def test_min_bid_floors_nonzero_claims_and_unavailable_stays_zero():
    tiny = recommend_faab_guidance(
        80, "TE", budget=100, remaining_budget=100, min_bid=1, league_settings=BASE
    )
    assert tiny.point_bid >= 1
    gone = recommend_faab_guidance(
        9000, "RB", is_starter=True, remaining_budget=40, available=False, league_settings=BASE
    )
    assert gone.point_bid == 0
    blocked = recommend_faab_guidance(
        9000, "RB", remaining_budget=1, min_bid=5, league_settings=BASE
    )
    assert blocked.point_bid == 0


def test_inputs_move_the_recommendation():
    base = recommend_faab(4000, "WR", budget=100, league_settings=BASE)
    need = recommend_faab(4000, "WR", budget=100, league_settings=BASE, roster_need=True)
    deep = recommend_faab(
        4000,
        "WR",
        budget=100,
        league_settings={**BASE, "league_size": 16, "bench_count": 10, "taxi_count": 4},
    )
    contend = recommend_faab(
        4000, "WR", is_starter=True, budget=100, league_settings=BASE, team_strategy="contend"
    )
    rebuild = recommend_faab(
        4000, "WR", is_starter=True, budget=100, league_settings=BASE, team_strategy="rebuild"
    )
    late = recommend_faab(
        4000,
        "WR",
        budget=100,
        league_settings={**BASE, "league_format": "Redraft"},
        week=14,
    )
    assert need > base
    assert deep != base
    assert contend != rebuild
    assert late < recommend_faab(
        4000, "WR", budget=100, league_settings={**BASE, "league_format": "Redraft"}
    )
