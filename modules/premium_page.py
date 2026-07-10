from __future__ import annotations

from html import escape

import streamlit as st

from modules import premium
from modules import stripe_billing


FREE_INCLUDES = (
    ("League import", "Load Sleeper leagues and keep the main roster workflow useful."),
    ("Dashboard snapshot", "Roster limit alerts, limited Next Moves, and basic team needs."),
    ("Trade preview", "Top generated trade ideas so the page has immediate value."),
    ("Priority Adds", "Best waiver adds before deeper board and FAAB detail."),
    ("Core roster view", "Roster priorities, core assets, starters, and basic team context."),
)


PREMIUM_INCLUDED_NOW = (
    ("Full Next Moves", "Expanded Dashboard stack with deeper roster, trade, waiver, and health signals."),
    ("Expanded League Pulse", "League-wide contender, rebuilder, and market context."),
    ("Full trade board", "More generated trade ideas, partner context, and player return search."),
    ("Full waiver board", "Stash candidates, watchlist depth, FAAB shortlist, and add/drop context."),
    ("Advanced roster decisions", "Trade-away, hold, drop, and bench-insulation reads."),
    ("Expanded league intelligence", "Deeper team context, franchise rank details, and league-wide signals already available in the app."),
)


POSSIBLE_FUTURE_FEATURES = (
    ("Live draft tools", "Possible future draft-room workflows if the beta proves the demand."),
    ("Weekly reports", "Possible recurring league summaries and movement tracking."),
    ("Historical franchise tracking", "Possible long-term snapshots for team direction and roster value changes."),
    ("Trade, injury, and waiver alerts", "Possible notification-style workflows after core recommendations are stable."),
    ("More platform support", "Possible broader platform coverage beyond current Sleeper-first support."),
)


def plan_status_label(entitlement: str) -> str:
    return "Premium" if entitlement == premium.PREMIUM else "Free"


def _plan_row_html(title: str, body: str, *, premium_row: bool = False) -> str:
    row_class = "premium-plan-row premium-plan-row-premium" if premium_row else "premium-plan-row"
    return (
        f"<div class='{row_class}'>"
        f"<div class='premium-plan-row-title'>{escape(title)}</div>"
        f"<div class='premium-plan-row-body'>{escape(body)}</div>"
        "</div>"
    )


def premium_page_html(
    *,
    entitlement: str = premium.FREE,
    billing_config: stripe_billing.StripeBillingConfig | None = None,
) -> str:
    billing_config = billing_config or stripe_billing.StripeBillingConfig()
    current_plan = plan_status_label(entitlement)
    free_rows = "".join(_plan_row_html(title, body) for title, body in FREE_INCLUDES)
    premium_rows = "".join(
        _plan_row_html(title, body, premium_row=True)
        for title, body in PREMIUM_INCLUDED_NOW
    )
    future_rows = "".join(
        _plan_row_html(title, body)
        for title, body in POSSIBLE_FUTURE_FEATURES
    )
    status_class = "premium-status-premium" if entitlement == premium.PREMIUM else "premium-status-free"
    if billing_config.configured:
        billing_body = (
            "Stripe test-mode billing is configured. Founder Premium checkout can be tested "
            "with Stripe test cards; live payments are not enabled."
        )
    else:
        billing_body = (
            "Billing setup is not enabled yet. This page previews the Premium plan structure; "
            "entitlement is currently controlled by account settings or the local development override."
        )
    return (
        "<div class='premium-page'>"
        "<div class='premium-page-header dg-preset-command'>"
        "<div class='premium-page-kicker'>Founder Access</div>"
        "<div class='premium-page-title'>Premium</div>"
        "<div class='premium-page-subtitle'>Early Access Premium unlocks the deeper tools already available in DynastyGM. Future ideas are listed separately and are not guaranteed.</div>"
        "</div>"
        "<div class='premium-status-panel dg-preset-secondary'>"
        "<div class='premium-status-label'>Current plan</div>"
        f"<div class='premium-status-value {status_class}'>{escape(current_plan)}</div>"
        "</div>"
        "<div class='premium-plan-grid'>"
        "<div class='premium-plan-slab premium-plan-free dg-preset-secondary'>"
        "<div class='premium-plan-label'>Free includes</div>"
        f"{free_rows}"
        "</div>"
        "<div class='premium-plan-slab premium-plan-premium dg-preset-primary-action'>"
        "<div class='premium-plan-label'>Included now with Premium</div>"
        f"{premium_rows}"
        "</div>"
        "</div>"
        "<div class='premium-plan-slab premium-plan-future dg-preset-secondary'>"
        "<div class='premium-plan-label'>Possible future features</div>"
        f"{future_rows}"
        "<div class='premium-plan-row-body'>These are roadmap candidates, not guaranteed deliverables or billing terms.</div>"
        "</div>"
        "<div class='premium-billing-note dg-preset-diagnostic'>"
        "<div class='premium-billing-note-title'>Billing status</div>"
        f"<div class='premium-billing-note-body'>{escape(billing_body)}</div>"
        "<div class='premium-billing-note-body premium-dev-note'>Local testing: set "
        "<code>DYNASTYGM_PREMIUM_OVERRIDE=true</code> to simulate Premium.</div>"
        "</div>"
        "</div>"
    )


def render_premium_page(*, entitlement: str = premium.FREE) -> None:
    config = stripe_billing.load_stripe_config(secrets=st.secrets)
    st.markdown(
        premium_page_html(entitlement=entitlement, billing_config=config),
        unsafe_allow_html=True,
    )
    if not config.configured:
        return

    st.caption("Stripe test mode only. Live billing is not enabled.")
    state = st.session_state
    auth_session = state.get("auth_session") if isinstance(state.get("auth_session"), dict) else {}
    account_profile = state.get("account_profile") if isinstance(state.get("account_profile"), dict) else {}
    user_id = str(auth_session.get("user_id") or account_profile.get("user_id") or "").strip()
    email = str(state.get("auth_email") or account_profile.get("email") or "").strip()
    stripe_customer_id = str(account_profile.get("stripe_customer_id") or "").strip()

    if entitlement == premium.PREMIUM:
        if stripe_customer_id:
            if st.button("Manage billing in Stripe test portal", key="premium_manage_billing_test", use_container_width=True):
                try:
                    portal = stripe_billing.create_customer_portal_session(
                        config=config,
                        stripe_customer_id=stripe_customer_id,
                    )
                    st.link_button("Open Stripe customer portal", getattr(portal, "url", ""), use_container_width=True)
                except Exception:
                    st.warning("Billing portal is not available right now. Check Stripe test configuration and try again.")
        else:
            st.info("Premium is active. A Stripe customer id is not linked yet, so portal management is unavailable.")
        return

    interval = st.radio(
        "Founder Premium test checkout",
        [stripe_billing.MONTHLY, stripe_billing.ANNUAL],
        format_func=lambda value: "Monthly Premium" if value == stripe_billing.MONTHLY else "Annual Premium",
        horizontal=True,
        key="premium_test_checkout_interval",
    )
    if st.button("Create Stripe test checkout", key="premium_create_test_checkout", use_container_width=True):
        if not user_id:
            st.warning("Sign in before starting a Premium checkout test.")
            return
        try:
            session = stripe_billing.create_checkout_session(
                config=config,
                user_id=user_id,
                email=email,
                interval=interval,
            )
            st.link_button("Open Stripe test checkout", getattr(session, "url", ""), use_container_width=True)
        except Exception:
            st.warning("Stripe test checkout is not available right now. Check test billing configuration and try again.")
