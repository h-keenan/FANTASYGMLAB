from __future__ import annotations

from collections.abc import Mapping
from html import escape
from typing import Any

import streamlit as st

from modules import app_config


# --------------------------------------------------------------------------
# Tier model
#
# Three tiers, ordered FREE < PRO < FRONT_OFFICE. Any caller that used to do
# `entitlement == PREMIUM` for "has paid access" should now do
# `is_at_least(entitlement, PRO)` — Front Office includes everything Pro
# has, so a bare equality check against one tier silently excludes the tier
# above it.
#
# Storage note (read this before changing raw-value handling below): the
# Supabase `profiles.entitlement` column keeps writing the *legacy* literal
# "premium" for the Pro tier — not "pro" — on purpose. `services/mobile_api_service.py`
# reads that same raw column directly (it does not import this module) and
# does `profile.get("entitlement") == "premium"` in a dozen places; renaming
# the stored value out from under it would silently downgrade every mobile
# Pro subscriber to Free the next time this webhook fires. Only the brand
# new Front Office tier gets a brand-new raw value ("front_office") — mobile
# has no Front Office support yet anyway, so there is nothing to break.
# `_normalize_tier` below is what turns that raw "premium" into the
# canonical PRO value for every *web* caller; new code should store/compare
# against PRO/FRONT_OFFICE and never hardcode "premium" again.
FREE = "free"
PRO = "pro"
FRONT_OFFICE = "front_office"

# Back-compat alias: the previous binary model's one paid tier was named
# PREMIUM. Every existing `premium.PREMIUM` call site keeps working and now
# means "Pro" (the direct successor of the old single paid tier) rather than
# a second, independent concept. New code should prefer PRO.
PREMIUM = PRO

# Raw legacy value still written to Supabase `profiles.entitlement` for the
# Pro tier. See the module docstring above for why this does not say "pro".
_LEGACY_PRO_RAW_VALUE = "premium"

_TIER_RANK: dict[str, int] = {FREE: 0, PRO: 1, FRONT_OFFICE: 2}
_KNOWN_TIERS = frozenset(_TIER_RANK)

# Public: every valid canonical/resolved entitlement value. Callers that
# memoize an already-resolved entitlement (e.g. app.py's session-state
# memo) should validate against this rather than hand-rolling
# `{FREE, PRO}` and silently treating FRONT_OFFICE as "needs refresh".
ALL_TIERS = (FREE, PRO, FRONT_OFFICE)

PREMIUM_OVERRIDE_ENV = "DYNASTYGM_PREMIUM_OVERRIDE"
PREMIUM_OVERRIDE_SECRET = "DYNASTYGM_PREMIUM_OVERRIDE"
DEBUG_AUTH_ENV = "DYNASTYGM_DEBUG_AUTH"
DEBUG_AUTH_SECRET = "DYNASTYGM_DEBUG_AUTH"
ENTITLEMENT_FIELD = "entitlement"


def _safe_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text if text else default


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return _safe_text(value).casefold() in {"1", "true", "yes", "on", "premium", "pro", "paid"}


def _is_mapping(value: Any) -> bool:
    return isinstance(value, Mapping)


def _normalize_tier(raw: Any) -> str:
    """Map any raw stored/legacy value to one of FREE/PRO/FRONT_OFFICE.

    Unknown or empty values degrade to FREE — an entitlement resolver must
    never fail open. "premium" (the legacy single-paid-tier value still
    written to Supabase) and "pro"/"paid" all resolve to PRO.
    """

    value = _safe_text(raw).casefold().replace("-", "_").replace(" ", "_")
    if value in {"front_office", "frontoffice", "front_office_tier"}:
        return FRONT_OFFICE
    if value in {_LEGACY_PRO_RAW_VALUE, "pro", "paid"}:
        return PRO
    return FREE


def is_at_least(entitlement: Any, minimum_tier: Any) -> bool:
    """True when `entitlement` is at `minimum_tier` or a tier above it.

    Normalizes both sides first, so callers may pass either a raw stored
    value or an already-canonical tier constant. The one place tier
    ordering is defined — callers should never hand-roll
    `entitlement in (PRO, FRONT_OFFICE)` checks.
    """

    return _TIER_RANK.get(_normalize_tier(entitlement), 0) >= _TIER_RANK.get(
        _normalize_tier(minimum_tier), 0
    )


def canonical_tier(raw: Any) -> str:
    """Public wrapper around the raw-value normalizer, for other modules
    that need to interpret a stored entitlement string (e.g. a webhook
    payload) without duplicating the tier-name mapping."""

    return _normalize_tier(raw)


