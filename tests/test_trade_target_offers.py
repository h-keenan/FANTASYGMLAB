"""Build an offer for a player on another team (modules.trade_target_offers).

The engine under test composes the Hub's target-player search, the Analyzer's
own verdict and the Analyzer's sweetener ranking; these tests pin the contract
the owner asked for: fair packages for both sides, superstar and cheap targets,
picks priced like everywhere else, untouchables never sent, and no stripping of
a thin position.
"""

from __future__ import annotations

import pandas as pd
import pytest
from freezegun import freeze_time

from modules import nfl_schedule, trade_ideas, trade_target_offers as tto, trade_value_bands
from modules.trade_hub_engine import apply_strategy_age_curve, strategy_adjusted_pick_score_multiplier
from scripts.profile_trade_hub import FixtureSpec, build_fixture

SCORE = "value_score"

# The fixture league is a 2026 dynasty league in week 8 (see _league). Whether
# a fair package exists for a given target depends on pick values and pick
# actionability, which read the real calendar (trade_ideas: as_of_year, the
# Analyzer's season window, bye weeks). Pin the clock to that league's week 8
# so the outcome is a property of the fixture, not of the day CI runs.
FIXTURE_NOW = "2026-10-28T12:00:00"


@pytest.fixture(scope="module", autouse=True)
def _pinned_world():
    """Frozen clock, no live NFL schedule, no memos carried over from other tests.

    The fixture teams (T01..) are fictional, so an empty schedule is the true
    answer for them; leaving the real one would make the module fetch
    data/nfl_games.csv over the network. Player values come from the fixture
    frame itself; nothing here reads data/players.db.
    """
    trade_ideas.clear_team_shape_memos()
    nfl_schedule.clear_load_games_cache()
    with freeze_time(FIXTURE_NOW), pytest.MonkeyPatch.context() as mp:
        mp.setattr(nfl_schedule, "load_games", lambda *a, **k: pd.DataFrame())
        yield
    trade_ideas.clear_team_shape_memos()
    nfl_schedule.clear_load_games_cache()


def _league(strategy="contender"):
    fx = build_fixture(FixtureSpec("target-offers", 8, 22, "1QB", strategy=strategy))
    fx["settings"] = dict(fx["settings"], current_week=8, max_roster_size=26, bench_count=17)
    return fx


def _offers(fx, target, *, strategy="contender", untouchables=(), players=None):
    pool = apply_strategy_age_curve(players if players is not None else fx["players"], strategy, SCORE)
    return tto.build_target_offers(
        df_players=pool,
        league_id="fixture-league",
        df_summary=fx["summary"],
        my_roster_id=1,
        target_player_id=target,
        rosters=fx["rosters"],
        untouchable_names=list(untouchables),
        league_settings=fx["settings"],
        score_field=SCORE,
        pick_score_multiplier=strategy_adjusted_pick_score_multiplier(1.0, strategy),
        team_strategy=strategy,
        adapter=fx["adapter"],
    )


def _mine(fx):
    return {str(p) for p in fx["rosters"][0]["players"]}


@pytest.fixture(scope="module")
def league():
    return _league()


def test_fair_packages_are_fair_for_both_sides(league):
    found = 0
    for target in ("F02-06", "F02-12", "F05-09", "F05-16", "F05-19"):
        result = _offers(league, target)
        # A target may honestly have no fair package, but a package that is
        # shown is never unfair.
        assert result["status"] in {"found", "none"}, result
        found += 1 if result["offers"] else 0
        _assert_fair(league, target, result["offers"])
    assert found >= 3


