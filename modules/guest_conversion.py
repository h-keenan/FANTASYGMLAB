"""Guest → free-account conversion: soft prompts, handoff, and copy.

Guests keep full first-value browsing. Soft prompts sell FREE continuity
(saved leagues / resume), never Premium. Auth handoff preserves guest league
context when safe; existing account defaults win on sign-in conflicts.
"""

from __future__ import annotations

from html import escape
from typing import Any, Mapping, MutableMapping

import streamlit as st

from modules import auth_supabase
from modules.html_rendering import render_html_fragment


GUEST_AUTH_RESUME_KEY = "_guest_auth_resume"
GUEST_AUTH_DIALOG_KEY = "_guest_auth_dialog_open"
GUEST_AUTH_DIALOG_MODE_KEY = "_guest_auth_dialog_mode"
GUEST_AUTH_DIALOG_SURFACE_KEY = "_guest_auth_dialog_surface"
DISMISS_PREFIX = "_guest_signup_dismissed_"
PROMPT_SEEN_PREFIX = "_guest_signup_prompt_seen_"

# Canonical free-account benefits that actually work today (auth cloud).
FREE_ACCOUNT_BENEFITS: tuple[str, ...] = (
    "Remember your Sleeper username and saved leagues",
    "Resume your default league on the next visit",
    "Keep league selection ready without re-importing",
    "Carry account preferences across sessions once signed in",
)

SIGNUP_TITLE = "Save your front office"
SIGNUP_BODY = (
    "Create a free account to keep this league and your personalized setup "
    "ready next time. No payment required."
)
GUEST_STATE_LABEL = "Browsing as guest"

GUEST_CONTINUITY_CSS = """
.dg-guest-continuity{align-items:flex-start;background:var(--color-surface-primary);border:var(--border-width-default) solid var(--color-border);display:flex;flex-direction:column;gap:var(--space-2xs);margin:var(--space-md) 0;max-width:40rem;padding:var(--space-sm) var(--space-md)}
.dg-guest-continuity strong{color:var(--color-text-primary);font:var(--font-card-title)}
.dg-guest-continuity span{color:var(--color-text-secondary);font:var(--font-body)}
.dg-guest-continuity-trust{color:var(--color-text-muted);font:var(--font-meta);margin-top:var(--space-3xs)}
"""

SURFACE_REASONS: Mapping[str, str] = {
    "dashboard": "Keep this Game Plan and league ready for next time.",
    "my_team": "Save this league so your roster workspace opens ready next visit.",
    "trade_hub": "Come back to the same league and trade workspace without re-importing.",
    "waivers": "Keep this league ready for the next waiver check.",
    "pqv": "Save this league so player context is waiting when you return.",
    "header": "Save your league and pick up where you left off.",
    "gm_menu": "Save this setup to your free account.",
    "launch": "Create a free account to restore your default league automatically.",
}


def is_guest(session_state: Mapping[str, Any] | None = None) -> bool:
    state = session_state if session_state is not None else st.session_state
    return not bool(auth_supabase.current_user_id(state))


def guest_account_label(session_state: Mapping[str, Any] | None = None) -> str:
    state = session_state if session_state is not None else st.session_state
    if auth_supabase.current_user_id(state):
        return "Signed in"
    return GUEST_STATE_LABEL


def soft_prompt_dismiss_key(surface: str) -> str:
    return f"{DISMISS_PREFIX}{str(surface or 'unknown').strip().lower()}"


def dismiss_soft_prompt(surface: str, session_state: MutableMapping[str, Any] | None = None) -> None:
    state = session_state if session_state is not None else st.session_state
    state[soft_prompt_dismiss_key(surface)] = True


def is_soft_prompt_dismissed(
    surface: str, session_state: Mapping[str, Any] | None = None
) -> bool:
    state = session_state if session_state is not None else st.session_state
    return bool(state.get(soft_prompt_dismiss_key(surface)))


def should_show_soft_prompt(
    surface: str,
    *,
    session_state: Mapping[str, Any] | None = None,
    require_league: bool = True,
) -> bool:
    state = session_state if session_state is not None else st.session_state
    if not is_guest(state):
        return False
    if require_league and not str(state.get("selected_league_id") or "").strip():
        return False
    if is_soft_prompt_dismissed(surface, state):
        return False
    return True


