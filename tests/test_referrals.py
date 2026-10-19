import unittest
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from modules import premium
from modules import referrals


USER_A = "11111111-1111-4111-8111-111111111111"
USER_B = "22222222-2222-4222-8222-222222222222"


class TestReferralCodeRoundTrip(unittest.TestCase):
    """Code <-> user_id is bijective — no lookup table needed anywhere."""

    def test_encode_then_decode_recovers_the_same_user_id(self):
        code = referrals.referral_code_for_user(USER_A)
        self.assertTrue(code)
        self.assertEqual(referrals.referrer_user_id_from_code(code), USER_A)

    def test_two_different_users_get_two_different_codes(self):
        self.assertNotEqual(
            referrals.referral_code_for_user(USER_A),
            referrals.referral_code_for_user(USER_B),
        )

    def test_random_uuids_never_collide_across_many_samples(self):
        codes = {referrals.referral_code_for_user(str(uuid.uuid4())) for _ in range(500)}
        self.assertEqual(len(codes), 500)

    def test_invalid_user_id_encodes_to_empty_string(self):
        self.assertEqual(referrals.referral_code_for_user("not-a-uuid"), "")
        self.assertEqual(referrals.referral_code_for_user(None), "")

    def test_garbage_code_decodes_to_empty_string_not_a_raise(self):
        self.assertEqual(referrals.referrer_user_id_from_code("not valid!!"), "")
        self.assertEqual(referrals.referrer_user_id_from_code(""), "")
        self.assertEqual(referrals.referrer_user_id_from_code(None), "")

    def test_referral_link_embeds_the_code_as_a_query_param(self):
        link = referrals.referral_link(USER_A, base_url="https://app.fantasygmlab.com")
        self.assertTrue(link.startswith("https://app.fantasygmlab.com/?ref="))
        code = link.split("ref=")[-1]
        self.assertEqual(referrals.referrer_user_id_from_code(code), USER_A)

    def test_referral_link_is_empty_for_an_invalid_user(self):
        self.assertEqual(referrals.referral_link("nope", base_url="https://x.test"), "")


class TestCaptureReferralCode(unittest.TestCase):
    """Session-only capture of a visiting `?ref=` link."""

    def test_valid_code_is_cached_pending(self):
        code = referrals.referral_code_for_user(USER_A)
        session_state: dict = {}
        referrals.capture_referral_code(code, session_state)
        self.assertEqual(session_state[referrals.PENDING_CODE_SESSION_KEY], code)
        self.assertEqual(session_state[referrals.PENDING_REFERRER_SESSION_KEY], USER_A)

    def test_blank_or_invalid_code_is_ignored(self):
        # "garbage" is not used here — every lowercase letter is a valid
        # base62 digit, so it decodes to *some* (almost certainly
        # nonexistent) UUID rather than failing to decode at all; see
        # test_garbage_code_decodes_to_empty_string_not_a_raise for a code
        # that is actually outside the base62 charset.
        session_state: dict = {}
        referrals.capture_referral_code("", session_state)
        referrals.capture_referral_code("not valid!!", session_state)
        referrals.capture_referral_code(None, session_state)
        self.assertNotIn(referrals.PENDING_CODE_SESSION_KEY, session_state)

    def test_self_referral_is_never_captured(self):
        code = referrals.referral_code_for_user(USER_A)
        session_state = {"auth_session": {"user_id": USER_A}}
        referrals.capture_referral_code(code, session_state)
        self.assertNotIn(referrals.PENDING_CODE_SESSION_KEY, session_state)

    def test_streamlit_list_shaped_query_value_is_unwrapped(self):
        code = referrals.referral_code_for_user(USER_A)
        session_state: dict = {}
        referrals.capture_referral_code([code], session_state)
        self.assertEqual(session_state[referrals.PENDING_CODE_SESSION_KEY], code)


