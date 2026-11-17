"""College prospect ingest: parsing, idempotent upsert, no-delete, retirement, freshness."""

from __future__ import annotations

import datetime as dt
import inspect
import json
import time

import pytest
import requests

from modules import college_prospect_ingest as ing
from modules import data_freshness

STATS = [
    {"playerId": 1, "category": "passing", "statType": "YDS", "stat": "2400"},
    {"playerId": 2, "category": "passing", "statType": "YDS", "stat": "40"},
    {"playerId": 3, "category": "receiving", "statType": "YDS", "stat": 800},
    {"playerId": 4, "category": "rushing", "statType": "ATT", "stat": 900},
    {"playerId": 5, "category": "rushing", "statType": "YDS", "stat": 900},
    {"playerId": 6, "category": "receiving", "statType": "YDS", "stat": 900},
]
ROSTER = [
    {"id": 1, "firstName": "Arch", "lastName": "Manning", "team": "Texas", "position": "QB", "year": 3},
    {"id": 2, "firstName": "Backup", "lastName": "Guy", "team": "Texas", "position": "QB", "year": 4},
    {"id": 3, "firstName": "Sophie", "lastName": "Moore", "team": "Texas", "position": "WR", "year": 2},
    {"id": 5, "firstName": "Lineman", "lastName": "Joe", "team": "Texas", "position": "OL", "year": 4},
    {"id": 6, "firstName": "Fresh", "lastName": "Man", "team": "Texas", "position": "WR", "year": 1},
]


def test_production_gate_and_roster_parsing():
    producers = ing.parse_production(STATS)
    assert producers == {"1", "3", "5", "6"}
    rows = ing.parse_roster(ROSTER, season=2026, producers=producers, draft_years=(2027, 2028))
    got = {(r["name"], r["draft_year"]) for r in rows}
    # junior -> 2027, sophomore -> 2028; walk-on, OL and a true freshman (2029) excluded
    assert got == {("Arch Manning", 2027), ("Sophie Moore", 2028)}


def test_season_and_class_years():
    assert ing.college_season(dt.date(2026, 11, 17)) == 2026
    assert ing.college_season(dt.date(2027, 3, 1)) == 2026
    assert ing.target_draft_years(2026) == (2027, 2028)
    assert ing.draft_year_for(4, 2026) == 2027 and ing.draft_year_for(1, 2026) == 2029


def test_reconcile_reuses_existing_ids_and_cites_source():
    cands = [{"name": "Arch Manning", "position": "QB", "school": "Texas", "draft_year": 2027, "cfbd_id": "1"},
             {"name": "New Guy", "position": "RB", "school": "Ohio State", "draft_year": 2028, "cfbd_id": "9"}]
    existing = [{"id": "2027-arch-manning-texas", "name": "Arch Manning", "school": "Texas", "draft_year": 2027}]
    rows = ing.reconcile(cands, existing, season=2026, now_iso="2026-11-17T00:00:00+00:00")
    by = {r["name"]: r for r in rows}
    assert by["Arch Manning"]["id"] == "2027-arch-manning-texas"
    assert by["New Guy"]["id"] == "2028-new-guy-ohio-state"
    assert all(r["source"] and r["source_url"].startswith("https://collegefootballdata.com/") for r in rows)


def test_payload_base_vs_extended():
    row = {"id": "a", "name": "A", "position": "QB", "school": "S", "draft_year": 2027, "source": "x", "source_url": "u", "ingested_at": "t", "junk": 1}
    assert set(ing.build_payload([row], extended=False)[0]) == set(ing.BASE_COLUMNS)
    assert set(ing.build_payload([row], extended=True)[0]) == set(ing.BASE_COLUMNS + ing.EXTENDED_COLUMNS)


class _Resp:
    def __init__(self, code=200, body=None):
        self.status_code, self._body = code, body

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(response=self)

    def json(self):
        return self._body


