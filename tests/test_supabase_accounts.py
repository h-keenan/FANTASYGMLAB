from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from modules import account_store, account_ui, auth_supabase


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

    def test_durable_auth_storage_bridge_installs_ios_resume_hooks(self):
        source = Path("modules/account_ui.py").read_text(encoding="utf-8")

        self.assertIn("installResumeHooks", source)
        self.assertIn('window.addEventListener("pageshow"', source)
        self.assertIn('window.addEventListener("focus"', source)
        self.assertIn('document.addEventListener("visibilitychange"', source)
        self.assertIn("pageshow_persisted", source)
        self.assertIn("_resume_reason", source)

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

    def test_missing_browser_storage_falls_back_to_session_only(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        with patch.object(account_ui.st, "session_state", {}), patch.object(
            account_ui,
            "AUTH_STORAGE_COMPONENT",
            side_effect=ValueError("Component is not registered"),
        ):
            actions = account_ui.render_durable_auth_bridge(config=config)

        self.assertFalse(actions["restored"])
        self.assertIn("session-only", actions["error"])

    def test_durable_auth_bridge_uses_valid_component_size(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        result = Mock()
        result.status = None
        result.stored = None
        with patch.object(account_ui.st, "session_state", {}), patch.object(
            account_ui,
            "AUTH_STORAGE_COMPONENT",
            return_value=result,
        ) as component:
            actions = account_ui.render_durable_auth_bridge(config=config)

        self.assertTrue(actions["storage_available"])
        self.assertEqual(component.call_args.kwargs["width"], 1)
        self.assertEqual(component.call_args.kwargs["height"], 1)

    def test_durable_auth_bridge_restores_from_resume_event_and_records_safe_status(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        result = Mock()
        result.status = {"action": "read", "ok": True, "reason": "visibilitychange", "durableAuthPresent": True}
        result.stored = {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_at": 9999999999,
            "user": {"id": "user-1", "email": "user@example.com"},
            "_resume_reason": "visibilitychange",
        }
        session_state = {}

        with patch.object(account_ui.st, "session_state", session_state), patch.object(
            account_ui,
            "AUTH_STORAGE_COMPONENT",
            return_value=result,
        ):
            actions = account_ui.render_durable_auth_bridge(config=config)

        self.assertTrue(actions["restored"], actions["error"])
        self.assertEqual(actions["resume_reason"], "visibilitychange")
        self.assertEqual(session_state["auth_restore_last_result"], "restored")
        self.assertEqual(session_state["auth_restore_last_reason"], "visibilitychange")
        self.assertEqual(session_state["auth_restore_last_status"]["action"], "read")
        self.assertNotIn("access", str(session_state["auth_restore_last_status"]))
        self.assertNotIn("refresh", str(session_state["auth_restore_last_status"]))

    def test_visible_default_saved_league_triggers_launch_auto_resume(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        session_state = {
            auth_supabase.AUTH_SESSION_KEY: {
                "access_token": "access",
                "user_id": "user-1",
            },
            auth_supabase.AUTH_USER_KEY: {"id": "user-1"},
            auth_supabase.AUTH_EMAIL_KEY: "user@example.com",
            "account_saved_leagues_cache": [
                {
                    "user_id": "user-1",
                    "sleeper_username": "sleeper",
                    "league_id": "league-1",
                    "league_name": "League One",
                    "is_default": True,
                }
            ],
        }
        with patch.object(account_ui.st, "session_state", session_state), patch.object(
            account_ui.st,
            "success",
        ), patch.object(account_ui.st, "caption"), patch.object(account_ui.st, "button", return_value=False):
            actions = account_ui.render_mobile_auth_entry(config=config, selected_league_id="")

        self.assertEqual(actions["resume_league"]["league_id"], "league-1")
        self.assertTrue(session_state["_supabase_launch_auto_resume_attempted_user-1"])

    def test_launch_auto_resume_respects_suppression(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        session_state = {
            auth_supabase.AUTH_SESSION_KEY: {
                "access_token": "access",
                "user_id": "user-1",
            },
            auth_supabase.AUTH_USER_KEY: {"id": "user-1"},
            "supabase_auto_resume_suppressed": True,
            "account_saved_leagues_cache": [
                {
                    "sleeper_username": "sleeper",
                    "league_id": "league-1",
                    "league_name": "League One",
                    "is_default": True,
                }
            ],
        }
        with patch.object(account_ui.st, "session_state", session_state), patch.object(
            account_ui.st,
            "success",
        ), patch.object(account_ui.st, "caption"), patch.object(account_ui.st, "button", return_value=False):
            actions = account_ui.render_mobile_auth_entry(config=config, selected_league_id="")

        self.assertIsNone(actions["resume_league"])

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
        self.assertIn("stripe_customer_id", get.call_args.args[0])

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
            profile, error = account_store.fetch_profile(config, "access-token", user_id="user-1")

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
        self.assertNotIn("schema cache", error)

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

    def test_app_restores_auth_before_saved_league_before_local_context(self):
        app_source = Path("app.py").read_text(encoding="utf-8")
        auth_idx = app_source.index("auth_restore = account_ui.render_durable_auth_bridge")
        profile_idx = app_source.index("_refresh_supabase_account_profile()")
        resume_idx = app_source.index("_maybe_auto_resume_supabase_league()", auth_idx)
        resolve_idx = app_source.index("resolve_active_league_context()", resume_idx)

        self.assertLess(auth_idx, resume_idx)
        self.assertLess(profile_idx, resume_idx)
        self.assertLess(resume_idx, resolve_idx)

    def test_app_caches_profile_for_premium_entitlement(self):
        app_source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn("def _refresh_supabase_account_profile(*, force: bool = False)", app_source)
        self.assertIn("account_store.fetch_profile", app_source)
        self.assertIn('st.session_state["account_profile"] = profile', app_source)

    def test_change_league_suppresses_auto_resume(self):
        app_source = Path("app.py").read_text(encoding="utf-8")

        self.assertIn('st.session_state.get("supabase_auto_resume_suppressed")', app_source)
        self.assertIn('st.session_state["supabase_auto_resume_suppressed"] = True', app_source)

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

    def test_guest_mode_account_panel_when_config_missing(self):
        with patch.object(account_ui.st, "markdown"), patch.object(account_ui.st, "subheader"), patch.object(
            account_ui.st,
            "caption",
        ), patch.object(account_ui.st, "session_state", {}):
            actions = account_ui.render_account_panel(config={})

        self.assertFalse(actions["logged_in"])
        self.assertIsNone(actions["resume_league"])

    def test_sidebar_account_panel_demotes_login_forms(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        session_state = {}
        with patch.object(account_ui.st, "session_state", session_state), patch.object(
            account_ui.st,
            "markdown",
        ), patch.object(account_ui.st, "subheader"), patch.object(account_ui.st, "caption") as caption, patch.object(
            account_ui.st,
            "tabs",
        ) as tabs:
            actions = account_ui.render_account_panel(config=config)

        self.assertFalse(actions["logged_in"])
        tabs.assert_not_called()
        self.assertIn("main launch screen", " ".join(str(call.args[0]) for call in caption.call_args_list))

    def test_fresh_launch_shows_explicit_account_or_guest_choices(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        session_state = {}
        with patch.object(account_ui.st, "session_state", session_state), patch.object(
            account_ui.st,
            "markdown",
        ), patch.object(account_ui.st, "caption"), patch.object(account_ui.st, "columns") as columns:
            left = Mock()
            right = Mock()
            columns.return_value = [left, right]
            left.__enter__ = Mock(return_value=left)
            left.__exit__ = Mock(return_value=None)
            right.__enter__ = Mock(return_value=right)
            right.__exit__ = Mock(return_value=None)
            with patch.object(account_ui.st, "button", return_value=False) as button:
                actions = account_ui.render_mobile_auth_entry(config=config)

        self.assertFalse(actions["continue_guest"])
        button_labels = [call.args[0] for call in button.call_args_list]
        self.assertIn("Create account / Sign in", button_labels)
        self.assertIn("Continue as guest", button_labels)

    def test_account_launch_copy_is_account_first(self):
        source = Path("modules/account_ui.py").read_text(encoding="utf-8")

        self.assertIn("launch-account-intro", source)
        self.assertIn("Save this league to your account", source)
        self.assertIn("Guest mode is fully usable", source)

    def test_signup_confirmation_uses_check_email_card(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        session_state = {
            "account_signup_check_email": True,
            auth_supabase.CONFIRMATION_EMAIL_KEY: "user@example.com",
        }
        with patch.object(account_ui.st, "session_state", session_state), patch.object(
            account_ui.st,
            "markdown",
        ) as markdown, patch.object(account_ui.st, "button", return_value=False), patch.object(account_ui.st, "caption"):
            actions = account_ui.render_mobile_auth_entry(config=config)

        self.assertFalse(actions["continue_guest"])
        self.assertIn("account-confirm-card", markdown.call_args.args[0])

    def test_confirmation_card_resend_success_and_cooldown(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        session_state = {}

        with patch.object(account_ui.st, "session_state", session_state), patch.object(
            account_ui.st,
            "markdown",
        ) as markdown, patch.object(account_ui.st, "button", return_value=True), patch.object(
            account_ui.st,
            "success",
        ) as success, patch.object(auth_supabase, "resend_signup_confirmation", return_value=(True, "")):
            account_ui.render_confirmation_required_card(
                config=config,
                email="user@example.com",
                key_prefix="test",
            )

        self.assertIn("Please confirm your email", markdown.call_args.args[0])
        success.assert_called_once_with("Confirmation email sent. Check your inbox and spam folder.")
        self.assertIn(auth_supabase.CONFIRMATION_RESEND_TS_KEY, session_state)

        with patch.object(account_ui.st, "session_state", session_state), patch.object(
            account_ui.st,
            "markdown",
        ), patch.object(account_ui.st, "button") as button, patch.object(account_ui.st, "caption") as caption:
            account_ui.render_confirmation_required_card(
                config=config,
                email="user@example.com",
                key_prefix="test",
            )

        button.assert_not_called()
        self.assertIn("another email in a moment", " ".join(str(call.args[0]) for call in caption.call_args_list))

    def test_confirmation_card_missing_email_disables_resend(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        with patch.object(account_ui.st, "session_state", {}), patch.object(account_ui.st, "markdown"), patch.object(
            account_ui.st,
            "info",
        ) as info, patch.object(account_ui.st, "button") as button:
            account_ui.render_confirmation_required_card(config=config, email="", key_prefix="test")

        button.assert_not_called()
        self.assertIn("Enter your email", info.call_args.args[0])

    def test_login_confirmation_error_shows_resend_flow_without_raw_error(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        session_state = {"launch_auth_mode": "account"}

        class _Tabs:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return None

        buttons = {
            "Continue as guest instead": False,
            "Log in": True,
            "Create account": False,
            "Resend confirmation email": False,
        }

        with patch.object(account_ui.st, "session_state", session_state), patch.object(account_ui.st, "markdown"), patch.object(
            account_ui.st,
            "tabs",
            return_value=[_Tabs(), _Tabs()],
        ), patch.object(account_ui.st, "text_input", side_effect=["user@example.com", "password", "", ""]), patch.object(
            account_ui.st,
            "button",
            side_effect=lambda label, **_kwargs: buttons.get(label, False),
        ), patch.object(account_ui.st, "caption"), patch.object(account_ui.st, "warning") as warning, patch.object(
            auth_supabase,
            "sign_in",
            return_value=(None, "Email not confirmed"),
        ):
            account_ui.render_mobile_auth_entry(config=config)

        self.assertTrue(session_state[auth_supabase.CONFIRMATION_REQUIRED_KEY])
        self.assertEqual(session_state[auth_supabase.CONFIRMATION_EMAIL_KEY], "user@example.com")
        warning.assert_not_called()

    def test_successful_login_survives_authenticated_rerun_without_trade_work(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        session_state = {"launch_auth_mode": "account"}
        payload = {
            "access_token": "access",
            "refresh_token": "refresh",
            "expires_in": 3600,
            "user": {"id": "user-1", "email": "user@example.com"},
        }
        buttons = {
            "Continue as guest instead": False,
            "Log in": True,
            "Create account": False,
        }

        with patch.object(account_ui.st, "session_state", session_state), patch.object(
            account_ui.st,
            "markdown",
        ), patch.object(account_ui.st, "tabs", return_value=[_StreamlitContext(), _StreamlitContext()]), patch.object(
            account_ui.st,
            "text_input",
            side_effect=["user@example.com", "password"],
        ), patch.object(
            account_ui.st,
            "button",
            side_effect=lambda label, **_kwargs: buttons.get(label, False),
        ), patch.object(account_ui.st, "caption"), patch.object(account_ui.st, "success"), patch.object(
            account_ui.st,
            "rerun",
            side_effect=_StreamlitRerun,
        ), patch.object(auth_supabase, "sign_in", return_value=(payload, "")), patch.object(
            account_ui,
            "cached_trade_ideas",
            create=True,
        ) as trade_generation, patch.object(
            account_ui,
            "enforce_trade_board",
            create=True,
        ) as trust_enforcement:
            with self.assertRaises(_StreamlitRerun):
                account_ui.render_mobile_auth_entry(config=config)

        self.assertEqual(auth_supabase.current_user_id(session_state), "user-1")
        self.assertEqual(auth_supabase.current_access_token(session_state), "access")
        self.assertEqual(
            session_state[auth_supabase.DURABLE_AUTH_PENDING_SAVE_KEY]["refresh_token"],
            "refresh",
        )
        trade_generation.assert_not_called()
        trust_enforcement.assert_not_called()

        with patch.object(account_ui.st, "session_state", session_state), patch.object(
            account_ui.st,
            "markdown",
        ), patch.object(account_ui.st, "success"), patch.object(account_ui.st, "info"), patch.object(
            account_ui.st,
            "caption",
        ), patch.object(account_ui.st, "button", return_value=False), patch.object(
            account_store,
            "fetch_saved_leagues",
            return_value=([], ""),
        ):
            actions = account_ui.render_mobile_auth_entry(config=config)

        self.assertTrue(actions["logged_in"])
        self.assertEqual(auth_supabase.current_user_id(session_state), "user-1")
        self.assertEqual(auth_supabase.current_access_token(session_state), "access")

    def test_invalid_login_credentials_show_visible_error(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        session_state = {"launch_auth_mode": "account"}
        buttons = {
            "Continue as guest instead": False,
            "Log in": True,
            "Create account": False,
        }

        with patch.object(account_ui.st, "session_state", session_state), patch.object(
            account_ui.st,
            "markdown",
        ), patch.object(account_ui.st, "tabs", return_value=[_StreamlitContext(), _StreamlitContext()]), patch.object(
            account_ui.st,
            "text_input",
            side_effect=["user@example.com", "wrong-password", "", ""],
        ), patch.object(
            account_ui.st,
            "button",
            side_effect=lambda label, **_kwargs: buttons.get(label, False),
        ), patch.object(account_ui.st, "caption"), patch.object(account_ui.st, "warning") as warning, patch.object(
            auth_supabase,
            "sign_in",
            return_value=(None, "Invalid login credentials"),
        ):
            account_ui.render_mobile_auth_entry(config=config)

        warning.assert_called_once_with("Could not sign in with that email and password.")
        self.assertEqual(auth_supabase.current_user_id(session_state), "")

    def test_logout_then_second_login_replaces_authenticated_session(self):
        config = {"enabled": True, "url": "https://example.supabase.co", "anon_key": "anon"}
        session_state = {"launch_auth_mode": "account"}
        auth_supabase.apply_auth_payload(
            session_state,
            {
                "access_token": "first-access",
                "refresh_token": "first-refresh",
                "user": {"id": "user-1", "email": "first@example.com"},
            },
        )

        with patch.object(account_ui.st, "session_state", session_state), patch.object(
            account_ui.st,
            "markdown",
        ), patch.object(account_ui.st, "subheader"), patch.object(account_ui.st, "caption"), patch.object(
            account_ui.st,
            "columns",
            return_value=[_StreamlitContext(), _StreamlitContext()],
        ), patch.object(
            account_ui.st,
            "button",
            side_effect=lambda label, **_kwargs: label == "Log out",
        ), patch.object(account_ui.st, "rerun", side_effect=_StreamlitRerun), patch.object(
            auth_supabase,
            "sign_out",
            return_value="",
        ):
            with self.assertRaises(_StreamlitRerun):
                account_ui.render_account_panel(config=config)

        self.assertEqual(auth_supabase.current_user_id(session_state), "")
        self.assertTrue(session_state[auth_supabase.DURABLE_AUTH_PENDING_CLEAR_KEY])

        bridge_result = Mock(status={"ok": True, "action": "clear"}, stored=None)
        with patch.object(account_ui.st, "session_state", session_state), patch.object(
            account_ui,
            "AUTH_STORAGE_COMPONENT",
            return_value=bridge_result,
        ):
            bridge_actions = account_ui.render_durable_auth_bridge(config=config)

        self.assertTrue(bridge_actions["cleared"])
        self.assertNotIn(auth_supabase.DURABLE_AUTH_PENDING_CLEAR_KEY, session_state)

        second_payload = {
            "access_token": "second-access",
            "refresh_token": "second-refresh",
            "user": {"id": "user-2", "email": "second@example.com"},
        }
        buttons = {
            "Continue as guest instead": False,
            "Log in": True,
            "Create account": False,
        }
        with patch.object(account_ui.st, "session_state", session_state), patch.object(
            account_ui.st,
            "markdown",
        ), patch.object(account_ui.st, "tabs", return_value=[_StreamlitContext(), _StreamlitContext()]), patch.object(
            account_ui.st,
            "text_input",
            side_effect=["second@example.com", "password"],
        ), patch.object(
            account_ui.st,
            "button",
            side_effect=lambda label, **_kwargs: buttons.get(label, False),
        ), patch.object(account_ui.st, "caption"), patch.object(account_ui.st, "success"), patch.object(
            account_ui.st,
            "rerun",
            side_effect=_StreamlitRerun,
        ), patch.object(auth_supabase, "sign_in", return_value=(second_payload, "")):
            with self.assertRaises(_StreamlitRerun):
                account_ui.render_mobile_auth_entry(config=config)

        self.assertEqual(auth_supabase.current_user_id(session_state), "user-2")
        self.assertEqual(auth_supabase.current_access_token(session_state), "second-access")
        self.assertNotIn(auth_supabase.DURABLE_AUTH_PENDING_CLEAR_KEY, session_state)

    def test_supabase_sql_documents_expected_account_schema(self):
        sql_path = Path("docs/supabase_accounts.sql")
        self.assertTrue(sql_path.exists())
        sql = sql_path.read_text(encoding="utf-8")

        self.assertIn("create table if not exists public.profiles", sql)
        self.assertIn("user_id uuid primary key references auth.users(id)", sql)
        self.assertIn("entitlement text not null default 'free'", sql)
        self.assertIn("entitlement in ('free', 'premium')", sql)
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

    def test_no_service_role_secret_is_hardcoded_in_account_sources(self):
        paths = [
            Path("modules/auth_supabase.py"),
            Path("modules/account_store.py"),
            Path("modules/account_ui.py"),
            Path("app.py"),
        ]
        combined = "\n".join(path.read_text(encoding="utf-8").casefold() for path in paths)

        self.assertNotIn("service_role", combined)
        self.assertNotIn("service-role", combined)


if __name__ == "__main__":
    unittest.main()
