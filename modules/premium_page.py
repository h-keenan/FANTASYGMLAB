from __future__ import annotations

from html import escape

import streamlit as st

from modules import brand_identity
from modules import premium
from modules import product_copy
from modules import stripe_billing
from modules.semantic_glyphs import glyph_html


PREMIUM_PLAN_CTA_COMPONENT = st.components.v2.component(
    "dgm_premium_plan_checkout_cta",
    html="""
      <button id="plan-cta" type="button"></button>
      <a id="checkout-fallback" target="_blank" rel="noopener">Open secure checkout</a>
    """,
    css="""
      :root { color-scheme: dark; }
      body { margin: 0; overflow: hidden; }
      #plan-cta, #checkout-fallback {
        /* Isolated web component (its own shadow-root-like document) — no
           access to the parent page's :root tokens. Border pinned to match
           design_tokens.py's --color-border-strong (#64748b) so this CTA's
           default outline clears WCAG 1.4.11 (3:1) instead of the previous
           #3b4452, which was only ~1.4:1 against this button's background. */
        align-items: center; background: #0a0c10; border: 1px solid #64748b;
        border-radius: 0; box-sizing: border-box; color: #f8fafc; display: flex;
        font: 750 12px/1.2 system-ui, sans-serif; justify-content: center;
        letter-spacing: .045em; min-height: 44px; padding: 10px 14px;
        text-align: center; text-decoration: none; text-transform: uppercase; width: 100%;
      }
      #plan-cta[data-selected="true"] { border-color: #22d3ee; color: #67e8f9; }
      #plan-cta:focus-visible, #checkout-fallback:focus-visible {
        outline: 3px solid rgba(103,232,249,.34); outline-offset: -3px;
      }
      #checkout-fallback { display: none; }
      #checkout-fallback[data-visible="true"] { display: flex; }
    """,
    js="""
    export default function(component) {
      const { data, parentElement, setTriggerValue } = component
      const button = parentElement.querySelector("#plan-cta")
      const fallback = parentElement.querySelector("#checkout-fallback")
      if (!button || !fallback) return
      const interval = String((data && data.interval) || "monthly")
      const popupName = "dgm-founder-premium-checkout"
      button.textContent = String((data && data.label) || "Choose Premium")
      button.dataset.selected = String(Boolean(data && data.selected))
      button.onclick = () => {
        const popup = window.open("about:blank", popupName)
        if (popup) {
          try {
            popup.document.title = "Preparing secure checkout"
            popup.document.body.textContent = "Preparing secure Stripe checkout…"
          } catch (_error) {}
        }
        const actionId = (globalThis.crypto && crypto.randomUUID)
          ? crypto.randomUUID()
          : `${Date.now()}-${Math.random().toString(36).slice(2)}`
        setTriggerValue("selection", { interval, action_id: actionId })
      }
      const redirectUrl = String((data && data.redirectUrl) || "")
      const redirectId = String((data && data.redirectId) || "")
      if (redirectUrl.startsWith("https://")) {
        const popup = window.open("", popupName)
        if (popup) {
          popup.location.replace(redirectUrl)
          setTriggerValue("redirect_ack", { redirect_id: redirectId })
        } else {
          fallback.href = redirectUrl
          fallback.dataset.visible = "true"
        }
      }
    }
    """,
)


CHECKOUT_REDIRECT_KEY = "_premium_checkout_redirect"
CHECKOUT_ACTION_KEY = "_premium_checkout_action_id"


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


