"""Signup Auth API path contract — PGRST125 regression guard."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from modules import account_store
from modules import auth_supabase


@pytest.mark.parametrize(
    "raw_url",
    [
        "https://abcd.supabase.co",
        "https://abcd.supabase.co/",
        "https://abcd.supabase.co/rest/v1",
        "https://abcd.supabase.co/rest/v1/",
        "https://abcd.supabase.co/auth/v1",
        "https://abcd.supabase.co/auth/v1/",
        "  https://abcd.supabase.co/rest/v1/?apikey=should-drop  ",
    ],
)
def test_normalize_supabase_project_url_strips_api_suffixes(raw_url: str):
    assert auth_supabase.normalize_supabase_project_url(raw_url) == "https://abcd.supabase.co"


def test_signup_final_path_snapshot_never_hits_rest():
    """Production PGRST125 came from `/rest/v1/auth/v1/signup` when URL included /rest/v1."""

    malformed_bases = (
        "https://proj.supabase.co/rest/v1",
        "https://proj.supabase.co/rest/v1/",
        "https://proj.supabase.co",
    )
    for base in malformed_bases:
        config = {"enabled": True, "url": base, "anon_key": "sb_publishable_test"}
        url = auth_supabase.auth_api_url(config, "signup")
        path = auth_supabase.sanitized_request_path(url)
        assert path == "/auth/v1/signup"
        assert "/rest/v1" not in path
        assert path.count("/auth/v1") == 1


def test_get_supabase_config_normalizes_rest_suffix():
    config = auth_supabase.get_supabase_config(
        secrets={},
        environ={
            "SUPABASE_URL": "https://live.supabase.co/rest/v1",
            "SUPABASE_ANON_KEY": "sb_publishable_abc",
        },
    )
    assert config["enabled"] is True
    assert config["url"] == "https://live.supabase.co"
    assert auth_supabase.sanitized_request_path(
        auth_supabase.auth_api_url(config, "signup")
    ) == "/auth/v1/signup"


def test_rest_url_not_doubled_when_config_has_rest_suffix():
    config = {"url": "https://live.supabase.co/rest/v1", "anon_key": "k", "enabled": True}
    assert account_store._rest_url(config, "profiles") == "https://live.supabase.co/rest/v1/profiles"
    assert (
        account_store._rest_url(config, "profiles", "user_id=eq.1")
        == "https://live.supabase.co/rest/v1/profiles?user_id=eq.1"
    )


def test_publishable_key_uses_apikey_only_until_user_jwt():
    config = {"anon_key": "sb_publishable_example_key", "url": "https://x.supabase.co"}
    headers = auth_supabase.auth_headers(config)
    assert headers["apikey"] == "sb_publishable_example_key"
    assert "Authorization" not in headers

    with_user = auth_supabase.auth_headers(config, access_token="user.jwt.token")
    assert with_user["Authorization"] == "Bearer user.jwt.token"
    assert with_user["apikey"] == "sb_publishable_example_key"


def test_legacy_jwt_anon_still_sends_bearer():
    anon = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.sig"
    headers = auth_supabase.auth_headers({"anon_key": anon})
    assert headers["apikey"] == anon
    assert headers["Authorization"] == f"Bearer {anon}"


def test_signup_posts_canonical_auth_path_even_with_rest_base(capsys):
    config = {
        "enabled": True,
        "url": "https://proj.supabase.co/rest/v1",
        "anon_key": "sb_publishable_test",
    }
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "access_token": "a.b.c",
        "refresh_token": "r",
        "user": {"id": "uid-1", "email": "new@example.com"},
    }
    with patch("modules.auth_supabase.requests.post", return_value=mock_response) as post:
        payload, error = auth_supabase.sign_up(config, "new@example.com", "StrongPass1!")
    assert error == ""
    assert payload is not None
    called_url = post.call_args.args[0]
    assert auth_supabase.sanitized_request_path(called_url) == "/auth/v1/signup"
    assert called_url == "https://proj.supabase.co/auth/v1/signup"
    headers = post.call_args.kwargs["headers"]
    assert headers["apikey"] == "sb_publishable_test"
    assert "Authorization" not in headers
    logged = capsys.readouterr().out
    assert "request_path" in logged
    assert "/auth/v1/signup" in logged
    assert "new@example.com" not in logged
    assert "StrongPass1!" not in logged
    assert "auth_user_created': True" in logged or '"auth_user_created": true' in logged.lower() or "auth_user_created': True" in logged
    # Failure-before-bootstrap contract: sign_up itself never claims profile bootstrap.
    assert "profile_bootstrap_ran': False" in logged or "profile_bootstrap_ran': False" in logged.replace(
        '"', "'"
    )


def test_signup_pgrst125_classified_as_invalid_api_path():
    classified = auth_supabase.classify_auth_error(
        "Invalid path is specified in request URL [PGRST125]",
        status_code=404,
    )
    assert classified["category"] == "invalid_api_path"
    assert classified["error_code"] == "PGRST125"


def test_signup_http_error_before_profile_bootstrap(capsys):
    config = {
        "enabled": True,
        "url": "https://proj.supabase.co",
        "anon_key": "sb_publishable_test",
    }
    mock_response = MagicMock()
    mock_response.status_code = 404
    mock_response.json.return_value = {
        "message": "Invalid path is specified in request URL",
        "code": "PGRST125",
    }
    with patch("modules.auth_supabase.requests.post", return_value=mock_response):
        payload, error = auth_supabase.sign_up(config, "user@example.com", "StrongPass1!")
    assert payload is None
    assert "PGRST125" in error
    logged = capsys.readouterr().out
    assert "auth_user_created': False" in logged or "auth_user_created': False" in logged.replace('"', "'")
    assert "profile_bootstrap_ran': False" in logged.replace('"', "'")
    assert "invalid_api_path" in logged
