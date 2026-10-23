"""Offline tests for modules.gsis_crosswalk and modules.news_evidence.

All players, URLs and article texts below are SYNTHETIC test fixtures, not
live data. HTTP is mocked; no network is touched.
"""

from __future__ import annotations

import hashlib

import pandas as pd

from modules import external_news_contract as enc
from modules import gsis_crosswalk as gx
from modules import news_evidence as ne

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


def _policies(status=ne.PERMITTED, excerpt=True, official=False):
    return {
        "syn-official.example": ne.SourcePolicy(status, "synthetic", official, "injury_report", excerpt, 80, 0.0),
        "syn-a.example": ne.SourcePolicy(status, "synthetic", False, "article", excerpt, 80, 0.0),
        "syn-b.example": ne.SourcePolicy(status, "synthetic", False, "article", False, 0, 0.0),
    }


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


def _fetcher(pages, status=ne.PERMITTED, robots="User-agent: *\nAllow: /", enabled=True, **kw):
    http = FakeHttp(pages, robots)
    f = ne.EvidenceFetcher(http, policies=_policies(status, **kw), enabled=lambda: enabled, sleep=lambda s: None)
    return f, http


A = "https://syn-a.example/a"
B = "https://syn-b.example/b"
O = "https://syn-official.example/o"
BODY = b"<html><script>x()</script><p>Test Alpha (hamstring) is questionable for Sunday.</p></html>"


def test_flag_off_means_no_network():
    f, http = _fetcher({A: BODY}, enabled=False)
    r = f.fetch(A)
    assert not r.ok and r.reason == "evidence_fetch_disabled" and http.calls == []


def test_shipped_registry_has_no_permitted_source_and_nfl_is_blocked():
    assert all(p.status != ne.PERMITTED for p in ne.SOURCE_POLICIES.values())
    assert ne.SOURCE_POLICIES["nfl.com"].status == ne.NOT_PERMITTED
    http = FakeHttp({})
    f = ne.EvidenceFetcher(http, enabled=lambda: True, sleep=lambda s: None)
    r = f.fetch("https://www.nfl.com/injuries/")
    assert r.reason == "source_not_permitted" and http.calls == []
    r = f.fetch("https://www.espn.com/nfl/story/x")
    assert r.reason == "source_needs_human_review" and http.calls == []


def test_refuses_non_allowlisted_http_and_unreviewed():
    f, http = _fetcher({A: BODY})
    assert f.fetch("https://evil.example/x").reason == "domain_not_allowlisted"
    assert f.fetch("http://syn-a.example/a").reason == "scheme_not_https"
    f2, h2 = _fetcher({A: BODY}, status=ne.NEEDS_REVIEW)
    assert f2.fetch(A).reason == "source_needs_human_review" and h2.calls == []


def test_robots_disallow_and_failure_fail_closed():
    f, http = _fetcher({A: BODY}, robots="User-agent: *\nDisallow: /")
    assert f.fetch(A).reason == "robots_disallow_or_unknown"
    assert [c[0] for c in http.calls] == ["https://syn-a.example/robots.txt"]

    def boom(url, headers, timeout):
        raise OSError("down")

    f2 = ne.EvidenceFetcher(boom, policies=_policies(), enabled=lambda: True, sleep=lambda s: None)
    assert f2.fetch(A).reason == "robots_disallow_or_unknown"


def test_fetch_hashes_exact_bytes_ua_timeout_and_original_url():
    f, http = _fetcher({A: BODY})
    r = f.fetch(A, original_url="https://orig.example/story")
    assert r.ok
    assert r.record["content_sha256"] == hashlib.sha256(BODY).hexdigest()
    assert r.record["original_url"] == "https://orig.example/story"
    assert r.record["retrieved_url"] == A and isinstance(r.record["checked_at"], int)
    page_call = [c for c in http.calls if c[0] == A][0]
    assert "FantasyDesk" in page_call[1]["User-Agent"] and page_call[2] == ne.FETCH_TIMEOUT_S
    assert "x()" not in r.text and "questionable" in r.text