# Mobile Paywall's benefit checklist — grounded in PREMIUM_INCLUDED_NOW so web
# and mobile can never describe two different sets of gated Premium features,
# even though mobile's paywall wants short one-line copy instead of a
# title+description row. Served to the app via GET /v1/me
# (services/mobile_api_service.py), so a copy change here reaches mobile
# without a client release. Mobile keeps a hardcoded copy of this exact list
# as an offline/fetch-failure fallback only — see mobile/src/screens/PaywallScreen.tsx.
MOBILE_PREMIUM_BENEFIT_LINES: tuple[dict[str, str], ...] = (
    {"title": "More next moves", "line": "Your full Next Move briefing, not just the top 4"},
    {
        "title": "Full League Pulse",
        "line": "Full League Pulse — see the whole league’s contenders and rebuilders",
    },
    {
        "title": "Full waiver board",
        "line": "The complete waiver board — stash candidates, watchlist depth, and a FAAB shortlist",
    },
    {
        "title": product_copy.PREMIUM_FULL_TRADE_HUB,
        "line": "Every Trade Hub idea, not just the first 2 (skip the ads)",
    },
    {
        "title": "GM Targets (full board)",
        "line": "GM Targets watchlist up to 50 players (Free is capped at 3)",
    },
)


def mobile_premium_benefit_lines() -> list[str]:
    """Single-line Premium benefit copy for the mobile Paywall screen.

    Every entry's `title` must exist in PREMIUM_INCLUDED_NOW, so this raises
    if a future edit renames or removes a benefit here without updating the
    other list — keeping web and mobile from silently drifting apart again.
    """
    known_titles = {title for title, _ in PREMIUM_INCLUDED_NOW}
    lines: list[str] = []
    for entry in MOBILE_PREMIUM_BENEFIT_LINES:
        title = entry["title"]
        if title not in known_titles:
            raise ValueError(f"Mobile Premium benefit line references unknown title: {title!r}")
        lines.append(entry["line"])
    return lines


POSSIBLE_FUTURE_FEATURES = (
    ("Weekly reports", "Possible recurring league summaries and movement tracking."),
    ("Historical franchise tracking", "Possible long-term snapshots for team direction and roster value changes."),
    ("Trade, injury, and waiver alerts", "Possible notification-style workflows after core recommendations are stable."),
    ("More platform support", "Possible broader platform coverage beyond current Sleeper-first support."),
)


def plan_status_label(entitlement: str) -> str:
    return "Premium" if entitlement == premium.PREMIUM else "Free"


# Static fallback used for interval validation and whenever no live-fetched
# pricing is supplied (e.g. direct calls to _plan_option_html in tests). The
# real display values shown to users come from stripe_billing.plan_display_details,
# which fetches the actual Stripe Price objects with a short cache and falls
# back to this same dict on any failure — see Gap 1 in the Premium pricing audit.
PLAN_DETAILS = stripe_billing.DEFAULT_PLAN_DETAILS


CAPABILITY_GLYPHS = {
    "League import": "league",
    "Dashboard overview": "home",
    "What Changed": "history",
    "GM Targets (limited)": "roster",
    "Share Recommendation": "trade",
    "Players explorer": "rankings",
    "Trade preview": "trade",
    "Priority Adds": "waiver",
    "Core roster view": "roster",
    "More next moves": "home",
    "Full League Pulse": "league",
    product_copy.PREMIUM_FULL_TRADE_HUB: "trade",
    "Full waiver board": "waiver",
    "Advanced roster decisions": "roster",
    "Decision Memory": "history",
    "GM Targets (full board)": "roster",
}


def normalize_checkout_interval(value: object) -> str:
    interval = str(value or "").strip().lower()
    return interval if interval in PLAN_DETAILS else stripe_billing.MONTHLY


def _plan_option_html(
    interval: str,
    *,
    selected: bool,
    plan_details: dict[str, tuple[str, str, str]] | None = None,
) -> str:
    details = plan_details or PLAN_DETAILS
    label, price, cadence = details[normalize_checkout_interval(interval)]
    selected_class = " premium-checkout-option-selected" if selected else ""
    selected_text = "Selected plan" if selected else "Available plan"
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
        "<div class='premium-plan-row-heading'>"
        f"{glyph_html(CAPABILITY_GLYPHS.get(title, 'more'), size='card')}"
        f"<div class='premium-plan-row-title'>{escape(title)}</div>"
        "</div>"
        f"<div class='premium-plan-row-body'>{escape(body)}</div>"
        "</div>"
    )


