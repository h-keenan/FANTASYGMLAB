import json
import sqlite3
import warnings

from modules import trade_ideas


def test_temporary_value_diagnostic():
    connection = sqlite3.connect("data/players.db")
    connection.row_factory = sqlite3.Row
    try:
        available = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(players)").fetchall()
        }
        desired = [
            "name", "player_id", "position", "team", "age", "value",
            "fantasycalc_value", "market_score", "score", "dynasty_score",
            "value_score", "rebuild_score", "player_tier", "opportunity_label",
        ]
        selected = [column for column in desired if column in available]
        rows = connection.execute(
            f"SELECT {', '.join(selected)} FROM players "
            "WHERE name IN ('Jalen Hurts', 'Ricky Pearsall') ORDER BY name"
        ).fetchall()
    finally:
        connection.close()
    third = trade_ideas._pick_value_components(
        2027,
        3,
        1,
        __import__("pandas").DataFrame(),
        league_settings={
            "league_format": "Dynasty",
            "qb_format": "1QB",
            "league_size": 12,
        },
    )
    warnings.warn(
        "VALUE_DIAGNOSTIC=" + json.dumps(
            {
                "players": [dict(row) for row in rows],
                "2027_round_3_mid": third,
            },
            sort_keys=True,
        ),
        UserWarning,
    )
