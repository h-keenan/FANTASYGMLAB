"""Data-truth audit (docs/audits/2026-11-data-truth.md, findings 1, 2 and 6): FantasyCalc cache freshness and parsing."""

import json
import os
import time

import pandas as pd
import pytest

from modules import data_freshness, fantasycalc

FLAG = fantasycalc.FRESH_CACHE_FLAG


class _Resp:
    status_code = 200

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


LIVE = [
    {"player": {"name": "Live One", "position": "WR", "maybeTeam": "DEN", "sleeperId": "11", "mflId": "21"}, "value": 8000, "overallRank": 1},
    {"player": {"name": "Zero Value", "position": "RB", "maybeTeam": "KC", "sleeperId": "12"}, "value": 0, "overallRank": 2},
    {"player": {"name": "Rank Only", "position": "TE", "maybeTeam": "SF", "sleeperId": "13"}, "overallRank": 3},
    {"player": {"name": "Legacy Team", "position": "QB", "team": "BUF", "sleeperId": "14"}, "value": 100},
]


@pytest.fixture
def seed(tmp_path, monkeypatch):
    """A July-style seed CSV that a fresh git checkout gives a brand new mtime."""

    path = str(tmp_path / "fantasycalc_values.csv")
    monkeypatch.setattr(fantasycalc, "FANTASYCALC_CACHE_PATH", path)
    pd.DataFrame([{"name": "Seed", "position": "WR", "team": "", "value": 9999}]).to_csv(path, index=False)
    return path


@pytest.fixture
def provider(monkeypatch):
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(args)
        return _Resp(LIVE)

    monkeypatch.setattr(fantasycalc.requests, "get", fake_get)
    return calls


def test_parse_fills_team_from_maybe_team_and_never_uses_rank_as_value(seed, provider, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    df = fantasycalc.get_dynasty_values()
    by_name = df.set_index("name")
    assert set(df["name"]) == {"Live One", "Legacy Team"}  # zero / missing value rows are dropped, not stored as their rank
    assert by_name.loc["Live One", "team"] == "DEN"
    assert by_name.loc["Legacy Team", "team"] == "BUF"
    assert by_name.loc["Live One", "value"] == 8000


def test_flag_off_keeps_legacy_mtime_ttl_and_serves_the_seed(seed, provider, monkeypatch):
    monkeypatch.delenv(FLAG, raising=False)
    df = fantasycalc.get_dynasty_values()
    assert list(df["name"]) == ["Seed"]
    assert provider == []  # the checkout mtime says "fresh": the provider is never asked (the audited bug)


def test_flag_on_refetches_a_seed_with_no_fetch_timestamp(seed, provider, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    df = fantasycalc.get_dynasty_values()
    assert "Live One" in set(df["name"])
    assert len(provider) == 1
    meta = json.load(open(fantasycalc.meta_path()))
    assert abs(meta["fetched_at"] - time.time()) < 60
    assert fantasycalc.fetched_at() == meta["fetched_at"]


def test_flag_on_serves_a_recently_fetched_cache_without_calling_the_provider(seed, provider, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    json.dump({"fetched_at": time.time() - 60}, open(fantasycalc.meta_path(), "w"))
    df = fantasycalc.get_dynasty_values()
    assert list(df["name"]) == ["Seed"]
    assert provider == []
    assert abs(df.attrs["as_of"] - (time.time() - 60)) < 5


def test_flag_on_old_fetch_timestamp_refetches_even_if_mtime_is_new(seed, provider, monkeypatch):
    monkeypatch.setenv(FLAG, "1")
    json.dump({"fetched_at": time.time() - 3 * fantasycalc.FANTASYCALC_CACHE_TTL_SECONDS}, open(fantasycalc.meta_path(), "w"))
    fantasycalc.get_dynasty_values()
    assert len(provider) == 1


def test_flag_on_provider_down_falls_back_to_seed_with_honest_as_of(seed, monkeypatch):
    monkeypatch.setenv(FLAG, "1")

    def boom(*a, **k):
        raise fantasycalc.requests.ConnectionError("down")

    monkeypatch.setattr(fantasycalc.requests, "get", boom)
    df = fantasycalc.get_dynasty_values()
    assert list(df["name"]) == ["Seed"]
    assert df.attrs["as_of"] == 0.0  # unknown provenance is reported as unknown, never as "just now"


def test_freshness_report_reads_the_fetch_timestamp_not_the_checkout_mtime(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    (data / "fantasycalc_values.csv").write_text("name,position,team,value\nA,WR,,1\n")
    monkeypatch.setenv(FLAG, "1")
    now = time.time()
    rows = {r["name"]: r for r in data_freshness.dataset_rows(now, str(data), True)}
    assert rows["values_fantasycalc"]["status"] == "warn"  # checkout mtime is "now", but nothing says it was ever fetched
    assert rows["values_fantasycalc"]["as_of"] is None
    (data / "fantasycalc_values.meta.json").write_text(json.dumps({"fetched_at": now - 40 * 3600}))
    rows = {r["name"]: r for r in data_freshness.dataset_rows(now, str(data), True)}
    assert rows["values_fantasycalc"]["status"] == "fail"  # 40h old vs the 30h in-season limit
    assert 39 < rows["values_fantasycalc"]["age_hours"] < 41
    assert rows["values_fantasycalc"]["as_of_source"] == "fetch_timestamp"


def test_freshness_report_unchanged_when_flag_off(tmp_path, monkeypatch):
    data = tmp_path / "data"
    data.mkdir()
    (data / "fantasycalc_values.csv").write_text("name,position,team,value\nA,WR,,1\n")
    monkeypatch.delenv(FLAG, raising=False)
    rows = {r["name"]: r for r in data_freshness.dataset_rows(time.time(), str(data), True)}
    assert rows["values_fantasycalc"]["status"] == "ok"
    assert rows["values_fantasycalc"]["as_of_source"] == "file_mtime"  # clients will not print an "as of" for this
    assert os.path.exists(data / "fantasycalc_values.csv")
