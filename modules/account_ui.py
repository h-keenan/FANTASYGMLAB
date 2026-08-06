from __future__ import annotations

from typing import Any
import time

import streamlit as st

from modules import account_store
from modules import auth_supabase
from modules import startup_coordinator
from modules import user_preferences

AUTH_STORAGE_COMPONENT = st.components.v2.component(
    "supabase_auth_storage",
    html="""<div id="supabase-auth-storage-root" aria-hidden="true"></div>""",
    js="""
    export default function(component) {
      const { data, setTriggerValue } = component
      const storageKey = (data && data.storageKey) || "dynastygm_supabase_auth_v2"
      const legacyKeys = (data && data.legacyStorageKeys) || ["dynastygm_supabase_auth"]
      const command = (data && data.command) || "read"
      const hasSession = Boolean(data && data.hasSession)
      window.__dynastyGmSupabaseAuthHasSession = hasSession

      const emit = (name, payload) => {
        setTriggerValue(name, { ...(payload || {}), ts: Date.now() })
      }

      const readRaw = () => {
        let raw = window.localStorage.getItem(storageKey)
        if (raw) return raw
        for (const legacy of legacyKeys) {
          raw = window.localStorage.getItem(legacy)
          if (raw) {
            try {
              window.localStorage.setItem(storageKey, raw)
              window.localStorage.removeItem(legacy)
            } catch (error) {}
            return raw
          }
        }
        return null
      }

      const readStoredAuth = (reason) => {
        const raw = readRaw()
        if (!raw) {
          emit("status", { action: "read", ok: true, reason, durableAuthPresent: false })
          return
        }
        const stored = JSON.parse(raw)
        emit("stored", stored && typeof stored === "object" ? { ...stored, _resume_reason: reason } : {})
      }

      const installResumeHooks = () => {
        const hookKey = "__dynastyGmSupabaseAuthResumeInstalled"
        if (window[hookKey]) return
        window[hookKey] = true
        const resumeRead = (reason) => {
          try {
            readStoredAuth(reason)
          } catch (error) {
            emit("status", { action: "resume_read", ok: false, reason })
          }
        }
        window.addEventListener("pageshow", (event) => {
          if (window.__dynastyGmSupabaseAuthHasSession) return
          resumeRead(event && event.persisted ? "pageshow_persisted" : "pageshow")
        })
        window.addEventListener("focus", () => {
          if (!window.__dynastyGmSupabaseAuthHasSession) resumeRead("focus")
        })
        document.addEventListener("visibilitychange", () => {
          if (!window.__dynastyGmSupabaseAuthHasSession && document.visibilityState === "visible") resumeRead("visibilitychange")
        })
      }

      try {
        if (command === "save") {
          const session = (data && data.session) || {}
          window.localStorage.setItem(storageKey, JSON.stringify(session))
          for (const legacy of legacyKeys) {
            try { window.localStorage.removeItem(legacy) } catch (error) {}
          }
          emit("status", { action: "saved", ok: true })
          return
        }
        if (command === "clear") {
          window.localStorage.removeItem(storageKey)
          for (const legacy of legacyKeys) {
            try { window.localStorage.removeItem(legacy) } catch (error) {}
          }
          emit("status", { action: "cleared", ok: true })
          return
        }
        installResumeHooks()
        if (hasSession) {
          emit("status", { action: "read", ok: true, reason: "session_present", durableAuthPresent: true })
          return
        }
        readStoredAuth("initial_read")
      } catch (error) {
        emit("status", { action: command, ok: false })
      }
    }
    """,
    isolate_styles=False,
)


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _auth_email(session_state) -> str:
    return _safe_text(session_state.get(auth_supabase.AUTH_EMAIL_KEY))


def _confirmation_email(session_state) -> str:
    return _safe_text(
        session_state.get(auth_supabase.CONFIRMATION_EMAIL_KEY)
        or session_state.get("launch_account_login_email")
        or session_state.get("launch_account_signup_email")
        or _auth_email(session_state)
    )