# --------------------------------------------------------------------------
# Tier capability flags
#
# These are deliberately dumb boolean/str lookups with no UI or gating logic
# attached — the paywall-trigger surfaces that call them own when/how to
# show an upsell. Keeping them here means tier ordering and feature
# membership have exactly one source of truth.

def can_export_share_card(entitlement: Any = None) -> bool:
    """Shareable trade-grade / power-ranking PNG export — a growth feature,
    unlimited on every tier including Free. The actual PNG generation is a
    separate workstream; this only states that it is never gated."""

    return True


def has_cross_league_exposure(entitlement: Any) -> bool:
    """Cross-league player-ownership view (Portfolio Exposure). Pro and up: the
    owner moved this from Front Office (no longer sold) to Pro."""

    return is_at_least(entitlement, PRO)


def has_early_access_flag(entitlement: Any) -> bool:
    """Front Office's "early access to new models/features" flag."""

    return _normalize_tier(entitlement) == FRONT_OFFICE


def has_priority_support_badge(entitlement: Any) -> bool:
    """Front Office's priority-support badge."""

    return _normalize_tier(entitlement) == FRONT_OFFICE


def premium_override_enabled(*, environ: dict | None = None, secrets: Any = None) -> bool:
    """Local/dev-only premium override. Never store payment data here."""
    if not app_config.customer_unsafe_debug_allowed(environ=environ, secrets=secrets):
        return False
    return _truthy(app_config.config_value(PREMIUM_OVERRIDE_ENV, environ=environ, secrets=secrets))


def debug_auth_enabled(*, environ: dict | None = None, secrets: Any = None) -> bool:
    """Developer-only auth/entitlement diagnostics gate."""
    if not app_config.customer_unsafe_debug_allowed(environ=environ, secrets=secrets):
        return False
    return _truthy(app_config.config_value(DEBUG_AUTH_ENV, environ=environ, secrets=secrets))


def _extract_settings(account: dict | None = None, user_settings: dict | None = None) -> dict:
    merged: dict[str, Any] = {}
    for source in (account, user_settings):
        if not _is_mapping(source):
            continue
        nested = source.get("settings")
        if _is_mapping(nested):
            merged.update(nested)
        merged.update(source)
    return merged


def _session_sources(session_state: Any) -> dict[str, dict]:
    state = session_state if _is_mapping(session_state) else {}
    auth_session = state.get("auth_session") if _is_mapping(state.get("auth_session")) else {}
    auth_user = state.get("auth_user") if _is_mapping(state.get("auth_user")) else {}
    has_authenticated_user = bool(_safe_text(auth_session.get("user_id") or auth_user.get("id")))
    account_profile = (
        state.get("account_profile")
        if has_authenticated_user and _is_mapping(state.get("account_profile"))
        else {}
    )
    account_user_settings = (
        state.get("account_user_settings")
        if has_authenticated_user and _is_mapping(state.get("account_user_settings"))
        else {}
    )
    return {
        "auth_session": auth_session,
        "auth_user": auth_user,
        "account_profile": account_profile,
        "account_user_settings": account_user_settings,
    }


