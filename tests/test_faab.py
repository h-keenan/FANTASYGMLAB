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


# --- Regression: bids scale with real value, auction context, waiver type ---

import pandas as pd

from modules import faab


def _rb(score, **kwargs):
    return recommend_faab_guidance(score, "RB", budget=100, remaining_budget=100, league_settings=BASE, **kwargs)


def test_scrub_and_real_player_no_longer_share_a_bid():
    # The old 0.5 score floor gave both of these $4–$6.
    scrub = _rb(100)
    real = _rb(2500)
    assert scrub.high_bid <= 1
    assert real.point_bid >= 4
    assert real.point_bid > scrub.point_bid


def test_bid_is_monotonic_in_value():
    bids = [_rb(score).point_bid for score in (100, 500, 1000, 2500, 5000, 8000)]
    assert bids == sorted(bids)
    assert bids[0] < bids[-1]


def test_scrub_shows_a_minimum_bid_range_not_a_bare_zero():
    scrub = _rb(100, min_bid=0)
    assert (scrub.low_bid, scrub.high_bid) == (0, 1)
    assert "minimum bid" in scrub.rationale.lower()
    floored = _rb(100, min_bid=2)
    assert floored.low_bid == 2 and floored.high_bid >= 2


def test_sleeper_waiver_mode_reads_waiver_type():
    assert faab.sleeper_waiver_mode({"settings": {"waiver_type": 2}}) == "faab"
    assert faab.sleeper_waiver_mode({"settings": {"waiver_type": 1}}) == "reverse_standings"
    assert faab.sleeper_waiver_mode({"settings": {"waiver_type": 0}}) == "rolling"
    assert faab.sleeper_waiver_mode({"settings": {}}) == "unknown"
    assert faab.league_uses_faab({"settings": {"waiver_type": 2}}) is True
    assert faab.league_uses_faab({"settings": {"waiver_type": 0}}) is False
    assert faab.league_uses_faab({"settings": {"waiver_type": 1}}) is False
    # Missing field fails open to FAAB so a FAAB league never loses its bids.
    assert faab.league_uses_faab({}) is True


def test_non_faab_league_gets_no_dollar_amounts():
    for mode in ("rolling", "reverse_standings"):
        guidance = recommend_faab_guidance(
            6000, "RB", is_starter=True, remaining_budget=100, league_settings=BASE, waiver_mode=mode
        )
        assert guidance.applicable is False
        assert guidance.point_bid == guidance.low_bid == guidance.high_bid == 0
        assert guidance.pct_low == guidance.pct_high == 0
        assert "$" not in guidance.as_label()
        assert "$" not in format_faab_block_html(guidance)
        assert "FAAB BID" not in format_faab_block_html(guidance)
        assert faab.faab_bid_range_label(guidance) == "Waiver claim"


def test_rolling_waivers_reserve_priority_for_starters():
    starter = recommend_faab_guidance(6000, "RB", is_starter=True, league_settings=BASE, waiver_mode="rolling")
    depth = recommend_faab_guidance(1200, "RB", league_settings=BASE, waiver_mode="rolling")
    assert "worth your waiver priority" in starter.rationale.lower()
    assert "save it" in depth.rationale.lower()


def _competition(needing, richer=0, with_budget=None, rivals=11):
    return faab.FaabCompetition(
        rival_count=rivals,
        rivals_needing=needing,
        rivals_needing_richer=richer,
        rivals_needing_with_budget=needing if with_budget is None else with_budget,
        budgets_known=True,
    )


def test_competition_moves_the_bid_and_is_named():
    alone = _rb(3000, competition=_competition(0))
    contested = _rb(3000, competition=_competition(3, richer=2))
    assert contested.point_bid > alone.point_bid
    assert contested.reasons[0] == "3 teams need a RB and 2 of them have more FAAB than you"
    assert "low bid should win" in alone.reasons[0]
    broke = _rb(3000, competition=_competition(3, richer=0, with_budget=0))
    assert broke.point_bid < _rb(3000, competition=_competition(3, richer=0)).point_bid
    assert "none has FAAB left" in broke.reasons[0]


def test_own_starter_need_is_a_big_boost():
    depth = _rb(3000)
    starter = _rb(3000, is_starter=True)
    starter_need = _rb(3000, is_starter=True, roster_need=True)
    assert depth.point_bid < starter.point_bid < starter_need.point_bid
    assert starter_need.point_bid >= 2 * depth.point_bid - 1
    assert "Fills a starting RB need for you" in starter_need.reasons


def test_catalysts_raise_the_bid_and_name_the_reason():
    breakout = faab.WaiverCatalyst("breakout", "Breakout: 24.0 pts in Week 6 (avg 6.0 before)", 1.20)
    plain = _rb(3000)
    lifted = _rb(3000, catalysts=[breakout])
    assert lifted.point_bid > plain.point_bid
    assert "Breakout: 24.0 pts in Week 6" in lifted.why


def test_wire_depth_relative_value():
    clear_best = _rb(3000, wire_scores=[3000, 1800, 1500])
    crowded = _rb(3000, wire_scores=[3100, 3000, 2950, 2900, 2850])
    assert clear_best.point_bid > crowded.point_bid
    assert "Clear best RB on the wire" in clear_best.reasons
    assert any("similar RBs" in reason for reason in crowded.reasons)


