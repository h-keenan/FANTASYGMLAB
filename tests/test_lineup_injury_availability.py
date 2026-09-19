"""A player ruled out must not win a starting slot from someone who can play.

Reported by a co-owner: a WR confirmed "Out" on Sleeper was still the
suggested FLEX starter, because suggest_optimal_lineup ranked purely on
season value and never asked whether the player was available at all.

The rule these tests pin down: "Out"/IR/PUP is a ruling and gets benched
whenever an available alternative exists at that slot; "Questionable" and
"Doubtful" are genuinely uncertain and stay startable (that call belongs to
the GM). Availability is a tiebreaker on top of season value, never a
re-ranking of it.
"""

import pandas as pd

from modules import team_eval
from modules.rankings import injury_display_label, is_ruled_out, summarize_team_injuries


# One QB + three WR slots' worth of settings, with a FLEX so the
# "does he sneak in through FLEX instead?" case is covered too.
_SETTINGS = {
    "qb_count": 1,
    "rb_count": 1,
    "wr_count": 1,
    "te_count": 0,
    "regular_flex_count": 1,
    "k_count": 0,
}


def _player(player_id, position, score, *, status="Active", injury_status=""):
    return {
        "player_id": player_id,
        "name": player_id,
        "position": position,
        "team": "HOU",
        "age": 26,
        "status": status,
        "injury_status": injury_status,
        "value_score": score,
        "dynasty_score": score,
    }


def _lineup(rows, settings=None):
    frame = team_eval.suggest_optimal_lineup(pd.DataFrame(rows), settings or _SETTINGS)
    return {row["player_id"]: row for _, row in frame.iterrows()}


def test_is_ruled_out_separates_a_ruling_from_uncertainty():
    # Built on injury_level, so "major" (IR/PUP/NFI/season-ending) is
    # always out...
    assert is_ruled_out("Injured Reserve", "") is True
    assert is_ruled_out("Active", "IR") is True
    assert is_ruled_out("PUP", "") is True
    # ...and a flat "Out" is a ruling even though injury_level files it
    # under the same "moderate" bucket as Doubtful.
    assert is_ruled_out("Active", "Out") is True
    assert is_ruled_out("Out", "") is True
    # Uncertainty is NOT a ruling — these stay the GM's call.
    assert is_ruled_out("Active", "Doubtful") is False
    assert is_ruled_out("Active", "Questionable") is False
    assert is_ruled_out("Active", "Day-To-Day") is False
    assert is_ruled_out("Active", "") is False
    # Whole-word only: nothing that merely spells "out" reads as a ruling.
    assert is_ruled_out("Active", "Workout limited") is False


def test_injury_display_label_reads_both_sleeper_fields():
    # The weekly tag when Sleeper sets one...
    assert injury_display_label("Active", "Questionable") == "Questionable"
    # ...and the roster status when the weekly tag is blank, which is
    # exactly the case an injury_status-only pill used to render as healthy.
    assert injury_display_label("Injured Reserve", "") == "Injured Reserve"
    # Healthy stays untagged, junk values included.
    assert injury_display_label("Active", "") == ""
    assert injury_display_label("Active", "None") == ""


def test_out_player_loses_his_slot_to_an_available_alternative():
    """The reported bug: highest season value, but he cannot play."""

    rows = [
        _player("qb", "QB", 500),
        _player("rb", "RB", 400),
        _player("wr_out", "WR", 9000, injury_status="Out"),
        _player("wr_healthy", "WR", 1000),
        _player("wr_depth", "WR", 900),
    ]
    lineup = _lineup(rows)

    # The Out WR outscores both alternatives and still starts nowhere —
    # not at WR, and not by sliding down into the FLEX either.
    assert lineup["wr_out"]["ruled_out"] is True
    assert lineup["wr_out"]["suggested_starter"] is False
    assert lineup["wr_out"]["slot"] == "BENCH"
    assert lineup["wr_healthy"]["slot"] == "WR"
    assert lineup["wr_depth"]["slot"] == "FLEX"


def test_ir_status_without_an_injury_status_tag_is_benched_too():
    """Season-ending unavailability arrives on `status`, not `injury_status`."""

    rows = [
        _player("qb", "QB", 500),
        _player("rb", "RB", 400),
        _player("wr_ir", "WR", 9000, status="Injured Reserve"),
        _player("wr_healthy", "WR", 1000),
        _player("wr_depth", "WR", 900),
    ]
    lineup = _lineup(rows)

    assert lineup["wr_ir"]["ruled_out"] is True
    assert lineup["wr_ir"]["suggested_starter"] is False
    assert lineup["wr_healthy"]["slot"] == "WR"


