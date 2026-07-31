"""Deterministic, anonymous fixtures for archetype admission testing."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


FIXTURE_VERSION = "archetype-fixtures-v1"


@dataclass(frozen=True)
class LeagueScenario:
    label: str
    league_settings: tuple[tuple[str, object], ...]
    roster_profile: str


def fixture_matrix() -> tuple[LeagueScenario, ...]:
    base = {
        "league_format": "Dynasty",
        "qb_format": "1QB",
        "te_premium": False,
        "starter_count": 9,
        "bench_count": 15,
        "league_size": 12,
    }

    def scenario(label: str, profile: str, **overrides: object) -> LeagueScenario:
        settings = {**base, **overrides}
        return LeagueScenario(label, tuple(sorted(settings.items())), profile)

    return (
        scenario("standard-1qb", "balanced"),
        scenario("superflex", "balanced", qb_format="Superflex", superflex_count=1),
        scenario("tight-end-premium", "balanced", te_premium=True),
        scenario("shallow-lineups", "balanced", starter_count=7, bench_count=10),
        scenario("deep-lineups", "balanced", starter_count=12, bench_count=20),
        scenario("contending-roster", "contender"),
        scenario("rebuilding-roster", "rebuild"),
        scenario("balanced-roster", "balanced"),
        scenario("aging-roster", "aging"),
        scenario("youth-heavy-roster", "youth"),
        scenario("strong-quarterback-room", "strong_qb"),
        scenario("weak-quarterback-room", "weak_qb"),
        scenario("strong-draft-capital", "strong_picks"),
        scenario("weak-draft-capital", "weak_picks"),
    )


def player_fixture() -> pd.DataFrame:
    """Return stable synthetic players spanning positions, ages, tiers, and risk."""

    rows = []
    positions = ("QB", "RB", "WR", "TE")
    for index in range(24):
        position = positions[index % len(positions)]
        value = 9200 - (index * 340)
        rows.append(
            {
                "player_id": f"FX-{index + 1:03d}",
                "name": f"Fixture Asset {index + 1:03d}",
                "position": position,
                "team": "FA" if index in {19, 23} else f"T{(index % 12) + 1:02d}",
                "age": 21 + (index % 14),
                "years_exp": index % 10,
                "dynasty_score": max(500, value),
                "value_score": max(400, value - 120),
                "market_score": max(450, value - 80),
                "role_score": max(350, value - 180),
                "opportunity_score": max(300, value - 220),
                "scarcity_score": 6400 if position == "QB" else 4800,
                "risk_multiplier": 0.72 if index in {5, 17} else 1.0,
                "status": "Injured Reserve" if index in {5, 17} else "Active",
                "injury_status": "Out" if index in {5, 17} else "",
                "search_rank": index + 1,
                "player_tier": (
                    "Elite" if value >= 8000 else
                    "Star" if value >= 6500 else
                    "Starter" if value >= 4000 else
                    "Depth"
                ),
                "rookie": index < 4,
                "volatility": "high" if index % 7 == 0 else "normal",
            }
        )
    return pd.DataFrame(rows)


def draft_pick_fixture() -> pd.DataFrame:
    rows = []
    for year_offset, year in enumerate((2027, 2028, 2029)):
        for round_number in (1, 2, 3, 4):
            rows.append(
                {
                    "asset_id": f"PICK-{year}-R{round_number}",
                    "year": year,
                    "round": round_number,
                    "value_score": 5000 - (year_offset * 550) - ((round_number - 1) * 900),
                }
            )
    return pd.DataFrame(rows)


def recommendation_fixture() -> tuple[dict[str, object], ...]:
    return (
        {
            "recommendation_id": "REC-001",
            "order": 1,
            "classification": "Trade",
            "strength": 0.91,
            "partner": "TEAM-02",
            "sent_assets": ("FX-010",),
            "received_assets": ("FX-006",),
        },
        {
            "recommendation_id": "REC-002",
            "order": 2,
            "classification": "Add",
            "strength": 0.78,
            "partner": "",
            "sent_assets": (),
            "received_assets": ("FX-020",),
        },
        {
            "recommendation_id": "REC-003",
            "order": 3,
            "classification": "Stash",
            "strength": 0.64,
            "partner": "",
            "sent_assets": (),
            "received_assets": ("FX-024",),
        },
    )
