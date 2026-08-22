from __future__ import annotations

from html import escape

import streamlit as st

from modules import brand_identity
from modules import premium
from modules import product_copy
from modules import stripe_billing


FREE_INCLUDES = (
    ("League import", "Load Sleeper leagues and keep the main roster tools useful."),
    ("Dashboard overview", "Today's Game Plan, limited Next Moves, and basic team needs."),
    ("What Changed", "Session history of meaningful recommendation transitions."),
    ("GM Targets (limited)", "Save up to three players you're actively considering."),
    ("Share Recommendation", "Download branded share cards from Trade Hub, Waivers, and Player Quick View."),
    ("Players explorer", "Filter the dynasty market and open Player Quick View."),
    ("Trade preview", "Top generated trade ideas so the page has immediate value."),
    ("Priority Adds", "Best waiver adds before deeper board and FAAB detail."),
    ("Core roster view", "Roster priorities, core assets, starters, and basic team context."),
)


# Launch-ready Premium depth only — must match effective_entitlement gates.
PREMIUM_INCLUDED_NOW = (
    ("More next moves", "Expanded Dashboard stack with deeper roster, trade, waiver, and health signals."),
    ("Full League Pulse", "League-wide contender, rebuilder, and trading posture on Dashboard."),
    (product_copy.PREMIUM_FULL_TRADE_HUB, "More generated trade ideas, partner context, and player return search."),
    ("Full waiver board", "Stash candidates, watchlist depth, FAAB shortlist, and add/drop context."),
    ("Advanced roster decisions", "Trade-away, hold, drop, Deep Analysis, and bench-insulation reads."),
    (
        "Decision Memory",
        "Durable cross-session history of material GM priority changes beyond the current session.",
    ),
    (
        "GM Targets (full board)",
        "Save up to fifty players per league with PQV Add/Remove and workflow handoffs.",
    ),
)


# Residual Ops-gated experiments only. Graduated features must not appear here.
PREMIUM_EXPERIMENTAL_WHEN_ENABLED: tuple[tuple[str, str], ...] = ()


POSSIBLE_FUTURE_FEATURES = (
    ("Weekly reports", "Possible recurring league summaries and movement tracking."),
    ("Historical franchise tracking", "Possible long-term snapshots for team direction and roster value changes."),
    ("Trade, injury, and waiver alerts", "Possible notification-style workflows after core recommendations are stable."),
    ("More platform support", "Possible broader platform coverage beyond current Sleeper-first support."),
)


def plan_status_label(entitlement: str) -> str:
    return "Premium" if entitlement == premium.PREMIUM else "Free"


PLAN_DETAILS = {
    stripe_billing.MONTHLY: ("Monthly", "$3.99", "per month"),
    stripe_billing.ANNUAL: ("Annual", "$19.99", "per year"),
}


def normalize_checkout_interval(value: object) -> str:
    interval = str(value or "").strip().lower()
    return interval if interval in PLAN_DETAILS else stripe_billing.MONTHLY