def _assert_fair(league, target, offers):
    assert len(offers) <= tto.MAX_OFFERS
    mine = _mine(league)
    for offer in offers:
        assert any(a["id"] == target for a in offer["receive"])
        # Only the caller's own players are ever sent.
        assert all(a["id"] in mine for a in offer["send"] if a["kind"] == "player")
        # Fair to the caller (the Analyzer says so) ...
        assert offer["verdict"] in {"FAIR", "ACCEPT"}
        assert offer["value_delta"] >= -trade_value_bands.EDGE
        # ... and not a skim of the other manager.
        assert offer["value_delta"] <= tto.PARTNER_MAX_USER_VALUE_GAIN
        assert offer["acceptance"]["label"] in {tto.ACCEPT_LIKELY, tto.ACCEPT_POSSIBLE, tto.ACCEPT_LONG_SHOT}
        assert offer["why"] and all(isinstance(line, str) and line for line in offer["why"])
    # No two identical packages.
    sigs = {(tuple(sorted(a["id"] for a in o["send"])), tuple(sorted(a["id"] for a in o["receive"]))) for o in offers}
    assert len(sigs) == len(offers)


def test_superstar_target_is_never_a_one_sided_junk_offer(league):
    result = _offers(league, "F02-00")  # the partner's best player
    for offer in result["offers"]:
        # Whatever is offered has to be real value, not filler for a cornerstone.
        assert offer["send_value"] >= 0.5 * offer["receive_value"]
        assert offer["value_delta"] <= tto.PARTNER_MAX_USER_VALUE_GAIN
    if result["status"] != "found":
        assert result["offers"] == []
        assert result["headline"]


def test_cheap_target_does_not_make_the_user_overpay(league):
    result = _offers(league, "F02-21")
    assert result["status"] == "found"
    target_value = result["target"]["value"]
    for offer in result["offers"]:
        # Either the send side is close to his price, or the other side adds
        # something back so the user is not paying a starter's price.
        returned_extra = len(offer["receive"]) > 1
        assert returned_extra or offer["send_value"] <= target_value + 1700
        assert offer["value_delta"] >= -trade_value_bands.EDGE


def test_overpay_is_balanced_by_what_the_other_side_adds_back(league):
    results = [_offers(league, t) for t in ("F02-09", "F02-16", "F05-12", "F05-19")]
    balanced = [o for r in results for o in r["offers"] if len(o["receive"]) > 1]
    assert balanced, "an overpaying package should be rebalanced with a real asset from the partner"
    partner_ids = {str(p) for p in league["rosters"][1]["players"]} | {str(p) for p in league["rosters"][4]["players"]}
    for offer in balanced:
        added = offer["receive"][1:]
        assert all(a["kind"] == "pick" or a["id"] in partner_ids for a in added)
        assert any("adds" in line for line in offer["why"])


def test_picks_in_packages_are_the_users_own_and_priced_like_the_draft_picks_screen(league):
    result = _offers(league, "F02-03")
    mult = strategy_adjusted_pick_score_multiplier(1.0, "contender")
    owned = trade_ideas._build_roster_pick_assets(
        "fixture-league", league["rosters"], league["summary"], league_settings=league["settings"],
        draft_status=None, adapter=league["adapter"],
    )
    my_picks = {
        f"{p['season']}:{p['round']}:{p['original_roster_id']}": int(round(int(p["score"]) * mult))
        for p in owned[1]
    }
    seen_pick = False
    for offer in result["offers"]:
        for asset in offer["send"]:
            if asset["kind"] == "pick":
                seen_pick = True
                assert asset["id"] in my_picks
                assert asset["value"] == my_picks[asset["id"]]
    assert seen_pick


def test_untouchables_are_never_sent(league):
    first = _offers(league, "F05-19")
    sent = {a["label"] for o in first["offers"] for a in o["send"] if a["kind"] == "player"}
    assert sent
    again = _offers(league, "F05-19", untouchables=sorted(sent))
    for offer in again["offers"]:
        assert not ({a["label"] for a in offer["send"]} & sent)


