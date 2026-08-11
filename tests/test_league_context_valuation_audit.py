"""Automatic league-settings → player-value calibration harnesses.

Proves Sleeper-shaped league payloads infer format without manual overrides,
that league multipliers move values in the expected direction, and that
settings digests isolate cross-league prepared frames.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

import app
from modules import prepared_player_frame
from modules import trade_ideas


ROOT = Path(__file__).resolve().parents[1]


def _sleeper_league(
    *,
    league_type: int,
    rec: float | None,
    roster_positions: list[str],
    total_rosters: int = 12,
    te_bonus: float = 0.0,
    reserve_slots: int = 0,
    pass_td: float | None = None,
    extra_scoring: dict | None = None,
) -> dict:
    scoring: dict = {}
    if rec is not None:
        scoring["rec"] = rec
    if te_bonus:
        scoring["bonus_rec_te"] = te_bonus
    if pass_td is not None:
        scoring["pass_td"] = pass_td
    if extra_scoring:
        scoring.update(extra_scoring)
    settings = {"type": league_type, "num_teams": total_rosters}
    if reserve_slots:
        settings["reserve_slots"] = reserve_slots
    return {
        "total_rosters": total_rosters,
        "settings": settings,
        "scoring_settings": scoring,
        "roster_positions": roster_positions,
    }


DYNASTY_1QB_STD = _sleeper_league(
    league_type=2,
    rec=0.0,
    roster_positions=["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "BN", "BN", "BN", "BN", "BN", "BN"],
)
DYNASTY_1QB_HALF = _sleeper_league(
    league_type=2,
    rec=0.5,
    roster_positions=["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "BN", "BN", "BN", "BN", "BN", "BN"],
)
DYNASTY_1QB_PPR = _sleeper_league(
    league_type=2,
    rec=1.0,
    roster_positions=["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "BN", "BN", "BN", "BN", "BN", "BN"],
)
DYNASTY_SF_HALF = _sleeper_league(
    league_type=2,
    rec=0.5,
    roster_positions=[
        "QB",
        "RB",
        "RB",
        "WR",
        "WR",
        "WR",
        "TE",
        "FLEX",
        "SUPER_FLEX",
        "BN",
        "BN",
        "BN",
        "BN",
        "BN",
        "BN",
        "TAXI",
        "TAXI",
        "IR",
    ],
    reserve_slots=1,
)
DYNASTY_SF_PPR = _sleeper_league(
    league_type=2,
    rec=1.0,
    roster_positions=[
        "QB",
        "RB",
        "RB",
        "WR",
        "WR",
        "WR",
        "TE",
        "FLEX",
        "SUPER_FLEX",
        "BN",
        "BN",
        "BN",
        "BN",
        "BN",
        "BN",
    ],
)
DYNASTY_TE_PREM = _sleeper_league(
    league_type=2,
    rec=1.0,
    te_bonus=1.5,
    roster_positions=["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "BN", "BN", "BN", "BN", "BN", "BN"],
)
REDRAFT_1QB_STD = _sleeper_league(
    league_type=0,
    rec=0.0,
    roster_positions=["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "FLEX", "BN", "BN", "BN", "BN", "BN"],
)
REDRAFT_PPR = _sleeper_league(
    league_type=0,
    rec=1.0,
    roster_positions=["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "BN", "BN", "BN", "BN", "BN"],
)
REDRAFT_SF = _sleeper_league(
    league_type=0,
    rec=1.0,
    roster_positions=["QB", "RB", "RB", "WR", "WR", "TE", "FLEX", "SUPER_FLEX", "BN", "BN", "BN", "BN", "BN"],
)
KEEPER_PPR = _sleeper_league(
    league_type=1,
    rec=1.0,
    roster_positions=["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "BN", "BN", "BN", "BN", "BN", "BN"],
)


def _player(
    player_id: str,
    *,
    position: str,
    age: float,
    dynasty_score: float,
    value_score: float | None = None,
    market_score: float | None = None,
    opportunity_score: float = 5000,
    role_score: float = 5000,
    scarcity_score: float = 5000,
    targets: float = 0,
    receptions: float = 0,
    years_exp: float = 3,
    status: str = "Active",
    injury_status: str = "",
    search_rank: int = 50,
) -> dict:
    market = market_score if market_score is not None else dynasty_score
    current = value_score if value_score is not None else dynasty_score
    return {
        "player_id": player_id,
        "name": player_id,
        "position": position,
        "team": "KC",
        "age": age,
        "years_exp": years_exp,
        "dynasty_score": dynasty_score,
        "value_score": current,
        "market_score": market,
        "role_score": role_score,
        "opportunity_score": opportunity_score,
        "scarcity_score": scarcity_score,
        "risk_multiplier": 1.0,
        "status": status,
        "injury_status": injury_status,
        "search_rank": search_rank,
        "targets": targets,
        "receptions": receptions,
    }


def _matrix_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            _player("elite_qb", position="QB", age=27, dynasty_score=9000, opportunity_score=9200, role_score=8500),
            _player("qb12", position="QB", age=28, dynasty_score=5200, opportunity_score=7600, role_score=8500),
            _player("qb24", position="QB", age=29, dynasty_score=2800, opportunity_score=5600, role_score=5600),
            _player("backup_qb", position="QB", age=24, dynasty_score=900, opportunity_score=2200, role_score=3600),
            _player(
                "slot_wr",
                position="WR",
                age=25,
                dynasty_score=7000,
                targets=140,
                receptions=100,
                opportunity_score=9200,
                role_score=8500,
            ),
            _player(
                "deep_wr",
                position="WR",
                age=26,
                dynasty_score=7000,
                targets=55,
                receptions=28,
                opportunity_score=7600,
                role_score=8500,
            ),
            _player(
                "pass_catch_rb",
                position="RB",
                age=24,
                dynasty_score=6500,
                targets=80,
                receptions=60,
                opportunity_score=7600,
                role_score=8500,
            ),
            _player(
                "early_down_rb",
                position="RB",
                age=25,
                dynasty_score=6500,
                targets=12,
                receptions=8,
                opportunity_score=7600,
                role_score=8500,
            ),
            _player(
                "target_te",
                position="TE",
                age=26,
                dynasty_score=6000,
                targets=120,
                receptions=85,
                opportunity_score=9200,
                role_score=8500,
            ),
            _player(
                "td_te",
                position="TE",
                age=29,
                dynasty_score=6000,
                targets=35,
                receptions=22,
                opportunity_score=5600,
                role_score=8500,
            ),
            _player("young_wr", position="WR", age=22, dynasty_score=7200, value_score=4800, years_exp=1),
            _player("old_wr", position="WR", age=31, dynasty_score=7200, value_score=7800, years_exp=9),
            _player("vet_rb", position="RB", age=29, dynasty_score=6800, value_score=7500, years_exp=7),
            _player("rookie_rb", position="RB", age=21, dynasty_score=5200, value_score=2800, years_exp=0),
            _player(
                "injured_star",
                position="WR",
                age=23,
                dynasty_score=8500,
                value_score=8500,
                status="Injured Reserve",
                injury_status="Torn ACL",
                years_exp=2,
            ),
            _player("healthy_vet", position="WR", age=28, dynasty_score=7000, value_score=7600, years_exp=6),
        ]
    )


# ---------------------------------------------------------------------------
# Automatic detection
# ---------------------------------------------------------------------------


def test_detect_dynasty_1qb_standard_half_ppr_ppr():
    std = app.detect_league_value_settings_from_payload(DYNASTY_1QB_STD)
    half = app.detect_league_value_settings_from_payload(DYNASTY_1QB_HALF)
    ppr = app.detect_league_value_settings_from_payload(DYNASTY_1QB_PPR)
    assert std["league_format"] == "Dynasty"
    assert std["scoring_format"] == "Standard"
    assert std["qb_format"] == "1QB"
    assert std["_sources"]["scoring_format"] == "Sleeper"
    assert half["scoring_format"] == "Half-PPR"
    assert ppr["scoring_format"] == "PPR"
    assert not std.get("_keeper_mode")


def test_detect_dynasty_superflex_and_te_premium():
    sf_half = app.detect_league_value_settings_from_payload(DYNASTY_SF_HALF)
    sf_ppr = app.detect_league_value_settings_from_payload(DYNASTY_SF_PPR)
    tep = app.detect_league_value_settings_from_payload(DYNASTY_TE_PREM)
    assert sf_half["qb_format"] == "Superflex"
    assert sf_half["scoring_format"] == "Half-PPR"
    assert sf_half["superflex_count"] == 1
    assert sf_half["taxi_count"] == 2
    assert sf_ppr["qb_format"] == "Superflex"
    assert sf_ppr["scoring_format"] == "PPR"
    assert tep["te_premium"] is True
    assert tep["_sources"]["te_premium"] == "Sleeper"


def test_detect_redraft_variants_and_keeper():
    red_std = app.detect_league_value_settings_from_payload(REDRAFT_1QB_STD)
    red_ppr = app.detect_league_value_settings_from_payload(REDRAFT_PPR)
    red_sf = app.detect_league_value_settings_from_payload(REDRAFT_SF)
    keeper = app.detect_league_value_settings_from_payload(KEEPER_PPR)
    assert red_std["league_format"] == "Redraft"
    assert red_std["scoring_format"] == "Standard"
    assert red_ppr["scoring_format"] == "PPR"
    assert red_sf["qb_format"] == "Superflex"
    assert keeper["league_format"] == "Dynasty"
    assert keeper["_keeper_mode"] is True


def test_missing_rec_does_not_silently_claim_sleeper_ppr():
    payload = _sleeper_league(
        league_type=2,
        rec=None,
        roster_positions=["QB", "RB", "WR", "TE", "FLEX", "BN"],
    )
    detected = app.detect_league_value_settings_from_payload(payload)
    assert detected["scoring_format"] == "PPR"  # default only
    assert detected["_sources"]["scoring_format"] == "default"
    assert "rec" not in detected.get("_detected_scoring", {})


def test_pass_td_detected_but_unused_metadata():
    payload = _sleeper_league(
        league_type=2,
        rec=1.0,
        roster_positions=["QB", "RB", "WR", "TE", "BN"],
        pass_td=6.0,
    )
    detected = app.detect_league_value_settings_from_payload(payload)
    assert detected["_detected_scoring"]["pass_td"] == 6.0
    # Multiplier path must not key off pass_td.
    source = (ROOT / "app.py").read_text(encoding="utf-8")
    multiplier = source.split("def _league_settings_multiplier", 1)[1].split("\ndef apply_valuation_lens", 1)[0]
    assert "pass_td" not in multiplier


# ---------------------------------------------------------------------------
# Dynasty vs redraft
# ---------------------------------------------------------------------------


def test_dynasty_vs_redraft_age_order_can_differ():
    frame = _matrix_frame()
    dynasty = app.apply_valuation_lens(
        frame, "Dynasty", {"league_format": "Dynasty", "scoring_format": "PPR", "qb_format": "1QB"}
    )
    redraft = app.apply_valuation_lens(
        frame, "Non-Dynasty", {"league_format": "Redraft", "scoring_format": "PPR", "qb_format": "1QB"}
    )
    d_young = int(dynasty.loc[dynasty["player_id"].eq("young_wr"), "dynasty_score"].iloc[0])
    d_old = int(dynasty.loc[dynasty["player_id"].eq("old_wr"), "dynasty_score"].iloc[0])
    r_young = int(redraft.loc[redraft["player_id"].eq("young_wr"), "value_score"].iloc[0])
    r_old = int(redraft.loc[redraft["player_id"].eq("old_wr"), "value_score"].iloc[0])
    # Dynasty lens keeps long-horizon scores; redraft current favors productive vet.
    assert d_young >= d_old or (d_old - d_young) < (r_old - r_young)
    assert r_old > r_young


def test_redraft_blends_dynasty_toward_current():
    frame = pd.DataFrame(
        [
            _player("p", position="WR", age=24, dynasty_score=8000, value_score=2000),
        ]
    )
    # Seed value_score as current before lens rewrite — lens rebuilds value then blends.
    valued = app.apply_valuation_lens(
        frame, "Dynasty", {"league_format": "Redraft", "scoring_format": "PPR", "qb_format": "1QB"}
    )
    # Redraft path rewrites dynasty_score toward current value_score.
    assert int(valued.iloc[0]["dynasty_score"]) != 8000


# ---------------------------------------------------------------------------
# PPR / TE premium profile differentials
# ---------------------------------------------------------------------------


def test_ppr_lifts_slot_wr_more_than_early_down_rb_relative_to_standard():
    frame = _matrix_frame()
    ppr = app.apply_valuation_lens(
        frame, "Dynasty", {"league_format": "Dynasty", "scoring_format": "PPR", "qb_format": "1QB"}
    )
    std = app.apply_valuation_lens(
        frame, "Dynasty", {"league_format": "Dynasty", "scoring_format": "Standard", "qb_format": "1QB"}
    )

    def score(df, pid):
        return int(df.loc[df["player_id"].eq(pid), "dynasty_score"].iloc[0])

    slot_delta = score(ppr, "slot_wr") - score(std, "slot_wr")
    early_rb_delta = score(ppr, "early_down_rb") - score(std, "early_down_rb")
    # Moving Standard → PPR should help the high-target WR more than the early-down RB
    # (RB is boosted in Standard, so PPR delta for early-down RB is negative/smaller).
    assert slot_delta > early_rb_delta


def test_te_premium_favors_target_earner_over_td_dependent():
    frame = _matrix_frame()
    base = {"league_format": "Dynasty", "scoring_format": "PPR", "qb_format": "1QB"}
    normal = app.apply_valuation_lens(frame, "Dynasty", {**base, "te_premium": False})
    premium = app.apply_valuation_lens(frame, "Dynasty", {**base, "te_premium": True})

    def score(df, pid):
        return int(df.loc[df["player_id"].eq(pid), "dynasty_score"].iloc[0])

    target_lift = score(premium, "target_te") - score(normal, "target_te")
    td_lift = score(premium, "td_te") - score(normal, "td_te")
    assert target_lift > 0
    assert td_lift > 0
    assert target_lift > td_lift


# ---------------------------------------------------------------------------
# Superflex / starters / team count
# ---------------------------------------------------------------------------


def test_superflex_raises_qb_relative_to_wr_and_1qb():
    frame = _matrix_frame()
    one = app.apply_valuation_lens(
        frame, "Dynasty", {"league_format": "Dynasty", "scoring_format": "PPR", "qb_format": "1QB"}
    )
    sf = app.apply_valuation_lens(
        frame,
        "Dynasty",
        {"league_format": "Dynasty", "scoring_format": "PPR", "qb_format": "Superflex", "superflex_count": 1},
    )

    def ratio(df):
        qb = int(df.loc[df["player_id"].eq("elite_qb"), "dynasty_score"].iloc[0])
        wr = int(df.loc[df["player_id"].eq("slot_wr"), "dynasty_score"].iloc[0])
        return qb / max(wr, 1)

    assert ratio(sf) > ratio(one)
    assert int(sf.loc[sf["player_id"].eq("elite_qb"), "dynasty_score"].iloc[0]) > int(
        one.loc[one["player_id"].eq("elite_qb"), "dynasty_score"].iloc[0]
    )
    # Backup QB also rises, but starter premium remains larger in absolute terms.
    starter_lift = int(sf.loc[sf["player_id"].eq("qb12"), "dynasty_score"].iloc[0]) - int(
        one.loc[one["player_id"].eq("qb12"), "dynasty_score"].iloc[0]
    )
    backup_lift = int(sf.loc[sf["player_id"].eq("backup_qb"), "dynasty_score"].iloc[0]) - int(
        one.loc[one["player_id"].eq("backup_qb"), "dynasty_score"].iloc[0]
    )
    assert starter_lift > backup_lift


def test_more_wr_starters_increases_wr_scarcity_multiplier():
    frame = _matrix_frame()
    shallow = app.apply_valuation_lens(
        frame,
        "Dynasty",
        {
            "league_format": "Dynasty",
            "scoring_format": "PPR",
            "qb_format": "1QB",
            "wr_count": 2,
            "starter_count": 8,
            "flex_count": 1,
            "league_size": 12,
        },
    )
    deep = app.apply_valuation_lens(
        frame,
        "Dynasty",
        {
            "league_format": "Dynasty",
            "scoring_format": "PPR",
            "qb_format": "1QB",
            "wr_count": 4,
            "starter_count": 12,
            "flex_count": 3,
            "league_size": 12,
        },
    )
    shallow_wr = int(shallow.loc[shallow["player_id"].eq("slot_wr"), "dynasty_score"].iloc[0])
    deep_wr = int(deep.loc[deep["player_id"].eq("slot_wr"), "dynasty_score"].iloc[0])
    assert deep_wr > shallow_wr


def test_team_count_changes_relative_pressure_not_uniform_inflation():
    frame = _matrix_frame()
    sizes = {}
    for size in (8, 10, 12, 14, 16):
        valued = app.apply_valuation_lens(
            frame,
            "Dynasty",
            {
                "league_format": "Dynasty",
                "scoring_format": "PPR",
                "qb_format": "1QB",
                "league_size": size,
                "starter_count": 9,
            },
        )
        sizes[size] = {
            "qb": int(valued.loc[valued["player_id"].eq("elite_qb"), "dynasty_score"].iloc[0]),
            "wr": int(valued.loc[valued["player_id"].eq("slot_wr"), "dynasty_score"].iloc[0]),
        }
    # Larger leagues raise starter pressure for skill positions.
    assert sizes[16]["wr"] >= sizes[8]["wr"]
    # 1QB deep leagues specifically bump QB further.
    qb_ratio_8 = sizes[8]["qb"] / max(sizes[8]["wr"], 1)
    qb_ratio_16 = sizes[16]["qb"] / max(sizes[16]["wr"], 1)
    assert qb_ratio_16 >= qb_ratio_8


def test_deeper_bench_taxi_boosts_young_stash_more_than_aging_vet():
    frame = _matrix_frame()
    shallow = app.apply_valuation_lens(
        frame,
        "Dynasty",
        {
            "league_format": "Dynasty",
            "scoring_format": "PPR",
            "qb_format": "1QB",
            "bench_count": 2,
            "taxi_count": 0,
            "ir_count": 0,
        },
    )
    deep = app.apply_valuation_lens(
        frame,
        "Dynasty",
        {
            "league_format": "Dynasty",
            "scoring_format": "PPR",
            "qb_format": "1QB",
            "bench_count": 10,
            "taxi_count": 4,
            "ir_count": 2,
        },
    )
    young_lift = int(deep.loc[deep["player_id"].eq("young_wr"), "dynasty_score"].iloc[0]) - int(
        shallow.loc[shallow["player_id"].eq("young_wr"), "dynasty_score"].iloc[0]
    )
    old_lift = int(deep.loc[deep["player_id"].eq("old_wr"), "dynasty_score"].iloc[0]) - int(
        shallow.loc[shallow["player_id"].eq("old_wr"), "dynasty_score"].iloc[0]
    )
    assert young_lift > old_lift


# ---------------------------------------------------------------------------
# Monotonicity / isolation / picks / news
# ---------------------------------------------------------------------------


def test_invariants_scoring_sf_te_starters():
    frame = _matrix_frame()
    ppr = app.apply_valuation_lens(
        frame, "Dynasty", {"league_format": "Dynasty", "scoring_format": "PPR", "qb_format": "1QB"}
    )
    std = app.apply_valuation_lens(
        frame, "Dynasty", {"league_format": "Dynasty", "scoring_format": "Standard", "qb_format": "1QB"}
    )
    assert int(ppr.loc[ppr["player_id"].eq("slot_wr"), "dynasty_score"].iloc[0]) >= int(
        std.loc[std["player_id"].eq("slot_wr"), "dynasty_score"].iloc[0]
    )

    one = app.apply_valuation_lens(
        frame, "Dynasty", {"league_format": "Dynasty", "scoring_format": "PPR", "qb_format": "1QB"}
    )
    sf = app.apply_valuation_lens(
        frame,
        "Dynasty",
        {"league_format": "Dynasty", "scoring_format": "PPR", "qb_format": "Superflex", "superflex_count": 1},
    )
    assert int(sf.loc[sf["player_id"].eq("elite_qb"), "dynasty_score"].iloc[0]) > int(
        one.loc[one["player_id"].eq("elite_qb"), "dynasty_score"].iloc[0]
    )

    no_tep = app.apply_valuation_lens(
        frame, "Dynasty", {"league_format": "Dynasty", "scoring_format": "PPR", "te_premium": False}
    )
    tep = app.apply_valuation_lens(
        frame, "Dynasty", {"league_format": "Dynasty", "scoring_format": "PPR", "te_premium": True}
    )
    assert int(tep.loc[tep["player_id"].eq("target_te"), "dynasty_score"].iloc[0]) > int(
        no_tep.loc[no_tep["player_id"].eq("target_te"), "dynasty_score"].iloc[0]
    )


def test_settings_key_isolates_superflex_ppr_tep_from_redraft_standard():
    a = app.detect_league_value_settings_from_payload(DYNASTY_TE_PREM)
    # Force SF+PPR+TEP combo for League A fingerprint.
    a["qb_format"] = "Superflex"
    a["superflex_count"] = 1
    a["te_premium"] = True
    b = app.detect_league_value_settings_from_payload(REDRAFT_1QB_STD)
    key_a = app.league_value_settings_key(a)
    key_b = app.league_value_settings_key(b)
    assert key_a != key_b
    sig_a = prepared_player_frame.build_frame_signature(
        public_fingerprint="fp",
        valuation_lens="Dynasty",
        score_field="dynasty_score",
        league_settings_key=key_a,
        scoring_format=a["scoring_format"],
        scoring_supported=True,
        archetype_id="balanced_dynasty",
        season="2026",
        row_count=100,
    )
    sig_b = prepared_player_frame.build_frame_signature(
        public_fingerprint="fp",
        valuation_lens="Non-Dynasty",
        score_field="value_score",
        league_settings_key=key_b,
        scoring_format=b["scoring_format"],
        scoring_supported=True,
        archetype_id="balanced_dynasty",
        season="2026",
        row_count=100,
    )
    assert sig_a != sig_b


def test_other_starter_count_included_in_settings_digest():
    base = dict(app.DEFAULT_LEAGUE_VALUE_SETTINGS)
    left = app.league_value_settings_key({**base, "other_starter_count": 0})
    right = app.league_value_settings_key({**base, "other_starter_count": 2})
    assert left != right


def test_redraft_pick_values_discounted_vs_dynasty():
    summary = pd.DataFrame({"roster_id": [1, 2, 3, 4], "total_score": [9000, 7000, 5000, 3000]})
    dynasty = trade_ideas._pick_value_components(
        2027, 1, 4, summary, league_settings={"league_format": "Dynasty", "qb_format": "1QB", "league_size": 12}
    )["score"]
    redraft = trade_ideas._pick_value_components(
        2027, 1, 4, summary, league_settings={"league_format": "Redraft", "qb_format": "1QB", "league_size": 12}
    )["score"]
    assert dynasty > redraft
    assert app.draft_pick_score_multiplier("Non-Dynasty", {"league_format": "Redraft"}) < app.draft_pick_score_multiplier(
        "Dynasty", {"league_format": "Dynasty"}
    )


def test_news_factor_remains_zero_after_league_lens():
    rankings_src = (ROOT / "modules" / "rankings.py").read_text(encoding="utf-8")
    assert 'df["news_factor"] = 0.0' in rankings_src
    frame = _matrix_frame()
    valued = app.apply_valuation_lens(
        frame, "Dynasty", {"league_format": "Dynasty", "scoring_format": "PPR", "qb_format": "Superflex"}
    )
    assert "news_factor" not in valued.columns or valued["news_factor"].fillna(0).eq(0).all()


def test_scenario_matrix_smoke_formats_change_scores():
    frame = _matrix_frame()
    configs = [
        ("Dynasty", {"league_format": "Dynasty", "scoring_format": "Standard", "qb_format": "1QB"}),
        ("Dynasty", {"league_format": "Dynasty", "scoring_format": "PPR", "qb_format": "1QB"}),
        ("Dynasty", {"league_format": "Dynasty", "scoring_format": "PPR", "qb_format": "Superflex", "superflex_count": 1}),
        ("Dynasty", {"league_format": "Dynasty", "scoring_format": "PPR", "qb_format": "1QB", "te_premium": True}),
        ("Non-Dynasty", {"league_format": "Redraft", "scoring_format": "PPR", "qb_format": "1QB"}),
    ]
    fingerprints = []
    for lens, settings in configs:
        valued = app.apply_valuation_lens(frame, lens, settings)
        field = app.valuation_score_field(lens)
        fingerprints.append(
            tuple(int(v) for v in pd.to_numeric(valued[field], errors="coerce").fillna(0).tolist())
        )
    assert len(set(fingerprints)) == len(fingerprints)