def get_entitlement_debug(
    account: dict | None = None,
    user_settings: dict | None = None,
    *,
    account_profile: dict | None = None,
    session_state: dict | None = None,
    environ: dict | None = None,
    secrets: Any = None,
) -> dict[str, Any]:
    if premium_override_enabled(environ=environ, secrets=secrets):
        return {
            "entitlement": PRO,
            "is_premium": True,
            "is_front_office": False,
            "source": "dev_override",
            "source_field": PREMIUM_OVERRIDE_ENV,
            "raw_value": "enabled",
            "reason": "dev_override",
        }

    source_name = ""
    canonical_value = ""
    fallback_settings: dict[str, Any] = {}
    profile_status = ""
    profile_error = ""

    if _is_mapping(account_profile) and bool(account_profile):
        profile = _extract_settings(account_profile, {})
        fallback_settings.update(profile)
        if profile.get(ENTITLEMENT_FIELD) is not None:
            canonical_value = _safe_text(profile.get(ENTITLEMENT_FIELD)).casefold()
            source_name = "account_profile.entitlement"
    elif _is_mapping(session_state):
        sources = _session_sources(session_state)
        auth_user = _extract_settings(sources["auth_user"], {})
        profile = _extract_settings(sources["account_profile"], {})
        account_settings = _extract_settings(sources["account_user_settings"], {})
        fallback_settings.update(auth_user)
        fallback_settings.update(account_settings)
        fallback_settings.update(profile)
        if profile.get(ENTITLEMENT_FIELD) is not None:
            canonical_value = _safe_text(profile.get(ENTITLEMENT_FIELD)).casefold()
            source_name = "account_profile.entitlement"
        elif auth_user.get(ENTITLEMENT_FIELD) is not None:
            canonical_value = _safe_text(auth_user.get(ENTITLEMENT_FIELD)).casefold()
            source_name = "auth_user.entitlement"
        elif account_settings.get(ENTITLEMENT_FIELD) is not None:
            canonical_value = _safe_text(account_settings.get(ENTITLEMENT_FIELD)).casefold()
            source_name = "account_user_settings.entitlement"
        profile_status = _safe_text(session_state.get("account_profile_status"))
        profile_error = _safe_text(session_state.get("account_profile_error"))
    else:
        account_settings = _extract_settings(account, {})
        user_setting_values = _extract_settings(user_settings, {})
        fallback_settings.update(user_setting_values)
        fallback_settings.update(account_settings)
        if account_settings.get(ENTITLEMENT_FIELD) is not None:
            canonical_value = _safe_text(account_settings.get(ENTITLEMENT_FIELD)).casefold()
            source_name = "account.entitlement"
        elif user_setting_values.get(ENTITLEMENT_FIELD) is not None:
            canonical_value = _safe_text(user_setting_values.get(ENTITLEMENT_FIELD)).casefold()
            source_name = "user_settings.entitlement"

    if canonical_value:
        tier = _normalize_tier(canonical_value)
        is_premium = tier != FREE
        return {
            "entitlement": tier,
            "is_premium": is_premium,
            "is_front_office": tier == FRONT_OFFICE,
            "source": source_name,
            "source_field": source_name,
            "raw_value": canonical_value,
            "reason": source_name,
            "profile_status": profile_status,
            "profile_error": profile_error,
        }

    tier_field = _safe_text(
        fallback_settings.get("subscription_tier")
        or fallback_settings.get("plan")
        or fallback_settings.get("tier")
    ).casefold()
    if tier_field and _normalize_tier(tier_field) != FREE:
        tier = _normalize_tier(tier_field)
        return {
            "entitlement": tier,
            "is_premium": True,
            "is_front_office": tier == FRONT_OFFICE,
            "source": "fallback_field",
            "source_field": "plan/tier",
            "raw_value": tier_field,
            "reason": "fallback_field",
            "profile_status": profile_status,
            "profile_error": profile_error,
        }

    for key in ("is_premium", "premium", "premium_enabled", "has_premium"):
        if _truthy(fallback_settings.get(key)):
            return {
                "entitlement": PRO,
                "is_premium": True,
                "is_front_office": False,
                "source": "fallback_field",
                "source_field": key,
                "raw_value": _safe_text(fallback_settings.get(key)),
                "reason": "fallback_field",
                "profile_status": profile_status,
                "profile_error": profile_error,
            }

    reason = "default_free"
    if profile_status == "missing":
        reason = "profile_missing"
    elif profile_status == "error":
        reason = "profile_error"
    return {
        "entitlement": FREE,
        "is_premium": False,
        "is_front_office": False,
        "source": reason,
        "source_field": "",
        "raw_value": "",
        "reason": reason,
        "profile_status": profile_status,
        "profile_error": profile_error,
    }


def _referral_comp_is_active(user_settings: Any) -> bool:
    """True when this account holds a live, unexpired referral comp window.

    Deferred import — modules.referrals is the comp's own owner (encoding,
    the 3-referral threshold, the 3-month cap); this module only consumes
    the single "is a comp live right now" boolean so the reward logic has
    exactly one implementation. Fails closed (never grants on an import or
    parse error) rather than raising into entitlement resolution.
    """
    try:
        from modules import referrals

        return referrals.comp_is_active(user_settings)
    except Exception:
        return False


