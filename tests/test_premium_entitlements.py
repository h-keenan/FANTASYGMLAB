import unittest
from collections import UserDict
from pathlib import Path

from modules import premium
from modules import premium_benefits


class TestPremiumEntitlements(unittest.TestCase):
    def test_default_entitlement_is_free(self):
        self.assertEqual(premium.get_user_entitlement(session_state={}), premium.FREE)
        self.assertFalse(premium.is_premium_user(session_state={}))

    def test_env_override_marks_user_premium(self):
        self.assertEqual(
            premium.get_user_entitlement(environ={"DYNASTYGM_PREMIUM_OVERRIDE": "true"}),
            premium.PREMIUM,
        )

    def test_streamlit_secret_override_marks_user_premium(self):
        self.assertEqual(
            premium.get_user_entitlement(environ={}, secrets={"DYNASTYGM_PREMIUM_OVERRIDE": "yes"}),
            premium.PREMIUM,
        )

    def test_missing_supabase_fields_degrade_to_free(self):
        account = {"user_id": "user-1", "email": "test@example.com"}
        settings = {"settings": {"theme": "dark"}}
        self.assertEqual(
            premium.get_user_entitlement(account=account, user_settings=settings, environ={}),
            premium.FREE,
        )

    def test_profile_entitlement_can_mark_premium_without_payment_data(self):
        self.assertEqual(
            premium.get_user_entitlement(account={"entitlement": "premium"}, environ={}),
            premium.PREMIUM,
        )

    def test_account_profile_argument_marks_premium(self):
        profile = {"user_id": "user-1", "entitlement": " premium "}
        debug = premium.get_entitlement_debug(account_profile=profile, environ={})

        self.assertEqual(debug["entitlement"], premium.PREMIUM)
        self.assertTrue(debug["is_premium"])
        self.assertEqual(debug["source"], "account_profile.entitlement")
        self.assertEqual(debug["raw_value"], "premium")
        self.assertEqual(
            premium.get_user_entitlement(account_profile=profile, environ={}),
            premium.PREMIUM,
        )
        self.assertTrue(premium.is_premium_user(account_profile=profile, environ={}))

    def test_entitlement_free_and_unknown_values_degrade_to_free(self):
        self.assertEqual(
            premium.get_user_entitlement(account={"entitlement": "free"}, environ={}),
            premium.FREE,
        )
        self.assertEqual(
            premium.get_user_entitlement(account={"entitlement": "gold"}, environ={}),
            premium.FREE,
        )

    def test_legacy_settings_fallback_remains_backward_compatible(self):
        self.assertEqual(
            premium.get_user_entitlement(user_settings={"settings": {"plan": "premium"}}, environ={}),
            premium.PREMIUM,
        )

    def test_canonical_entitlement_takes_precedence_over_legacy_fields(self):
        self.assertEqual(
            premium.get_user_entitlement(
                account={"entitlement": "free"},
                user_settings={"settings": {"plan": "premium", "is_premium": True}},
                environ={},
            ),
            premium.FREE,
        )

    def test_dev_override_returns_premium_regardless_of_profile_value(self):
        self.assertEqual(
            premium.get_user_entitlement(
                account={"entitlement": "free"},
                environ={"DYNASTYGM_PREMIUM_OVERRIDE": "true"},
            ),
            premium.PREMIUM,
        )

    def test_session_profile_requires_authenticated_user(self):
        self.assertEqual(
            premium.get_user_entitlement(
                session_state={"account_profile": {"entitlement": "premium"}},
                environ={},
            ),
            premium.FREE,
        )
        self.assertEqual(
            premium.get_user_entitlement(
                session_state={
                    "auth_session": {"user_id": "user-1"},
                    "account_profile": {"entitlement": "premium"},
                },
                environ={},
            ),
            premium.PREMIUM,
        )

    def test_stale_session_user_settings_require_authenticated_user(self):
        self.assertEqual(
            premium.get_user_entitlement(
                session_state={"account_user_settings": {"settings": {"plan": "premium"}}},
                environ={},
            ),
            premium.FREE,
        )

    def test_account_profile_entitlement_wins_over_stale_user_settings(self):
        state = {
            "auth_session": {"user_id": "user-1"},
            "account_profile": {"user_id": "user-1", "entitlement": "premium"},
            "account_user_settings": {"settings": {"entitlement": "free", "plan": "free"}},
        }

        debug = premium.get_entitlement_debug(session_state=state, environ={})

        self.assertEqual(debug["entitlement"], premium.PREMIUM)
        self.assertTrue(debug["is_premium"])
        self.assertEqual(debug["source"], "account_profile.entitlement")
        self.assertEqual(premium.get_user_entitlement(session_state=state, environ={}), premium.PREMIUM)

    def test_streamlit_session_state_mapping_profile_marks_premium(self):
        state = UserDict(
            {
                "auth_session": {"user_id": "user-1"},
                "auth_email": "user@example.com",
                "account_profile_status": "loaded",
                "account_profile": {
                    "user_id": "user-1",
                    "email": "user@example.com",
                    "entitlement": "premium",
                },
                "account_user_settings": {"settings": {"entitlement": "free"}},
            }
        )

        debug = premium.get_entitlement_debug(session_state=state, environ={})

        self.assertEqual(debug["entitlement"], premium.PREMIUM)
        self.assertTrue(debug["is_premium"])
        self.assertEqual(debug["source"], "account_profile.entitlement")
        self.assertEqual(debug["raw_value"], "premium")
        self.assertEqual(debug["profile_status"], "loaded")

    def test_entitlement_debug_reports_profile_missing_and_error(self):
        missing = premium.get_entitlement_debug(
            session_state={
                "auth_session": {"user_id": "user-1"},
                "account_profile_status": "missing",
            },
            environ={},
        )
        error = premium.get_entitlement_debug(
            session_state={
                "auth_session": {"user_id": "user-1"},
                "account_profile_status": "error",
                "account_profile_error": "RLS blocked profile fetch.",
            },
            environ={},
        )

        self.assertEqual(missing["entitlement"], premium.FREE)
        self.assertEqual(missing["reason"], "profile_missing")
        self.assertEqual(error["entitlement"], premium.FREE)
        self.assertEqual(error["reason"], "profile_error")
        self.assertIn("RLS blocked", error["profile_error"])

    def test_entitlement_debug_reports_dev_override_source(self):
        debug = premium.get_entitlement_debug(
            session_state={
                "auth_session": {"user_id": "user-1"},
                "account_profile": {"entitlement": "free"},
            },
            environ={"DYNASTYGM_PREMIUM_OVERRIDE": "true"},
        )

        self.assertEqual(debug["entitlement"], premium.PREMIUM)
        self.assertEqual(debug["source"], "dev_override")

    def test_auth_debug_gate_is_dev_only(self):
        self.assertFalse(premium.debug_auth_enabled(environ={}, secrets={}))
        self.assertTrue(premium.debug_auth_enabled(environ={"DYNASTYGM_DEBUG_AUTH": "true"}, secrets={}))
        self.assertTrue(premium.debug_auth_enabled(environ={}, secrets={"DYNASTYGM_DEBUG_AUTH": "yes"}))

    def test_premium_lock_component_renders_without_checkout(self):
        html = premium.premium_lock_html("Full trade board", "More ideas.", feature="Premium Trade Hub")
        self.assertIn("premium-lock", html)
        self.assertIn("premium-badge", html)
        self.assertIn("Premium Trade Hub", html)
        self.assertNotIn("stripe", html.casefold())
        self.assertNotIn("checkout", html.casefold())
        self.assertNotIn("subscribe", html.casefold())
        self.assertNotIn("payment", html.casefold())

    def test_premium_lock_copy_is_short_and_value_focused(self):
        html = premium.premium_lock_html(
            "Full waiver board",
            "Stash candidates, watchlist depth, and deeper add/drop context.",
            feature="Premium Waivers",
        )

        self.assertIn("Full waiver board", html)
        self.assertIn("Upgrade to Premium", html)
        self.assertIn("Included with Premium", html)
        self.assertIn("Stash candidates", html)
        for blocked_word in ("checkout", "stripe", "subscribe now", "payment link"):
            self.assertNotIn(blocked_word, html.casefold())


    def test_billing_foundation_does_not_add_client_side_self_upgrade(self):
        combined = "\n".join(
            Path(path).read_text(encoding="utf-8").casefold()
            for path in (
                "modules/premium.py",
                "modules/premium_benefits.py",
                "modules/account_store.py",
                "modules/stripe_billing.py",
            )
        )

        for blocked_word in (
            "update profiles set entitlement",
            "entitlement = 'premium'",
            '"entitlement": "premium"',
            "payment link",
            "subscribe now",
        ):
            self.assertNotIn(blocked_word, combined)


if __name__ == "__main__":
    unittest.main()