def _premium_intro_html(*, entitlement: str) -> str:
    from modules import premium_conversion

    current_plan = plan_status_label(entitlement)
    status_class = "premium-status-premium" if entitlement == premium.PREMIUM else "premium-status-free"
    return (
        "<div class='premium-page premium-page-intro'>"
        "<div class='premium-page-header dg-preset-command'>"
        f"<div class='premium-page-kicker'>{escape(brand_identity.PRODUCT_NAME)} · {escape(brand_identity.FOUNDER_BETA_LABEL)}</div>"
        "<div class='premium-page-title'>Premium</div>"
        f"<div class='premium-page-subtitle'>{escape(premium_conversion.VALUE_PROP_HEADLINE)}. "
        f"{escape(premium_conversion.VALUE_PROP_BODY)}</div>"
        "</div>"
        "<div class='premium-status-panel dg-preset-secondary'>"
        "<div class='premium-status-label'>Current plan</div>"
        f"<div class='premium-status-value {status_class}'>{escape(current_plan)}</div>"
        "</div>"
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
        f"{_premium_intro_html(entitlement=entitlement)}"
        "<div class='premium-page premium-page-details'>"
        "<div class='premium-comparison-heading'>"
        "<div class='premium-page-kicker'>Compare access</div>"
        "<div class='premium-section-title'>What each plan includes today</div>"
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
        "<div class='premium-billing-note'>"
        "<div class='premium-billing-note-title'>Billing</div>"
        f"<div class='premium-billing-note-body'>{escape(billing_body)}</div>"
        f"{local_override_note}"
        "</div>"
        "</div>"
    )


