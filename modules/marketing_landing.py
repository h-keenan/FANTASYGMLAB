"""Public Founder Beta marketing landing — presentation only.

Answers what FantasyGM Lab is, what to do next, and that guest import is allowed.
Does not load league, rankings, or Trade Hub work.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

import streamlit as st

from modules import brand_identity
from modules import premium_page
from modules import stripe_billing
from modules.marketing_landing_styles import MARKETING_LANDING_CSS


_REPO_ROOT = Path(__file__).resolve().parents[1]
MARKETING_ASSET_DIR = _REPO_ROOT / "assets" / "marketing"

# Concise value proposition — grounded in PRODUCT_TAGLINE, not a new claim.
HERO_VALUE = "League-aware recommendations for dynasty managers."
HERO_SUPPORT = (
    "Import a Sleeper league, then work trades, waivers, and roster decisions "
    "with a clear next move."
)
TRUST_LINE = "Sleeper supported · Free account optional · No payment required"

PRIMARY_CTA_LABEL = "Import your league"
SECONDARY_CTA_LABEL = "See how it works"
PRICING_CTA_LABEL = "Compare Free & Premium"

WHAT_IT_DOES = (
    (
        "Today's Game Plan",
        "A short stack of what to do next — trades, waivers, and roster priorities for this league.",
        "dashboard.jpg",
    ),
    (
        "Trade Hub",
        "Generated trade paths with package review, partner context, and value change you can inspect.",
        "trade-share.jpg",
    ),
    (
        "Waivers",
        "Priority Adds and deeper waiver boards so you can act before the window closes.",
        "waiver-share.jpg",
    ),
    (
        "Player rankings & context",
        "Player Quick View with current value, recommendation, and the context behind the call.",
        "player-share.jpg",
    ),
    (
        "What Changed / Decision Memory",
        "Session What Changed on Free; Decision Memory adds experimental cross-session continuity when enabled.",
        "decision-memory.jpg",
    ),
    (
        "GM Targets",
        "Experimental saved players to monitor — rank, ownership, and advice without changing recommendations.",
        "dashboard-desktop.jpg",
    ),
)

WHY_DIFFERENT = (
    ("League-aware", "Advice is scoped to the league you imported."),
    ("Scoring-aware", "Reads respect your league's scoring and roster shape."),
    ("Recommendation context", "See why a move is suggested, not only a ranked name."),
    ("Current rankings", "Player context stays tied to the current ranking set."),
    ("Canonical consistency", "Trade Hub, Waivers, and PQV share one recommendation source of truth."),
    ("Decision history", "What Changed (and Decision Memory when enabled) keep priorities visible."),
)

FOUNDER_INCLUDED = (
    "Free core workflow: import, Game Plan, trade preview, Priority Adds, core roster tools.",
    "Early Access Premium depth on the same surfaces — not a separate product.",
    "Labeled experimental lanes when enabled.",
)

FOUNDER_EXPERIMENTAL = (
    "Decision Memory — cross-session GM priority history.",
    "GM Targets — saved players to monitor.",
    "Share Recommendation — branded share images for advice you can already see.",
)

TRUST_POINTS = (
    "Recommendations stay consistent across Dashboard, Trade Hub, Waivers, and PQV.",
    "Ranking and advice context are inspectable in-product — not a black-box pitch.",
    "Experimental tools are labeled; roadmap ideas are not billed as guarantees.",
)


def screenshot_path(filename: str) -> Path:
    return MARKETING_ASSET_DIR / filename


def available_screenshots() -> tuple[Path, ...]:
    return tuple(sorted(MARKETING_ASSET_DIR.glob("*.jpg")))


def _track(event: str, *, source_surface: str, once_key: str = "") -> None:
    try:
        from modules import launch_analytics

        launch_analytics.track_event(
            event,
            props=launch_analytics.build_context_props(
                st.session_state,
                route="landing",
                source_surface=source_surface,
            ),
            once_key=once_key,
            state=st.session_state,
        )
    except Exception:
        pass


PROOF_JOBS = (
    (
        "Roster decisions",
        "See what is strong, thin, and worth acting on for the roster you imported.",
    ),
    (
        "Trades",
        "Trade paths scoped to this league's teams, scoring, and roster shape.",
    ),
    (
        "Player values",
        "Current values plus the inspectable context behind the recommendation.",
    ),
    (
        "League context",
        "Standings, needs, and manager tendencies for the league you actually play in.",
    ),
)


def landing_proof_html() -> str:
    """Lightweight product proof — copy only, no football data or screenshot bytes."""

    cards = "".join(
        (
            "<article class='fgl-landing__proof-card'>"
            f"<h3>{escape(title)}</h3>"
            f"<p>{escape(body)}</p>"
            "</article>"
        )
        for title, body in PROOF_JOBS
    )
    return (
        "<section class='fgl-landing__proof' id='fgl-how-it-works' "
        "data-fgl-how-it-works='1' aria-label='How FantasyGM Lab works'>"
        "<div class='fgl-landing__kicker'>How it works</div>"
        "<h2>FantasyGM Lab analyzes the league you import</h2>"
        "<p class='fgl-landing__support'>"
        "Import a Sleeper league, then get roster, trade, value, and league reads "
        "for that team — not a generic ranking dump."
        "</p>"
        f"<div class='fgl-landing__proof-grid'>{cards}</div>"
        "</section>"
    )


def landing_hero_html() -> str:
    mark = brand_identity.mark_img_html(size_px=48, css_class="fgl-landing__mark")
    badge = brand_identity.founder_beta_badge_html(compact=True)
    return (
        "<section class='fgl-landing__hero' aria-label='FantasyGM Lab introduction'>"
        "<div class='fgl-landing__brand-row'>"
        f"{mark}"
        "<div class='fgl-landing__brand-copy'>"
        f"<div class='fgl-landing__product'>{escape(brand_identity.PRODUCT_NAME)}</div>"
        f"{badge}"
        "</div></div>"
        f"<h1 class='fgl-landing__value'>{escape(HERO_VALUE)}</h1>"
        f"<p class='fgl-landing__support'>{escape(HERO_SUPPORT)}</p>"
        f"<p class='fgl-landing__trust'>{escape(TRUST_LINE)}</p>"
        "</section>"
    )


def _list_html(items: tuple[str, ...]) -> str:
    return "<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>"


def landing_body_html(
    *,
    billing_configured: bool,
    detail: bool = False,
    include_pricing: bool = False,
) -> str:
    """Deferred detail only — cold paint keeps feature lists off the first viewport."""

    free_titles = tuple(title for title, _ in premium_page.FREE_INCLUDES)
    premium_titles = tuple(title for title, _ in premium_page.PREMIUM_INCLUDED_NOW)
    if billing_configured:
        billing_note = (
            "Secure Founder Premium checkout uses Stripe test mode. "
            "No live charge will be made. Live billing is not enabled."
        )
    else:
        billing_note = (
            "Premium checkout appears when billing is enabled for your account. "
            "Live billing is not enabled."
        )

    sections: list[str] = []
    if detail:
        what_lines = tuple(f"{title} — {body}" for title, body, _file in WHAT_IT_DOES)
        why_lines = tuple(f"{title} — {body}" for title, body in WHY_DIFFERENT)
        sections.append(
            "<section class='fgl-landing__section' id='fgl-how-it-works'>"
            "<div class='fgl-landing__kicker'>What it does</div>"
            "<h2>Front-office tools for the league you manage</h2>"
            f"{_list_html(what_lines)}"
            "</section>"
            "<section class='fgl-landing__section'>"
            "<div class='fgl-landing__kicker'>Why it's different</div>"
            "<h2>League-aware recommendations with inspectable context</h2>"
            f"{_list_html(why_lines)}"
            "</section>"
            "<section class='fgl-landing__section' id='fgl-founder-beta'>"
            "<div class='fgl-landing__kicker'>Founder Beta</div>"
            "<h2>Early access with clear labels</h2>"
            "<div class='fgl-landing__split'>"
            "<div><h3>What's included</h3>"
            f"{_list_html(FOUNDER_INCLUDED)}"
            "</div><div><h3>What's experimental</h3>"
            f"{_list_html(FOUNDER_EXPERIMENTAL)}"
            "<p class='fgl-landing__note'>Experimental tools do not change core recommendation generation.</p>"
            "</div></div></section>"
            "<section class='fgl-landing__section'>"
            "<div class='fgl-landing__kicker'>Trust</div>"
            "<h2>Inspectable recommendations, not hype</h2>"
            f"{_list_html(TRUST_POINTS)}"
            "</section>"
        )
    if include_pricing:
        sections.append(
            "<section class='fgl-landing__section' id='fgl-pricing'>"
            "<div class='fgl-landing__kicker'>Free vs Premium</div>"
            "<h2>Start free. Premium adds depth on the same jobs.</h2>"
            "<div class='fgl-landing__split'>"
            "<div class='fgl-landing__plan fgl-landing__plan--free'><h3>Free includes</h3>"
            f"{_list_html(free_titles)}"
            "</div>"
            "<div class='fgl-landing__plan fgl-landing__plan--premium'><h3>Included now with Premium</h3>"
            f"{_list_html(premium_titles)}"
            "<p class='fgl-landing__note'>Premium is deeper decision support on the same FantasyGM Lab surfaces — "
            "not a separate product.</p>"
            "</div></div>"
            f"<p class='fgl-landing__billing'>{escape(billing_note)}</p>"
            "</section>"
        )
    return "".join(sections)


def render_screenshot_gallery() -> None:
    """Progressive product proof — only after secondary CTA to keep cold payload light."""

    st.markdown(
        "<div class='fgl-landing__gallery-intro'>"
        "<div class='fgl-landing__kicker'>Product surfaces</div>"
        "<h2>Real FantasyGM Lab screens</h2>"
        "<p>Captured from the product UI fixtures — not marketing mockups.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    shown_files: set[str] = set()
    shown = 0
    for title, body, filename in WHAT_IT_DOES:
        path = screenshot_path(filename)
        if not path.exists() or filename in shown_files:
            continue
        shown_files.add(filename)
        st.markdown(
            f"<div class='fgl-landing__shot-caption'><strong>{escape(title)}</strong>"
            f" — {escape(body)}</div>",
            unsafe_allow_html=True,
        )
        st.image(str(path), use_container_width=True)
        shown += 1
    if shown == 0:
        st.caption("Product screenshots will appear here once the marketing asset pack is generated.")


def render_marketing_landing() -> dict[str, bool]:
    """Cold funnel head: hero, CTAs, and lightweight proof before import.

    Screenshot bytes stay behind the secondary CTA. Pricing stays deferred.
    """

    # Landing-only CSS — keep it out of global APP_CSS so authenticated protobuf stays flat.
    st.markdown(f"<style>{MARKETING_LANDING_CSS}</style>", unsafe_allow_html=True)
    st.markdown(
        "<div class='fgl-landing' data-fgl-landing='1'>"
        f"{landing_hero_html()}"
        "</div>",
        unsafe_allow_html=True,
    )

    # Default guest so the next visible job is import — account stays one tap away.
    if not str(st.session_state.get("launch_auth_mode") or "").strip():
        st.session_state["launch_auth_mode"] = "guest"

    cta1, cta2 = st.columns(2)
    actions = {"primary": False, "secondary": False, "pricing": False}
    with cta1:
        if st.button(
            PRIMARY_CTA_LABEL,
            key="landing_primary_cta",
            type="primary",
            use_container_width=True,
        ):
            actions["primary"] = True
            st.session_state["landing_focus"] = "get_started"
            st.session_state["launch_auth_mode"] = "guest"
            _track("primary_cta_clicked", source_surface="landing_hero", once_key="")
    with cta2:
        if st.button(
            SECONDARY_CTA_LABEL,
            key="landing_secondary_cta",
            use_container_width=True,
        ):
            actions["secondary"] = True
            st.session_state["landing_focus"] = "how_it_works"
            st.session_state["landing_show_screenshots"] = True
            _track("secondary_cta_clicked", source_surface="landing_hero", once_key="")

    st.markdown(
        "<div class='fgl-landing' data-fgl-landing='1'>"
        f"{landing_proof_html()}"
        "</div>",
        unsafe_allow_html=True,
    )
    if st.session_state.get("landing_show_screenshots"):
        render_screenshot_gallery()
        st.session_state["_landing_gallery_rendered"] = True

    # Import heading below is the next-step cue — no duplicate "Next" banner.
    return actions


def render_marketing_landing_deferred() -> dict[str, bool]:
    """Pricing + detail + gallery — after account/import so cold path stays an onboarding funnel."""

    billing = stripe_billing.load_stripe_config(secrets=st.secrets)
    actions = {"primary": False, "secondary": False, "pricing": False}

    focus = _safe_focus_key(st.session_state.get("landing_focus"))
    detail = bool(
        st.session_state.get("landing_show_screenshots") or focus in {"how_it_works", "pricing"}
    )
    include_pricing = detail or focus == "pricing"
    show_controls = True

    st.markdown(
        "<div class='fgl-landing fgl-landing--deferred' data-fgl-landing-deferred='1'>"
        "<section class='fgl-landing__section fgl-landing__section--deferred'>"
        "<div class='fgl-landing__kicker'>Optional</div>"
        "<h2>Product details &amp; pricing</h2>"
        "<p class='fgl-landing__support'>"
        "Import first if you are ready. Open details only when you want them."
        "</p>"
        "</section>"
        "</div>",
        unsafe_allow_html=True,
    )
    if show_controls and st.button(
        PRICING_CTA_LABEL, key="landing_pricing_cta", use_container_width=False
    ):
        actions["pricing"] = True
        st.session_state["landing_focus"] = "pricing"
        st.session_state["landing_show_screenshots"] = True
        _track("pricing_viewed", source_surface="landing_pricing", once_key="session")
        detail = True
        include_pricing = True
        focus = "pricing"

    deferred = landing_body_html(
        billing_configured=billing.configured,
        detail=detail,
        include_pricing=include_pricing,
    )
    if deferred:
        st.markdown(
            "<div class='fgl-landing' data-fgl-landing='1'>"
            f"{deferred}"
            "</div>",
            unsafe_allow_html=True,
        )

    if (
        st.session_state.get("landing_show_screenshots")
        and focus == "how_it_works"
        and not st.session_state.get("_landing_gallery_rendered")
    ):
        render_screenshot_gallery()
        st.session_state["_landing_gallery_rendered"] = True
    return actions


def _safe_focus_key(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return text if text in {"get_started", "how_it_works", "pricing"} else ""


def _safe_focus(value: object) -> str:
    return {
        "get_started": "import your league below",
        "how_it_works": "product proof is on this page, before import",
        "pricing": "Free vs Premium appears below after import",
    }.get(_safe_focus_key(value), "")
