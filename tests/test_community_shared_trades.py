"""Opt-in Community shared trades: sanitizing, endpoints, graceful degradation."""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from modules import community_shared_trades as cst

TRADE_ID = "11111111-2222-3333-4444-555555555555"
AUTH = {"Authorization": "Bearer good-token"}


def _client(monkeypatch):
    pytest.importorskip("httpx")
    from fastapi.testclient import TestClient

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-key-for-tests")
    from services import mobile_api_service

    return TestClient(mobile_api_service.app)


def _auth_response():
    response = Mock(status_code=200)
    response.json.return_value = {"id": "user-123", "email": "gm@example.com"}
    return response


def _body(**overrides):
    body = {
        "send": [{"asset_type": "player", "name": "Sender Guy", "position": "WR", "player_id": "100", "score": 70}],
        "receive": [{"asset_type": "pick", "name": "2027 1st", "label": "2027 1st"}],
        "grade": "accept",
        "band": "LEAN ACCEPT",
        "why": "Strong value gain at a position of need.",
        "display_name": "",
    }
    body.update(overrides)
    return body


# --- sanitizing ---------------------------------------------------------


def test_display_name_blank_means_anonymous_and_is_trimmed():
    assert cst.clean_display_name("  ") == ""
    assert cst.clean_display_name("anonymous") == ""
    assert cst.clean_display_name("  Coach   Z  ") == "Coach Z"
    assert len(cst.clean_display_name("x" * 200)) == cst.DISPLAY_NAME_MAX


@pytest.mark.parametrize("name", ["sh1t", "F.u.c.k", "visit www.spam.com", "me@mail.com"])
def test_display_name_rejects_profanity_links_and_emails(name):
    with pytest.raises(cst.ShareError):
        cst.clean_display_name(name)


def test_blocklist_does_not_flag_player_names():
    assert not cst.contains_blocked_language("Dickerson and Bucky Irving for Mike Evans")
    assert cst.clean_why("Dickerson is a fair return") == "Dickerson is a fair return"


def test_why_is_stripped_of_links_markup_and_capped_and_dropped_if_profane():
    assert "http" not in cst.clean_why("great https://x.co/abc deal <script>")
    assert "<" not in cst.clean_why("a <b>deal</b>")
    assert len(cst.clean_why("w" * 5000)) == cst.WHY_MAX
    assert cst.clean_why("this is shit") == ""


def test_build_share_row_validates_and_never_trusts_extra_fields():
    row = cst.build_share_row("user-1", {**_body(), "hidden": False, "report_count": 0, "user_id": "evil"})
    assert row["user_id"] == "user-1"
    assert row["grade"] == "ACCEPT"
    assert row["display_name"] is None
    assert set(row) == {"user_id", "display_name", "send", "receive", "grade", "band", "why"}
    assert row["receive"][0]["asset_type"] == "pick"
    with pytest.raises(cst.ShareError):
        cst.build_share_row("user-1", _body(send=[]))
    with pytest.raises(cst.ShareError):
        cst.build_share_row("user-1", _body(grade="GREAT"))


def test_assets_are_capped():
    assets = [{"name": f"P{i}"} for i in range(40)]
    assert len(cst.clean_assets(assets)) == cst.ASSET_MAX


def test_project_item_hides_user_id_and_defaults_to_anonymous():
    item = cst.project_item({"id": "t1", "user_id": "user-1", "display_name": None, "grade": "FAIR"}, "user-1")
    assert "user_id" not in item
    assert item["display_name"] == "Anonymous"
    assert item["mine"] is True
    assert cst.project_item({"id": "t1", "user_id": "user-2"}, "user-1")["mine"] is False


# --- endpoints ----------------------------------------------------------


def test_shared_trade_endpoints_require_auth(monkeypatch):
    client = _client(monkeypatch)
    assert client.get("/v1/community/shared-trades").status_code == 401
    assert client.post("/v1/community/shared-trades", json=_body()).status_code == 401
    assert client.delete(f"/v1/community/shared-trades/{TRADE_ID}").status_code == 401
    assert client.post(f"/v1/community/shared-trades/{TRADE_ID}/report", json={}).status_code == 401


def test_feed_degrades_to_unavailable_when_table_missing(monkeypatch):
    client = _client(monkeypatch)
    missing = Mock(status_code=404)
    missing.json.return_value = {"code": "PGRST205", "message": "Could not find the table"}
    with patch("requests.get", side_effect=[_auth_response(), missing]):
        response = client.get("/v1/community/shared-trades", headers=AUTH)
    assert response.status_code == 200
    assert response.json() == {"ok": True, "available": False, "trades": []}


