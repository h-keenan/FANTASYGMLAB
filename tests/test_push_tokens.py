"""modules.push_tokens — registration validation and Expo push delivery."""

from __future__ import annotations

from unittest.mock import Mock, patch

from modules import push_tokens


def test_is_expo_push_token_accepts_expo_format_only():
    assert push_tokens.is_expo_push_token("ExponentPushToken[abc123]")
    assert push_tokens.is_expo_push_token("ExpoPushToken[abc123]")
    assert not push_tokens.is_expo_push_token("not-a-token")
    assert not push_tokens.is_expo_push_token("")
    assert not push_tokens.is_expo_push_token(None)


def test_normalize_platform_only_accepts_known_values():
    assert push_tokens.normalize_platform("ios") == "ios"
    assert push_tokens.normalize_platform("ANDROID") == "android"
    assert push_tokens.normalize_platform("web") == ""
    assert push_tokens.normalize_platform(None) == ""


def test_register_token_rejects_malformed_token_without_a_network_call():
    with patch("requests.post") as mock_post:
        ok, error = push_tokens.register_token(
            {"url": "https://example.supabase.co", "anon_key": "anon"},
            "access-token",
            user_id="user-123",
            expo_push_token="not-a-real-token",
        )
    assert ok is False
    assert error
    mock_post.assert_not_called()


def test_send_expo_push_notifications_chunks_at_expo_limit():
    tokens = [f"ExponentPushToken[{i}]" for i in range(150)]
    response = Mock(status_code=200)
    response.json.return_value = {"data": [{"status": "ok"}] * 100}

    with patch("requests.post", return_value=response) as mock_post:
        result = push_tokens.send_expo_push_notifications(tokens, title="Hi", body="There")

    assert result["ok"] is True
    assert result["sent"] == 150
    # 150 tokens at a 100-per-request chunk size is two requests, not one.
    assert mock_post.call_count == 2
    first_call_messages = mock_post.call_args_list[0].kwargs["json"]
    assert len(first_call_messages) == 100
    assert first_call_messages[0]["to"] == tokens[0]
    assert first_call_messages[0]["title"] == "Hi"
    assert first_call_messages[0]["body"] == "There"


def test_send_expo_push_notifications_ignores_non_expo_tokens():
    result = push_tokens.send_expo_push_notifications(
        ["garbage", ""], title="Hi", body="There"
    )
    assert result == {"ok": False, "sent": 0, "error": "No valid push tokens."}


def test_send_expo_push_notifications_fails_soft_on_network_error():
    with patch("requests.post", side_effect=Exception("boom")):
        result = push_tokens.send_expo_push_notifications(
            ["ExponentPushToken[abc]"], title="Hi", body="There"
        )
    assert result["ok"] is False
    assert result["sent"] == 0
    assert "boom" in result["error"]