def test_thin_data_widens_the_range_and_says_so():
    thin = recommend_faab_guidance(5000, "RB", league_settings=BASE)
    rich = _rb(5000, wire_scores=[5000, 2000], competition=_competition(2))
    assert thin.data_confidence == "low"
    assert rich.data_confidence == "high"
    thin_width = (thin.high_bid - thin.low_bid) / max(thin.point_bid, 1)
    rich_width = (rich.high_bid - rich.low_bid) / max(rich.point_bid, 1)
    assert thin_width > rich_width


def test_bid_never_exceeds_sixty_percent_of_pool():
    huge = _rb(
        10000,
        is_starter=True,
        roster_need=True,
        competition=_competition(8, richer=5),
        catalysts=[faab.WaiverCatalyst("breakout", "x", 1.2), faab.WaiverCatalyst("trending", "y", 1.25)],
    )
    assert huge.point_bid <= 60


def test_breakout_catalyst_from_weekly_stats():
    stats = {
        "weekly": [
            {"week": 1, "games_played": 1, "fantasy_points_ppr": 5.0},
            {"week": 2, "games_played": 1, "fantasy_points_ppr": 7.0},
            {"week": 3, "games_played": 1, "fantasy_points_ppr": 22.5},
        ]
    }
    hit = faab.breakout_catalyst(stats, current_week=4)
    assert hit is not None and hit.code == "breakout"
    assert "22.5 pts in Week 3" in hit.text and "avg 6.0" in hit.text
    # Old news: the big game wasn't last week.
    assert faab.breakout_catalyst(stats, current_week=6) is None
    steady = {"weekly": [{"week": w, "games_played": 1, "fantasy_points_ppr": 15.0} for w in (1, 2, 3)]}
    assert faab.breakout_catalyst(steady, current_week=4) is None


def test_role_and_trending_catalysts():
    row = pd.Series({"workload_trend": "Rising", "depth_chart_order_delta": 1})
    codes = [c.code for c in faab.role_catalysts(row)]
    assert codes == ["role", "depth_chart"]
    assert faab.trending_catalyst({"count": 4210, "rank": 3}).text == "Trending on Sleeper: 4,210 adds in 24h"
    assert faab.trending_catalyst(None) is None


def test_starting_slots_respect_flex_rules():
    slots = faab.starting_slots_by_position(
        ["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "WRRB_FLEX", "SUPER_FLEX", "IDP_FLEX", "BN"]
    )
    assert slots == {"QB": 2, "RB": 4, "WR": 4, "TE": 2, "K": 0}


def _market_frame():
    rows = []
    # Rival 2: two strong RBs, one on IR (doesn't count).
    rows += [
        {"player_id": "r2a", "position": "RB", "dynasty_score": 6000, "status": "Active", "injury_status": ""},
        {"player_id": "r2b", "position": "RB", "dynasty_score": 5000, "status": "Active", "injury_status": "IR"},
    ]
    # Rival 3: deep at RB.
    rows += [
        {"player_id": f"r3{i}", "position": "RB", "dynasty_score": 5000, "status": "Active", "injury_status": ""}
        for i in range(3)
    ]
    # Me: one RB.
    rows += [{"player_id": "m1", "position": "RB", "dynasty_score": 4000, "status": "Active", "injury_status": ""}]
    rows += [{"player_id": "fa1", "position": "RB", "dynasty_score": 3000, "status": "Active", "injury_status": ""}]
    return pd.DataFrame(rows)


def test_market_from_real_payload_shapes():
    league = {"settings": {"waiver_budget": 100, "waiver_type": 2}, "roster_positions": ["RB", "RB", "BN"]}
    rosters = [
        {"roster_id": 1, "players": ["m1"], "settings": {"waiver_budget_used": 60}},
        {"roster_id": 2, "players": ["r2a", "r2b"], "settings": {"waiver_budget_used": 10}},
        {"roster_id": 3, "players": ["r30", "r31", "r32"], "settings": {"waiver_budget_used": 0}},
    ]
    frame = _market_frame()
    market = faab.build_faab_market(
        league=league,
        rosters=rosters,
        my_roster_id=1,
        valued=frame,
        score_field="dynasty_score",
        free_agents=frame[frame["player_id"] == "fa1"].assign(stale_free_agent=False),
    )
    assert market.my_remaining == 40
    competition = faab.estimate_competition(market, "RB", 3000)
    # Rival 2's IR back doesn't count, so the free agent would start there;
    # rival 3 is two-deep with better backs.
    assert competition.rivals_needing == 1
    assert competition.rivals_needing_richer == 1
    assert faab.market_starter_status(market, "RB", 3000) is True

    guidance = faab.faab_guidance_for_free_agent(
        frame[frame["player_id"] == "fa1"].iloc[0],
        score_field="dynasty_score",
        league_settings=BASE,
        waiver_mode="faab",
        market=market,
        budget_initial=100,
        remaining_budget=40,
        needed_positions=["RB"],
    )
    assert guidance.applicable is True
    assert guidance.high_bid <= 40
    assert guidance.reasons[0] == "1 team needs a RB and 1 of them has more FAAB than you"
    assert "Fills a starting RB need for you" in guidance.reasons
