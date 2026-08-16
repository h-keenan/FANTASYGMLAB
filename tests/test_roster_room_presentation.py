from modules.roster_room_presentation import (
    canonicalize_surplus_and_thin,
    surplus_thin_summary_clause,
)


def test_overlap_without_need_stays_surplus_not_thin():
    surplus, thin = canonicalize_surplus_and_thin(
        ["WR", "TE", "RB"],
        ["RB", "QB"],
        needed=["QB"],
    )
    assert surplus == ["WR", "TE", "RB"]
    assert thin == ["QB"]
    assert "RB" not in thin


def test_overlap_with_need_drops_surplus():
    surplus, thin = canonicalize_surplus_and_thin(
        ["WR", "RB"],
        ["RB", "QB"],
        needed=["RB", "QB"],
    )
    assert surplus == ["WR"]
    assert thin == ["RB", "QB"]


def test_kicker_surplus_is_preserved():
    surplus, thin = canonicalize_surplus_and_thin(
        ["WR", "K"],
        ["QB"],
        needed=["QB"],
    )
    assert surplus == ["WR", "K"]
    assert thin == ["QB"]


def test_summary_clause_has_no_rb_contradiction():
    clause = surplus_thin_summary_clause(
        ["WR", "TE", "RB"],
        ["RB", "QB"],
        needed=["QB"],
    )
    assert clause == "Surplus: WR, TE, RB | Thin: QB"