def premium_details_html(
    *,
    entitlement: str = premium.FREE,
    billing_config: stripe_billing.StripeBillingConfig | None = None,
    show_local_override_note: bool = False,
) -> str:
    full = premium_page_html(
        entitlement=entitlement,
        billing_config=billing_config,
        show_local_override_note=show_local_override_note,
    )
    intro = _premium_intro_html(entitlement=entitlement)
    return full[len(intro):]


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
    show_override = premium.debug_auth_enabled(secrets=st.secrets)
    st.markdown(_premium_intro_html(entitlement=entitlement), unsafe_allow_html=True)
    if not config.configured:
        st.markdown(
            premium_details_html(
                entitlement=entitlement,
                billing_config=config,
                show_local_override_note=show_override,
            ),
            unsafe_allow_html=True,
        )
        return

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
                        "Billing portal is not available right now. Please try again in a moment."
                    )
        else:
            st.info("Premium is active. Billing management appears after Stripe links a customer id.")
        st.markdown(
            premium_details_html(
                entitlement=entitlement,
                billing_config=config,
                show_local_override_note=show_override,
            ),
            unsafe_allow_html=True,
        )
        return

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
    st.markdown(
        premium_details_html(
            entitlement=entitlement,
            billing_config=config,
            show_local_override_note=show_override,
        ),
        unsafe_allow_html=True,
    )
    with st.container(key="premium_plan_purchase"):
        st.markdown(
            "<div class='premium-checkout-heading'>"
            "<div class='premium-page-kicker'>Choose your plan</div>"
            "<div class='premium-section-title'>Founder Premium pricing</div>"
            "<div class='premium-checkout-support'>One click takes you to Stripe's secure checkout page.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        # Live-sourced from the real Stripe Price objects when reachable
        # (briefly cached), falling back to PLAN_DETAILS on any failure — see
        # stripe_billing.plan_display_details.
        plan_details = stripe_billing.plan_display_details(config)
        selected_interval = normalize_checkout_interval(st.session_state.get(interval_key))
        plan_columns = st.columns(2, gap="small")
        clicked_interval = ""
        clicked_action_id = ""
        redirect_payload = (
            dict(st.session_state.get(CHECKOUT_REDIRECT_KEY))
            if isinstance(st.session_state.get(CHECKOUT_REDIRECT_KEY), dict)
            else {}
        )
        for column, plan_interval in zip(
            plan_columns,
            (stripe_billing.MONTHLY, stripe_billing.ANNUAL),
        ):
            selected = selected_interval == plan_interval
            label, price, cadence = plan_details[plan_interval]
            with column:
                st.markdown(
                    _plan_option_html(plan_interval, selected=selected, plan_details=plan_details),
                    unsafe_allow_html=True,
                )
                redirect_for_plan = (
                    redirect_payload
                    if str(redirect_payload.get("interval") or "") == plan_interval
                    else {}
                )
                component_result = PREMIUM_PLAN_CTA_COMPONENT(
                    data={
                        "interval": plan_interval,
                        "label": f"Choose {label} — {price}/{'mo' if plan_interval == stripe_billing.MONTHLY else 'yr'}",
                        "selected": selected,
                        "redirectUrl": str(redirect_for_plan.get("url") or ""),
                        "redirectId": str(redirect_for_plan.get("redirect_id") or ""),
                    },
                    key=f"premium_choose_{plan_interval}",
                    height=44,
                )
                selection = getattr(component_result, "selection", None)
                if isinstance(selection, dict):
                    action_id = str(selection.get("action_id") or "").strip()
                    selected_plan = normalize_checkout_interval(selection.get("interval"))
                else:
                    action_id = ""
                    selected_plan = plan_interval
                if action_id and action_id != str(st.session_state.get(CHECKOUT_ACTION_KEY) or ""):
                    st.session_state[interval_key] = plan_interval
                    selected_interval = selected_plan
                    clicked_interval = selected_plan
                    clicked_action_id = action_id
                redirect_ack = getattr(component_result, "redirect_ack", None)
                if (
                    isinstance(redirect_ack, dict)
                    and str(redirect_ack.get("redirect_id") or "")
                    == str(redirect_payload.get("redirect_id") or "")
                ):
                    st.session_state.pop(CHECKOUT_REDIRECT_KEY, None)
        st.caption(
            "Recurring subscription. Manage renewal or cancellation from the billing portal."
            if config.billing_mode == "live"
            else "Founder Beta uses Stripe test mode. No live charge will be made from this checkout."
        )

    if clicked_interval:
        chosen = normalize_checkout_interval(clicked_interval)
        st.session_state[CHECKOUT_ACTION_KEY] = clicked_action_id
        pending = premium_conversion.peek_checkout_intent()
        premium_conversion.capture_checkout_intent(
            interval=chosen,
            feature=pending.get("feature") or "general_premium_page",
            surface="premium_plan_card",
            route="premium",
        )
        if not user_id:
            guest_conversion.open_auth_dialog(mode="signup", surface="premium_checkout")
        else:
            try:
                pending = premium_conversion.peek_checkout_intent()
                premium_conversion.track_premium_event(
                    "premium_checkout_started",
                    surface="premium_plan_card",
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
                checkout_url = str(getattr(session, "url", "") or "").strip()
                if not checkout_url.startswith("https://"):
                    raise ValueError("Checkout returned an invalid navigation URL.")
                st.session_state[CHECKOUT_REDIRECT_KEY] = {
                    "interval": chosen,
                    "redirect_id": clicked_action_id,
                    "url": checkout_url,
                }
                st.rerun()
            except Exception:
                st.warning(
                    "Checkout is not available right now. Please try again in a moment."
                )
    if not user_id and premium_conversion.peek_checkout_intent().get("surface") == "premium_plan_card":
        st.caption("Create a free account or sign in before checkout — your Premium intent is saved.")
    # stMain remains the sole scroll owner. This route-end clearance keeps the
    # final billing control above the fixed application controls without adding
    # a nested height/overflow container.
    st.markdown("<div class='premium-route-end' aria-hidden='true'></div>", unsafe_allow_html=True)