def capture_guest_resume(
    session_state: MutableMapping[str, Any] | None = None,
    *,
    prompt_surface: str = "",
    intended_action: str = "",
) -> dict[str, Any]:
    """Snapshot guest workspace before auth apply wipes account-bound keys."""

    state = session_state if session_state is not None else st.session_state
    if not is_guest(state):
        return {}
    payload = {
        "platform": str(
            state.get("active_platform") or state.get("selected_platform") or "sleeper"
        ).strip(),
        "username": str(state.get("username") or "").strip(),
        "selected_league_id": str(state.get("selected_league_id") or "").strip(),
        "selected_league_name": str(state.get("selected_league_name") or "").strip(),
        "my_roster_id": state.get("my_roster_id"),
        "route": str(state.get("platform_nav_page") or "dashboard").strip() or "dashboard",
        "player_id": str(state.get("player_quick_view_player_id") or "").strip(),
        "prompt_surface": str(prompt_surface or "").strip(),
        "intended_action": str(intended_action or "").strip(),
    }
    state[GUEST_AUTH_RESUME_KEY] = payload
    return payload


def peek_guest_resume(session_state: Mapping[str, Any] | None = None) -> dict[str, Any]:
    state = session_state if session_state is not None else st.session_state
    payload = state.get(GUEST_AUTH_RESUME_KEY)
    return dict(payload) if isinstance(payload, dict) else {}


def clear_guest_resume(session_state: MutableMapping[str, Any] | None = None) -> None:
    state = session_state if session_state is not None else st.session_state
    state.pop(GUEST_AUTH_RESUME_KEY, None)


def _track(event: str, *, surface: str = "", route: str = "", extra: dict | None = None) -> None:
    try:
        from modules import launch_analytics

        props_extra = {"prompt_surface": surface} if surface else {}
        if extra:
            props_extra.update(extra)
        once = None
        if event.endswith("_completed") or event in {
            "guest_first_useful",
            "guest_signup_prompt_seen",
        }:
            once = "session"
        launch_analytics.track_event(
            event,
            props=launch_analytics.build_context_props(
                st.session_state,
                route=route or str(st.session_state.get("platform_nav_page") or ""),
                source_surface=surface or "guest_conversion",
                extra=props_extra or None,
            ),
            once_key=once,
            state=st.session_state,
        )
    except Exception:
        pass


def mark_guest_first_useful(*, route: str = "dashboard") -> None:
    if not is_guest():
        return
    _track("guest_first_useful", surface="dashboard", route=route)


def open_auth_dialog(*, mode: str = "signup", surface: str = "header") -> None:
    normalized = "signin" if str(mode).strip().lower() in {"signin", "login", "sign_in"} else "signup"
    capture_guest_resume(prompt_surface=surface, intended_action=normalized)
    st.session_state[GUEST_AUTH_DIALOG_KEY] = True
    st.session_state[GUEST_AUTH_DIALOG_MODE_KEY] = normalized
    st.session_state[GUEST_AUTH_DIALOG_SURFACE_KEY] = str(surface or "header")
    event = "guest_signin_started" if normalized == "signin" else "guest_signup_started"
    _track(event, surface=surface)


def close_auth_dialog(session_state: MutableMapping[str, Any] | None = None) -> None:
    state = session_state if session_state is not None else st.session_state
    state.pop(GUEST_AUTH_DIALOG_KEY, None)
    state.pop(GUEST_AUTH_DIALOG_MODE_KEY, None)
    state.pop(GUEST_AUTH_DIALOG_SURFACE_KEY, None)


def soft_prompt_html(*, surface: str, body: str = "") -> str:
    reason = body or SURFACE_REASONS.get(surface, SIGNUP_BODY)
    return (
        "<div class='dg-guest-continuity' role='region' "
        f"data-guest-continuity='{escape(surface, quote=True)}'>"
        f"<strong>{escape(SIGNUP_TITLE)}</strong>"
        f"<span>{escape(reason)}</span>"
        "<div class='dg-guest-continuity-trust'>Free account · no payment required</div>"
        "</div>"
    )


