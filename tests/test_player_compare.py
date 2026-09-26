import unittest

import pandas as pd

import app
from modules import player_compare


def _row(**overrides) -> pd.Series:
    base = {
        "player_id": "1",
        "name": "Player One",
        "position": "WR",
        "team": "KC",
        "age": 24,
        "value_score": 8000,
        "dynasty_score": 8000,
        "canonical_position_rank": 3,
        "position_rank": 3,
        "market_score": 80,
        "opportunity_score": 70,
        "scarcity_score": 60,
        "role_score": 50,
    }
    base.update(overrides)
    return pd.Series(base)


class TestPlayerCompareRows(unittest.TestCase):
    def test_build_value_rows_matches_mobile_field_set(self):
        row_a = _row()
        row_b = _row(player_id="2", value_score=7000, dynasty_score=7000, canonical_position_rank=1, position_rank=1, age=27)
        rows = player_compare.build_value_rows(row_a, row_b, score_field="dynasty_score")
        self.assertEqual([row.label for row in rows], ["Value Score", "Position Rank", "Age"])
        value_row, rank_row, age_row = rows
        self.assertEqual((value_row.a, value_row.b), (8000.0, 7000.0))
        self.assertEqual((rank_row.a, rank_row.b), (3.0, 1.0))
        self.assertEqual((age_row.a, age_row.b), (24.0, 27.0))

    def test_build_model_rows_matches_mobile_field_set(self):
        row_a = _row()
        row_b = _row(player_id="2", market_score=60, opportunity_score=90, scarcity_score=None, role_score=50)
        rows = player_compare.build_model_rows(row_a, row_b)
        self.assertEqual(
            [row.label for row in rows],
            ["Market", "Opportunity", "Scarcity", "Role"],
        )
        # Scarcity is null on side B — never coerced to 0.
        scarcity_row = rows[2]
        self.assertEqual(scarcity_row.a, 60.0)
        self.assertIsNone(scarcity_row.b)

    def test_has_any_value_false_when_both_sides_entirely_null(self):
        rows = (
            player_compare.CompareRow("Market", None, None),
            player_compare.CompareRow("Opportunity", None, None),
        )
        self.assertFalse(player_compare.has_any_value(rows))

    def test_position_rank_lower_wins(self):
        row = player_compare.CompareRow("Position Rank", 3.0, 1.0, lower_is_better=True)
        html = player_compare.compare_row_html(row)
        # Side B (rank #1) is the win — the only pill carrying the win class,
        # and it sits after the label (i.e. it's the B-side cell, not A's).
        self.assertEqual(html.count("pqv-compare-pill-win"), 1)
        label_index = html.index("POSITION RANK")
        win_index = html.index("pqv-compare-pill-win")
        self.assertGreater(win_index, label_index)

    def test_value_score_higher_wins(self):
        rows = player_compare.build_value_rows(
            _row(value_score=8000, dynasty_score=8000),
            _row(player_id="2", value_score=7000, dynasty_score=7000),
            score_field="dynasty_score",
        )
        html = player_compare.compare_row_html(rows[0])
        self.assertEqual(html.count("pqv-compare-pill-win"), 1)
        self.assertIn("8,000", html)

    def test_tie_highlights_neither_side(self):
        row = player_compare.CompareRow("Role", 50.0, 50.0)
        html = player_compare.compare_row_html(row)
        self.assertNotIn("pqv-compare-pill-win", html)

    def test_missing_side_renders_em_dash_never_a_win(self):
        row = player_compare.CompareRow("Scarcity", 60.0, None)
        html = player_compare.compare_row_html(row)
        self.assertNotIn("pqv-compare-pill-win", html)
        self.assertIn("—", html)

    def test_compare_rows_html_wraps_every_row(self):
        rows = player_compare.build_model_rows(_row(), _row(player_id="2"))
        html = player_compare.compare_rows_html(rows)
        self.assertEqual(html.count("pqv-compare-row"), len(rows) + 1)  # +1 for the wrapper's own class name match


class TestPlayerCompareAppWiring(unittest.TestCase):
    def test_open_player_compare_sets_side_a_and_clears_quick_view(self):
        app.st.session_state.clear()
        app.st.session_state["player_quick_view_player_id"] = "999"
        app.open_player_compare("123")
        self.assertEqual(app.st.session_state.get("player_compare_player_a_id"), "123")
        self.assertNotIn("player_compare_player_b_id", app.st.session_state)
        self.assertNotIn("player_quick_view_player_id", app.st.session_state)

    def test_open_player_compare_ignores_blank_id(self):
        app.st.session_state.clear()
        app.open_player_compare("   ")
        self.assertNotIn("player_compare_player_a_id", app.st.session_state)

    def test_clear_player_compare_pops_both_keys(self):
        app.st.session_state.clear()
        app.st.session_state["player_compare_player_a_id"] = "1"
        app.st.session_state["player_compare_player_b_id"] = "2"
        app._clear_player_compare()
        self.assertNotIn("player_compare_player_a_id", app.st.session_state)
        self.assertNotIn("player_compare_player_b_id", app.st.session_state)


if __name__ == "__main__":
    unittest.main()