def render_confirmation_required_card(*, config: dict, email: str = "", key_prefix: str = "account") -> None:
    st.markdown(
        "<div class='account-confirm-card'>"
        "<div class='account-confirm-title'>Please confirm your email to continue.</div>"
        "<div class='account-confirm-copy'>Check your inbox, spam, or promotions folder. You can resend the confirmation email below.</div>"
        "</div>",
        unsafe_allow_html=True,
    )
    clean_email = _safe_text(email)
    if not clean_email:
        st.info("Enter your email address in the account form, then request another confirmation email.")
        return
    now = int(time.time())
    last_sent = int(st.session_state.get(auth_supabase.CONFIRMATION_RESEND_TS_KEY) or 0)
    cooldown_remaining = max(0, auth_supabase.CONFIRMATION_RESEND_COOLDOWN_SECONDS - (now - last_sent))
    if cooldown_remaining > 0:
        st.caption("You can request another email in a moment.")
        return
    if st.button("Resend confirmation email", key=f"{key_prefix}_resend_confirmation_email", use_container_width=True):
        sent, error = auth_supabase.resend_signup_confirmation(config, clean_email)
        st.session_state[auth_supabase.CONFIRMATION_RESEND_TS_KEY] = now
        if sent:
            st.success("Confirmation email sent. Check your inbox and spam folder.")
        else:
            st.warning("We could not send another confirmation email right now. Please try again in a moment.")


def render_durable_auth_bridge(*, config: dict) -> dict:
    actions = {
        "restored": False,
        "refreshed": False,
        "cleared": False,
        "pending": False,
        "storage_available": False,
        "error": "",
        "resume_reason": "",
    }
    if not auth_supabase.is_configured(config):
        return actions

    command = "read"
    session_payload = None
    if st.session_state.pop(auth_supabase.DURABLE_AUTH_PENDING_CLEAR_KEY, False):
        command = "clear"
        actions["cleared"] = True
    elif auth_supabase.DURABLE_AUTH_PENDING_SAVE_KEY in st.session_state:
        command = "save"
        session_payload = st.session_state.pop(auth_supabase.DURABLE_AUTH_PENDING_SAVE_KEY, None)

    try:
        result = AUTH_STORAGE_COMPONENT(
            key="supabase_auth_storage_bridge",
            data={
                "command": command,
                "storageKey": auth_supabase.DURABLE_AUTH_STORAGE_KEY,
                "legacyStorageKeys": list(auth_supabase.DURABLE_AUTH_LEGACY_STORAGE_KEYS),
                "session": session_payload or {},
                "hasSession": bool(auth_supabase.current_user_id(st.session_state)),
            },
            width=1,
            height=1,
        )
    except ValueError as exc:
        if "is not registered" not in str(exc):
            raise
        actions["error"] = "Browser auth storage is unavailable; using session-only login."
        return actions

    actions["storage_available"] = True
    status = getattr(result, "status", None)
    if isinstance(status, dict):
        st.session_state["auth_restore_last_status"] = {
            "action": _safe_text(status.get("action")),
            "ok": bool(status.get("ok", True)),
            "reason": _safe_text(status.get("reason")),
            "durable_auth_present": bool(status.get("durableAuthPresent")),
        }
    if isinstance(status, dict) and status.get("ok") is False:
        actions["error"] = "Browser auth storage is unavailable; using session-only login."
        st.session_state["auth_restore_last_result"] = "storage_error"
        return actions
    if command != "read" or auth_supabase.current_user_id(st.session_state):
        return actions

    stored = getattr(result, "stored", None)
    if command == "read" and status is None and stored is None:
        actions["pending"] = True
        return actions
    if not isinstance(stored, dict) or not stored:
        return actions
    resume_reason = _safe_text(stored.get("_resume_reason"), "stored_auth")
    actions["resume_reason"] = resume_reason
    st.session_state["auth_restore_last_reason"] = resume_reason
    restored, error, refreshed = auth_supabase.restore_auth_payload(
        config,
        st.session_state,
        stored,
    )
    actions["restored"] = restored
    actions["refreshed"] = refreshed
    actions["error"] = error
    st.session_state["auth_restore_last_result"] = "restored" if restored else "restore_failed"
    st.session_state["auth_restore_last_refreshed"] = bool(refreshed)
    if not restored and error:
        auth_supabase.queue_durable_auth_clear(st.session_state)
    return actions