def render_soft_signup_prompt(
    *,
    surface: str,
    config: dict | None = None,
    body: str = "",
    require_league: bool = True,
) -> bool:
    """One restrained continuity module. Returns True when rendered."""

    if not should_show_soft_prompt(surface, require_league=require_league):
        return False

    from modules.html_rendering import inject_global_styles

    inject_global_styles(GUEST_CONTINUITY_CSS)
    render_html_fragment(soft_prompt_html(surface=surface, body=body))

    seen_key = f"{PROMPT_SEEN_PREFIX}{surface}"
    if not st.session_state.get(seen_key):
        st.session_state[seen_key] = True
        _track("guest_signup_prompt_seen", surface=surface)

    cols = st.columns([1, 1, 1])
    with cols[0]:
        if st.button(
            "Create account",
            key=f"guest_signup_{surface}",
            use_container_width=True,
            type="primary",
        ):
            open_auth_dialog(mode="signup", surface=surface)
            st.rerun()
    with cols[1]:
        if st.button(
            "Sign in",
            key=f"guest_signin_{surface}",
            use_container_width=True,
        ):
            open_auth_dialog(mode="signin", surface=surface)
            st.rerun()
    with cols[2]:
        if st.button(
            "Not now",
            key=f"guest_dismiss_{surface}",
            use_container_width=True,
        ):
            dismiss_soft_prompt(surface)
            st.rerun()
    return True


def _apply_resume_workspace(state: MutableMapping[str, Any], resume: Mapping[str, Any]) -> None:
    username = str(resume.get("username") or "").strip()
    league_id = str(resume.get("selected_league_id") or "").strip()
    league_name = str(resume.get("selected_league_name") or "").strip()
    platform = str(resume.get("platform") or "sleeper").strip() or "sleeper"
    route = str(resume.get("route") or "dashboard").strip() or "dashboard"
    if username:
        state["username"] = username
    if platform:
        state["selected_platform"] = platform
        state["active_platform"] = platform
    if league_id:
        state["selected_league_id"] = league_id
        state["selected_league_name"] = league_name
        if resume.get("my_roster_id") is not None:
            state["my_roster_id"] = resume.get("my_roster_id")
        state["_identity_established"] = True
        state["_league_selection_established"] = True
        # Guest→auth resume restores workspace that originated in THIS session.
        from modules import session_isolation

        session_isolation.mark_explicit_guest_league_import(state)
    if route:
        state["_pending_platform_route"] = route
    player_id = str(resume.get("player_id") or "").strip()
    if player_id and route in {"players", "player_quick_view", "dashboard"}:
        state["player_quick_view_player_id"] = player_id


def finish_auth_from_guest(
    *,
    config: dict,
    mode: str,
    surface: str = "",
) -> None:
    """Restore guest context after apply_auth_payload and optionally save league.

    Sign-in conflict rule: if the account already has a default saved league,
    account truth wins (do not overwrite with guest league). Otherwise restore
    the guest league and save it.
    """

    from modules import account_ui
    from modules import account_store
    from modules import startup_coordinator

    resume = peek_guest_resume()
    clear_guest_resume()
    session = auth_supabase.current_auth_session(st.session_state) or {}
    access_token = str(session.get("access_token") or "")
    user_id = str(session.get("user_id") or "")
    email = str(session.get("email") or "")

    prefer_account_default = str(mode).strip().lower() in {"signin", "login"}
    account_has_default = False
    if prefer_account_default and access_token and user_id:
        saved_rows, _error = account_store.fetch_saved_leagues(
            config, access_token, user_id=user_id
        )
        default_league = account_store.default_saved_league(
            saved_rows or [], require_default=True
        )
        account_has_default = bool(default_league)

    if resume and not account_has_default:
        _apply_resume_workspace(st.session_state, resume)
        if access_token and user_id and resume.get("username") and resume.get("selected_league_id"):
            account_ui.save_current_context(
                config=config,
                access_token=access_token,
                user_id=user_id,
                email=email,
                username=str(resume.get("username") or ""),
                selected_league_id=str(resume.get("selected_league_id") or ""),
                selected_league_name=str(resume.get("selected_league_name") or ""),
                my_roster_id=resume.get("my_roster_id"),
            )
            st.session_state["account_resume_notice"] = (
                "Account ready. Your league is saved for next time."
            )
        elif resume.get("selected_league_id"):
            st.session_state["account_resume_notice"] = (
                "Signed in. Returning you to the league you were browsing."
            )
    elif account_has_default:
        st.session_state["account_resume_notice"] = (
            "Signed in. Resuming your saved league."
        )
        # Leave league empty so auto-resume picks the account default.

    st.session_state.pop("account_saved_leagues_cache", None)
    startup_coordinator.reset_startup_coordinator(st.session_state)
    close_auth_dialog()
    try:
        from modules import premium_conversion

        if surface == "premium_checkout" or premium_conversion.peek_checkout_intent(
            st.session_state
        ):
            premium_conversion.mark_resume_checkout_after_auth(st.session_state)
    except Exception:
        pass
    event = (
        "guest_signin_completed"
        if prefer_account_default
        else "guest_signup_completed"
    )
    _track(event, surface=surface or str(resume.get("prompt_surface") or ""))


