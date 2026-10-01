"""First-run web welcome modal (Fix 2 of the welcome/signup audit, 2026-09-30).

Closes the "web has no pre-use tutorial" gap mobile already has (its 5-slide
OnboardingScreen carousel). Shown once, as a dismissible dialog, immediately
after the FIRST successful league import this session — see app.py's
set_selected_league(), which arms `mark_pending` only when
`selected_league_id` transitions from unset to set (both the single-league
auto-select path and the explicit "Open League" card path go through that
one function, so this never needs a second hook).

Reuses modules.ui_modal's ModalContent/ModalSection exactly as
modules.dashboard_orientation already does for its own (separate, UNTOUCHED)
nav-tour card — this is a new, EARLIER, separate step, not a replacement:
dashboard_orientation's card only ever appears once a roster has loaded on
the Dashboard itself; this modal appears the moment a league exists at all,
before that card is even eligible to show (its own gating is unchanged).

Content:
  (a) a short value-prop beat, adapted from modules.marketing_landing's
      existing hero copy (APP_HERO_STATEMENT / APP_HERO_SUPPORT) rather than
      new copy, per the task brief.
  (b) the team-stance declaration from Fix 1 — writes through the SAME path
      modules.team_stance_ui's workspace already uses (team_stance.
      set_stance), not a parallel write path.

Guest-vs-account trigger judgment call (documented in the PR description,
Fix 2): fires for BOTH a guest's first import and a brand-new account's
first import. modules.guest_conversion treats guest browsing as a fully
legitimate, standalone experience (capture_guest_resume /
finish_auth_from_guest exist specifically to carry a guest's workspace
through signup rather than gate it behind one) — withholding this
orientation from guests would under-serve exactly the audience Fix 4 makes
more prominent, and the copy below never claims an "account" a guest
doesn't have. Dismissal is marked durable+account-wide for an authenticated
user (mirrors — does not reuse — dashboard_orientation's own separate
`dashboard_orientation_dismissed` user-settings key, which stays untouched);
for a guest, with no durable per-guest store to write to, it is session-only
(same precedent as modules.guest_conversion's own per-surface soft-prompt
dismiss flags).
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

import streamlit as st

from modules import marketing_landing
from modules import team_stance
from modules import ui_modal


PENDING_KEY = "_welcome_orientation_pending"
SHOWN_THIS_SESSION_KEY = "_welcome_orientation_shown_session"
# A distinct user_settings key from user_preferences.ONBOARDING_DISMISSED_KEY
# ("dashboard_orientation_dismissed") — a different feature, deliberately
# not sharing a flag.
ACCOUNT_SETTINGS_SEEN_KEY = "welcome_orientation_seen"
SURFACE = "welcome_orientation"


def mark_pending(session_state: MutableMapping[str, Any]) -> None:
    """Arm the one-shot "show it next render" signal.

    Call exactly where app.py's set_selected_league() detects a brand-new
    (this-session) league selection — `selected_league_id and not
    previous_league_id` — for both a guest and an authenticated user.
    """

    session_state[PENDING_KEY] = True


def _account_settings_seen(user_settings: Mapping[str, Any] | None) -> bool:
    if not isinstance(user_settings, Mapping):
        return False
    settings = user_settings.get("settings")
    if not isinstance(settings, Mapping):
        return False
    return settings.get(ACCOUNT_SETTINGS_SEEN_KEY) is True


def should_show(
    session_state: Mapping[str, Any],
    *,
    user_settings: Mapping[str, Any] | None = None,
) -> bool:
    """Pure visibility contract — pending, not already shown, not dismissed."""

    if not session_state.get(PENDING_KEY):
        return False
    if session_state.get(SHOWN_THIS_SESSION_KEY):
        return False
    if _account_settings_seen(user_settings):
        return False
    return True


def _mark_seen(
    session_state: MutableMapping[str, Any],
    *,
    config: Mapping[str, Any] | None,
) -> None:
    """Best-effort durable mark for an authenticated user; always sets the
    session-local flag regardless (covers guests, and a failed write).

    Marked at render-decision time, not on dialog close: this modal is
    inherently one-time, so "about to show" and "has been shown" are the
    same moment no matter how the user later closes it (X, outside click,
    or the in-modal stance picker below).
    """

    session_state[SHOWN_THIS_SESSION_KEY] = True
    session_state[PENDING_KEY] = False
    try:
        from modules import account_store
        from modules import auth_supabase

        user_id = auth_supabase.current_user_id(session_state)
        access_token = auth_supabase.current_access_token(session_state)
        if not user_id or not access_token:
            return
        resolved_config = dict(config) if isinstance(config, Mapping) else {}
        current = session_state.get("account_user_settings")
        if current is None:
            # Not yet loaded this session — this can fire before
            # modules.user_preferences.refresh_authenticated_preferences has
            # run (e.g. a returning user's league auto-resumes on a brand
            # new session before the Dashboard's own preferences load).
            # account_store.upsert_user_settings replaces the WHOLE settings
            # JSON column, so fetching first is required — without it, this
            # write would silently wipe every other durable preference
            # (League Orientation's dismissal, FAAB budgets, theme/density).
            current, fetch_error = account_store.fetch_user_settings(
                resolved_config, access_token, user_id=user_id
            )
            if fetch_error:
                return
        existing_settings = (
            current.get("settings") if isinstance(current, Mapping) else None
        )
        values = dict(existing_settings) if isinstance(existing_settings, Mapping) else {}
        values[ACCOUNT_SETTINGS_SEEN_KEY] = True
        payload = account_store.build_user_settings_payload(user_id=user_id, settings=values)
        saved, _error = account_store.upsert_user_settings(resolved_config, access_token, payload)
        if saved:
            session_state["account_user_settings"] = payload
    except Exception:
        pass


def _render_stance_picker(*, session_state: MutableMapping[str, Any], league_id: str) -> None:
    """Fix 1 (web): the "declare your team situation" step onboarding
    content promises. Writes through team_stance.set_stance — the exact
    function modules.team_stance_ui's standalone workspace already calls —
    never a parallel write path. Silently absent for a guest (the stance
    feature itself requires authentication; see team_stance.can_access_stance)
    rather than showing a control that cannot save.
    """

    if not team_stance.can_access_stance(session_state):
        return
    st.divider()
    st.markdown("**Tell us your team's situation**")
    st.caption(team_stance.SUPPORTING_COPY)
    current = team_stance.fetch_stance_for_league(session_state, league_id=league_id)
    options = list(team_stance.STANCE_OPTIONS)
    labels = [team_stance.STANCE_LABELS[key] for key in options]
    default_index = options.index(current) if current in options else 0
    chosen_label = st.radio(
        "Team Situation",
        labels,
        index=default_index,
        horizontal=True,
        key=f"welcome_orientation_stance_{league_id}",
        label_visibility="collapsed",
    )
    chosen = options[labels.index(chosen_label)]
    if chosen != current:
        team_stance.set_stance(session_state, league_id=league_id, stance=chosen)


def welcome_modal_content() -> ui_modal.ModalContent:
    return ui_modal.ModalContent(
        title=marketing_landing.APP_HERO_STATEMENT,
        eyebrow="Welcome",
        summary=marketing_landing.APP_HERO_SUPPORT,
        sections=(
            ui_modal.ModalSection(
                "What to expect",
                "Today's Game Plan leads with your single best next move — trades, "
                "waivers, and roster priorities for this league, not a raw stat dump.",
            ),
        ),
        footer="You can revisit how it works anytime from the Dashboard.",
    )


def render_welcome_orientation_if_applicable(
    *,
    session_state: MutableMapping[str, Any],
    config: Mapping[str, Any] | None,
    league_id: object,
    user_settings: Mapping[str, Any] | None = None,
) -> bool:
    """Render the modal when applicable; return whether it was shown."""

    league_key = str(league_id or "").strip()
    if not league_key:
        return False
    if not should_show(session_state, user_settings=user_settings):
        return False

    _mark_seen(session_state, config=config)

    def _extra_body() -> None:
        _render_stance_picker(session_state=session_state, league_id=league_key)

    ui_modal.render_modal(welcome_modal_content(), surface=SURFACE, extra_body=_extra_body)
    return True