def _plan_option_html(interval: str, *, selected: bool) -> str:
    label, price, cadence = PLAN_DETAILS[normalize_checkout_interval(interval)]
    selected_class = " premium-checkout-option-selected" if selected else ""
    selected_text = "Selected" if selected else "Available"
    return (
        f"<div class='premium-checkout-option{selected_class}' "
        f"data-premium-plan='{escape(interval)}' aria-label='{escape(label)} plan, {escape(price)} {escape(cadence)}, {selected_text}'>"
        f"<div class='premium-checkout-option-status'>{selected_text}</div>"
        f"<div class='premium-checkout-option-name'>{escape(label)}</div>"
        f"<div class='premium-checkout-option-price'>{escape(price)}</div>"
        f"<div class='premium-checkout-option-cadence'>{escape(cadence)}</div>"
        "</div>"
    )


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
    show_local_override_note: bool = False,
) -> str:
    from modules import premium_conversion

    billing_config = billing_config or stripe_billing.StripeBillingConfig()
    current_plan = plan_status_label(entitlement)
    free_rows = "".join(_plan_row_html(title, body) for title, body in FREE_INCLUDES)
    premium_rows = "".join(
        _plan_row_html(title, body, premium_row=True)
        for title, body in PREMIUM_INCLUDED_NOW
    )
    experimental_rows = "".join(
        _plan_row_html(title, body)
        for title, body in PREMIUM_EXPERIMENTAL_WHEN_ENABLED
    )
    experimental_slab = (
        (
            "<div class='premium-plan-slab premium-plan-future dg-preset-secondary'>"
            "<div class='premium-plan-label'>Experimental when enabled</div>"
            f"{experimental_rows}"
            "<div class='premium-plan-row-body'>These require Ops experiment flags and are not "
            "guaranteed for every Premium account.</div>"
            "</div>"
        )
        if PREMIUM_EXPERIMENTAL_WHEN_ENABLED
        else ""
    )
    future_rows = "".join(
        _plan_row_html(title, body)
        for title, body in POSSIBLE_FUTURE_FEATURES
    )
    status_class = "premium-status-premium" if entitlement == premium.PREMIUM else "premium-status-free"
    if billing_config.configured:
        if billing_config.billing_mode == "live":
            billing_body = (
                "Secure recurring Founder Premium checkout is processed by Stripe. "
                "Manage renewal or cancellation from the billing portal."
            )
        else:
            billing_body = (
                "Secure Founder Premium checkout uses Stripe test mode. "
                "Use Stripe test cards during Founder Beta — no live charge will be made."
            )
    else:
        billing_body = (
            "Premium checkout will appear here once billing is enabled for your account. "
            "Live billing is not enabled. Your current plan status is shown above."
        )
    local_override_note = (
        "<div class='premium-billing-note-body premium-dev-note'>Local testing: set "
        "<code>DYNASTYGM_PREMIUM_OVERRIDE=true</code> to simulate Premium.</div>"
        if show_local_override_note
        else ""
    )
    return (
        "<div class='premium-page'>"
        "<div class='premium-page-header dg-preset-command'>"
        f"<div class='premium-page-kicker'>{escape(brand_identity.FOUNDER_BETA_LABEL)}</div>"
        "<div class='premium-page-title'>Premium</div>"
        f"<div class='premium-page-subtitle'>{escape(premium_conversion.VALUE_PROP_HEADLINE)}. "
        f"{escape(premium_conversion.VALUE_PROP_BODY)} "
        f"{escape(brand_identity.PRODUCT_NAME)} separates Free depth from Premium history "
        "and board capacity — residual experiments stay Ops-gated.</div>"
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
        f"{experimental_slab}"
        "<div class='premium-plan-slab premium-plan-future dg-preset-secondary'>"
        "<div class='premium-plan-label'>Possible future features</div>"
        f"{future_rows}"
        "<div class='premium-plan-row-body'>These are roadmap candidates, not guaranteed deliverables or billing terms.</div>"
        "</div>"
        "<div class='premium-billing-note dg-preset-diagnostic'>"
        "<div class='premium-billing-note-title'>Billing</div>"
        f"<div class='premium-billing-note-body'>{escape(billing_body)}</div>"
        f"{local_override_note}"
        "</div>"
        "</div>"
    )


