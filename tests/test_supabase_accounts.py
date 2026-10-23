from contextlib import nullcontext
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from modules import account_store, auth_supabase, premium, saved_leagues


class _StreamlitContext:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None


class _StreamlitRerun(RuntimeError):
    pass


class TestSupabaseAccounts(unittest.TestCase):
    def test_missing_config_disables_accounts_without_crashing(self):
        config = auth_supabase.get_supabase_config(secrets={}, environ={})

        self.assertFalse(config["enabled"])
        self.assertFalse(auth_supabase.is_configured(config))

    def test_auth_helpers_import_without_secrets(self):
        session_state = {}

        self.assertEqual(auth_supabase.current_auth_session(session_state), {})
        self.assertEqual(auth_supabase.current_user_id(session_state), "")
        self.assertEqual(auth_supabase.current_access_token(session_state), "")

    def test_auth_payload_populates_session_state_keys(self):
        session_state = {}

        auth_supabase.apply_auth_payload(
            session_state,
            {
                "access_token": "token",
                "refresh_token": "refresh",
                "user": {"id": "user-1", "email": "user@example.com"},
            },
        )

        self.assertEqual(session_state[auth_supabase.AUTH_EMAIL_KEY], "user@example.com")
        self.assertEqual(session_state[auth_supabase.AUTH_SESSION_KEY]["user_id"], "user-1")
        self.assertEqual(session_state[auth_supabase.ACCOUNT_MODE_KEY], "account")

    def test_durable_auth_payload_contains_restore_fields(self):
        payload = auth_supabase.durable_auth_payload(
            {
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_in": 3600,
                "user": {"id": "user-1", "email": "user@example.com"},
            },
            now=100,
        )

        self.assertEqual(payload["access_token"], "access")
        self.assertEqual(payload["refresh_token"], "refresh")
        self.assertEqual(payload["user_id"], "user-1")
        self.assertEqual(payload["email"], "user@example.com")
        self.assertEqual(payload["expires_at"], 3700)

    def test_auth_restore_succeeds_from_stored_token_payload(self):
        session_state = {}
        restored, error, refreshed = auth_supabase.restore_auth_payload(
            {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"},
            session_state,
            {
                "access_token": "access",
                "refresh_token": "refresh",
                "expires_at": 9999999999,
                "user": {"id": "user-1", "email": "user@example.com"},
            },
        )

        self.assertTrue(restored, error)
        self.assertFalse(refreshed)
        self.assertEqual(auth_supabase.current_user_id(session_state), "user-1")
        self.assertIn(auth_supabase.DURABLE_AUTH_PENDING_SAVE_KEY, session_state)


    def test_expired_access_token_uses_refresh_token(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        session_state = {}
        response = Mock(status_code=200)
        response.json.return_value = {
            "access_token": "new-access",
            "refresh_token": "new-refresh",
            "expires_in": 3600,
            "user": {"id": "user-1", "email": "user@example.com"},
        }
        with patch.object(auth_supabase.requests, "post", return_value=response) as post:
            restored, error, refreshed = auth_supabase.restore_auth_payload(
                config,
                session_state,
                {
                    "access_token": "old-access",
                    "refresh_token": "old-refresh",
                    "expires_at": 1,
                    "user": {"id": "user-1", "email": "user@example.com"},
                },
            )

        self.assertTrue(restored, error)
        self.assertTrue(refreshed)
        self.assertEqual(auth_supabase.current_access_token(session_state), "new-access")
        self.assertIn("grant_type=refresh_token", post.call_args.args[0])

    def test_failed_refresh_clears_durable_auth(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        session_state = {}
        response = Mock(status_code=401)
        response.json.return_value = {"message": "Invalid refresh token"}
        with patch.object(auth_supabase.requests, "post", return_value=response):
            restored, error, refreshed = auth_supabase.restore_auth_payload(
                config,
                session_state,
                {
                    "access_token": "old-access",
                    "refresh_token": "old-refresh",
                    "expires_at": 1,
                    "user": {"id": "user-1", "email": "user@example.com"},
                },
            )

        self.assertFalse(restored)
        self.assertFalse(refreshed)
        self.assertIn("Invalid refresh token", error)
        self.assertTrue(session_state[auth_supabase.DURABLE_AUTH_PENDING_CLEAR_KEY])

    def test_transient_network_failure_during_refresh_does_not_clear_durable_auth(self):
        # A DNS blip/connection reset/timeout while refreshing the access
        # token is not evidence the refresh token itself is invalid. Prior
        # behavior wiped the durable session on ANY refresh error, which
        # signed users out on ordinary network flakiness during the
        # ~hourly token-refresh window. Only a definitive 4xx response from
        # Supabase (test_failed_refresh_clears_durable_auth, above) should
        # clear it; this transient case should fail the attempt but leave
        # the stored refresh token intact for the next rerun to retry.
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        session_state = {}
        with patch.object(auth_supabase.requests, "post", side_effect=OSError("network unreachable")):
            restored, error, refreshed = auth_supabase.restore_auth_payload(
                config,
                session_state,
                {
                    "access_token": "old-access",
                    "refresh_token": "old-refresh",
                    "expires_at": 1,
                    "user": {"id": "user-1", "email": "user@example.com"},
                },
            )

        self.assertFalse(restored)
        self.assertFalse(refreshed)
        self.assertEqual(error, auth_supabase.TRANSIENT_AUTH_NETWORK_ERROR)
        self.assertNotIn(auth_supabase.DURABLE_AUTH_PENDING_CLEAR_KEY, session_state)

    def test_logout_clear_marks_durable_auth_for_removal(self):
        session_state = {
            auth_supabase.AUTH_SESSION_KEY: {"access_token": "access"},
            auth_supabase.AUTH_USER_KEY: {"id": "user-1"},
            auth_supabase.AUTH_EMAIL_KEY: "user@example.com",
            "account_profile": {"entitlement": "premium"},
            "account_profile_status": "loaded",
            "account_profile_error": "old error",
            "account_user_settings": {"settings": {"theme": "dark"}},
            "auth_restore_last_status": {"action": "read"},
            "auth_restore_last_result": "restored",
            "auth_restore_last_reason": "visibilitychange",
            "auth_restore_last_refreshed": False,
            "_supabase_profile_loaded_user-1": True,
        }

        auth_supabase.queue_durable_auth_clear(session_state)
        auth_supabase.clear_auth_session(session_state)

        self.assertTrue(session_state[auth_supabase.DURABLE_AUTH_PENDING_CLEAR_KEY])
        self.assertEqual(session_state[auth_supabase.ACCOUNT_MODE_KEY], "guest")
        self.assertEqual(auth_supabase.current_user_id(session_state), "")
        self.assertNotIn("account_profile", session_state)
        self.assertNotIn("account_profile_status", session_state)
        self.assertNotIn("account_profile_error", session_state)
        self.assertNotIn("account_user_settings", session_state)
        self.assertNotIn("auth_restore_last_status", session_state)
        self.assertNotIn("auth_restore_last_result", session_state)
        self.assertNotIn("auth_restore_last_reason", session_state)
        self.assertNotIn("auth_restore_last_refreshed", session_state)
        self.assertNotIn("_supabase_profile_loaded_user-1", session_state)


    def test_saved_league_payload_handles_partial_fields(self):
        payload = account_store.build_saved_league_payload(
            user_id="user-1",
            sleeper_username="sleeper",
            league_id="league-1",
            league_name="League One",
            roster_id=7,
        )

        self.assertEqual(payload["user_id"], "user-1")
        self.assertEqual(payload["sleeper_username"], "sleeper")
        self.assertEqual(payload["league_id"], "league-1")
        self.assertEqual(payload["league_name"], "League One")
        self.assertEqual(payload["roster_id"], "7")
        self.assertEqual(payload["team_id"], "7")
        self.assertTrue(payload["is_default"])

    def test_profile_payload_matches_documented_schema(self):
        payload = account_store.build_profile_payload(
            user_id="user-1",
            email="user@example.com",
            display_name="User",
            sleeper_username="sleeper",
        )

        self.assertEqual(
            set(payload.keys()),
            {"user_id", "email", "display_name", "sleeper_username"},
        )
        self.assertEqual(payload["user_id"], "user-1")

    def test_user_settings_payload_does_not_write_entitlement_fields(self):
        payload = account_store.build_user_settings_payload(
            user_id="user-1",
            settings={
                "theme": "dark",
                "entitlement": "premium",
                "plan": "premium",
                "tier": "premium",
                "is_premium": True,
                "customer_id": "customer-1",
                "stripe_customer_id": "cus_123",
                "stripe_subscription_id": "sub_123",
                "stripe_subscription_status": "active",
                "stripe_price_id": "price_123",
                "premium_updated_at": "2026-01-01T00:00:00Z",
            },
        )

        self.assertEqual(payload["user_id"], "user-1")
        self.assertEqual(payload["settings"], {"theme": "dark"})

    def test_fetch_profile_reads_current_user_profile_row(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        response = Mock(status_code=200)
        response.json.return_value = [{"user_id": "user-1", "entitlement": "premium"}]
        with patch.object(account_store.requests, "get", return_value=response) as get:
            profile, error = account_store.fetch_profile(config, "access-token", user_id="user-1")

        self.assertFalse(error)
        self.assertEqual(profile["entitlement"], "premium")
        self.assertIn("entitlement", get.call_args.args[0])
        self.assertNotIn("stripe_customer_id", get.call_args.args[0])

    def test_fetch_user_settings_reads_existing_preference_row(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        response = Mock(status_code=200)
        response.json.return_value = [
            {"user_id": "user-1", "settings": {"dashboard_orientation_dismissed": True}}
        ]
        with patch.object(account_store.requests, "get", return_value=response) as get:
            settings, error = account_store.fetch_user_settings(
                config, "access-token", user_id="user-1"
            )

        self.assertFalse(error)
        self.assertTrue(settings["settings"]["dashboard_orientation_dismissed"])
        self.assertIn("user_settings", get.call_args.args[0])

    def test_fetch_profile_falls_back_when_optional_stripe_columns_are_missing(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        missing_column_response = Mock(status_code=400)
        missing_column_response.json.return_value = {"message": "column profiles.stripe_customer_id does not exist"}
        base_response = Mock(status_code=200)
        base_response.json.return_value = [{"user_id": "user-1", "entitlement": "premium"}]

        with patch.object(account_store.requests, "get", side_effect=[missing_column_response, base_response]) as get:
            profile, error = account_store.fetch_profile(
                config, "access-token", user_id="user-1", include_billing=True
            )

        self.assertFalse(error)
        self.assertEqual(profile["entitlement"], "premium")
        self.assertEqual(get.call_count, 2)
        self.assertIn("stripe_customer_id", get.call_args_list[0].args[0])
        self.assertIn("select=user_id,email,display_name,sleeper_username,entitlement&limit=1", get.call_args_list[1].args[0])

    def test_fetch_profile_tolerates_single_dict_response_shape(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        response = Mock(status_code=200)
        response.json.return_value = {"user_id": "user-1", "entitlement": "premium"}
        with patch.object(account_store.requests, "get", return_value=response):
            profile, error = account_store.fetch_profile(config, "access-token", user_id="user-1")

        self.assertFalse(error)
        self.assertEqual(profile["entitlement"], "premium")

    def test_fetch_profile_error_is_detectable(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        response = Mock(status_code=403)
        response.json.return_value = {"message": "permission denied for table profiles"}
        with patch.object(account_store.requests, "get", return_value=response):
            profile, error = account_store.fetch_profile(config, "access-token", user_id="user-1")

        self.assertEqual(profile, {})
        self.assertIn("permission denied", error)

    def test_saved_league_state_is_scoped_to_authenticated_user(self):
        first = account_store.build_saved_league_payload(
            user_id="user-1",
            sleeper_username="same-sleeper",
            league_id="league-1",
        )
        second = account_store.build_saved_league_payload(
            user_id="user-2",
            sleeper_username="same-sleeper",
            league_id="league-1",
        )

        self.assertNotEqual(first["user_id"], second["user_id"])
        self.assertEqual(first["league_id"], second["league_id"])

    def test_upsert_saved_league_uses_user_and_league_conflict_key(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        patch_response = Mock(status_code=204)
        patch_response.json.return_value = []
        post_response = Mock(status_code=201)
        post_response.json.return_value = []
        with patch.object(account_store.requests, "patch", return_value=patch_response) as patch_request, patch.object(
            account_store.requests,
            "post",
            return_value=post_response,
        ) as post:
            saved, error = account_store.upsert_saved_league(
                config,
                "access-token",
                account_store.build_saved_league_payload(
                    user_id="user-1",
                    league_id="league-1",
                ),
            )

        self.assertTrue(saved, error)
        self.assertIn("/saved_leagues?user_id=eq.user-1", patch_request.call_args.args[0])
        self.assertEqual(patch_request.call_args.kwargs["json"], {"is_default": False})
        self.assertIn("on_conflict=user_id,league_id", post.call_args.args[0])
        self.assertNotIn("service", str(post.call_args).casefold())

    def test_migrate_saved_league_upserts_new_id_then_deletes_the_old_row(self):
        # Real production bug, 2026-10-21: a saved league whose Sleeper
        # season rolled over (new league_id every season, linked via
        # previous_league_id) kept pointing at the stale id forever. Real
        # id pair, live-verified against Sleeper: league "Revivalry",
        # 2025 league_id 1250325243881345024 rolled over to 2026 league_id
        # 1325866097718620160.
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        patch_response = Mock(status_code=204)
        patch_response.json.return_value = []
        post_response = Mock(status_code=201)
        post_response.json.return_value = []
        delete_response = Mock(status_code=204)
        delete_response.json.return_value = []
        with patch.object(
            account_store.requests, "patch", return_value=patch_response
        ), patch.object(
            account_store.requests, "post", return_value=post_response
        ) as post, patch.object(
            account_store.requests, "delete", return_value=delete_response
        ) as delete:
            ok, error = account_store.migrate_saved_league(
                config,
                "access-token",
                user_id="user-1",
                old_league_id="1250325243881345024",
                new_league_id="1325866097718620160",
                sleeper_username="lukamagic777777",
                league_name="Revivalry",
                is_default=True,
            )

        self.assertTrue(ok, error)
        self.assertIn("on_conflict=user_id,league_id", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["json"]["league_id"], "1325866097718620160")
        self.assertIn("/saved_leagues?", delete.call_args.args[0])
        self.assertIn("user_id=eq.user-1", delete.call_args.args[0])
        self.assertIn("league_id=eq.1250325243881345024", delete.call_args.args[0])

    def test_migrate_saved_league_never_deletes_old_row_when_the_upsert_fails(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        post_response = Mock(status_code=500)
        post_response.json.return_value = {"message": "boom"}
        with patch.object(
            account_store.requests, "post", return_value=post_response
        ), patch.object(account_store.requests, "delete") as delete:
            ok, error = account_store.migrate_saved_league(
                config,
                "access-token",
                user_id="user-1",
                old_league_id="1250325243881345024",
                new_league_id="1325866097718620160",
            )

        self.assertFalse(ok)
        self.assertTrue(error)
        delete.assert_not_called()

    def test_missing_tables_return_friendly_setup_error(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        response = Mock(status_code=404)
        response.json.return_value = {
            "message": "Could not find the table 'public.profiles' in the schema cache"
        }
        with patch.object(account_store.requests, "post", return_value=response):
            saved, error = account_store.upsert_profile(
                config,
                "access-token",
                account_store.build_profile_payload(user_id="user-1"),
            )

        self.assertFalse(saved)
        self.assertIn("Supabase tables are not set up yet", error)
        self.assertIn("docs/supabase_accounts.sql", error)
        self.assertNotIn("schema cache", error)

    def test_missing_table_setup_error_names_that_tables_own_migration_file(self):
        """_safe_error used to always blame docs/supabase_accounts.sql no
        matter which table's lookup actually failed — wrong for any table
        set up by a different docs/supabase_*.sql file."""
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        response = Mock(status_code=404)
        response.json.return_value = {
            "message": "Could not find the table 'public.mobile_alert_reads' in the schema cache"
        }
        with patch.object(account_store.requests, "get", return_value=response):
            rows, error = account_store.fetch_rows(
                config, "access-token", "mobile_alert_reads", user_id="user-1"
            )

        self.assertEqual(rows, [])
        self.assertIn("docs/supabase_mobile_alert_reads.sql", error)
        self.assertNotIn("supabase_accounts.sql", error)

    def test_missing_table_setup_error_falls_back_for_an_unmapped_table(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        response = Mock(status_code=404)
        response.json.return_value = {"message": "Could not find the table 'public.some_new_table'"}
        with patch.object(account_store.requests, "get", return_value=response):
            rows, error = account_store.fetch_rows(
                config, "access-token", "some_new_table", user_id="user-1"
            )

        self.assertEqual(rows, [])
        self.assertIn("docs/supabase_accounts.sql", error)

    def test_fetch_saved_leagues_filters_current_user_only(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        response = Mock(status_code=200)
        response.json.return_value = [{"user_id": "user-1", "league_id": "league-1"}]
        with patch.object(account_store.requests, "get", return_value=response) as get:
            rows, error = account_store.fetch_saved_leagues(config, "access-token", user_id="user-1")

        self.assertFalse(error)
        self.assertEqual(rows[0]["league_id"], "league-1")
        self.assertIn("user_id=eq.user-1", get.call_args.args[0])

    def test_default_saved_league_prefers_current_default(self):
        row = account_store.default_saved_league(
            [
                {"league_id": "old", "is_default": False},
                {"league_id": "current", "is_default": True},
            ]
        )

        self.assertEqual(row["league_id"], "current")

    def test_default_saved_league_can_require_explicit_default(self):
        rows = [{"league_id": "old", "is_default": False}]

        self.assertEqual(account_store.default_saved_league(rows, require_default=True), {})
        self.assertEqual(account_store.default_saved_league(rows)["league_id"], "old")


    def test_signup_confirmation_state_detection(self):
        self.assertTrue(
            auth_supabase.signup_requires_email_confirmation(
                {"user": {"id": "user-1", "email": "user@example.com"}}
            )
        )
        self.assertFalse(
            auth_supabase.signup_requires_email_confirmation(
                {
                    "access_token": "token",
                    "user": {"id": "user-1", "email": "user@example.com"},
                }
            )
        )

    def test_auth_error_detects_email_confirmation_required(self):
        self.assertTrue(auth_supabase.auth_error_requires_email_confirmation("Email not confirmed"))
        self.assertTrue(auth_supabase.auth_error_requires_email_confirmation("confirm your email before signing in"))
        self.assertFalse(auth_supabase.auth_error_requires_email_confirmation("Invalid login credentials"))

    def test_resend_signup_confirmation_posts_to_supabase_resend_endpoint(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        response = Mock(status_code=200)
        response.json.return_value = {}

        with patch.object(auth_supabase.requests, "post", return_value=response) as post:
            sent, error = auth_supabase.resend_signup_confirmation(config, "user@example.com")

        self.assertTrue(sent, error)
        self.assertFalse(error)
        self.assertIn("/auth/v1/resend", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["json"], {"type": "signup", "email": "user@example.com"})

    def test_resend_signup_confirmation_handles_missing_email_and_failure_friendly(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        sent, error = auth_supabase.resend_signup_confirmation(config, "")

        self.assertFalse(sent)
        self.assertIn("Enter your email", error)

        response = Mock(status_code=429)
        response.json.return_value = {"message": "For security purposes, you can only request this after 60 seconds"}
        with patch.object(auth_supabase.requests, "post", return_value=response):
            sent, error = auth_supabase.resend_signup_confirmation(config, "user@example.com")

        self.assertFalse(sent)
        self.assertIn("60 seconds", error)

    def test_request_password_reset_posts_to_recover_endpoint(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        response = Mock(status_code=200)
        response.json.return_value = {}

        with patch.object(auth_supabase.requests, "post", return_value=response) as post:
            sent, error = auth_supabase.request_password_reset(config, "user@example.com")

        self.assertTrue(sent, error)
        self.assertFalse(error)
        self.assertIn("/auth/v1/recover", post.call_args.args[0])
        self.assertEqual(post.call_args.kwargs["json"], {"email": "user@example.com"})

    def test_request_password_reset_rejects_invalid_email_without_network_call(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}

        with patch.object(auth_supabase.requests, "post") as post:
            sent, error = auth_supabase.request_password_reset(config, "not-an-email")

        post.assert_not_called()
        self.assertFalse(sent)
        self.assertIn("valid email", error.casefold())

    def test_password_reset_request_never_reveals_whether_email_has_an_account(self):
        # Supabase's own /recover endpoint returns HTTP 200 for both an
        # existing and a nonexistent email (anti user-enumeration). Even if
        # some error text would otherwise classify as "an account already
        # exists for that email" (classify_auth_error's duplicate_user
        # category), the caller-facing copy must never surface that — it
        # would leak account existence through what has to stay a neutral
        # "forgot password" flow.
        message = auth_supabase.password_reset_request_user_message(
            "A user with this email address has already been registered"
        )

        self.assertNotIn("already", message.casefold())
        self.assertIn("if an account exists", message.casefold())

        # Genuinely actionable failures that cannot leak account existence
        # (rate limiting, bad request shape, provider outage) are still
        # surfaced as-is rather than always collapsing to the neutral copy.
        rate_limited = auth_supabase.password_reset_request_user_message("Too many requests")
        self.assertIn("too many attempts", rate_limited.casefold())

    def test_update_user_password_requires_minimum_length_without_network_call(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}

        with patch.object(auth_supabase.requests, "put") as put:
            payload, error = auth_supabase.update_user_password(config, "access-token", "short")

        put.assert_not_called()
        self.assertIsNone(payload)
        self.assertIn("6 characters", error)

    def test_update_user_password_puts_to_user_endpoint_with_bearer_token(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        response = Mock(status_code=200)
        response.json.return_value = {"id": "user-1", "email": "user@example.com"}

        with patch.object(auth_supabase.requests, "put", return_value=response) as put:
            payload, error = auth_supabase.update_user_password(
                config, "recovery-access-token", "newpassword123"
            )

        self.assertFalse(error)
        self.assertEqual(payload["id"], "user-1")
        self.assertIn("/auth/v1/user", put.call_args.args[0])
        self.assertEqual(put.call_args.kwargs["json"], {"password": "newpassword123"})
        self.assertEqual(
            put.call_args.kwargs["headers"]["Authorization"], "Bearer recovery-access-token"
        )

    def test_password_recovery_pending_state_round_trips(self):
        session_state = {}
        self.assertFalse(auth_supabase.is_password_recovery_pending(session_state))

        auth_supabase.enter_password_recovery_pending(session_state)
        self.assertTrue(auth_supabase.is_password_recovery_pending(session_state))

        auth_supabase.clear_password_recovery_pending(session_state)
        self.assertFalse(auth_supabase.is_password_recovery_pending(session_state))

    def test_logout_clears_password_recovery_pending(self):
        session_state = {auth_supabase.PASSWORD_RECOVERY_PENDING_KEY: True}
        auth_supabase.clear_auth_session(session_state)
        self.assertFalse(auth_supabase.is_password_recovery_pending(session_state))


    def test_supabase_sql_documents_expected_account_schema(self):
        sql_path = Path("docs/supabase_accounts.sql")
        self.assertTrue(sql_path.exists())
        sql = sql_path.read_text(encoding="utf-8")

        self.assertIn("create table if not exists public.profiles", sql)
        self.assertIn("user_id uuid primary key references auth.users(id)", sql)
        self.assertIn("entitlement text not null default 'free'", sql)
        self.assertIn("entitlement in ('free', 'premium', 'pro', 'front_office')", sql)
        self.assertIn("create table if not exists public.saved_leagues", sql)
        self.assertIn("league_id text not null", sql)
        self.assertIn("is_default boolean not null default false", sql)
        self.assertIn("enable row level security", sql)
        self.assertIn("create policy profiles_select_own", sql)
        self.assertIn("using (auth.uid() = user_id)", sql)
        self.assertIn("prevent_profile_entitlement_client_update", sql)
        self.assertIn("Profile entitlement is managed outside the client app", sql)
        self.assertIn("service_role", sql)
        self.assertIn("before insert or update", sql)

    def test_supabase_entitlement_migration_is_additive_and_manual(self):
        sql_path = Path("docs/supabase_profile_entitlement.sql")
        self.assertTrue(sql_path.exists())
        sql = sql_path.read_text(encoding="utf-8").casefold()

        self.assertIn("alter table public.profiles", sql)
        self.assertIn("add column if not exists entitlement", sql)
        self.assertIn("default 'free'", sql)
        self.assertIn("check (entitlement in ('free', 'premium'))", sql)
        self.assertIn("prevent_profile_entitlement_client_update", sql)
        self.assertIn("profiles_enforce_entitlement_authority", sql)
        self.assertIn("service_role", sql)
        self.assertNotIn("checkout", sql)
        self.assertNotIn("webhook", sql)

    def test_supabase_stripe_billing_sql_documents_optional_server_updated_fields(self):
        sql = Path("docs/supabase_stripe_billing.sql").read_text(encoding="utf-8").casefold()

        self.assertIn("add column if not exists stripe_customer_id", sql)
        self.assertIn("add column if not exists stripe_subscription_id", sql)
        self.assertIn("add column if not exists stripe_subscription_status", sql)
        self.assertIn("add column if not exists stripe_price_id", sql)
        self.assertIn("add column if not exists premium_updated_at", sql)
        self.assertIn("verified server-side webhook", sql)
        self.assertNotIn("sk_test_", sql)
        self.assertNotIn("whsec_", sql)


if __name__ == "__main__":
    unittest.main()


class TestSavedLeagueCap(unittest.TestCase):
    """Free keeps one league; Premium keeps many — enforced on every surface.

    modules.saved_leagues is the single authority: the web "Save league"
    button and the mobile API's POST /v1/leagues/save both read the cap from
    it, so a Free account can't get a second league by switching apps.
    """

    config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}

    def _saved_rows_response(self, rows):
        response = Mock(status_code=200)
        response.json.return_value = rows
        return response

    def _save(self, *, entitlement, existing_rows, league_id="league-2"):
        profile_write = Mock(status_code=201)
        profile_write.json.return_value = []
        league_write = Mock(status_code=201)
        league_write.json.return_value = []
        clear_default = Mock(status_code=204)
        clear_default.json.return_value = []
        with patch.object(
            account_store.requests, "get", return_value=self._saved_rows_response(existing_rows)
        ), patch.object(
            account_store.requests, "post", side_effect=[profile_write, league_write]
        ) as post, patch.object(
            account_store.requests, "patch", return_value=clear_default
        ):
            saved, error = account_ui.save_current_context(
                config=self.config,
                access_token="access-token",
                user_id="user-1",
                email="gm@example.com",
                username="gm_dynasty",
                selected_league_id=league_id,
                selected_league_name="Second League",
                my_roster_id=3,
                entitlement=entitlement,
            )
        return saved, error, post


    def test_cap_values_per_entitlement(self):
        self.assertEqual(
            saved_leagues.max_leagues_for_entitlement(premium.FREE),
            saved_leagues.MAX_LEAGUES_FREE,
        )
        # coridian_, 2026-10-19: "go ahead and do that until we have
        # enough features to segregate between pro and front office" --
        # unlimited saved leagues (represented as the large guard value,
        # not a literal None, for this back-compat int-returning wrapper)
        # now applies to Pro too, same as Front Office already had.
        self.assertEqual(
            saved_leagues.max_leagues_for_entitlement(premium.PREMIUM),
            saved_leagues.MAX_LEAGUES_FRONT_OFFICE_GUARD,
        )
        self.assertEqual(
            saved_leagues.max_leagues_for_entitlement(premium.FRONT_OFFICE),
            saved_leagues.MAX_LEAGUES_FRONT_OFFICE_GUARD,
        )
        # Unknown/absent entitlement must never grant the larger cap.
        self.assertEqual(
            saved_leagues.max_leagues_for_entitlement(""),
            saved_leagues.MAX_LEAGUES_FREE,
        )
        self.assertEqual(saved_leagues.MAX_LEAGUES_FREE, 1)
        self.assertGreater(saved_leagues.MAX_LEAGUES_FRONT_OFFICE_GUARD, saved_leagues.MAX_LEAGUES_FREE)

    def test_cap_resolves_from_the_session_entitlement_chain(self):
        free_session = {
            "auth_session": {"user_id": "user-1", "access_token": "tok"},
            "auth_user": {"id": "user-1"},
            "account_profile": {"entitlement": premium.FREE},
        }
        premium_session = dict(free_session)
        premium_session["account_profile"] = {"entitlement": premium.PREMIUM}

        self.assertEqual(
            saved_leagues.max_leagues_for_session(free_session),
            saved_leagues.MAX_LEAGUES_FREE,
        )
        self.assertEqual(
            saved_leagues.max_leagues_for_session(premium_session),
            saved_leagues.MAX_LEAGUES_FRONT_OFFICE_GUARD,
        )

    def test_is_at_cap_counts_only_distinct_other_leagues(self):
        rows = [{"league_id": "league-1"}, {"league_id": "league-1"}, {"league_id": ""}]

        self.assertFalse(saved_leagues.is_at_cap(rows, league_id="league-1", cap=1))
        self.assertTrue(saved_leagues.is_at_cap(rows, league_id="league-2", cap=1))
        self.assertFalse(saved_leagues.is_at_cap(rows, league_id="league-2", cap=2))
        self.assertFalse(saved_leagues.is_at_cap([], league_id="league-1", cap=1))