def test_questionable_and_doubtful_players_still_start():
    """Uncertainty is not a ruling — auto-benching these would take a real
    judgement call away from the GM, and they routinely play."""

    rows = [
        _player("qb", "QB", 500),
        _player("rb", "RB", 400),
        _player("wr_questionable", "WR", 9000, injury_status="Questionable"),
        _player("wr_doubtful", "WR", 8000, injury_status="Doubtful"),
        _player("wr_healthy", "WR", 10),
    ]
    lineup = _lineup(rows)

    assert lineup["wr_questionable"]["ruled_out"] is False
    assert lineup["wr_questionable"]["slot"] == "WR"
    assert lineup["wr_doubtful"]["ruled_out"] is False
    assert lineup["wr_doubtful"]["slot"] == "FLEX"
    assert lineup["wr_healthy"]["suggested_starter"] is False


def test_an_out_player_still_fills_a_slot_nothing_else_can():
    """Availability is a preference, not a hard filter: the lineup stays
    complete, and the row says `ruled_out` so the surface can flag it."""

    rows = [
        _player("qb", "QB", 500),
        _player("rb", "RB", 400),
        _player("wr_out", "WR", 9000, injury_status="Out"),
    ]
    lineup = _lineup(rows)

    assert lineup["wr_out"]["slot"] == "WR"
    assert lineup["wr_out"]["suggested_starter"] is True
    assert lineup["wr_out"]["ruled_out"] is True


def test_availability_never_outranks_value_among_available_players():
    """The lineup stays season-value-based: this fix only reorders healthy
    vs. ruled-out, never healthy vs. healthy."""

    rows = [
        _player("qb", "QB", 500),
        _player("rb", "RB", 400),
        _player("wr_best", "WR", 3000),
        _player("wr_mid", "WR", 2000),
        _player("wr_worst", "WR", 1000),
    ]
    lineup = _lineup(rows)

    assert lineup["wr_best"]["slot"] == "WR"
    assert lineup["wr_mid"]["slot"] == "FLEX"
    assert lineup["wr_worst"]["suggested_starter"] is False
    assert all(not row["ruled_out"] for row in lineup.values())


def test_a_benched_out_player_is_still_reported_as_an_injured_starter():
    """The health read must not improve just because the optimizer routed
    around the injury: modules.rankings.summarize_team_injuries counts a
    `displaced_by_injury` player as an injured starter."""

    rows = [
        _player("qb", "QB", 500),
        _player("rb", "RB", 400),
        _player("wr_out", "WR", 9000, injury_status="Out", status="Injured Reserve"),
        _player("wr_healthy", "WR", 1000),
        _player("wr_depth", "WR", 900),
    ]
    frame = pd.DataFrame(rows)
    lineup_df = team_eval.suggest_optimal_lineup(frame, _SETTINGS)

    displaced = dict(zip(lineup_df["player_id"], lineup_df["displaced_by_injury"]))
    assert displaced["wr_out"] is True
    # Only the player who actually lost a slot — not every ruled-out player.
    assert not any(value for key, value in displaced.items() if key != "wr_out")

    summary = summarize_team_injuries(frame, lineup_df)
    assert summary["injured_starters"] == 1
    assert summary["health_flag"] != "Healthy"
    assert summary["injury_impact_flag"] != "Stable"


def test_a_deep_bench_injury_is_not_an_injured_starter():
    """The flip side: a ruled-out player who would never have started either
    way is not counted as a lineup hit."""

    rows = [
        _player("qb", "QB", 500),
        _player("rb", "RB", 400),
        _player("wr_healthy", "WR", 1000),
        _player("wr_depth", "WR", 900),
        _player("wr_scrub_out", "WR", 1, injury_status="Out"),
    ]
    frame = pd.DataFrame(rows)
    lineup_df = team_eval.suggest_optimal_lineup(frame, _SETTINGS)

    displaced = dict(zip(lineup_df["player_id"], lineup_df["displaced_by_injury"]))
    assert displaced["wr_scrub_out"] is False
    assert summarize_team_injuries(frame, lineup_df)["injured_starters"] == 0


def test_frames_without_status_columns_are_treated_as_available():
    """Several callers build score-only frames; they must keep working."""

    frame = pd.DataFrame(
        [
            {"player_id": "qb", "position": "QB", "value_score": 500},
            {"player_id": "wr", "position": "WR", "value_score": 400},
        ]
    )
    lineup = team_eval.suggest_optimal_lineup(frame, _SETTINGS)

    assert lineup["ruled_out"].tolist() == [False, False]
    assert set(lineup[lineup["suggested_starter"]]["slot"]) == {"QB", "WR"}


def test_empty_roster_frame_still_carries_the_availability_column():
    empty = team_eval.suggest_optimal_lineup(pd.DataFrame(columns=["player_id", "position"]), _SETTINGS)

    assert "ruled_out" in empty.columns
    assert empty.empty
