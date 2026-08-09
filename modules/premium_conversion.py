"""Premium conversion: intent capture, CTA language, and checkout resume.

Sells launch-ready Premium depth only. Experimental features stay flagged and
are not promised as included-by-default Premium. Stripe sessions are created
only after an explicit checkout click.
"""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

import streamlit as st

from modules import auth_restore_lifecycle
from modules import auth_supabase


CHECKOUT_INTENT_KEY = "_premium_checkout_intent"
RESUME_CHECKOUT_FLAG = "_premium_resume_checkout"

# Canonical product CTA (locks / contextual upgrade).
PRIMARY_CTA = "Upgrade to Premium"
SECONDARY_CTA = "See what Premium includes"
CHECKOUT_CTA = "Start Founder Premium checkout"

VALUE_PROP_HEADLINE = "Go deeper on the decisions that matter"
VALUE_PROP_BODY = (
    "Premium expands the same Game Plan, Trade Hub, Waivers, and My Team workflows "
    "you already use — more moves, fuller boards, and deeper roster analysis."
)

# Stable attribution tokens for analytics (no PII).
FEATURE_ATTRIBUTION: Mapping[str, str] = {
    "premium dashboard": "more_next_moves",
    "more next moves": "more_next_moves",
    "premium league pulse": "league_pulse",
    "full league pulse": "league_pulse",
    "premium trade hub": "trade_depth",
    "full trade idea board": "trade_depth",
    "player-focused trade search": "trade_depth",
    "premium waivers": "waiver_depth",
    "full waiver board and faab shortlist": "waiver_depth",
    "faab helper": "waiver_depth",
    "premium my team": "deep_analysis",
    "deep analysis": "deep_analysis",
    "bench insulation detail": "deep_analysis",
    "advanced roster decisions": "deep_analysis",
    "decision memory": "decision_memory",
    "gm targets": "gm_targets",
    "general": "general_premium_page",
    "premium": "general_premium_page",
}


def attribution_feature(feature: object = "", title: object = "") -> str:
    blob = f"{feature or ''} {title or ''}".strip().casefold()
    for needle, token in FEATURE_ATTRIBUTION.items():
        if needle in blob:
            return token
    cleaned = "".join(ch if ch.isalnum() or ch in {"_", "-"} else "_" for ch in blob)
    cleaned = cleaned.strip("_")[:40]
    return cleaned or "general_premium_page"


def clear_entitlement_presentation_memo(
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """Drop cached Free/Premium presentation so profile refresh can take effect."""

    state = session_state if session_state is not None else st.session_state
    state.pop(auth_restore_lifecycle.ENTITLEMENT_MEMO_KEY, None)
    state.pop(auth_restore_lifecycle.ENTITLEMENT_MEMO_USER_KEY, None)
    state.pop("_effective_entitlement", None)


def capture_checkout_intent(
    session_state: MutableMapping[str, Any] | None = None,
    *,
    interval: str = "",
    feature: str = "",
    surface: str = "",
    route: str = "",
    return_route: str = "premium",
) -> dict[str, Any]:
    state = session_state if session_state is not None else st.session_state
    payload = {
        "interval": str(interval or "").strip(),
        "feature": attribution_feature(feature),
        "surface": str(surface or "").strip()[:80],
        "route": str(route or state.get("platform_nav_page") or "").strip()[:80],
        "return_route": str(return_route or "premium").strip() or "premium",
        "league_id": str(state.get("selected_league_id") or "").strip(),
    }
    state[CHECKOUT_INTENT_KEY] = payload
    return payload


def peek_checkout_intent(
    session_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    state = session_state if session_state is not None else st.session_state
    payload = state.get(CHECKOUT_INTENT_KEY)
    return dict(payload) if isinstance(payload, dict) else {}


def clear_checkout_intent(
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    state = session_state if session_state is not None else st.session_state
    state.pop(CHECKOUT_INTENT_KEY, None)
    state.pop(RESUME_CHECKOUT_FLAG, None)


def mark_resume_checkout_after_auth(
    session_state: MutableMapping[str, Any] | None = None,
) -> None:
    """After guest→auth, return to Premium so the user can complete checkout."""

    state = session_state if session_state is not None else st.session_state
    intent = peek_checkout_intent(state)
    if not intent:
        return
    state[RESUME_CHECKOUT_FLAG] = True
    state["_pending_platform_route"] = str(intent.get("return_route") or "premium")


def track_premium_event(
    event: str,
    *,
    surface: str = "",
    feature: str = "",
    route: str = "",
    extra: Mapping[str, Any] | None = None,
    once_key: str | None = None,
) -> None:
    try:
        from modules import launch_analytics

        props_extra: dict[str, Any] = {
            "prompt_surface": surface or "premium",
            "item_kind": attribution_feature(feature)[:80],
        }
        if extra:
            props_extra.update(dict(extra))
        launch_analytics.track_event(
            event,
            props=launch_analytics.build_context_props(
                st.session_state,
                route=route or str(st.session_state.get("platform_nav_page") or "premium"),
                source_surface=surface or "premium",
                extra=props_extra,
            ),
            once_key=once_key,
            state=st.session_state,
        )
    except Exception:
        pass


def note_gate_seen(*, feature: str, title: str = "", surface: str = "premium_lock") -> None:
    token = attribution_feature(feature, title)
    once = f"premium_gate:{token}"
    track_premium_event(
        "premium_gate_seen",
        surface=surface,
        feature=token,
        once_key=once,
    )


def begin_upgrade_flow(
    *,
    feature: str = "",
    title: str = "",
    surface: str = "premium_lock",
    interval: str = "",
) -> None:
    """Capture intent and route toward Premium (auth first when guest)."""

    from modules import guest_conversion

    token = attribution_feature(feature, title)
    capture_checkout_intent(
        feature=token,
        surface=surface,
        interval=interval,
        route=str(st.session_state.get("platform_nav_page") or ""),
        return_route="premium",
    )
    track_premium_event(
        "premium_cta_clicked",
        surface=surface,
        feature=token,
    )
    if guest_conversion.is_guest():
        guest_conversion.open_auth_dialog(mode="signup", surface="premium_checkout")
        return
    st.session_state["_pending_platform_route"] = "premium"


def handle_billing_return_success(session_state: MutableMapping[str, Any] | None = None) -> None:
    state = session_state if session_state is not None else st.session_state
    clear_entitlement_presentation_memo(state)
    clear_checkout_intent(state)
    track_premium_event(
        "premium_checkout_completed",
        surface="stripe_return",
        feature="general_premium_page",
        route="premium",
        extra={"billing_flag": "success"},
        once_key="session",
    )


def handle_billing_return_cancel(session_state: MutableMapping[str, Any] | None = None) -> None:
    state = session_state if session_state is not None else st.session_state
    track_premium_event(
        "premium_checkout_cancelled",
        surface="stripe_return",
        feature=peek_checkout_intent(state).get("feature", "general_premium_page"),
        route="premium",
        extra={"billing_flag": "cancel"},
        once_key="session",
    )


def maybe_emit_entitlement_activated(
    *,
    before: str,
    after: str,
) -> None:
    if str(after).casefold() != "premium":
        return
    if str(before).casefold() == "premium":
        return
    if not auth_supabase.current_user_id(st.session_state):
        return
    track_premium_event(
        "premium_entitlement_activated",
        surface="entitlement_refresh",
        feature="general_premium_page",
        route="premium",
        once_key="session",
    )