def render_guest_auth_dialog(*, config: dict) -> None:
    """Modal signup/signin from an in-app continuity prompt. Mount only when open."""

    if not st.session_state.get(GUEST_AUTH_DIALOG_KEY):
        return
    if auth_supabase.current_user_id(st.session_state):
        close_auth_dialog()
        return

    mode = str(st.session_state.get(GUEST_AUTH_DIALOG_MODE_KEY) or "signup")
    surface = str(st.session_state.get(GUEST_AUTH_DIALOG_SURFACE_KEY) or "header")
    title = "Sign in" if mode == "signin" else "Create account"

    def _on_dismiss() -> None:
        close_auth_dialog()

    @st.dialog(title, on_dismiss=_on_dismiss)
    def _dialog() -> None:
        if not auth_supabase.is_configured(config):
            st.info("Accounts are not configured yet. You can keep browsing as a guest.")
            if st.button("Close", key="guest_auth_close_unconfigured"):
                close_auth_dialog()
                st.rerun()
            return

        if auth_supabase.is_pending_email_confirmation(st.session_state):
            from modules import account_ui

            account_ui.render_confirmation_required_card(
                config=config,
                email=auth_supabase.pending_confirmation_email(st.session_state),
                key_prefix="guest_dialog",
            )
            if st.button("Use a different email", key="guest_dialog_different_email"):
                auth_supabase.clear_pending_email_confirmation(st.session_state)
                st.session_state[GUEST_AUTH_DIALOG_MODE_KEY] = "signup"
                st.rerun()
            if st.button("Continue as guest", key="guest_dialog_continue_guest_pending"):
                auth_supabase.clear_pending_email_confirmation(st.session_state)
                close_auth_dialog()
                st.rerun()
            return

        st.caption(SIGNUP_BODY)
        resume = peek_guest_resume()
        if resume.get("selected_league_name") or resume.get("username"):
            bits = []
            if resume.get("selected_league_name"):
                bits.append(str(resume["selected_league_name"]))
            if resume.get("username"):
                bits.append(f"@{resume['username']}")
            st.caption("Keeping · " + " · ".join(bits))

        if mode == "signin":
            email = st.text_input("Email", key="guest_dialog_login_email")
            password = st.text_input(
                "Password", type="password", key="guest_dialog_login_password"
            )
            if st.button("Sign in", key="guest_dialog_login_button", type="primary", use_container_width=True):
                capture_guest_resume(prompt_surface=surface, intended_action="signin")
                payload, error = auth_supabase.sign_in(config, email, password)
                if error:
                    if auth_supabase.auth_error_requires_email_confirmation(error):
                        auth_supabase.mark_confirmation_required(st.session_state, email)
                        st.warning("Confirm your email, then sign in.")
                    else:
                        st.warning(auth_supabase.signin_user_message(error))
                else:
                    auth_supabase.apply_auth_payload(st.session_state, payload or {})
                    auth_supabase.queue_durable_auth_save(st.session_state, payload or {})
                    finish_auth_from_guest(config=config, mode="signin", surface=surface)
                    st.rerun()
            if st.button("Need an account? Create account", key="guest_dialog_switch_signup"):
                st.session_state[GUEST_AUTH_DIALOG_MODE_KEY] = "signup"
                st.rerun()
        else:
            email = st.text_input("Email", key="guest_dialog_signup_email")
            password = st.text_input(
                "Password", type="password", key="guest_dialog_signup_password"
            )
            st.caption("We'll email you a confirmation link.")
            if st.button(
                "Create account",
                key="guest_dialog_signup_button",
                type="primary",
                use_container_width=True,
                disabled=bool(st.session_state.get("_auth_signup_in_flight")),
            ):
                if st.session_state.get("_auth_signup_in_flight"):
                    st.info("Creating your account…")
                else:
                    st.session_state["_auth_signup_in_flight"] = True
                    capture_guest_resume(prompt_surface=surface, intended_action="signup")
                    _track("guest_signup_started", surface=surface)
                    with st.spinner("Creating your account…"):
                        payload, error = auth_supabase.sign_up(config, email, password)
                    st.session_state.pop("_auth_signup_in_flight", None)
                    if error:
                        if auth_supabase.auth_error_requires_email_confirmation(error):
                            auth_supabase.enter_pending_email_confirmation(
                                st.session_state, email
                            )
                            close_auth_dialog()
                            st.rerun()
                        else:
                            st.warning(auth_supabase.signup_user_message(error))
                    elif (
                        auth_supabase.signup_requires_email_confirmation(payload)
                        or not auth_supabase.session_is_authenticated_for_app(payload)
                    ):
                        auth_supabase.enter_pending_email_confirmation(
                            st.session_state,
                            email,
                            payload=payload if isinstance(payload, dict) else None,
                        )
                        _track(
                            "guest_signup_completed",
                            surface=surface,
                            extra={"confirmation_required": True},
                        )
                        close_auth_dialog()
                        st.rerun()
                    else:
                        auth_supabase.apply_auth_payload(st.session_state, payload or {})
                        if not auth_supabase.current_user_id(st.session_state):
                            auth_supabase.enter_pending_email_confirmation(
                                st.session_state, email, payload=payload
                            )
                            close_auth_dialog()
                            st.rerun()
                        auth_supabase.queue_durable_auth_save(st.session_state, payload or {})
                        auth_supabase.log_auth_operation_diagnostic(
                            operation="signup",
                            category="success_bootstrap",
                            auth_user_created=True,
                            profile_bootstrap_ran=True,
                            durable_session_write=True,
                        )
                        finish_auth_from_guest(config=config, mode="signup", surface=surface)
                        st.rerun()
            if st.button("Already have an account? Sign in", key="guest_dialog_switch_signin"):
                st.session_state[GUEST_AUTH_DIALOG_MODE_KEY] = "signin"
                st.rerun()

        if st.button("Keep browsing as guest", key="guest_dialog_keep_guest"):
            close_auth_dialog()
            st.rerun()

    _dialog()


def render_profile_guest_actions(*, key_prefix: str = "executive_profile") -> None:
    """Quiet Create / Sign in affordances inside the You popover."""

    if not is_guest():
        return
    st.caption(GUEST_STATE_LABEL)
    if st.button(
        "Create account",
        key=f"{key_prefix}_guest_signup",
        use_container_width=True,
        type="primary",
    ):
        open_auth_dialog(mode="signup", surface="header")
        st.rerun()
    if st.button(
        "Sign in",
        key=f"{key_prefix}_guest_signin",
        use_container_width=True,
    ):
        open_auth_dialog(mode="signin", surface="header")
        st.rerun()


def render_gm_menu_save_entry() -> None:
    if not should_show_soft_prompt("gm_menu", require_league=True):
        return
    if st.button(
        "Save this setup",
        key="gm_menu_guest_save_setup",
        use_container_width=True,
    ):
        open_auth_dialog(mode="signup", surface="gm_menu")
        st.rerun()
