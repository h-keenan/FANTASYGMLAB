"""Regression: History trade grades price traded picks with the shared pick model.

Reproduces the Wk 8 three-team trade where "Not Your Dad's Dih" received a 2028
R1 + 2027 R1 and was graded D because the grader priced every pick at a flat
mid-round ~2,900 (no original-owner slot, no per-year discount, no league
context). Player values are the repo's FantasyCalc numbers
(data/fantasycalc_values.csv).
"""

from __future__ import annotations

import pandas as pd

from modules import league_history as history
from modules import transaction_grades as grades
from modules import trade_ideas

NYDD, SHIESTY, TITUS = 1, 2, 3
WEAK_OWNER, MID_OWNER = 9, 10  # original owners of the two firsts

PROFILES = {
    str(rid): {"team_name": name, "username": name.lower(), "owner_name": name}
    for rid, name in (
        (NYDD, "Not Your Dad's Dih"),
        (SHIESTY, "Shiesty"),
        (TITUS, "KING TITUS"),
    )
}
PLAYERS = {
    "jeanty": {"name": "Ashton Jeanty", "position": "RB", "team": "LV"},
    "brown": {"name": "A.J. Brown", "position": "WR", "team": "PHI"},
    "swift": {"name": "D'Andre Swift", "position": "RB", "team": "CHI"},
}
# FantasyCalc dynasty values from data/fantasycalc_values.csv.
LOOKUP = {
    "jeanty": {"current_value": 7932},
    "brown": {"current_value": 3685},
    "swift": {"current_value": 2265},
}


def _raw():
    def pick(season, rnd, original, prev, owner):
        return {
            "season": str(season),
            "round": rnd,
            "roster_id": original,
            "previous_owner_id": prev,
            "owner_id": owner,
        }

    return {
        "transaction_id": "wk8-three-team",
        "type": "trade",
        "status": "complete",
        "roster_ids": [NYDD, SHIESTY, TITUS],
        # Jeanty (from NYDD) + Brown (from Shiesty) to KING TITUS, Swift (from
        # KING TITUS) to Shiesty; KING TITUS pays two firsts to NYDD and a 2nd
        # to Shiesty.
        "adds": {"jeanty": TITUS, "brown": TITUS, "swift": SHIESTY},
        "drops": {"jeanty": NYDD, "brown": SHIESTY, "swift": TITUS},
        "draft_picks": [
            pick(2028, 1, MID_OWNER, TITUS, NYDD),
            pick(2027, 1, WEAK_OWNER, TITUS, NYDD),
            pick(2029, 2, MID_OWNER, TITUS, SHIESTY),
        ],
        "status_updated": 1_793_000_000_000,
    }


def _graded(pick_index=None):
    tx = history.normalize_transaction(
        _raw(), league_id="L", season="2026", week=8, profiles=PROFILES, player_lookup=PLAYERS
    )
    grades.price_trade_picks([tx], pick_index)
    return tx, grades.grade_trade(tx, player_lookup=LOOKUP, current_week=10)


def _league_pick_index():
    """What list_draft_pick_assets prices: the original owner's projected slot."""

    def asset(season, rnd, original, percentile, bucket, label):
        comp = trade_ideas.pick_value_components(
            season,
            rnd,
            original,
            pd.DataFrame(),
            team_context={"tier_bucket": bucket, "team_modifier": 1.0, "slot_percentile": percentile},
            next_draft_year=2027,
        )
        return {
            "asset_type": "pick",
            "season": season,
            "round": rnd,
            "original_roster_id": original,
            "score": comp["score"],
            "projected_slot_label": label,
        }

    return trade_ideas.index_pick_assets(
        [
            asset(2027, 1, WEAK_OWNER, 0.9, "early", "1.02"),
            asset(2028, 1, MID_OWNER, 0.5, "mid", "1.06"),
            asset(2029, 2, MID_OWNER, 0.5, "mid", "2.06"),
        ]
    )


def _side(report, team):
    return next(s for s in report["sides"] if s["team"] == team)


def test_flat_priced_picks_were_the_bug():
    """Without the original owner's slot the picks fall to the neutral model,
    which still discounts by year (2028 < 2027) rather than a flat 2,900."""

    tx, _ = _graded()
    values = {(p["season"], p["round"]): p["current_value"] for p in tx["sides"][0]["receives"] if p["kind"] == "pick"}
    assert values[("2027", 1)] > values[("2028", 1)]
    assert values[("2027", 1)] != values[("2028", 1)]


def test_original_owner_slot_prices_the_firsts_above_a_flat_round_value():
    tx, report = _graded(_league_pick_index())
    picks = {(p["season"], p["round"]): p for p in tx["sides"][0]["receives"] if p["kind"] == "pick"}
    # An early 2027 1st from a weak team is worth far more than the old flat 2,900.
    assert picks[("2027", 1)]["current_value"] > 4000
    assert picks[("2027", 1)]["projected_slot_label"] == "1.02"
    nydd = _side(report, "Not Your Dad's Dih")
    flat_ratio = (2900 + 2900) / 7932
    assert nydd["ratio"] > flat_ratio + 0.10
    assert not nydd["letter"].startswith(("D", "F"))
    assert nydd["timing_label"] == "Provisional"
    assert nydd["confidence"] == "Low confidence"


def test_each_team_gets_its_own_why_naming_the_team():
    _, report = _graded(_league_pick_index())
    whys = {s["team"]: s["why"] for s in report["sides"]}
    assert set(whys) == {"Not Your Dad's Dih", "Shiesty", "KING TITUS"}
    for team, why in whys.items():
        assert why.startswith(f"{team}: received ")
    assert "2 firsts" in whys["Not Your Dad's Dih"]
    assert "Ashton Jeanty" in whys["Not Your Dad's Dih"]
    assert "Ashton Jeanty" in whys["KING TITUS"] and "A.J. Brown" in whys["KING TITUS"]
    assert "2029 2nd" in whys["Shiesty"]
    assert len(set(whys.values())) == 3


def test_provisional_picks_are_valued_at_market_not_discounted():
    """A provisional grade lowers confidence; it does not haircut the pick."""

    tx, report = _graded(_league_pick_index())
    nydd = _side(report, "Not Your Dad's Dih")
    received = sum(p["current_value"] for p in tx["sides"][0]["receives"] if p["kind"] == "pick")
    indexed = sum(a["score"] for k, a in _league_pick_index().items() if k[1] == 1)
    assert received == indexed
    assert nydd["provisional"] is True