def test_feed_returns_projected_rows_without_user_id(monkeypatch):
    client = _client(monkeypatch)
    rows = Mock(status_code=200)
    rows.json.return_value = [
        {
            "id": TRADE_ID,
            "user_id": "user-123",
            "display_name": "Coach Z",
            "send": [{"asset_type": "player", "name": "A"}],
            "receive": [{"asset_type": "player", "name": "B"}],
            "grade": "ACCEPT",
            "band": "LEAN ACCEPT",
            "why": "ok",
            "created_at": "2026-10-22T00:00:00Z",
            "hidden": False,
        },
        {"id": "hidden-one", "user_id": "x", "hidden": True},
    ]
    with patch("requests.get", side_effect=[_auth_response(), rows]) as mock_get:
        response = client.get("/v1/community/shared-trades", headers=AUTH)
    body = response.json()
    assert body["available"] is True
    assert [t["id"] for t in body["trades"]] == [TRADE_ID]
    assert body["trades"][0]["mine"] is True
    assert "user_id" not in body["trades"][0]
    assert "hidden=eq.false" in mock_get.call_args_list[1].args[0]


def test_share_inserts_own_sanitized_row(monkeypatch):
    client = _client(monkeypatch)
    recent = Mock(status_code=200)
    recent.json.return_value = []
    created = Mock(status_code=201)
    created.json.return_value = [{"id": TRADE_ID, "user_id": "user-123", "grade": "ACCEPT"}]
    with patch("requests.get", side_effect=[_auth_response(), recent]):
        with patch("requests.post", return_value=created) as mock_post:
            response = client.post("/v1/community/shared-trades", json=_body(display_name="  Coach  Z "), headers=AUTH)
    assert response.status_code == 200
    assert response.json()["ok"] is True
    posted = mock_post.call_args.kwargs["json"]
    assert posted["user_id"] == "user-123"
    assert posted["display_name"] == "Coach Z"
    assert "hidden" not in posted and "report_count" not in posted


def test_share_rejects_bad_name_and_bad_grade(monkeypatch):
    client = _client(monkeypatch)
    with patch("requests.get", return_value=_auth_response()):
        assert client.post("/v1/community/shared-trades", json=_body(display_name="shit"), headers=AUTH).status_code == 422
        assert client.post("/v1/community/shared-trades", json=_body(grade="WOW"), headers=AUTH).status_code == 422
        too_many = [{"name": f"P{i}"} for i in range(30)]
        assert client.post("/v1/community/shared-trades", json=_body(send=too_many), headers=AUTH).status_code == 422


def test_share_is_rate_limited_per_user(monkeypatch):
    client = _client(monkeypatch)
    recent = Mock(status_code=200)
    recent.json.return_value = [{"id": str(i)} for i in range(cst.SHARES_PER_HOUR)]
    with patch("requests.get", side_effect=[_auth_response(), recent]):
        with patch("requests.post") as mock_post:
            response = client.post("/v1/community/shared-trades", json=_body(), headers=AUTH)
    assert response.status_code == 429
    mock_post.assert_not_called()


def test_share_reports_unavailable_when_table_missing(monkeypatch):
    client = _client(monkeypatch)
    missing = Mock(status_code=404)
    missing.json.return_value = {}
    with patch("requests.get", side_effect=[_auth_response(), missing]):
        response = client.post("/v1/community/shared-trades", json=_body(), headers=AUTH)
    assert response.status_code == 200
    assert response.json()["ok"] is False
    assert response.json()["available"] is False


def test_delete_scopes_to_caller_and_validates_id(monkeypatch):
    client = _client(monkeypatch)
    with patch("requests.get", return_value=_auth_response()):
        assert client.delete("/v1/community/shared-trades/not-a-uuid;drop", headers=AUTH).status_code in {404, 422}
        with patch("requests.delete", return_value=Mock(status_code=204)) as mock_delete:
            response = client.delete(f"/v1/community/shared-trades/{TRADE_ID}", headers=AUTH)
    assert response.json() == {"ok": True}
    url = mock_delete.call_args.args[0]
    assert f"id=eq.{TRADE_ID}" in url and "user_id=eq.user-123" in url


def test_report_stores_one_report_per_user(monkeypatch):
    client = _client(monkeypatch)
    with patch("requests.get", return_value=_auth_response()):
        with patch("requests.post", return_value=Mock(status_code=201)) as mock_post:
            response = client.post(
                f"/v1/community/shared-trades/{TRADE_ID}/report", json={"reason": "spam <b>"}, headers=AUTH
            )
    assert response.json() == {"ok": True}
    assert mock_post.call_args.kwargs["json"] == {
        "trade_id": TRADE_ID,
        "reporter_id": "user-123",
        "reason": "spam b",
    }
    assert "resolution=ignore-duplicates" in mock_post.call_args.kwargs["headers"]["Prefer"]
    assert "community_shared_trade_reports" in mock_post.call_args.args[0]


def test_sql_hides_after_same_threshold_as_python():
    from pathlib import Path

    sql = (Path(__file__).resolve().parents[1] / "docs" / "supabase_community_trades.sql").read_text()
    assert f">= {cst.HIDE_AFTER_REPORTS}" in sql
    assert "enable row level security" in sql
