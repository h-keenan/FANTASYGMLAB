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

# Application welcome (Streamlit). Static marketing site may keep PRIMARY_CTA_LABEL.
APP_HERO_STATEMENT = "Dynasty decisions, built around your league."
APP_HERO_SUPPORT = (
    "Import your Sleeper league for roster, trade, waiver, and player "
    "recommendations based on your actual league."
)
APP_PRIMARY_CTA_LABEL = "Import Sleeper League"
GUEST_PATH_NOTE = (
    "No account is required to import a Sleeper league. Sign in only if you "
    "want to save and restore leagues on a later visit."
)
SIGNED_IN_PATH_NOTE = (
    "Sign in to save leagues and preferences to your account so they can restore "
    "on a later visit when this browser still has your session."
)
UNSIGNED_PERSISTENCE_NOTE = (
    "Using FantasyGM without an account. Sign in to save and restore your leagues."
)
SIGNED_OUT_ENTRY_KEY = "signed_out_entry"
WELCOME_FLOW_STATES = (
    "welcome",
    "import",
    "sign_in",
    "create_account",
    "authenticated",
)

# Concise value proposition — grounded in PRODUCT_TAGLINE, not a new claim.
HERO_VALUE = "League-aware recommendations for dynasty managers."
HERO_SUPPORT = (
    "Import a Sleeper league, then work trades, waivers, and roster decisions "
    "with a clear next move."
)
TRUST_LINE = "No account required to try it · Sleeper supported"

PRIMARY_CTA_LABEL = "Import your league"
SECONDARY_CTA_LABEL = "Sign in"
GUEST_CTA_LABEL = "Continue as guest"

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


HOW_IT_WORKS_CTA_LABEL = "See how it works"
PRICING_CTA_LABEL = "Compare Free & Premium"

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
        "Player values & waivers",
        "Current values plus inspectable context when the waiver window is open.",
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


def _migrate_signed_out_entry(state: dict) -> str:
    """Collapse legacy focus/auth-mode flags into one signed-out entry."""

    current = str(state.get(SIGNED_OUT_ENTRY_KEY) or "").strip()
    if current in {"welcome", "import", "sign_in", "create_account"}:
        return current
    if str(state.get("selected_league_id") or "").strip():
        return "welcome"
    form = str(state.get("launch_account_form") or "").strip().lower()
    if form == "create":
        return "create_account"
    if form == "signin":
        return "sign_in"
    focus = str(state.get("landing_focus") or "").strip()
    if focus == "sign_in":
        return "sign_in"
    if focus in {"get_started", "guest_import"}:
        return "import"
    mode = str(state.get("launch_auth_mode") or "").strip().lower()
    if mode == "account" and form != "create":
        return "sign_in"
    leagues = state.get("leagues_for_user")
    if isinstance(leagues, list) and leagues:
        return "import"
    if state.get("league_lookup_attempted"):
        return "import"
    platform = str(state.get("league_import_platform") or "").strip()
    if platform and platform != "Sleeper":
        return "import"
    return "welcome"


def welcome_flow_state(session_state: object) -> str:
    """Canonical signed-out owner: welcome | import | sign_in | create_account.

    Authenticated is derived from auth/session truth, not a masquerading
    signed-out UI state. Unsigned import is the former guest path.
    """

    state = session_state if isinstance(session_state, dict) else {}
    try:
        from modules import auth_supabase

        if auth_supabase.session_is_signed_in(state) or auth_supabase.current_user_id(state):
            return "authenticated"
        if auth_supabase.is_pending_email_confirmation(state):
            return "sign_in"
    except Exception:
        pass
    resolved = _migrate_signed_out_entry(state)
    if isinstance(session_state, dict) and str(state.get(SIGNED_OUT_ENTRY_KEY) or "").strip() != resolved:
        if resolved in {"welcome", "import", "sign_in", "create_account"}:
            state[SIGNED_OUT_ENTRY_KEY] = resolved
    return resolved


def set_signed_out_entry(session_state: object, entry: str) -> str:
    if not isinstance(session_state, dict):
        return "welcome"
    resolved = str(entry or "welcome").strip()
    if resolved not in {"welcome", "import", "sign_in", "create_account"}:
        resolved = "welcome"
    session_state[SIGNED_OUT_ENTRY_KEY] = resolved
    if resolved == "welcome":
        session_state.pop("landing_focus", None)
        session_state.pop("launch_account_form", None)
        session_state.pop("launch_auth_mode", None)
    elif resolved == "import":
        session_state["landing_focus"] = "get_started"
        session_state.pop("launch_account_form", None)
        session_state.pop("launch_auth_mode", None)
    elif resolved == "sign_in":
        session_state["landing_focus"] = "sign_in"
        session_state["launch_auth_mode"] = "account"
        session_state["launch_account_form"] = "signin"
    else:
        session_state["landing_focus"] = "sign_in"
        session_state["launch_auth_mode"] = "account"
        session_state["launch_account_form"] = "create"
    return resolved


def reset_welcome_flow(session_state: object) -> None:
    if not isinstance(session_state, dict):
        return
    session_state.pop(SIGNED_OUT_ENTRY_KEY, None)
    session_state.pop("landing_focus", None)
    session_state.pop("launch_account_form", None)
    session_state.pop("launch_auth_mode", None)


def welcome_import_open(session_state: object) -> bool:
    """True after Import is chosen, or when an authenticated user still needs a league."""

    flow = welcome_flow_state(session_state)
    return flow in {"import", "authenticated"}