def test_a_thin_position_is_not_stripped_to_buy_a_player():
    fx = _league()
    # RB room down to exactly the two starters. Every other RB leaves.
    mine = [str(p) for p in fx["rosters"][0]["players"]]
    rbs = fx["players"][(fx["players"]["player_id"].isin(mine)) & (fx["players"]["position"] == "RB")]
    keep = list(rbs.sort_values("value_score", ascending=False)["player_id"].head(2))
    drop = set(rbs["player_id"]) - set(keep)
    fx["rosters"][0]["players"] = [p for p in mine if p not in drop]
    total = 0
    for target in ("F02-06", "F02-12", "F05-09", "F05-16", "F05-19"):
        result = _offers(fx, target)
        total += len(result["offers"])
        for offer in result["offers"]:
            sent_ids = {a["id"] for a in offer["send"] if a["kind"] == "player"}
            assert not (sent_ids & set(keep)), (target, offer["send"])
    assert total > 0, "the check above must have real offers to look at"


def test_own_player_and_free_agent_are_not_trade_targets(league):
    own = _offers(league, "F01-05")
    assert own["status"] == "own_player" and own["offers"] == []
    fa = _offers(league, "NOT-ON-A-ROSTER")
    assert fa["status"] == "not_rostered" and "Waivers" in fa["headline"]


def test_offers_are_ranked_and_capped(league):
    result = _offers(league, "F05-19")
    ranks = [o["rank"] for o in result["offers"]]
    assert ranks == list(range(1, len(ranks) + 1))
    assert len(result["offers"]) <= tto.MAX_OFFERS


# ----------------------------------------------------------------- pure pieces

def _idea(send, receive=None, **extra):
    base = {
        "send_assets": send,
        "receive_assets": receive or [{"asset_type": "player", "player_id": "t", "label": "Target", "score": 5000}],
        "market_realism_score": 70,
        "partner_fit_score": 3,
        "analyzer_value_delta": 0,
    }
    base.update(extra)
    return base


def _p(pid, score=3000):
    return {"asset_type": "player", "player_id": pid, "label": pid, "score": score}


def _pk(season, rnd):
    return {"asset_type": "pick", "label": f"{season} Round {rnd}", "score": 800, "season": season, "round": rnd, "original_roster_id": 1}


def test_acceptance_read_labels_follow_partner_side_numbers():
    assert tto.acceptance_read(_idea([_p("a")]))["label"] == tto.ACCEPT_LIKELY
    assert tto.acceptance_read(_idea([_p("a")], market_realism_score=60))["label"] == tto.ACCEPT_POSSIBLE
    assert tto.acceptance_read(_idea([_p("a")], market_realism_score=40))["label"] == tto.ACCEPT_LONG_SHOT
    # They would be giving up real value: one rung down.
    assert tto.acceptance_read(_idea([_p("a")], analyzer_value_delta=450))["label"] == tto.ACCEPT_POSSIBLE
    reads = [tto.acceptance_read(_idea([_p("a")], market_realism_score=s)) for s in (80, 60, 30)]
    assert all(r["reason"] for r in reads)


def test_select_offers_prefers_different_structures():
    a = _idea([_p("a")])
    a2 = _idea([_p("a"), _p("z")])
    b = _idea([_pk(2026, 1), _pk(2026, 2)])
    c = _idea([_p("c"), _pk(2027, 2)])
    chosen = tto.select_offers([a, a2, b, c], limit=3)
    assert chosen[0] is a
    assert b in chosen and c in chosen and a2 not in chosen
    # A thin field still returns what exists.
    assert tto.select_offers([a, a2], limit=3) == [a, a2]


def test_why_lines_use_real_numbers_and_name_what_the_partner_adds():
    idea = _idea(
        [_p("a", 3000), _pk(2026, 3)],
        my_score=3800, their_score=5000, posture_lineup_points=11.4, analyzer_weeks_text="over Weeks 8-17",
        hub_target_fit_reason="This player fits because WR is one of your current pressure positions.",
        balance_added_labels=["2027 Round 3"],
    )
    lines = tto.why_lines(idea, target_name="Target", partner_name="Rivals")
    text = " ".join(lines)
    assert "11 lineup points over Weeks 8-17" in text
    assert "3,800" in text and "5,000" in text
    assert "Rivals adds 2027 Round 3" in text
    assert "Draft Picks screen" in text