def test_rate_limit_sleeps_between_same_host_fetches():
    sleeps, now = [], [100.0]
    http = FakeHttp({A: BODY})
    pol = {"syn-a.example": ne.SourcePolicy(ne.PERMITTED, "s", min_interval_s=5.0)}
    f = ne.EvidenceFetcher(http, policies=pol, enabled=lambda: True, clock=lambda: now[0], sleep=sleeps.append)
    f.fetch(A)
    f.fetch(A)
    assert sleeps and 4.9 < sleeps[0] <= 5.0


def test_non_200_bad_type_and_oversize():
    f, _ = _fetcher({A: BODY})
    assert f.fetch("https://syn-a.example/missing").reason == "http_404"
    f2 = ne.EvidenceFetcher(lambda u, headers, timeout: (200, "text/plain", b"x" * (ne.MAX_BYTES + 1)) if not u.endswith("robots.txt") else (404, "", b""),
                            policies=_policies(), enabled=lambda: True, sleep=lambda s: None)
    assert f2.fetch(A).reason == "response_too_large"
    f3 = ne.EvidenceFetcher(lambda u, headers, timeout: (200, "image/png", b"x") if not u.endswith("robots.txt") else (404, "", b""),
                            policies=_policies(), enabled=lambda: True, sleep=lambda s: None)
    assert f3.fetch(A).reason == "unsupported_content_type"


# ------------------------------------------------------------ claim binding


def _item(status="reported", designation="questionable", extra_claims=()):
    claims = [
        {"id": "c_ev", "field": "event_type", "value": "INJURY", "status": "active", "source_ids": []},
        {"id": "c_des", "field": "availability_designation", "value": designation, "status": "active", "source_ids": []},
        *extra_claims,
    ]
    return {"id": "evt1", "player": {"name": "Test Alpha", "team": "HOU"}, "claims": claims, "status": status, "published_ts": 1_000}


def test_claim_requires_player_and_designation_in_same_sentence():
    claim = {"id": "c", "field": "availability_designation", "value": "questionable"}
    ok = ne.evaluate_claim(claim, "Test Alpha is questionable.", player_name="Test Alpha")
    assert ok["supported"]
    other = ne.evaluate_claim(claim, "Test Alpha practiced. Someone Else is questionable.", player_name="Test Alpha")
    assert not other["supported"] and other["reason"] == "designation_not_found_near_player"
    nobody = ne.evaluate_claim(claim, "A WR is questionable.", player_name="Test Alpha")
    assert nobody["reason"] == "player_not_in_document"
    wrong = ne.evaluate_claim({**claim, "value": "doubtful"}, "Test Alpha is questionable.", player_name="Test Alpha")
    assert not wrong["supported"]


def test_team_claim_needs_team_near_player():
    c = {"id": "t", "field": "team_affiliation", "value": "HOU"}
    assert ne.evaluate_claim(c, "Test Alpha of the Texans.", player_name="Test Alpha", team_names=["Texans"])["supported"]
    assert not ne.evaluate_claim(c, "Test Alpha of the Cowboys.", player_name="Test Alpha", team_names=["Texans"])["supported"]


def test_hash_alone_never_confirms_even_from_official_source():
    f, _ = _fetcher({O: b"<p>Weather report for Sunday. Nothing about injuries.</p>"}, official=True)
    out = ne.check_item(_item(), f, ne.EvidenceStore(), urls=[{"url": O}], now_ts=2_000)
    assert out["provenance"][0]["content_sha256"]
    assert out["status"] == "reported" and out["review_only"] is True
    assert all(not c["evidence_supported"] for c in out["claims"])
    assert out["evidence"]["status"] == "unavailable"


def test_official_matching_document_confirms_and_excerpt_is_capped():
    f, _ = _fetcher({O: BODY}, official=True)
    out = ne.check_item(_item(), f, ne.EvidenceStore(), urls=[{"url": O}], now_ts=2_000)
    assert out["status"] == "confirmed" and out["review_only"] is False
    assert {c["status"] for c in out["claims"]} == {"supported"}
    ex = out["provenance"][0]["excerpt"]
    assert ex and len(ex) <= 80
    assert not any(k.startswith("_") for k in out["provenance"][0])


def test_no_excerpt_when_policy_forbids():
    f, _ = _fetcher({O: BODY}, excerpt=False, official=True)
    out = ne.check_item(_item(), f, ne.EvidenceStore(), urls=[{"url": O}], now_ts=2_000)
    assert out["provenance"][0]["excerpt"] is None