class TestReferralConnectionReward(unittest.TestCase):
    """The 3-referral threshold and the 3-free-month cap — pure logic."""

    def test_first_two_distinct_connections_grant_nothing(self):
        state = None
        for i in range(2):
            result = referrals.with_referral_connection_recorded(
                state, referred_user_id=f"user-{i}"
            )
            state = {"settings": result["settings"]}
        program = referrals.program_state(state)
        self.assertEqual(program["connected_count"], 2)
        self.assertEqual(program["comp_months_granted"], 0)
        self.assertIsNone(program.get("comp_until"))

    def test_third_distinct_connection_grants_one_comp_month(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        state = None
        for i in range(3):
            result = referrals.with_referral_connection_recorded(
                state, referred_user_id=f"user-{i}", now=now
            )
            state = {"settings": result["settings"]}
        program = referrals.program_state(state)
        self.assertEqual(program["connected_count"], 3)
        self.assertEqual(program["comp_months_granted"], 1)
        comp_until = datetime.fromisoformat(program["comp_until"])
        self.assertEqual(comp_until, now + timedelta(days=30))

    def test_reconnecting_the_same_referred_user_does_not_double_count(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        first = referrals.with_referral_connection_recorded(
            None, referred_user_id="user-0", now=now
        )
        second = referrals.with_referral_connection_recorded(
            {"settings": first["settings"]}, referred_user_id="user-0", now=now
        )
        self.assertTrue(second["already_counted"])
        program = referrals.program_state({"settings": second["settings"]})
        self.assertEqual(program["connected_count"], 1)
        self.assertEqual(program["comp_months_granted"], 0)

    def test_nine_distinct_referrals_cap_at_three_comp_months(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        state = None
        for i in range(9):
            result = referrals.with_referral_connection_recorded(
                state, referred_user_id=f"user-{i}", now=now + timedelta(days=i)
            )
            state = {"settings": result["settings"]}
        program = referrals.program_state(state)
        self.assertEqual(program["connected_count"], 9)
        self.assertEqual(program["comp_months_granted"], 3)

    def test_a_tenth_and_twelfth_referral_grant_no_further_months_past_the_cap(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        state = None
        for i in range(12):
            result = referrals.with_referral_connection_recorded(
                state, referred_user_id=f"user-{i}", now=now + timedelta(days=i)
            )
            state = {"settings": result["settings"]}
        program = referrals.program_state(state)
        self.assertEqual(program["connected_count"], 12)
        self.assertEqual(program["comp_months_granted"], 3)
        self.assertEqual(referrals.comp_months_remaining_capacity(state), 0)

    def test_stacking_extends_from_the_existing_comp_until_not_from_now(self):
        # Two comp-earning batches of 3, the second landing while the first
        # month is still active, must ADD 30 days on top of the existing
        # comp_until rather than restarting the clock from "now".
        t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
        state = None
        for i in range(3):
            result = referrals.with_referral_connection_recorded(
                state, referred_user_id=f"batch1-{i}", now=t0
            )
            state = {"settings": result["settings"]}
        first_comp_until = datetime.fromisoformat(referrals.program_state(state)["comp_until"])
        self.assertEqual(first_comp_until, t0 + timedelta(days=30))

        t1 = t0 + timedelta(days=5)  # still well inside the first comp month
        for i in range(3):
            result = referrals.with_referral_connection_recorded(
                state, referred_user_id=f"batch2-{i}", now=t1
            )
            state = {"settings": result["settings"]}
        program = referrals.program_state(state)
        self.assertEqual(program["comp_months_granted"], 2)
        second_comp_until = datetime.fromisoformat(program["comp_until"])
        self.assertEqual(second_comp_until, first_comp_until + timedelta(days=30))

    def test_comp_is_active_true_before_expiry_false_after(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        state = None
        for i in range(3):
            result = referrals.with_referral_connection_recorded(
                state, referred_user_id=f"user-{i}", now=now
            )
            state = {"settings": result["settings"]}
        self.assertTrue(referrals.comp_is_active(state, now=now + timedelta(days=1)))
        self.assertFalse(referrals.comp_is_active(state, now=now + timedelta(days=31)))

    def test_no_settings_at_all_has_no_active_comp(self):
        self.assertFalse(referrals.comp_is_active(None))
        self.assertFalse(referrals.comp_is_active({}))


class TestAttributionRecord(unittest.TestCase):
    def test_merge_preserves_unrelated_settings(self):
        existing = {"settings": {"theme_mode": "dark"}}
        updated = referrals.with_attribution_recorded(
            existing, referrer_user_id=USER_A, code="abc"
        )
        self.assertEqual(updated["settings"]["theme_mode"], "dark")
        record = updated["settings"][referrals.REFERRAL_ATTRIBUTION_KEY]
        self.assertEqual(record["referrer_user_id"], USER_A)
        self.assertTrue(record["connected_recorded"])

    def test_attribution_record_reads_back_the_merged_value(self):
        updated = referrals.with_attribution_recorded(None, referrer_user_id=USER_A, code="abc")
        # `updated` (`{"settings": {...}}`) is already row-shaped — the
        # shape every other reader here (attribution_record, program_state)
        # expects as its own input.
        record = referrals.attribution_record(updated)
        self.assertEqual(record["referrer_user_id"], USER_A)


class TestGrantReferralCredit(unittest.TestCase):
    """Cross-row service-role write, mirroring modules.stripe_webhook's
    own GET/PATCH test style (SimpleNamespace + Mock request_session)."""

    def _config(self):
        return {"url": "https://example.supabase.co", "service_role_key": "service-key"}

    def test_invalid_pair_is_rejected_without_any_request(self):
        session = SimpleNamespace(get=Mock(), post=Mock())
        ok, error = referrals.grant_referral_credit(
            config=self._config(),
            referrer_user_id=USER_A,
            referred_user_id=USER_A,
            request_session=session,
        )
        self.assertFalse(ok)
        session.get.assert_not_called()

    def test_unconfigured_service_role_is_rejected(self):
        session = SimpleNamespace(get=Mock(), post=Mock())
        ok, error = referrals.grant_referral_credit(
            config={"url": "", "service_role_key": ""},
            referrer_user_id=USER_A,
            referred_user_id=USER_B,
            request_session=session,
        )
        self.assertFalse(ok)
        session.get.assert_not_called()

    def test_successful_credit_patches_merged_settings_back(self):
        get_response = SimpleNamespace(
            status_code=200,
            json=Mock(return_value=[{"user_id": USER_A, "settings": {}}]),
        )
        post_response = SimpleNamespace(status_code=201)
        session = SimpleNamespace(
            get=Mock(return_value=get_response),
            post=Mock(return_value=post_response),
        )
        ok, error = referrals.grant_referral_credit(
            config=self._config(),
            referrer_user_id=USER_A,
            referred_user_id=USER_B,
            request_session=session,
        )
        self.assertTrue(ok)
        self.assertEqual(error, "")
        call = session.post.call_args
        self.assertIn("/rest/v1/user_settings?on_conflict=user_id", call.args[0])
        self.assertEqual(call.kwargs["headers"]["Authorization"], "Bearer service-key")
        written_program = call.kwargs["json"]["settings"][referrals.REFERRAL_PROGRAM_KEY]
        self.assertEqual(written_program["referred_user_ids"], [USER_B])
        self.assertEqual(written_program["connected_count"], 1)

    def test_already_counted_referral_skips_the_write_entirely(self):
        existing_settings = {
            referrals.REFERRAL_PROGRAM_KEY: {
                "referred_user_ids": [USER_B],
                "connected_count": 1,
                "comp_months_granted": 0,
                "comp_until": None,
            }
        }
        get_response = SimpleNamespace(
            status_code=200,
            json=Mock(return_value=[{"user_id": USER_A, "settings": existing_settings}]),
        )
        session = SimpleNamespace(get=Mock(return_value=get_response), post=Mock())
        ok, error = referrals.grant_referral_credit(
            config=self._config(),
            referrer_user_id=USER_A,
            referred_user_id=USER_B,
            request_session=session,
        )
        self.assertTrue(ok)
        session.post.assert_not_called()

    def test_get_failure_is_reported_without_raising(self):
        get_response = SimpleNamespace(status_code=500, json=Mock(return_value={}))
        session = SimpleNamespace(get=Mock(return_value=get_response), post=Mock())
        ok, error = referrals.grant_referral_credit(
            config=self._config(),
            referrer_user_id=USER_A,
            referred_user_id=USER_B,
            request_session=session,
        )
        self.assertFalse(ok)
        self.assertTrue(error)

    def test_network_exception_is_caught_not_raised(self):
        session = SimpleNamespace(get=Mock(side_effect=RuntimeError("boom")))
        ok, error = referrals.grant_referral_credit(
            config=self._config(),
            referrer_user_id=USER_A,
            referred_user_id=USER_B,
            request_session=session,
        )
        self.assertFalse(ok)
        self.assertTrue(error)


class TestHandleSleeperConnected(unittest.TestCase):
    """End-to-end wiring: attribution write + referrer credit, idempotent."""

    def _session_state(self, *, pending_referrer=USER_A, user_id=USER_B):
        code = referrals.referral_code_for_user(pending_referrer)
        return {
            referrals.PENDING_CODE_SESSION_KEY: code,
            referrals.PENDING_REFERRER_SESSION_KEY: pending_referrer,
            "auth_session": {"user_id": user_id, "access_token": "token-123"},
            "account_user_settings": {"user_id": user_id, "settings": {}},
        }

    def test_no_pending_code_is_a_clean_no_op(self):
        error = referrals.handle_sleeper_connected(config={}, session_state={})
        self.assertEqual(error, "")

    def test_guest_without_auth_keeps_the_pending_marker_for_later(self):
        session_state = self._session_state()
        session_state.pop("auth_session")
        error = referrals.handle_sleeper_connected(config={}, session_state=session_state)
        self.assertEqual(error, "")
        self.assertIn(referrals.PENDING_CODE_SESSION_KEY, session_state)

    def test_self_referral_clears_the_marker_and_grants_nothing(self):
        session_state = self._session_state(pending_referrer=USER_A, user_id=USER_A)
        with patch("modules.referrals.grant_referral_credit") as mock_grant:
            error = referrals.handle_sleeper_connected(config={}, session_state=session_state)
        self.assertEqual(error, "")
        mock_grant.assert_not_called()
        self.assertNotIn(referrals.PENDING_CODE_SESSION_KEY, session_state)

    def test_successful_flow_persists_attribution_and_credits_referrer(self):
        session_state = self._session_state()
        with patch("modules.account_store.upsert_user_settings", return_value=(True, "")) as mock_upsert, \
             patch("modules.referrals.grant_referral_credit", return_value=(True, "")) as mock_grant:
            error = referrals.handle_sleeper_connected(config={"url": "x"}, session_state=session_state)
        self.assertEqual(error, "")
        mock_upsert.assert_called_once()
        mock_grant.assert_called_once()
        call_kwargs = mock_grant.call_args.kwargs
        self.assertEqual(call_kwargs["referrer_user_id"], USER_A)
        self.assertEqual(call_kwargs["referred_user_id"], USER_B)
        # Own-row attribution marker now reflects the persisted payload.
        attribution = referrals.attribution_record(session_state["account_user_settings"])
        self.assertTrue(attribution.get("connected_recorded"))
        self.assertNotIn(referrals.PENDING_CODE_SESSION_KEY, session_state)
        self.assertNotIn(referrals.PENDING_REFERRER_SESSION_KEY, session_state)

    def test_already_attributed_session_never_calls_credit_again(self):
        session_state = self._session_state()
        session_state["account_user_settings"] = referrals.with_attribution_recorded(
            None, referrer_user_id=USER_A, code="whatever"
        )
        with patch("modules.referrals.grant_referral_credit") as mock_grant:
            error = referrals.handle_sleeper_connected(config={}, session_state=session_state)
        self.assertEqual(error, "")
        mock_grant.assert_not_called()

    def test_attribution_write_failure_is_returned_and_skips_the_credit_call(self):
        session_state = self._session_state()
        with patch(
            "modules.account_store.upsert_user_settings",
            return_value=(False, "Something went wrong."),
        ), patch("modules.referrals.grant_referral_credit") as mock_grant:
            error = referrals.handle_sleeper_connected(config={}, session_state=session_state)
        self.assertEqual(error, "Something went wrong.")
        mock_grant.assert_not_called()


class TestEffectiveEntitlementReferralComp(unittest.TestCase):
    """modules.premium.effective_entitlement: comp upgrades Free only, and
    never overrides a real paid subscription."""

    def _comp_settings(self, *, active: bool):
        now = datetime.now(timezone.utc)
        delta = timedelta(days=5) if active else -timedelta(days=5)
        return {
            "settings": {
                referrals.REFERRAL_PROGRAM_KEY: {
                    "referred_user_ids": ["a", "b", "c"],
                    "connected_count": 3,
                    "comp_months_granted": 1,
                    "comp_until": (now + delta).isoformat(),
                }
            }
        }

    def test_free_profile_with_active_comp_resolves_pro(self):
        profile = {"user_id": "u1", "entitlement": "free"}
        tier = premium.effective_entitlement(
            account_profile=profile,
            user_settings=self._comp_settings(active=True),
        )
        self.assertEqual(tier, premium.PRO)

    def test_free_profile_with_expired_comp_resolves_free(self):
        profile = {"user_id": "u1", "entitlement": "free"}
        tier = premium.effective_entitlement(
            account_profile=profile,
            user_settings=self._comp_settings(active=False),
        )
        self.assertEqual(tier, premium.FREE)

    def test_no_profile_at_all_with_active_comp_still_resolves_free(self):
        # Guests with no Supabase account can never have a settings row, so
        # this documents intent rather than a realistic path, but it must
        # never grant Pro to someone with no authenticated account at all.
        tier = premium.effective_entitlement(
            account_profile=None,
            session_state=None,
            user_settings=self._comp_settings(active=True),
        )
        self.assertEqual(tier, premium.FREE)

    def test_active_paid_pro_subscription_is_unaffected_by_an_active_comp(self):
        profile = {"user_id": "u1", "entitlement": "premium"}  # legacy raw Pro value
        tier = premium.effective_entitlement(
            account_profile=profile,
            user_settings=self._comp_settings(active=True),
        )
        self.assertEqual(tier, premium.PRO)

    def test_active_front_office_subscription_is_unaffected_by_an_active_comp(self):
        profile = {"user_id": "u1", "entitlement": "front_office"}
        tier = premium.effective_entitlement(
            account_profile=profile,
            user_settings=self._comp_settings(active=True),
        )
        self.assertEqual(tier, premium.FRONT_OFFICE)

    def test_dev_override_still_wins_over_everything(self):
        profile = {"user_id": "u1", "entitlement": "free"}
        tier = premium.effective_entitlement(
            account_profile=profile,
            user_settings=self._comp_settings(active=False),
            environ={premium.PREMIUM_OVERRIDE_ENV: "1"},
        )
        self.assertEqual(tier, premium.PRO)

    def test_comp_is_read_from_session_state_account_user_settings_fallback(self):
        profile = {"user_id": "u1", "entitlement": "free"}
        session_state = {
            "auth_session": {"user_id": "u1"},
            "account_profile": profile,
            "account_user_settings": self._comp_settings(active=True),
        }
        tier = premium.effective_entitlement(session_state=session_state)
        self.assertEqual(tier, premium.PRO)


class TestInviteCtaRenders(unittest.TestCase):
    """Smoke test: the League Rankings CTA actually renders and its button
    click fires without raising (modules.referral_ui is otherwise untested
    by the pure-logic cases above, which only exercise modules.referrals)."""

    @pytest.mark.known_flaky
    def test_renders_referral_link_and_copy_button_for_a_signed_in_user(self):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_string(
            "import streamlit as st\n"
            "from modules import referral_ui\n"
            "st.session_state.setdefault('auth_session', {'user_id': "
            f"'{USER_A}', 'access_token': 'tok'}})\n"
            "referral_ui.render_invite_cta(session_state=st.session_state)\n"
        )
        at.run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.button), 1)

        at.button[0].click().run()
        self.assertFalse(at.exception)

    def test_renders_nothing_for_a_signed_out_session(self):
        from streamlit.testing.v1 import AppTest

        at = AppTest.from_string(
            "import streamlit as st\n"
            "from modules import referral_ui\n"
            "referral_ui.render_invite_cta(session_state=st.session_state)\n"
        )
        at.run()
        self.assertFalse(at.exception)
        self.assertEqual(len(at.button), 0)


if __name__ == "__main__":
    unittest.main()
