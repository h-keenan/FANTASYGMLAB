
from __future__ import annotations

import hashlib

import pandas as pd

from modules import external_news_contract as enc
from modules import gsis_crosswalk as gx

SYN = {
    "1": {"player_id": "1", "full_name": "Test Alpha", "team": "HOU", "position": "WR", "gsis_id": "00-0012345"},
    "2": {"player_id": "2", "full_name": "Test Beta", "team": "DAL", "position": "RB", "gsis_id": " 00-0012346 "},
    "3": {"player_id": "3", "full_name": "Test Gamma", "team": "NYG", "position": "TE", "gsis_id": "0012347"},
    "4": {"player_id": "4", "full_name": "Test Delta", "team": "SF", "position": "QB", "gsis_id": "00-0099999"},
    "5": {"player_id": "5", "full_name": "Test Eps", "team": "SF", "position": "QB", "gsis_id": "00-0099999"},
    "6": {"player_id": "6", "full_name": "Test Zeta", "team": "KC", "position": "WR"},
    "7": {"player_id": "7", "full_name": "Same Name", "team": "KC", "position": "WR", "gsis_id": "00-0000007"},
    "8": {"player_id": "8", "full_name": "Same Name Jr.", "team": "KC", "position": "WR", "gsis_id": "00-0000008"},
}


def test_crosswalk_reason_codes():
    cw = gx.build_gsis_crosswalk(SYN)
    assert cw.lookup("1") == ("00-0012345", None)
    assert cw.lookup("2") == ("00-0012346", None)  # whitespace trimmed, still well-formed
    assert cw.lookup("3") == (None, gx.R_MALFORMED)
    assert cw.lookup("4") == (None, gx.R_SHARED) and cw.lookup("5") == (None, gx.R_SHARED)
    assert cw.lookup("6") == (None, gx.R_NOT_MAPPED)
    assert cw.lookup("999") == (None, gx.R_NOT_IN_DUMP)


def test_canonical_match_requires_unique_triple():
    cw = gx.build_gsis_crosswalk(SYN)
    assert cw.lookup_canonical("test alpha", "hou", "wr") == ("00-0012345", "1", None)
    assert cw.lookup_canonical("Test Alpha", "DAL", "WR")[2] == gx.R_NOT_IN_DUMP
    assert cw.lookup_canonical("Same Name", "KC", "WR")[2] == gx.R_AMBIGUOUS  # suffix-normalised collision
    assert cw.lookup_canonical("Test Alpha", "", "WR")[2] == gx.R_NO_KEY


def test_flag_default_off(monkeypatch):
    monkeypatch.delenv(gx.FLAG_ENV, raising=False)
    assert gx.load_gsis_crosswalk() is None
    monkeypatch.setenv(gx.FLAG_ENV, "0")
    assert gx.load_gsis_crosswalk() is None


def _df():
    return pd.DataFrame(
        [
            {"player_id": "1", "name": "Test Alpha", "team": "HOU", "position": "WR"},
            {"player_id": "3", "name": "Test Gamma", "team": "NYG", "position": "TE"},
        ]
    )


def test_identity_uses_crosswalk_only_when_supplied():
    off = enc.resolve_player_identity(_df(), "1", "Test Alpha")
    assert off["player_ids"]["gsis"] is None
    assert off["player_ids"]["gsis_unavailable_reason"] == "no_gsis_crosswalk_available"
    on = enc.resolve_player_identity(_df(), "1", "Test Alpha", gsis_crosswalk=gx.build_gsis_crosswalk(SYN))
    assert on["player_ids"]["gsis"] == "00-0012345"
    bad = enc.resolve_player_identity(_df(), "3", "Test Gamma", gsis_crosswalk=gx.build_gsis_crosswalk(SYN))
    assert bad["player_ids"]["gsis"] is None and bad["player_ids"]["gsis_unavailable_reason"] == gx.R_MALFORMED


def test_identity_rejects_name_team_pointing_elsewhere():
    sw = dict(SYN)
    sw["10"] = {"player_id": "10", "full_name": "Test Alpha", "team": "HOU", "position": "WR", "gsis_id": "00-0055555"}
    cw = gx.build_gsis_crosswalk(sw)
    out = enc.resolve_player_identity(_df(), "1", "Test Alpha", gsis_crosswalk=cw)
    assert out["player_ids"]["gsis"] is None


# ------------------------------------------------------------------ fetch


class FakeHttp:
    def __init__(self, pages, robots="User-agent: *\nAllow: /"):
        self.pages, self.robots, self.calls = pages, robots, []

    def __call__(self, url, headers, timeout):
        self.calls.append((url, dict(headers), timeout))
        if url.endswith("/robots.txt"):
            return 200, "text/plain", self.robots.encode()
        if url not in self.pages:
            return 404, "text/html", b""
        return 200, "text/html; charset=utf-8", self.pages[url]


A = "https://syn-a.example/a"
B = "https://syn-b.example/b"
O = "https://syn-official.example/o"
BODY = b"<html><script>x()</script><p>Test Alpha (hamstring) is questionable for Sunday.</p></html>"


# ------------------------------------------------------------ claim binding


def _item(status="reported", designation="questionable", extra_claims=()):
    claims = [
        {"id": "c_ev", "field": "event_type", "value": "INJURY", "status": "active", "source_ids": []},
        {"id": "c_des", "field": "availability_designation", "value": designation, "status": "active", "source_ids": []},
        *extra_claims,
    ]
    return {"id": "evt1", "player": {"name": "Test Alpha", "team": "HOU"}, "claims": claims, "status": status, "published_ts": 1_000}
