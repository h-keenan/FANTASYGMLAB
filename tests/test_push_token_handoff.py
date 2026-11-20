"""Push token handoff: one owner per device token (docs/audits/2026-11-push-token-handoff.md)."""

from __future__ import annotations

from unittest.mock import Mock, patch

from modules import experimental_graduation as eg
from modules import push_tokens

CFG = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
TOKEN = "ExponentPushToken[device1]"


def test_flag_registered_with_owner():
    row = eg.FLAG_REGISTRY[push_tokens.HANDOFF_FLAG]
    assert row["owner"] == "Zach" and row["default"] == "on"


def test_register_reowns_with_service_role_for_the_caller(monkeypatch):
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")
    monkeypatch.delenv(push_tokens.HANDOFF_FLAG, raising=False)
    with patch("requests.post", return_value=Mock(status_code=201)) as post:
        ok, _ = push_tokens.register_token(CFG, "jwt-b", user_id="user-b", expo_push_token=TOKEN, platform="ios")
    assert ok
    assert post.call_count == 1  # one atomic upsert, no delete-then-insert gap
    kwargs = post.call_args.kwargs
    assert kwargs["headers"]["Authorization"] == "Bearer svc"
    assert kwargs["json"]["user_id"] == "user-b"
    assert "on_conflict=expo_push_token" in post.call_args.args[0]


def test_register_flag_off_uses_user_jwt_only(monkeypatch):
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")
    monkeypatch.setenv(push_tokens.HANDOFF_FLAG, "0")
    with patch("requests.post", return_value=Mock(status_code=201)) as post:
        push_tokens.register_token(CFG, "jwt-b", user_id="user-b", expo_push_token=TOKEN)
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer jwt-b"


def test_register_without_service_key_falls_back_to_jwt(monkeypatch):
    monkeypatch.delenv(push_tokens.HANDOFF_FLAG, raising=False)
    monkeypatch.setattr("modules.app_config.config_value", lambda key, **kw: "")
    with patch("requests.post", return_value=Mock(status_code=201)) as post:
        ok, _ = push_tokens.register_token(CFG, "jwt-b", user_id="user-b", expo_push_token=TOKEN)
    assert ok and post.call_args.kwargs["headers"]["Authorization"] == "Bearer jwt-b"


def test_service_reown_retries_without_unapplied_timezone_column(monkeypatch):
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")
    with patch("requests.post", side_effect=[Mock(status_code=400), Mock(status_code=201)]) as post:
        ok, _ = push_tokens.register_token(CFG, "jwt", user_id="u", expo_push_token=TOKEN, timezone="America/Chicago")
    assert ok
    assert "timezone" in post.call_args_list[0].kwargs["json"]
    assert "timezone" not in post.call_args_list[1].kwargs["json"]


def test_unregister_is_scoped_to_the_caller_and_never_service_role(monkeypatch):
    # A unregistering B's token: the user_id filter plus delete RLS remove only rows A owns.
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "svc")
    with patch("requests.delete", return_value=Mock(status_code=204)) as delete:
        push_tokens.unregister_token(CFG, "jwt-a", user_id="user-a", expo_push_token=TOKEN)
    url = delete.call_args.args[0]
    assert "user_id=eq.user-a" in url and "expo_push_token=eq.ExponentPushToken[device1]" in url
    assert delete.call_args.kwargs["headers"]["Authorization"] == "Bearer jwt-a"


def test_senders_drop_a_token_whose_owner_differs(monkeypatch):
    monkeypatch.delenv(push_tokens.HANDOFF_FLAG, raising=False)
    rows = [
        {"user_id": "user-a", "expo_push_token": TOKEN, "updated_at": "2026-11-01T00:00:00Z"},
        {"user_id": "user-b", "expo_push_token": TOKEN, "updated_at": "2026-11-02T00:00:00Z"},
        {"user_id": "user-a", "expo_push_token": "ExponentPushToken[other]", "updated_at": "2026-11-01T00:00:00Z"},
    ]
    out = push_tokens.owned_recipients(rows)
    assert out == {"user-b": [TOKEN], "user-a": ["ExponentPushToken[other]"]}


def test_fetch_push_recipients_uses_owner_filter(monkeypatch):
    from modules import push_triggers

    cfg = push_triggers.PushTriggerConfig(url="https://example.supabase.co", service_role_key="svc")
    rows = [
        {"user_id": "user-a", "expo_push_token": TOKEN, "updated_at": "2026-11-01T00:00:00Z"},
        {"user_id": "user-b", "expo_push_token": TOKEN, "updated_at": "2026-11-02T00:00:00Z"},
    ]
    resp = Mock(status_code=200)
    resp.json.return_value = rows
    with patch("requests.get", return_value=resp):
        assert push_triggers.fetch_push_recipients(cfg) == {"user-b": [TOKEN]}


def test_owner_filter_off_passes_rows_through(monkeypatch):
    monkeypatch.setenv(push_tokens.HANDOFF_FLAG, "0")
    rows = [
        {"user_id": "user-a", "expo_push_token": TOKEN},
        {"user_id": "user-b", "expo_push_token": TOKEN},
    ]
    assert push_tokens.owned_recipients(rows) == {"user-a": [TOKEN], "user-b": [TOKEN]}