def render_account_panel(
    *,
    config: dict,
    username: str = "",
    selected_league_id: str = "",
    selected_league_name: str = "",
    my_roster_id=None,
) -> dict:
    actions = {
        "resume_league": None,
        "saved": False,
        "logged_in": False,
    }
    st.markdown("---")
    st.subheader("Account")
    if not auth_supabase.is_configured(config):
        st.caption("Accounts are unavailable in this environment. Guest mode is active.")
        st.session_state.setdefault(auth_supabase.ACCOUNT_MODE_KEY, "guest")
        return actions

    session = auth_supabase.current_auth_session(st.session_state)
    user_id = auth_supabase.current_user_id(st.session_state)
    access_token = auth_supabase.current_access_token(st.session_state)
    if user_id and access_token:
        actions["logged_in"] = True
        email = _auth_email(st.session_state)
        st.caption(f"Signed in as {email or 'account user'}")
        button_cols = st.columns(2)
        with button_cols[0]:
            if st.button("Save league", key="account_save_current_league", use_container_width=True):
                saved, error = save_current_context(
                    config=config,
                    access_token=access_token,
                    user_id=user_id,
                    email=email,
                    username=username,
                    selected_league_id=selected_league_id,
                    selected_league_name=selected_league_name,
                    my_roster_id=my_roster_id,
                )
                actions["saved"] = saved
                if saved:
                    st.success("Saved.")
                    st.session_state.pop("account_saved_leagues_cache", None)
                else:
                    st.warning("Could not save league context right now. Please try again.")
        with button_cols[1]:
            if st.button("Log out", key="account_logout", use_container_width=True):
                error = auth_supabase.sign_out(config, access_token)
                auth_supabase.queue_durable_auth_clear(st.session_state)
                auth_supabase.clear_auth_session(st.session_state)
                st.session_state.pop("account_saved_leagues_cache", None)
                startup_coordinator.reset_startup_coordinator(st.session_state)
                if error:
                    st.warning(error)
                st.rerun()

        saved_rows = st.session_state.get("account_saved_leagues_cache")
        if not isinstance(saved_rows, list):
            saved_rows, error = account_store.fetch_saved_leagues(
                config,
                access_token,
                user_id=user_id,
            )
            if error:
                st.caption("Saved leagues could not be loaded right now.")
                saved_rows = []
            st.session_state["account_saved_leagues_cache"] = saved_rows
        if saved_rows:
            option_labels = {
                saved_league_label(row): row
                for row in saved_rows
                if _safe_text(row.get("league_id"))
            }
            selected_label = st.selectbox(
                "Saved league",
                list(option_labels.keys()),
                key="account_saved_league_select",
            )
            if st.button("Resume saved league", key="account_resume_saved_league", use_container_width=True):
                actions["resume_league"] = option_labels.get(selected_label)
        else:
            st.caption("No saved leagues yet.")

        with st.expander("Profile preferences", expanded=False):
            settings_row = st.session_state.get("account_user_settings")
            onboarding_hidden = user_preferences.onboarding_is_dismissed(settings_row)
            st.caption(
                "League Orientation is hidden on every device."
                if onboarding_hidden
                else "Reset League Orientation to show it again on the Dashboard."
            )
            if st.button(
                "Reset onboarding",
                key="account_reset_onboarding",
                use_container_width=True,
                help="Show League Orientation again on the Dashboard.",
            ):
                error = user_preferences.persist_authenticated_onboarding(
                    config=config,
                    session_state=st.session_state,
                    dismissed=False,
                )
                if error:
                    st.warning("Onboarding could not be reset right now. Please try again.")
                else:
                    st.success("League Orientation will appear again.")
        return actions

    st.caption("Use the main launch screen to create an account or sign in. Guest mode remains available.")
    return actions


