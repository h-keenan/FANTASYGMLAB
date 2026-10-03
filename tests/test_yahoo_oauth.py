"""Unit tests for the Yahoo OAuth2 client scaffolding (modules/platforms/yahoo_oauth.py).

These tests use mocked HTTP responses shaped like Yahoo's *documented*
token response (see that module's docstring for sources) — none of them
contact the real Yahoo API. They verify the URL/parameter building and
response parsing logic only; they cannot and do not verify Yahoo's actual
live behavior. See docs/yahoo-oauth-integration-spike-runbook.md for what a
human must do to complete that verification.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock
from urllib.parse import parse_qs, urlparse

from modules.platforms import yahoo_oauth


class FakeResponse:
    def __init__(self, status_code=200, json_payload=None, text="", raise_exc=None):
        self.status_code = status_code
        self._json_payload = json_payload
        self.text = text
        self._raise_exc = raise_exc

    def raise_for_status(self):
        if self._raise_exc is not None:
            raise self._raise_exc

    def json(self):
        if self._json_payload is None:
            raise ValueError("no json body")
        return self._json_payload


class TestBuildAuthorizationUrl(unittest.TestCase):
    def test_builds_url_with_required_params(self):
        url = yahoo_oauth.build_authorization_url(
            redirect_uri="https://example.com/callback",
            client_id="test-client-id",
        )
        parsed = urlparse(url)
        self.assertEqual(f"{parsed.scheme}://{parsed.netloc}{parsed.path}", yahoo_oauth.AUTHORIZATION_ENDPOINT)
        params = parse_qs(parsed.query)
        self.assertEqual(params["client_id"], ["test-client-id"])
        self.assertEqual(params["redirect_uri"], ["https://example.com/callback"])
        self.assertEqual(params["response_type"], ["code"])
        self.assertNotIn("state", params)

    def test_includes_optional_state_and_language(self):
        url = yahoo_oauth.build_authorization_url(
            redirect_uri="https://example.com/callback",
            client_id="test-client-id",
            state="csrf-xyz",
            language="en-us",
        )
        params = parse_qs(urlparse(url).query)
        self.assertEqual(params["state"], ["csrf-xyz"])
        self.assertEqual(params["language"], ["en-us"])

    def test_reads_client_id_from_environ_when_not_passed(self):
        url = yahoo_oauth.build_authorization_url(
            redirect_uri="https://example.com/callback",
            environ={"YAHOO_CLIENT_ID": "from-env"},
        )
        params = parse_qs(urlparse(url).query)
        self.assertEqual(params["client_id"], ["from-env"])

    def test_missing_client_id_raises(self):
        with self.assertRaises(yahoo_oauth.YahooOAuthError):
            yahoo_oauth.build_authorization_url(redirect_uri="https://example.com/callback", environ={})

    def test_missing_redirect_uri_raises(self):
        with self.assertRaises(yahoo_oauth.YahooOAuthError):
            yahoo_oauth.build_authorization_url(client_id="cid", environ={})


class TestTokenExchange(unittest.TestCase):
    def _documented_token_payload(self):
        # Shape per https://developer.yahoo.com/oauth2/guide/flows_authcode/
        return {
            "access_token": "fake-access-token",
            "token_type": "bearer",
            "expires_in": 3600,
            "refresh_token": "fake-refresh-token",
            "xoauth_yahoo_guid": "FAKEGUID123",
        }

    def test_exchange_code_for_token_posts_basic_auth_and_parses_response(self):
        session = MagicMock()
        session.post.return_value = FakeResponse(json_payload=self._documented_token_payload())

        token = yahoo_oauth.exchange_code_for_token(
            code="auth-code-123",
            redirect_uri="https://example.com/callback",
            client_id="cid",
            client_secret="secret",
            session=session,
        )

        self.assertEqual(token.access_token, "fake-access-token")
        self.assertEqual(token.refresh_token, "fake-refresh-token")
        self.assertEqual(token.expires_in, 3600)
        self.assertEqual(token.yahoo_guid, "FAKEGUID123")
        self.assertFalse(token.is_expired())

        call_args = session.post.call_args
        self.assertEqual(call_args.args[0], yahoo_oauth.TOKEN_ENDPOINT)
        self.assertEqual(call_args.kwargs["data"]["grant_type"], "authorization_code")
        self.assertEqual(call_args.kwargs["data"]["code"], "auth-code-123")
        self.assertEqual(call_args.kwargs["data"]["redirect_uri"], "https://example.com/callback")
        auth_header = call_args.kwargs["headers"]["Authorization"]
        self.assertTrue(auth_header.startswith("Basic "))
        # Decoding isn't required for the behavior, but the secret must not leak in plaintext.
        self.assertNotIn("secret", auth_header)

    def test_refresh_access_token_uses_refresh_grant(self):
        session = MagicMock()
        session.post.return_value = FakeResponse(json_payload=self._documented_token_payload())

        yahoo_oauth.refresh_access_token(
            refresh_token="old-refresh-token",
            client_id="cid",
            client_secret="secret",
            session=session,
        )

        call_args = session.post.call_args
        self.assertEqual(call_args.kwargs["data"]["grant_type"], "refresh_token")
        self.assertEqual(call_args.kwargs["data"]["refresh_token"], "old-refresh-token")

    def test_http_error_raises_yahoo_oauth_error_without_leaking_secret(self):
        session = MagicMock()
        session.post.return_value = FakeResponse(
            status_code=400,
            text='{"error": "invalid_grant"}',
            raise_exc=RuntimeError("400 Client Error"),
        )

        with self.assertRaises(yahoo_oauth.YahooOAuthError) as raised:
            yahoo_oauth.exchange_code_for_token(
                code="bad-code",
                redirect_uri="https://example.com/callback",
                client_id="cid",
                client_secret="super-secret-value",
                session=session,
            )
        self.assertNotIn("super-secret-value", str(raised.exception))

    def test_non_json_response_raises(self):
        session = MagicMock()
        session.post.return_value = FakeResponse(json_payload=None, text="<html>not json</html>")

        with self.assertRaises(yahoo_oauth.YahooOAuthError):
            yahoo_oauth.exchange_code_for_token(
                code="code",
                redirect_uri="https://example.com/callback",
                client_id="cid",
                client_secret="secret",
                session=session,
            )

    def test_missing_credentials_raise_before_any_request(self):
        session = MagicMock()
        with self.assertRaises(yahoo_oauth.YahooOAuthError):
            yahoo_oauth.exchange_code_for_token(
                code="code",
                redirect_uri="https://example.com/callback",
                environ={},
                session=session,
            )
        session.post.assert_not_called()


class TestTokenExpiryAndRefreshHelper(unittest.TestCase):
    def test_is_expired_true_when_past_expiry_minus_skew(self):
        token = yahoo_oauth.YahooOAuthToken(
            access_token="a",
            refresh_token="r",
            token_type="bearer",
            expires_in=100,
            yahoo_guid="g",
            obtained_at=0.0,
            raw={},
        )
        self.assertTrue(token.is_expired())

    def test_ensure_fresh_token_returns_same_token_when_not_expired(self):
        token = yahoo_oauth.YahooOAuthToken.from_response(
            {"access_token": "a", "refresh_token": "r", "expires_in": 999999},
        )
        result = yahoo_oauth.ensure_fresh_token(token)
        self.assertIs(result, token)

    def test_ensure_fresh_token_refreshes_when_expired(self):
        expired = yahoo_oauth.YahooOAuthToken(
            access_token="old",
            refresh_token="r",
            token_type="bearer",
            expires_in=1,
            yahoo_guid="g",
            obtained_at=0.0,
            raw={},
        )
        session = MagicMock()
        session.post.return_value = FakeResponse(
            json_payload={"access_token": "new", "refresh_token": "r2", "expires_in": 3600}
        )
        refreshed = yahoo_oauth.ensure_fresh_token(
            expired, client_id="cid", client_secret="secret", session=session
        )
        self.assertEqual(refreshed.access_token, "new")

    def test_from_response_requires_access_token(self):
        with self.assertRaises(yahoo_oauth.YahooOAuthError):
            yahoo_oauth.YahooOAuthToken.from_response({"refresh_token": "r"})


if __name__ == "__main__":
    unittest.main()