def effective_entitlement(
    *,
    account_profile: dict | None = None,
    session_state: dict | None = None,
    user_settings: dict | None = None,
    environ: dict | None = None,
    secrets: Any = None,
) -> str:
    """Resolve the product entitlement from one authoritative source chain.

    Development override wins. In production, only the authenticated
    Supabase profile may grant a paid tier; absent or free profile data
    resolves Free. Returns one of FREE / PRO / FRONT_OFFICE.

    Referral comp (see modules.referrals): a live, unexpired
    ``referral_program.comp_until`` on this account's own `user_settings`
    upgrades an otherwise-Free resolution to Pro. It never applies when the
    Stripe-derived profile tier already resolved Pro or Front Office — a
    real paid subscription is authoritative and is never downgraded,
    reinterpreted, or "stacked" by a comp; the comp only ever fills in for
    an actually-Free account. This is additive to the existing source
    chain above, not a replacement of it.
    """
    if premium_override_enabled(environ=environ, secrets=secrets):
        return PRO

    profile = account_profile if _is_mapping(account_profile) else None
    if profile is None and _is_mapping(session_state):
        profile = _session_sources(session_state).get("account_profile")

    # No authenticated Supabase account at all (guest) — a referral comp is
    # account-scoped state, so there is nothing to check; keep the original
    # immediate-Free behavior exactly as it was before this comp addition.
    if not _is_mapping(profile) or not profile:
        return FREE

    resolved = get_entitlement_debug(
        account_profile=profile,
        environ={},
        secrets=None,
    )
    resolved_tier = resolved.get("entitlement")
    tier = resolved_tier if resolved_tier in _KNOWN_TIERS else FREE

    if tier == FREE:
        settings = user_settings if _is_mapping(user_settings) else None
        if settings is None and _is_mapping(session_state):
            settings = session_state.get("account_user_settings")
        if _is_mapping(settings) and _referral_comp_is_active(settings):
            return PRO

    return tier


def get_user_entitlement(
    account: dict | None = None,
    user_settings: dict | None = None,
    *,
    account_profile: dict | None = None,
    session_state: dict | None = None,
    environ: dict | None = None,
    secrets: Any = None,
) -> str:
    return str(
        get_entitlement_debug(
            account,
            user_settings,
            account_profile=account_profile,
            session_state=session_state,
            environ=environ,
            secrets=secrets,
        ).get("entitlement", FREE)
    )


def is_premium_user(*args, **kwargs) -> bool:
    """True for Pro or Front Office (i.e. "has paid access")."""

    return is_at_least(get_user_entitlement(*args, **kwargs), PRO)


def is_front_office_user(*args, **kwargs) -> bool:
    return get_user_entitlement(*args, **kwargs) == FRONT_OFFICE


def premium_enabled(*args, **kwargs) -> bool:
    return is_premium_user(*args, **kwargs)


def premium_badge_html(label: str = "Premium") -> str:
    return f"<span class='premium-badge'>{escape(_safe_text(label, 'Premium'))}</span>"


def premium_lock_html(
    title: str,
    body: str = "",
    *,
    feature: str = "",
    cta: str = "Upgrade to Premium",
) -> str:
    title_text = _safe_text(title, "Premium feature")
    body_text = _safe_text(body, "Upgrade later to unlock this deeper analysis.")
    feature_text = _safe_text(feature, "Premium")
    cta_text = _safe_text(cta, "Upgrade to Premium")
    return (
        "<div class='premium-lock dg-preset-secondary'>"
        "<div class='premium-lock-top'>"
        f"{premium_badge_html(feature_text)}"
        f"<span class='premium-lock-cta'>{escape(cta_text)}</span>"
        "</div>"
        f"<div class='premium-lock-title'>{escape(title_text)}</div>"
        f"<div class='premium-lock-body'>{escape(body_text)}</div>"
        "<div class='premium-lock-included'>Included with Premium</div>"
        "</div>"
    )


def render_premium_lock(
    title: str,
    body: str = "",
    *,
    feature: str = "",
    cta: str = "Upgrade to Premium",
) -> None:
    st.markdown(
        premium_lock_html(title, body, feature=feature, cta=cta),
        unsafe_allow_html=True,
    )


def premium_blur_preview_html(label: str, *, rows: int = 3) -> str:
    """Abstract, non-data-revealing preview rows for a locked section.

    Pairs with render_premium_lock (rendered immediately after this) so a
    locked feature stays visible — per the relaunch paywall spec: a
    blurred preview plus an "Unlock" CTA, never hidden outright. The rows
    are empty placeholders with a literal CSS blur() (see
    modules.paywall_gate_styles.PAYWALL_GATE_CSS), not a blur() filter over
    real Pro-only data — same "tease the shape, not the content" principle
    as modules.trade_hub_ui.trade_hub_locked_preview_html.
    """

    slots = max(0, min(int(rows or 0), 5))
    bars = "".join(
        "<div class='paywall-blur-row' aria-hidden='true'></div>" for _ in range(slots)
    )
    return (
        "<div class='paywall-blur-preview'>"
        f"<p class='paywall-blur-label'>{escape(_safe_text(label, 'Locked'))}</p>"
        f"{bars}"
        "</div>"
    )