def test_single_nonofficial_match_is_reported_not_confirmed():
    f, _ = _fetcher({A: BODY})
    out = ne.check_item(_item(), f, ne.EvidenceStore(), urls=[{"url": A}], now_ts=2_000)
    assert out["status"] == "reported" and {c["status"] for c in out["claims"]} == {"supported"}


def test_independent_corroboration_needs_distinct_origins():
    f, _ = _fetcher({A: BODY, B: BODY})
    same_origin = ne.check_item(
        _item(), f, ne.EvidenceStore(),
        urls=[{"url": A, "original_url": "https://orig.example/s"}, {"url": B, "original_url": "https://orig.example/s"}],
        now_ts=2_000,
    )
    assert same_origin["status"] == "reported"  # syndication of one origin counts once
    two = ne.check_item(_item(), f, ne.EvidenceStore(), urls=[{"url": A}, {"url": B}], now_ts=2_000)
    assert two["status"] == "confirmed"


def test_partial_support_is_not_confirmed():
    f, _ = _fetcher({O: BODY}, official=True)
    out = ne.check_item(_item(designation="doubtful"), f, ne.EvidenceStore(), urls=[{"url": O}], now_ts=2_000)
    assert out["status"] == "reported" and out["evidence"]["status"] == "partial"


def test_changed_hash_creates_new_revision_and_supersedes_prior():
    store = ne.EvidenceStore()
    f1, _ = _fetcher({A: BODY})
    r1 = ne.check_item(_item(), f1, store, urls=[{"url": A}], now_ts=2_000)
    r1b = ne.check_item(_item(), f1, store, urls=[{"url": A}], now_ts=2_001)
    assert r1["provenance"][0]["revision_id"] == r1b["provenance"][0]["revision_id"]
    f2, _ = _fetcher({A: BODY.replace(b"questionable", b"doubtful")})
    r2 = ne.check_item(_item(), f2, store, urls=[{"url": A}], now_ts=2_100)
    p = r2["provenance"][0]
    assert p["revision_id"] != r1["provenance"][0]["revision_id"]
    assert p["previous_revision_id"] == r1["provenance"][0]["revision_id"]
    assert p["prior_revision_status"] == "superseded"
    assert [c for c in r2["claims"] if c["field"] == "availability_designation"][0]["status"] == "active"  # no longer supported


def test_retraction_notice_flips_claims_to_retracted():
    store = ne.EvidenceStore()
    f1, _ = _fetcher({A: BODY})
    ne.check_item(_item(), f1, store, urls=[{"url": A}], now_ts=2_000)
    f2, _ = _fetcher({A: BODY + b"<p>Retraction: this article has been retracted.</p>"})
    r2 = ne.check_item(_item(), f2, store, urls=[{"url": A}], now_ts=2_100)
    assert r2["status"] == "retracted" and r2["retracted"] is True
    assert {c["status"] for c in r2["claims"]} == {"retracted"}
    assert r2["provenance"][0]["prior_revision_status"] == "retracted"
    assert r2["review_only"] is True


def test_freshness_urgent_vs_general_uses_checked_at():
    f, _ = _fetcher({A: BODY})
    out = ne.check_item(_item(), f, ne.EvidenceStore(), urls=[{"url": A}], now_ts=int(f._clock()) + 20 * 60)
    fr = out["freshness"]
    assert fr["class"] == "urgent_availability" and fr["max_checked_age_seconds"] == 900
    assert fr["checked_within_limit"] is False
    out2 = ne.check_item(_item(), f, ne.EvidenceStore(), urls=[{"url": A}], now_ts=int(f._clock()) + 60)
    assert out2["freshness"]["checked_within_limit"] is True


def test_check_item_unfetchable_is_honest():
    f, _ = _fetcher({}, enabled=False)
    out = ne.check_item(_item(), f, ne.EvidenceStore(), urls=[{"url": A}], now_ts=2_000)
    assert out["provenance"] == [] and out["status"] == "reported"
    assert out["evidence"]["status"] == "unavailable"
    assert out["evidence"]["reason_codes"] == [f"{A}:evidence_fetch_disabled"]
    assert out["freshness"]["checked_within_limit"] is None