def render_mobile_auth_entry(
    *,
    config: dict,
    username: str = "",
    selected_league_id: str = "",
    selected_league_name: str = "",
    my_roster_id=None,
) -> dict:
    actions = {
        "resume_league": None,
        "continue_guest": False,
        "logged_in": bool(auth_supabase.current_user_id(st.session_state)),
    }
    st.markdown(
        "<div class='launch-section-intro launch-account-intro'>"
        "<div class='launch-section-eyebrow'>Account</div>"
        "<div class='launch-section-title'>Save your league context</div>"
        "<div class='launch-section-copy'>Create an account to restore your default league automatically, or continue as a guest and import by Sleeper username.</div>"
        "</div>",
        unsafe_allow_html=True,
    )

    if not auth_supabase.is_configured(config):
        st.info("Accounts are not configured yet. Continue as a guest and import your Sleeper league below.")
        actions["continue_guest"] = True
        return actions

    if auth_supabase.current_user_id(st.session_state):
        email = _auth_email(st.session_state)
        st.success(f"Signed in as {email or 'account user'}.")
        saved_rows = st.session_state.get("account_saved_leagues_cache")
        if not isinstance(saved_rows, list):
            saved_rows, error = account_store.fetch_saved_leagues(
                config,
                auth_supabase.current_access_token(st.session_state),
                user_id=auth_supabase.current_user_id(st.session_state),
            )
            if error:
                st.warning(account_store.customer_safe_error(error, context="saved_leagues"))
                saved_rows = []
            st.session_state["account_saved_leagues_cache"] = saved_rows
        default_league = account_store.default_saved_league(saved_rows, require_default=True)
        if default_league:
            st.caption(f"Default saved league: {saved_league_label(default_league)}")
            auto_resume_key = f"_supabase_launch_auto_resume_attempted_{auth_supabase.current_user_id(st.session_state)}"
            if (
                not _safe_text(selected_league_id)
                and not st.session_state.get("supabase_auto_resume_suppressed")
                and not st.session_state.get(auto_resume_key)
            ):
                st.session_state[auto_resume_key] = True
                actions["resume_league"] = default_league
                return actions
            if st.button("Resume saved league", key="launch_resume_saved_league", use_container_width=True, type="primary"):
                actions["resume_league"] = default_league
        elif saved_rows:
            st.caption("Choose a saved league or add another Sleeper league.")
            option_labels = {
                saved_league_label(row): row
                for row in saved_rows
                if _safe_text(row.get("league_id"))
            }
            if option_labels:
                selected_label = st.selectbox(
                    "Saved league",
                    list(option_labels.keys()),
                    key="launch_saved_league_select",
                )
                if st.button("Open saved league", key="launch_open_saved_league", use_container_width=True, type="primary"):
                    actions["resume_league"] = option_labels.get(selected_label)
        else:
            st.info("Add your Sleeper leagues to save a default league to this account.")
        if st.button("Continue with Sleeper username", key="launch_continue_guest_signed_in", use_container_width=True):
            actions["continue_guest"] = True
        return actions

    if st.session_state.get("account_signup_check_email") or st.session_state.get(auth_supabase.CONFIRMATION_REQUIRED_KEY):
        render_confirmation_required_card(
            config=config,
            email=_confirmation_email(st.session_state),
            key_prefix="launch",
        )
        if st.button("Continue with Sleeper username", key="launch_continue_guest_after_signup", use_container_width=True):
            actions["continue_guest"] = True
        if st.button("Back to account login", key="launch_back_to_login", use_container_width=True):
            st.session_state["account_signup_check_email"] = False
            auth_supabase.clear_confirmation_required(st.session_state)
            st.rerun()
        return actions

    launch_mode = _safe_text(st.session_state.get("launch_auth_mode")).strip().lower()
    if launch_mode not in {"account", "guest"}:
        choice_cols = st.columns(2)
        with choice_cols[0]:
            if st.button("Create account / Sign in", key="launch_choose_account", use_container_width=True, type="primary"):
                st.session_state["launch_auth_mode"] = "account"
                st.rerun()
        with choice_cols[1]:
            if st.button("Continue as guest", key="launch_choose_guest", use_container_width=True):
                st.session_state["launch_auth_mode"] = "guest"
                actions["continue_guest"] = True
        st.caption("Guest mode is fully usable. Accounts add saved leagues and default-league restore.")
        return actions

    if launch_mode == "guest":
        actions["continue_guest"] = True
        st.caption("Guest mode active. Import a league below.")
        if st.button("Sign in instead", key="launch_guest_to_account", use_container_width=True):
            st.session_state["launch_auth_mode"] = "account"
            st.rerun()
        return actions

    if st.button("Continue as guest instead", key="launch_account_to_guest", use_container_width=True):
        st.session_state["launch_auth_mode"] = "guest"
        actions["continue_guest"] = True
        return actions

    st.markdown("#### Create account / Sign in")
    tabs = st.tabs(["Log in", "Create account"])
    with tabs[0]:
        login_email = st.text_input("Email", key="launch_account_login_email")
        login_password = st.text_input("Password", type="password", key="launch_account_login_password")
        if st.button("Log in", key="launch_account_login_button", use_container_width=True, type="primary"):
            payload, error = auth_supabase.sign_in(config, login_email, login_password)
            if error:
                if auth_supabase.auth_error_requires_email_confirmation(error):
                    auth_supabase.mark_confirmation_required(st.session_state, login_email)
                    render_confirmation_required_card(
                        config=config,
                        email=login_email,
                        key_prefix="login",
                    )
                else:
                    st.warning("Could not sign in with that email and password.")
            else:
                auth_supabase.apply_auth_payload(st.session_state, payload or {})
                auth_supabase.queue_durable_auth_save(st.session_state, payload or {})
                st.session_state.pop("account_saved_leagues_cache", None)
                startup_coordinator.reset_startup_coordinator(st.session_state)
                st.success("Logged in.")
                st.rerun()
    with tabs[1]:
        signup_email = st.text_input("Email", key="launch_account_signup_email")
        signup_password = st.text_input("Password", type="password", key="launch_account_signup_password")
        st.caption("If your email needs confirmation, check your inbox before signing in.")
        if st.button("Create account", key="launch_account_signup_button", use_container_width=True, type="primary"):
            payload, error = auth_supabase.sign_up(config, signup_email, signup_password)
            if error:
                if auth_supabase.auth_error_requires_email_confirmation(error):
                    auth_supabase.mark_confirmation_required(st.session_state, signup_email)
                    render_confirmation_required_card(
                        config=config,
                        email=signup_email,
                        key_prefix="signup",
                    )
                else:
                    st.warning("Could not create the account right now. Please check the email and password, then try again.")
            elif auth_supabase.signup_requires_email_confirmation(payload):
                auth_supabase.mark_confirmation_required(st.session_state, signup_email)
                st.session_state["account_signup_check_email"] = True
                try:
                    from modules import launch_analytics

                    launch_analytics.track_event(
                        "account_created",
                        props={"confirmation_required": True},
                        once_key="session",
                    )
                except Exception:
                    pass
                st.rerun()
            else:
                auth_supabase.apply_auth_payload(st.session_state, payload or {})
                auth_supabase.queue_durable_auth_save(st.session_state, payload or {})
                session = auth_supabase.current_auth_session(st.session_state)
                if session.get("access_token") and session.get("user_id"):
                    save_current_context(
                        config=config,
                        access_token=session.get("access_token"),
                        user_id=session.get("user_id"),
                        email=session.get("email"),
                        username=username,
                        selected_league_id=selected_league_id,
                        selected_league_name=selected_league_name,
                        my_roster_id=my_roster_id,
                    )
                st.session_state.pop("account_saved_leagues_cache", None)
                startup_coordinator.reset_startup_coordinator(st.session_state)
                try:
                    from modules import launch_analytics

                    launch_analytics.track_event(
                        "account_created",
                        props={"confirmation_required": False},
                        once_key="session",
                    )
                except Exception:
                    pass
                st.success("Account created.")
                st.rerun()
    st.caption("Accounts save your Sleeper and league context. Guest mode remains available.")
    return actions