def render_premium_page(*, entitlement: str = premium.FREE) -> None:
    from modules import guest_conversion
    from modules import premium_conversion

    config = stripe_billing.load_stripe_config(secrets=st.secrets)
    try:
        billing_flag = str(st.query_params.get("billing", "") or "").strip().casefold()
    except Exception:
        billing_flag = ""
    if billing_flag == "success":
        # checkout_completed is emitted once by premium_conversion.handle_billing_return_success
        premium_conversion.handle_billing_return_success()
        st.success(
            "Checkout complete. Premium activates after Stripe confirms billing — "
            "your plan status refreshes on this page."
        )
    elif billing_flag in {"cancel", "cancelled", "canceled"}:
        premium_conversion.handle_billing_return_cancel()
        st.info("Checkout cancelled. Your Free plan is unchanged — you can resume anytime.")
    st.markdown(
        premium_page_html(
            entitlement=entitlement,
            billing_config=config,
            show_local_override_note=premium.debug_auth_enabled(secrets=st.secrets),
        ),
        unsafe_allow_html=True,
    )
    if not config.configured:
        return

    st.caption(
        "Stripe securely manages recurring billing and cancellation."
        if config.billing_mode == "live"
        else "No live charge will be made."
    )
    state = st.session_state
    auth_session = state.get("auth_session") if isinstance(state.get("auth_session"), dict) else {}
    account_profile = state.get("account_profile") if isinstance(state.get("account_profile"), dict) else {}
    user_id = str(auth_session.get("user_id") or account_profile.get("user_id") or "").strip()
    email = str(state.get("auth_email") or account_profile.get("email") or "").strip()
    stripe_customer_id = str(account_profile.get("stripe_customer_id") or "").strip()

    if entitlement == premium.PREMIUM:
        if stripe_customer_id:
            if st.button("Manage Billing", key="premium_manage_billing_test", use_container_width=True):
                try:
                    from modules import launch_analytics

                    launch_analytics.track_event(
                        "portal_opened",
                        props=launch_analytics.build_context_props(
                            st.session_state,
                            route="premium",
                            source_surface="manage_billing",
                        ),
                        state=st.session_state,
                    )
                    portal = stripe_billing.create_customer_portal_session(
                        config=config,
                        stripe_customer_id=stripe_customer_id,
                    )
                    st.link_button(
                        "Open billing portal",
                        getattr(portal, "url", ""),
                        use_container_width=True,
                    )
                except Exception:
                    st.warning(
                        "Billing portal is not available right now. Check billing configuration and try again."
                    )
        else:
            st.info("Premium is active. Billing management appears after Stripe links a customer id.")
        return

    st.markdown(
        f"**{premium_conversion.VALUE_PROP_HEADLINE}.** "
        f"{premium_conversion.VALUE_PROP_BODY}"
    )
    if st.session_state.get(premium_conversion.RESUME_CHECKOUT_FLAG):
        st.caption("Welcome back — continue checkout when you are ready.")
        st.session_state.pop(premium_conversion.RESUME_CHECKOUT_FLAG, None)
    intent = premium_conversion.peek_checkout_intent()
    default_interval = intent.get("interval") or stripe_billing.MONTHLY
    if default_interval not in {stripe_billing.MONTHLY, stripe_billing.ANNUAL}:
        default_interval = stripe_billing.MONTHLY
    interval_key = "premium_test_checkout_interval"
    if interval_key not in st.session_state:
        st.session_state[interval_key] = default_interval
    st.markdown("<div class='premium-checkout-heading'>Choose your plan</div>", unsafe_allow_html=True)
    selected_interval = normalize_checkout_interval(st.session_state.get(interval_key))
    plan_columns = st.columns(2, gap="small")
    for column, plan_interval in zip(
        plan_columns,
        (stripe_billing.MONTHLY, stripe_billing.ANNUAL),
    ):
        selected = selected_interval == plan_interval
        label, price, cadence = PLAN_DETAILS[plan_interval]
        with column:
            st.markdown(
                _plan_option_html(plan_interval, selected=selected),
                unsafe_allow_html=True,
            )
            if st.button(
                "Selected" if selected else f"Choose {label}",
                key=f"premium_choose_{plan_interval}",
                use_container_width=True,
                disabled=selected,
            ):
                st.session_state[interval_key] = plan_interval
                selected_interval = plan_interval
    st.caption(
        "Recurring subscription. Manage renewal or cancellation from the billing portal."
        if config.billing_mode == "live"
        else "Founder Beta uses Stripe test mode. No live charge will be made from this checkout."
    )

    run_checkout_key = "_premium_run_founder_checkout"

    def _on_founder_checkout() -> None:
        chosen = normalize_checkout_interval(st.session_state.get(interval_key))
        pending = premium_conversion.peek_checkout_intent()
        premium_conversion.capture_checkout_intent(
            interval=chosen,
            feature=pending.get("feature") or "general_premium_page",
            surface="founder_checkout",
            route="premium",
        )
        if not str(
            (st.session_state.get("auth_session") or {}).get("user_id")
            or (st.session_state.get("account_profile") or {}).get("user_id")
            or ""
        ).strip():
            guest_conversion.open_auth_dialog(mode="signup", surface="premium_checkout")
            return
        st.session_state[run_checkout_key] = True

    st.button(
        premium_conversion.CHECKOUT_CTA,
        key="premium_create_test_checkout",
        use_container_width=True,
        type="primary",
        on_click=_on_founder_checkout,
    )
    if not user_id and premium_conversion.peek_checkout_intent().get("surface") == "founder_checkout":
        st.caption("Create a free account or sign in before checkout — your Premium intent is saved.")
    if entitlement == premium.PREMIUM:
        return
    if st.session_state.pop(run_checkout_key, False):
        if not user_id:
            st.warning("Create a free account or sign in before checkout — your Premium intent is saved.")
            return
        try:
            chosen = normalize_checkout_interval(st.session_state.get(interval_key))
            pending = premium_conversion.peek_checkout_intent()
            # Single emit path — premium_conversion normalizes checkout_started.
            premium_conversion.track_premium_event(
                "premium_checkout_started",
                surface="founder_checkout",
                feature=pending.get("feature") or "general_premium_page",
                route="premium",
                extra={"interval": chosen},
                once_key=f"{user_id}:{chosen}:premium",
            )
            session = stripe_billing.create_checkout_session(
                config=config,
                user_id=user_id,
                email=email,
                interval=chosen,
            )
            st.link_button(
                "Continue to checkout",
                getattr(session, "url", ""),
                use_container_width=True,
            )
        except Exception:
            st.warning(
                "Checkout is not available right now. Check billing configuration and try again."
            )
    # stMain remains the sole scroll owner. This route-end clearance keeps the
    # final billing control above the fixed application controls without adding
    # a nested height/overflow container.
    st.markdown("<div class='premium-route-end' aria-hidden='true'></div>", unsafe_allow_html=True)