def test_upsert_is_merge_on_id_and_falls_back_without_migration(monkeypatch):
    calls = []

    def fake_post(url, headers=None, data=None, timeout=None):
        calls.append((url, headers, json.loads(data)))
        return _Resp(400 if "source" in json.loads(data)[0] else 200)

    monkeypatch.setattr(ing.requests, "post", fake_post)
    row = {"id": "a", "name": "A", "position": "QB", "school": "S", "draft_year": 2027, "source": "x", "source_url": "u", "ingested_at": "t"}
    sent, extended = ing.upsert_with_fallback("https://p.supabase.co", "k", [row])
    assert (sent, extended) == (1, False)
    assert all("on_conflict=id" in c[0] and "merge-duplicates" in c[1]["Prefer"] for c in calls)
    assert "source" not in calls[-1][2][0]


def test_no_delete_anywhere(monkeypatch):
    src = inspect.getsource(ing)
    assert "requests.delete" not in src and "method=\"DELETE\"" not in src and ".delete(" not in src
    monkeypatch.setattr(ing.requests, "delete", lambda *a, **k: pytest.fail("delete called"), raising=False)


PICKS_CSV = (
    "season,round,pick,team,gsis_id,pfr_player_name,position\n"
    "2027,1,3,NYJ,00-0099999,Arch Manning,QB\n"
    "2027,2,40,DEN,00-0088888,Other Guy,WR\n"
    "2027,7,250,KC,00-0077777,Sophie Moore,CB\n"
)


def test_retirement_mapping():
    picks = ing.parse_draft_picks(PICKS_CSV)
    prospects = [
        {"id": "p1", "name": "Arch Manning", "position": "QB", "school": "Texas", "draft_year": 2027, "drafted": False},
        {"id": "p2", "name": "Sophie Moore", "position": "WR", "school": "Texas", "draft_year": 2027},  # CB pick: position mismatch
        {"id": "p3", "name": "Arch Manning", "position": "QB", "school": "Texas", "draft_year": 2028},  # wrong year
        {"id": "p4", "name": "Already Done", "position": "QB", "school": "X", "draft_year": 2027, "drafted": True},
    ]
    ups = ing.map_retirements(prospects, picks, sleeper_by_gsis={"00-0099999": "12345"})
    assert len(ups) == 1
    u = ups[0]
    assert (u["id"], u["drafted"], u["nfl_team"], u["draft_round"], u["draft_pick"], u["nfl_gsis_id"], u["sleeper_player_id"]) == ("p1", True, "NYJ", 1, 3, "00-0099999", "12345")


def test_run_skips_cleanly_without_cfbd_key(monkeypatch):
    monkeypatch.setattr(ing.requests, "get", lambda *a, **k: (_ for _ in ()).throw(requests.ConnectionError()))
    status = ing.run(environ={"SUPABASE_URL": "https://p.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "k"}, today=dt.date(2026, 11, 16))
    assert status["classes"]["status"] == "skipped_no_key"


def test_run_requires_supabase():
    assert ing.run(environ={})["ok"] is False


def _write_status(tmp_path, **over):
    status = {"ran_at": dt.datetime.fromtimestamp(time.time() - 3600, dt.timezone.utc).isoformat(), "ok": True, "classes": {"status": "ok"}}
    status.update(over)
    (tmp_path / data_freshness.COLLEGE_PROSPECTS_STATUS_FILE).write_text(json.dumps(status))


def test_freshness_entry(tmp_path):
    now = time.time()
    assert data_freshness.college_prospects_row(now, str(tmp_path), True)["status"] == "warn"  # not run yet
    _write_status(tmp_path)
    assert data_freshness.college_prospects_row(now, str(tmp_path), True)["status"] == "ok"
    _write_status(tmp_path, classes={"status": "empty"}, ok=False)
    assert data_freshness.college_prospects_row(now, str(tmp_path), True)["status"] == "fail"
    _write_status(tmp_path, ran_at=dt.datetime.fromtimestamp(now - 24 * 12 * 3600, dt.timezone.utc).isoformat())
    assert data_freshness.college_prospects_row(now, str(tmp_path), True)["status"] == "fail"
    report = data_freshness.build_report(now, str(tmp_path))
    assert "college_prospects" in {r["name"] for r in report["datasets"]}