def save_current_context(
    *,
    config: dict,
    access_token: str,
    user_id: str,
    email: str = "",
    username: str = "",
    selected_league_id: str = "",
    selected_league_name: str = "",
    my_roster_id=None,
) -> tuple[bool, str]:
    if not user_id:
        return False, "No logged-in account found."
    profile_payload = account_store.build_profile_payload(
        user_id=user_id,
        email=email,
        sleeper_username=username,
    )
    profile_saved, profile_error = account_store.upsert_profile(
        config,
        access_token,
        profile_payload,
    )
    if not profile_saved:
        return False, profile_error
    if not username or not selected_league_id:
        return True, ""
    league_payload = account_store.build_saved_league_payload(
        user_id=user_id,
        sleeper_username=username,
        league_id=selected_league_id,
        league_name=selected_league_name,
        roster_id=my_roster_id,
        team_id=my_roster_id,
        is_default=True,
    )
    return account_store.upsert_saved_league(
        config,
        access_token,
        league_payload,
    )


def saved_league_label(row: dict) -> str:
    league_name = _safe_text(row.get("league_name"), "Saved league")
    sleeper_username = _safe_text(row.get("sleeper_username"))
    league_id = _safe_text(row.get("league_id"))
    suffix = f" | {sleeper_username}" if sleeper_username else ""
    id_suffix = f" | {league_id[-6:]}" if league_id else ""
    return f"{league_name}{suffix}{id_suffix}"