def landing_capability_preview_html() -> str:
    """Compact welcome preview — never between a selected action and its form."""

    items = "".join(
        (
            "<li class='fgl-landing__preview-item'>"
            f"<strong>{escape(title)}</strong>"
            f"<span>{escape(body)}</span>"
            "</li>"
        )
        for title, body in PROOF_JOBS
    )
    return (
        "<ul class='fgl-landing__preview' aria-label='What you can do after import'>"
        f"{items}"
        "</ul>"
    )


def landing_composition_html() -> str:
    """Backward-compatible alias for the compact capability preview."""

    return landing_capability_preview_html()


def landing_hero_html(*, compact: bool = False) -> str:
    mark = brand_identity.mark_img_html(size_px=36 if compact else 40, css_class="fgl-landing__mark")
    badge = brand_identity.founder_beta_badge_html(compact=True)
    if compact:
        return (
            "<section class='fgl-landing__hero fgl-landing__hero--compact' "
            "aria-label='FantasyGM Lab'>"
            "<div class='fgl-landing__brand-row'>"
            f"{mark}"
            "<div class='fgl-landing__brand-copy'>"
            f"<div class='fgl-landing__product'>{escape(brand_identity.PRODUCT_NAME)}</div>"
            f"{badge}"
            "</div></div>"
            "</section>"
        )
    return (
        "<section class='fgl-landing__hero' aria-label='FantasyGM Lab introduction'>"
        "<div class='fgl-landing__brand-row'>"
        f"{mark}"
        "<div class='fgl-landing__brand-copy'>"
        f"<div class='fgl-landing__product'>{escape(brand_identity.PRODUCT_NAME)}</div>"
        f"{badge}"
        "</div></div>"
        "<div class='fgl-landing__hero-grid'>"
        "<div class='fgl-landing__hero-copy'>"
        f"<h1 class='fgl-landing__value'>{escape(APP_HERO_STATEMENT)}</h1>"
        f"<p class='fgl-landing__support'>{escape(APP_HERO_SUPPORT)}</p>"
        "</div>"
        "<div class='fgl-landing__hero-actions' aria-hidden='true'></div>"
        "</div>"
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
    """State-driven signed-out entry. No provider I/O."""

    st.markdown(f"<style>{MARKETING_LANDING_CSS}</style>", unsafe_allow_html=True)
    flow = welcome_flow_state(st.session_state)
    st.session_state["_welcome_hero_signin_rendered"] = flow == "welcome"

    actions = {"primary": False, "secondary": False, "guest": False, "pricing": False, "back": False}
    compact_header = flow in {"import", "sign_in", "create_account"}
    st.markdown(
        "<div class='fgl-landing' data-fgl-landing='1' "
        f"data-fgl-welcome-flow='{escape(flow)}'>"
        f"{landing_hero_html(compact=compact_header)}"
        "</div>",
        unsafe_allow_html=True,
    )
    if compact_header:
        if st.button("Back", key="landing_back_cta", use_container_width=False):
            actions["back"] = True
            reset_welcome_flow(st.session_state)
            st.rerun()
        return actions

    if st.button(
        APP_PRIMARY_CTA_LABEL,
        key="landing_primary_cta",
        type="primary",
        use_container_width=True,
    ):
        actions["primary"] = True
        set_signed_out_entry(st.session_state, "import")
        _track("primary_cta_clicked", source_surface="landing_hero", once_key="")
        st.rerun()
    if st.button(
        SECONDARY_CTA_LABEL,
        key="landing_secondary_cta",
        type="secondary",
        use_container_width=True,
    ):
        actions["secondary"] = True
        set_signed_out_entry(st.session_state, "sign_in")
        _track("secondary_cta_clicked", source_surface="landing_hero", once_key="")
        st.rerun()
    st.markdown(
        f"<p class='fgl-landing__trust'>{escape(TRUST_LINE)}</p>",
        unsafe_allow_html=True,
    )
    return actions


def auth_pending_owns_entry() -> bool:
    try:
        from modules import auth_supabase

        return bool(auth_supabase.is_pending_email_confirmation(st.session_state))
    except Exception:
        return False


def render_marketing_landing_deferred() -> dict[str, bool]:
    """Compact supporting copy — not a product brochure."""

    billing = stripe_billing.load_stripe_config(secrets=st.secrets)
    actions = {"primary": False, "secondary": False, "pricing": False}
    focus = _safe_focus_key(st.session_state.get("landing_focus"))
    include_pricing = focus == "pricing" or bool(st.session_state.get("landing_show_pricing"))

    st.markdown(
        "<div class='fgl-landing fgl-landing--deferred' data-fgl-landing-deferred='1'>"
        f"{landing_capability_preview_html()}"
        "</div>",
        unsafe_allow_html=True,
    )
    if st.button(
        PRICING_CTA_LABEL, key="landing_pricing_cta", use_container_width=False
    ):
        actions["pricing"] = True
        st.session_state["landing_focus"] = "pricing"
        st.session_state["landing_show_pricing"] = True
        _track("pricing_viewed", source_surface="landing_pricing", once_key="session")
        include_pricing = True

    deferred = landing_body_html(
        billing_configured=billing.configured,
        detail=False,
        include_pricing=include_pricing,
    )
    if deferred:
        st.markdown(
            "<div class='fgl-landing' data-fgl-landing='1'>"
            f"{deferred}"
            "</div>",
            unsafe_allow_html=True,
        )
    return actions


def _safe_focus_key(value: object) -> str:
    text = "" if value is None else str(value).strip()
    return text if text in {
        "get_started",
        "guest_import",
        "how_it_works",
        "pricing",
        "sign_in",
    } else ""


def _safe_focus(value: object) -> str:
    return {
        "get_started": "import your league below",
        "how_it_works": "product proof is on this page, before import",
        "pricing": "Free vs Premium appears below after import",
    }.get(_safe_focus_key(value), "")
