"""Adaptive advertising API: pure builders, contract invariants, routes and docs drift.

Throwaway fixtures only: no data/players.db, no network, no rankings.load_players.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest

from modules import external_ad_api as A
import external_ad_fixtures as F

ITEM_KEYS = {"id", "kind", "timestamp", "evidence", "methodology", "confidence", "freshness", "unavailable_reason", "relevance"}
ENVELOPE_KEYS = {"status", "unavailable_reason", "generated_at", "season", "phase", "methodology", "freshness", "count", "items", "endpoint"}
REPO = Path(__file__).resolve().parent.parent


def _assert_contract(payload):
    assert ENVELOPE_KEYS <= payload.keys()
    assert payload["count"] == len(payload["items"])
    if payload["items"]:
        assert payload["status"] == "ok" and payload["unavailable_reason"] is None
    else:
        assert payload["status"] == "unavailable" and payload["unavailable_reason"]
    for it in payload["items"]:
        assert ITEM_KEYS <= it.keys()
        assert it["confidence"] in A.CONFIDENCE_LEVELS
        assert it["evidence"] and it["methodology"] and it["timestamp"]
        assert {"data_as_of", "age_hours", "stale", "source"} <= it["freshness"].keys()


# --- plan -------------------------------------------------------------------


@pytest.mark.parametrize(
    "as_of,sub,top_dynasty,top_redraft",
    [
        ("2026-12-15", "fantasy_playoffs", "playoff_sos", "lineup_decisions"),
        ("2026-12-08", "playoff_push", "playoff_sos", "playoff_sos"),
        ("2026-11-10", "deadline_window", "dynasty_value_changes", "lineup_decisions"),
        ("2026-04-25", "draft_season", "rookies", "depth_chart_changes"),
        ("2026-07-20", "training_camp", "depth_chart_changes", "depth_chart_changes"),
    ],
)
def test_plan_is_phase_aware_and_splits_dynasty_from_redraft(as_of, sub, top_dynasty, top_redraft):
    d = A.endpoint_plan(as_of=as_of, league_type="dynasty", exclude_ids=[], limit=8, now=F.NOW)
    r = A.endpoint_plan(as_of=as_of, league_type="redraft", exclude_ids=[], limit=8, now=F.NOW)
    _assert_contract(d)
    assert d["sub_phase"] == sub
    assert d["items"][0]["module"] == top_dynasty
    assert r["items"][0]["module"] == top_redraft


def test_plan_offseason_does_not_promote_redraft_modules_for_redraft():
    r = A.endpoint_plan(as_of="2027-01-20", league_type="redraft", exclude_ids=[], limit=8, now=F.NOW)
    scores = [i["relevance_redraft"] for i in r["items"]]
    assert max(scores) <= 0.4  # nothing in the Jan offseason is high-relevance for redraft


def test_plan_exclude_ids_and_validation():
    full = A.endpoint_plan(as_of="2026-12-15", league_type="both", exclude_ids=[], limit=8, now=F.NOW)
    ids = [i["id"] for i in full["items"]]
    cut = A.endpoint_plan(as_of="2026-12-15", league_type="both", exclude_ids=[ids[0]], limit=8, now=F.NOW)
    assert ids[0] not in [i["id"] for i in cut["items"]]
    with pytest.raises(ValueError):
        A.endpoint_plan(as_of="nope", league_type="both", exclude_ids=[], limit=8, now=F.NOW)
    with pytest.raises(ValueError):
        A.endpoint_plan(as_of=None, league_type="x", exclude_ids=[], limit=8, now=F.NOW)


def test_plan_all_excluded_is_unavailable_with_reason():
    ids = [i["id"] for i in A.endpoint_plan(as_of="2026-12-15", league_type="both", exclude_ids=[], limit=20, now=F.NOW)["items"]]
    out = A.endpoint_plan(as_of="2026-12-15", league_type="both", exclude_ids=ids, limit=8, now=F.NOW)
    _assert_contract(out)
    assert out["status"] == "unavailable"


# --- playoff SOS ------------------------------------------------------------


def test_playoff_sos_ranks_easiest_schedule_first_and_carries_evidence():
    items = A.build_playoff_sos(F.games(), F.DEFENSE, season=2026, weeks=[15, 16, 17], now=F.NOW, defense_as_of=A._iso(F.NOW))
    by_team = {i["team"]: i for i in items}
    # AAA: wk15 CCC(avg), wk16 BBB(weak), wk17 bye; CCC: AAA(tough)+BBB(weak)
    assert by_team["AAA"]["opponents"][2] == {"week": 17, "opponent": None, "is_home": None, "bye": True}
    assert by_team["AAA"]["by_position"]["WR"]["avg_points_allowed"] == pytest.approx(32.5)
    assert by_team["AAA"]["by_position"]["WR"]["rank_easiest"] == 1
    assert by_team["BBB"]["by_position"]["WR"]["rank_easiest"] == 3  # sees tough AAA + average CCC
    assert by_team["AAA"]["by_position"]["WR"]["vs_league_avg_pct"] > 0
    assert all(i["evidence"] for i in items)


def test_playoff_sos_without_defense_or_games_is_empty_not_invented():
    assert A.build_playoff_sos(F.games(), {}, season=2026, weeks=[15], now=F.NOW, defense_as_of=None) == []
    assert A.build_playoff_sos(F.games().iloc[0:0], F.DEFENSE, season=2026, weeks=[15], now=F.NOW, defense_as_of=None) == []


def test_playoff_sos_low_sample_lowers_confidence():
    d = {t: {p: {**v, "games_sampled": 2} for p, v in pos.items()} for t, pos in F.DEFENSE.items()}
    items = A.build_playoff_sos(F.games(), d, season=2026, weeks=[15, 16, 17], now=F.NOW, defense_as_of=None)
    assert {i["confidence"] for i in items} == {"low"}


def test_playoff_sos_endpoint_validates_and_reports_unavailable(monkeypatch):
    monkeypatch.setattr(A, "load_games", lambda: F.games())
    monkeypatch.setattr(A, "load_defense", lambda season: {})
    out = A.endpoint_playoff_sos(season=2026, start_week=15, end_week=17, position=None, limit=None, now=F.NOW)
    _assert_contract(out)
    assert out["status"] == "unavailable"
    for bad in ({"start_week": 17, "end_week": 15}, {"start_week": 10, "end_week": 17}, {"position": "K"}):
        kwargs = {"season": 2026, "start_week": 15, "end_week": 17, "position": None, "limit": None, **bad}
        with pytest.raises(ValueError):
            A.endpoint_playoff_sos(now=F.NOW, **kwargs)


# --- waivers ----------------------------------------------------------------


def test_waiver_replacements_pair_injured_starter_with_healthy_trending_adds():
    items = A.build_waiver_replacements(F.BOARD, F.TRENDING, F.ROSTER_PCT, now=F.NOW, board_as_of=F.BOARD_AS_OF)
    assert [i["injured_player"]["player_id"] for i in items] == ["100"]
    reps = items[0]["replacements"]
    assert [r["player_id"] for r in reps] == ["101", "102"]  # RB 103 is the wrong position
    assert reps[0]["same_team"] is True and reps[0]["availability_verified"] is True
    assert items[0]["confidence"] == "medium"


def test_waiver_replacements_drop_widely_rostered_and_downgrade_without_roster_pct():
    items = A.build_waiver_replacements(F.BOARD, F.TRENDING, {"101": {"current": 80.0}, "102": {"current": 31.5}}, now=F.NOW, board_as_of=None)
    assert [r["player_id"] for r in items[0]["replacements"]] == ["102"]
    no_pct = A.build_waiver_replacements(F.BOARD, F.TRENDING, {}, now=F.NOW, board_as_of=None)
    assert no_pct[0]["confidence"] == "low" and not no_pct[0]["replacements"][0]["availability_verified"]


def test_waiver_endpoint_unavailable_outside_regular_season(monkeypatch):
    monkeypatch.setattr(A, "load_board", lambda db, fmt: (F.BOARD, F.BOARD_AS_OF))
    monkeypatch.setattr(A, "clock_info", lambda today=None: {"season": 2026, "phase": "offseason", "week": None, "source": "calendar"})
    out = A.endpoint_waiver_replacements(db_path="x", fmt="superflex", limit=5, now=F.NOW)
    _assert_contract(out)
    assert out["status"] == "unavailable" and "offseason" in out["unavailable_reason"]


# --- lineup decisions -------------------------------------------------------


def test_lineup_decisions_flag_only_borderline_players_with_real_gaps():
    matchups = A.week_matchups(F.games(), 2026, 16)  # BBB hosts AAA
    board = F.BOARD + [dict(F.BOARD[3], player_id="200", name="Gil Flex", team="BBB", position_rank=24)]
    items = A.build_lineup_decisions(board, matchups, F.DEFENSE, season=2026, week=16, now=F.NOW, board_as_of=F.BOARD_AS_OF)
    verdicts = {i["player"]["player_id"]: i["verdict"] for i in items}
    # AAA players face weak BBB -> start; BBB RBs face tough AAA -> sit. The injured WR1, the out-of-band
    # rookie and CCC (no game that week) never appear.
    assert verdicts == {"101": "start", "103": "start", "104": "sit", "200": "sit"}
    assert all(i["confidence"] in ("low", "medium") for i in items)


def test_lineup_decisions_skip_injured_byes_and_unrated_opponents():
    matchups = A.week_matchups(F.games(), 2026, 16)
    hurt = [dict(r, injury_status="Out") for r in F.BOARD]
    assert A.build_lineup_decisions(hurt, matchups, F.DEFENSE, season=2026, week=16, now=F.NOW, board_as_of=None) == []
    assert A.build_lineup_decisions(F.BOARD, {}, F.DEFENSE, season=2026, week=16, now=F.NOW, board_as_of=None) == []
    assert A.build_lineup_decisions(F.BOARD, matchups, {}, season=2026, week=16, now=F.NOW, board_as_of=None) == []


def test_lineup_endpoint_offseason_reason(monkeypatch):
    monkeypatch.setattr(A, "load_board", lambda db, fmt: (F.BOARD, F.BOARD_AS_OF))
    monkeypatch.setattr(A, "clock_info", lambda today=None: {"season": 2026, "phase": "offseason", "week": None, "source": "calendar"})
    out = A.endpoint_lineup_decisions(db_path="x", fmt="1qb", week=None, season=None, limit=5, now=F.NOW)
    _assert_contract(out)
    assert out["status"] == "unavailable" and "regular-season week" in out["unavailable_reason"]


# --- value changes ----------------------------------------------------------


def test_value_changes_split_risers_and_fallers_and_ignore_small_moves():
    items = A.build_value_changes(F.LATEST_RATINGS, F.BASELINE_RATINGS, F.BOARD, latest_date="2026-12-07", baseline_date="2026-11-30", now=F.NOW)
    got = {i["player"]["player_id"]: (i["direction"], i["rating_delta"]) for i in items}
    assert got == {"101": ("riser", 8), "103": ("faller", -5)}  # +1 / -1 / 0 / unmatched ignored
    assert items[0]["window"]["span_days"] == 7


def test_value_changes_endpoint_unavailable_when_history_building(monkeypatch):
    monkeypatch.setattr(A, "load_board", lambda db, fmt: (F.BOARD, F.BOARD_AS_OF))
    monkeypatch.setattr(A, "load_rating_snapshots", lambda days: {"reason": "history is still building"})
    out = A.endpoint_value_changes(db_path="x", fmt="superflex", days=7, limit=5, now=F.NOW)
    _assert_contract(out)
    assert out["unavailable_reason"] == "history is still building"
    with pytest.raises(ValueError):
        A.endpoint_value_changes(db_path="x", fmt="superflex", days=2, limit=5, now=F.NOW)


# --- prepared capabilities --------------------------------------------------


def test_rookies_carry_adp_landing_spot_and_honest_nulls():
    items = A.build_rookies(F.BOARD, F.ROOKIE_ADP, F.SLEEPER_PLAYERS, now=F.NOW, board_as_of=F.BOARD_AS_OF)
    by = {i["player"]["player_id"]: i for i in items}
    assert [i["our_rank"] for i in items] == [1, 2] and set(by) == {"105", "106"}
    assert by["105"]["adp"] == 4.5 and by["105"]["landing_spot"]["depth_chart_order"] == 2
    assert by["106"]["adp"] is None and by["106"]["confidence"] == "low"
    assert by["105"]["draft_capital"] is None and by["105"]["draft_capital_unavailable_reason"]


def test_rookies_endpoint_unavailable_without_rookies(monkeypatch):
    monkeypatch.setattr(A, "load_board", lambda db, fmt: ([r for r in F.BOARD if r["years_exp"] != 0], F.BOARD_AS_OF))
    monkeypatch.setattr(A, "load_rookie_adp", lambda: {})
    monkeypatch.setattr(A, "load_sleeper_players", lambda: {})
    out = A.endpoint_rookies(db_path="x", fmt="superflex", limit=5, now=F.NOW)
    _assert_contract(out)
    assert out["status"] == "unavailable" and "No rookies" in out["unavailable_reason"]


def test_depth_chart_changes_and_team_changes_unavailable(monkeypatch):
    items = A.build_depth_chart_changes(F.DEPTH_SNAPSHOTS, F.BOARD, now=F.NOW)
    assert [(i["player"]["player_id"], i["direction"]) for i in items] == [("103", "up")]
    assert A.build_depth_chart_changes({"2026-W49": {"103": 1}}, F.BOARD, now=F.NOW) == []
    monkeypatch.setattr(A, "load_board", lambda db, fmt: (F.BOARD, F.BOARD_AS_OF))
    monkeypatch.setattr(A, "load_depth_snapshots", lambda: F.DEPTH_SNAPSHOTS)
    out = A.endpoint_changes(db_path="x", fmt="superflex", limit=5, now=F.NOW)
    _assert_contract(out)
    assert out["sections"]["team_changes"]["status"] == "unavailable" and out["sections"]["team_changes"]["unavailable_reason"]


def test_roster_construction_is_structured_unavailable():
    out = A.endpoint_roster_construction(now=F.NOW)
    _assert_contract(out)
    assert out["status"] == "unavailable" and "no user or league data" in out["unavailable_reason"]


# --- demos ------------------------------------------------------------------


def test_demo_scenarios_are_deterministic_and_labelled_synthetic():
    a = A.endpoint_demo_scenarios(scenario_type=None, now=F.NOW)
    b = A.endpoint_demo_scenarios(scenario_type=None, now=F.NOW)
    assert a == b
    _assert_contract(a)
    assert all(i["synthetic"] for i in a["items"]) and a["disclaimer"]
    assert [i["verdict"] for i in a["items"]] == ["Start Demo Runner A", "Claim Demo Receiver Y", "Accept"]
    assert all("utm_source=desktop_ad_app" in v for i in a["items"] for v in i["links"].values())
    assert [i["scenario_type"] for i in A.endpoint_demo_scenarios(scenario_type="trade", now=F.NOW)["items"]] == ["trade"]
    with pytest.raises(ValueError):
        A.endpoint_demo_scenarios(scenario_type="nope")


def test_demo_scenarios_carry_matching_try_urls_with_utm_convention():
    out = A.endpoint_demo_scenarios(scenario_type=None, now=F.NOW)
    by_type = {i["scenario_type"]: i for i in out["items"]}
    assert "/try/start-sit?" in by_type["start_sit"]["try_url"]
    assert "/try/waivers?" in by_type["waiver_claim"]["try_url"] and "/try/trade?" in by_type["trade"]["try_url"]
    for item in out["items"]:
        assert "try" not in item["links"]  # links keep their original desktop_ad_app convention
        assert "utm_source=ad_app" in item["try_url"] and f"utm_content={item['id']}" in item["try_url"]
        # additive: the original links are untouched
        assert "utm_source=desktop_ad_app" in item["links"]["sample_league"]
    assert {t["topic"] for t in out["try_links"]} == {"start-sit", "trade", "waivers", "playoffs", "dynasty-values"}
    custom = A.endpoint_demo_scenarios(
        scenario_type="trade", now=F.NOW,
        utm={"utm_medium": "paid_social", "utm_campaign": "Trade Check!", "utm_content": "vid_12", "utm_term": "", "utm_source": "evil"},
    )
    url = custom["items"][0]["try_url"]
    assert "utm_source=ad_app" in url and "utm_medium=paid_social" in url and "utm_campaign=tradecheck" in url
    assert "utm_content=vid_12" in url and "evil" not in url and "utm_term" not in url
    assert all("utm_campaign=tradecheck" in t["url"] for t in custom["try_links"])


# --- routes: auth, validation, byte-compat -----------------------------------


@pytest.fixture
def client(monkeypatch):
    from fastapi.testclient import TestClient

    from services import mobile_api_service as svc

    monkeypatch.setenv(svc.EXTERNAL_API_KEY_ENV, "k")
    monkeypatch.setattr(A, "load_board", lambda db, fmt: (F.BOARD, F.BOARD_AS_OF))
    monkeypatch.setattr(A, "load_games", lambda: F.games())
    monkeypatch.setattr(A, "load_defense", lambda season: F.DEFENSE)
    return TestClient(svc.app)


ROUTES = [
    "/v1/external/promo/plan", "/v1/external/playoff-sos", "/v1/external/waivers/replacements",
    "/v1/external/lineup/decisions", "/v1/external/dynasty/value-changes", "/v1/external/rookies",
    "/v1/external/changes", "/v1/external/dynasty/roster-construction", "/v1/external/demo/scenarios",
]


@pytest.mark.parametrize("path", ROUTES)
def test_routes_require_the_external_api_key(client, path):
    assert client.get(path).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get(path, headers={"Authorization": "Bearer k"}).status_code == 200


def test_route_validation_is_422_and_playoff_sos_serves_fixture(client):
    h = {"Authorization": "Bearer k"}
    assert client.get("/v1/external/promo/plan", params={"league_type": "x"}, headers=h).status_code == 422
    assert client.get("/v1/external/waivers/replacements", params={"format": "x"}, headers=h).status_code == 422
    assert client.get("/v1/external/demo/scenarios", params={"type": "x"}, headers=h).status_code == 422
    passthrough = client.get("/v1/external/demo/scenarios", params={"type": "trade", "utm_campaign": "spring_ads"}, headers=h).json()
    assert "utm_campaign=spring_ads" in passthrough["items"][0]["try_url"]
    body = client.get("/v1/external/playoff-sos", params={"season": 2026}, headers=h).json()
    _assert_contract(body)
    assert body["status"] == "ok" and {i["team"] for i in body["items"]} == {"AAA", "BBB", "CCC"}


def test_existing_external_routes_are_unchanged():
    from services import mobile_api_service as svc

    paths = {r.path for r in svc.app.routes}
    for legacy in (
        "/v1/external/players/{player_id}/projections", "/v1/external/projections", "/v1/external/players/{player_id}/news",
        "/v1/external/news", "/v1/external/players/{player_id}/rating-history", "/v1/external/players/{player_id}/background",
        "/v1/external/players/{player_id}/week-result", "/v1/external/recap", "/v1/external/trades/interesting",
        "/v1/external/trades/interesting/{item_id}/share-card.png",
    ):
        assert legacy in paths


def test_module_reads_no_user_data():
    src = (REPO / "modules" / "external_ad_api.py").read_text()
    for banned in ("require_user", "account_store", "load_players", "build_players_table", "billing", "premium"):
        assert banned not in src


# --- docs drift -------------------------------------------------------------


def test_docs_examples_match_generated_output():
    import importlib.util

    spec = importlib.util.spec_from_file_location("gen_ad_examples", REPO / "scripts" / "generate_external_ad_examples.py")
    G = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(G)

    doc = (REPO / "docs" / "external-api-contract.md").read_text()
    for name, payload in G.examples().items():
        block = f"<!-- example:{name} -->\n```json\n{json.dumps(payload, indent=2)}\n```\n<!-- /example:{name} -->"
        assert block in doc, f"docs example {name} is stale; run scripts/generate_external_ad_examples.py --write"


def test_every_new_route_is_documented():
    doc = (REPO / "docs" / "external-api-contract.md").read_text()
    for path in ROUTES:
        assert path in doc


# --- public playoff SOS projection -------------------------------------------


def test_public_playoff_sos_is_a_trimmed_projection_and_never_caches_empty(monkeypatch):
    from modules import public_playoff_sos as P

    P._cache.clear()
    monkeypatch.setattr(A, "load_games", lambda: F.games())
    monkeypatch.setattr(A, "load_defense", lambda season: F.DEFENSE)
    monkeypatch.setattr(A, "_team_aliases", lambda: {})
    out = P.get_public_playoff_sos(season=2026, now=F.NOW)
    assert out["status"] == "ok" and out["count"] == len(out["teams"]) > 0
    team = out["teams"][0]
    assert set(team) == {"team", "confidence", "opponents", "by_position"}
    assert not {"evidence", "relevance", "freshness"} & set(team)
    assert out["weeks"] == [15, 16, 17]
    assert P._cache  # cached when it has teams

    P._cache.clear()
    monkeypatch.setattr(A, "load_defense", lambda season: {})
    empty = P.get_public_playoff_sos(season=2026, now=F.NOW)
    assert empty["status"] == "unavailable" and empty["teams"] == [] and empty["unavailable_reason"]
    assert not P._cache
