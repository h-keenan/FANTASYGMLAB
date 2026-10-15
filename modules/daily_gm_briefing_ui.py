"""Streamlit presentation for Today's Game Plan."""

from __future__ import annotations

import re
from html import escape
from typing import Callable
from collections.abc import Mapping

import streamlit as st

from modules import daily_gm_briefing as briefing_mod
from modules import compact_fantasy_assets
from modules import ui_primitives
from modules.html_rendering import inject_global_styles, render_html_fragment
from modules.semantic_glyphs import glyph_html
from modules.trade_visual_language import priority_tier_html


# Scoped to Dashboard Game Plan renders — keep off the global cold-path CSS budget.
DAILY_GM_BRIEFING_CSS = """
<style>
.dg-daily-briefing-quiet{display:flex;flex-direction:column;gap:var(--space-2xs)}
.dg-daily-briefing-quiet strong{color:var(--color-success);font:var(--font-card-title)}
.dg-daily-briefing-quiet span{color:var(--color-text-secondary);font:var(--font-body);max-width:42rem}
.dg-game-plan-lede{color:var(--color-text-secondary);font:var(--type-caption-emphasis);margin:0;text-align:left}
.dg-game-plan-utility{align-items:center;color:var(--color-text-muted);display:flex;font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);margin:0;min-height:var(--touch-target-min);text-align:left}
div[class*="st-key-"][class*="_lede"] [data-testid="stCaptionContainer"],div[class*="st-key-"][class*="_lede"] p{color:var(--color-text-secondary);font:var(--type-caption-emphasis);margin:0}
div[class*="st-key-"][class*="_utility"] [data-testid="stCaptionContainer"],div[class*="st-key-"][class*="_utility"] p{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);margin:0}
.dg-game-plan-card{background:var(--color-surface-primary);border:var(--border-width-default) solid var(--color-border);display:flex;flex-direction:column;gap:var(--space-sm);height:auto;min-width:0;padding:var(--space-sm)}
.dg-game-plan-card-primary{background:var(--color-surface-raised);border:var(--border-width-semantic) solid var(--color-accent)}
.dg-gp-opponent{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);margin-top:calc(-1 * var(--space-2xs))}
/* Top Priority card only (mobile Next Move parity): the opponent username
   reads as a card-title-weight name, not a muted caption — scoped to
   .dg-game-plan-card-primary so every other dg-gp-opponent context (none
   today, but the base rule above stays the safe default) is unaffected. */
.dg-game-plan-card-primary .dg-gp-opponent{color:var(--color-text-primary);font:var(--font-card-title);letter-spacing:normal;margin-top:0;text-transform:none}
.dg-gp-priority-icon{align-items:center;color:var(--color-accent);display:inline-flex;flex:0 0 auto;height:1rem;width:1rem}
.dg-gp-priority-icon svg{display:block;height:100%;width:100%}
.dg-gp-kind-pill{background:var(--color-surface-secondary);border:var(--border-width-default) solid var(--color-border-strong);border-radius:var(--radius-pill);padding:2px var(--space-sm)}
/* Every Game Plan card's ring-opted avatars (Top Priority give/get, Top
   Waiver Opportunity's single player, League Movement's give/get) use one
   uniform accent ring (not a per-player tier color) — overrides the custom
   property player_tier_identity.portrait_frame_classes()'s shared
   dg-tier-frame--ring box-shadow reads, same mechanism My Team/Trade Hub
   use for tier rings, just pinned to a single color here. Scoped to
   .dg-game-plan-card (the shared base class every card carries, not just
   .dg-game-plan-card-primary) so the three cards on the same Dashboard
   screen read as one consistent design language instead of one polished
   card next to two plain ones. */
/* Reference ring reads as a vivid lime-green, not the card's cyan accent —
   --color-success is the closest existing semantic green token (no new
   color invented). Scoped to the ringed avatar itself (not every avatar in
   the card) so it only ever touches the portraits that actually opted into
   avatar_ring=True. Also circles the avatar here only: every avatar
   site-wide stays square (.dg-compact-asset-avatar has no border-radius
   outside this scope) — that's a bigger decision the product owner hasn't
   made. overflow:hidden on .dg-compact-asset-avatar already clips the
   absolutely-positioned, object-fit:cover headshot cleanly to the circle. */
.dg-game-plan-card .dg-compact-asset-avatar.dg-tier-frame--ring{--dg-tier-a:var(--color-success);border-radius:50%;box-shadow:0 0 0 3px var(--dg-tier-a),0 0 4px 0 color-mix(in srgb,var(--dg-tier-a) 30%,transparent)}
/* Value-as-pill: value_edge_html()'s own markup is reused verbatim — this
   only hides the directional triangle/magnitude bar and fills the number
   as a chip, color-keyed off the polarity data attribute it already emits. */
.dg-game-plan-card-primary [data-tvl-edge]{justify-content:space-between;width:100%}
.dg-game-plan-card-primary [data-tvl-edge] .tvl-edge-dir,
.dg-game-plan-card-primary [data-tvl-edge] .tvl-edge-mark{display:none}
.dg-game-plan-card-primary [data-tvl-edge] .tvl-edge-num{border-radius:var(--radius-pill);display:inline-block;padding:2px var(--space-sm)}
.dg-game-plan-card-primary [data-tvl-edge=neg] .tvl-edge-num{background:color-mix(in srgb,var(--color-danger) 20%,transparent)}
.dg-game-plan-card-primary [data-tvl-edge=pos] .tvl-edge-num{background:color-mix(in srgb,var(--color-success) 20%,transparent)}
.dg-game-plan-card-primary [data-tvl-edge=even] .tvl-edge-num{background:var(--color-surface-secondary)}
.dg-daily-briefing-kicker-row{align-items:center;display:flex;flex-wrap:wrap;gap:var(--space-xs);justify-content:space-between;min-width:0}
.dg-daily-briefing-kicker{align-items:center;color:var(--color-text-primary);display:inline-flex;font:var(--font-card-title);gap:var(--space-2xs);letter-spacing:var(--letter-spacing-badge);opacity:1;text-transform:uppercase}
.dg-game-plan-card{opacity:1}
.dg-daily-briefing-kind{align-items:center;color:var(--color-text-secondary);display:inline-flex;font:var(--type-supporting-metadata);gap:var(--space-xs);letter-spacing:var(--letter-spacing-badge);opacity:1;text-transform:uppercase}
.dg-daily-briefing-kind .dg-glyph{opacity:1}
.dg-daily-briefing-kind .dg-glyph{margin-right:0}
.dg-daily-briefing-headline{color:var(--color-text-primary);font:var(--font-card-title)}
.dg-game-plan-card-primary .dg-daily-briefing-headline{font:var(--type-section-title)}
.dg-daily-briefing-reason{color:var(--color-text-secondary);font:var(--type-caption-emphasis);max-width:40rem}
.dg-daily-briefing-rank{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge)}
.dg-game-plan-card .dg-compact-asset--standard{--size-asset-standard:3.25rem}
div[class*="st-key-"][class*="_header"]{align-items:flex-start;display:flex;flex-direction:column;gap:var(--space-2xs);min-width:0;width:100%}
div[class*="st-key-"][class*="_header"] .dg-ui-section-header{margin:0!important;padding:0 0 var(--space-2xs)!important;width:100%}
div[class*="st-key-"][class*="_header"] .dg-ui-section-title{margin:0!important;text-align:left}
div[class*="st-key-"][class*="_lede"],div[class*="st-key-"][class*="_utility"]{flex:0 0 auto;height:auto;min-width:0;overflow:visible;width:auto}
div[class*="st-key-"][class*="_status_row"] [data-testid="stVerticalBlock"]{align-items:center;display:flex;flex-direction:row;flex-wrap:wrap;gap:var(--space-xs);min-width:0;width:100%}
div[class*="st-key-"][class*="_status_row"] [data-testid="stElementContainer"],
div[class*="st-key-"][class*="_status_row"] [data-testid="element-container"]{flex:0 0 auto;max-width:100%;min-width:0;width:auto!important}
div[class*="st-key-"][class*="_refresh_row"]{display:block;flex:0 0 auto;margin:0;max-width:100%;min-width:0;overflow:visible;width:auto}
div[class*="st-key-"][class*="_refresh_row"] [data-testid="stElementContainer"]{height:auto;overflow:visible}
div[class*="_refresh_recommendations"]{display:block;justify-content:flex-start;margin:0;max-width:100%;min-width:0}
div[class*="_refresh_recommendations"] button{max-width:100%;min-width:0;white-space:nowrap!important;width:auto!important}
div[class*="st-key-"][class*="_cards"]{align-items:start;display:grid;gap:var(--space-sm);grid-template-columns:minmax(0,1fr)}
div[class*="st-key-"][class*="_card_"] [data-testid=stButton]>button{width:100%}
div[class*="st-key-"][class*="dg_cta_"]{margin:0}
/* Outlined, not filled — transparent fill, accent border + text. */
div[class*="st-key-"][class*="dg_cta_primary"] [data-testid=stButton]>button{background:transparent!important;border:var(--border-width-semantic) solid var(--color-accent)!important;color:var(--color-accent)!important;font-weight:var(--font-weight-button)}
div[class*="st-key-"][class*="auto_strategy_help"] button,div[class*="st-key-auto_strategy_help"] button{min-height:var(--touch-target-min)!important;width:auto!important;white-space:nowrap!important}
@media (min-width:1024px){
.dg-game-plan-card{padding:var(--space-md)}
div[class*="st-key-"][class*="_cards"]{align-items:start;grid-template-columns:minmax(0,1.7fr) minmax(0,1fr)}
div[class*="st-key-"][class*="_cards"]:not(:has([class*="_card_2"])){grid-template-columns:minmax(0,1fr)}
div[class*="st-key-"][class*="_card_1"]{grid-column:1;grid-row:auto}
div[class*="st-key-"][class*="_cards"]:has([class*="_card_3"]) [class*="_card_1"]{grid-row:1 / span 2}
div[class*="_refresh_recommendations"]{justify-content:flex-start}
}
@media (max-width:1023px){
div[class*="_refresh_recommendations"]{display:block;width:auto}
div[class*="_refresh_recommendations"] button{min-height:var(--touch-target-min)!important;width:auto!important}
}
@media (max-width:760px){
div[class*="st-key-"][class*="_cards"]{grid-template-columns:minmax(0,1fr)}
div[class*="st-key-"][class*="_card_1"]{grid-column:auto;grid-row:auto}
.dg-daily-briefing-reason{max-width:100%}
.dg-game-plan-card-primary .dg-daily-briefing-headline{font:var(--font-card-title)}
}
</style>
"""

# Top Priority kicker-only lightning bolt. Deliberately NOT a semantic_glyphs
# concept: that registry is pinned to a small, reusable 8-12 icon vocabulary
# (tests/test_semantic_glyphs.py), and this bolt is a single-surface kicker
# mark, not a reusable destination/kind icon — same stroke style (currentColor,
# square linecap/miter) as the shared set, scoped locally instead.
_PRIORITY_ICON_HTML = (
    "<span class='dg-gp-priority-icon' aria-hidden='true'>"
    "<svg viewBox='0 0 24 24' focusable='false'>"
    "<path fill='none' stroke='currentColor' stroke-width='1.75' "
    "stroke-linecap='square' stroke-linejoin='miter' "
    "d='M13 3L6 13h5l-1 8 7-10h-5l1-8z'/>"
    "</svg></span>"
)

_KIND_LABELS = {
    briefing_mod.CATEGORY_TOP_PRIORITY: "",
    briefing_mod.CATEGORY_WATCH: "Watch",
    briefing_mod.CATEGORY_WAIVER: "Waiver",
    briefing_mod.CATEGORY_LEAGUE_MOVEMENT: "League",
}


def _category_kicker(category: str) -> str:
    return escape(briefing_mod.CATEGORY_LABELS.get(category, category.replace("_", " ").title()))


def _kind_badge(item: briefing_mod.DailyBriefingItem) -> str:
    if item.destination == "trade_hub" or (
        item.category == briefing_mod.CATEGORY_TOP_PRIORITY
        and item.destination == "trade_hub"
    ):
        return "Trade"
    if item.destination == "waivers" or item.category == briefing_mod.CATEGORY_WAIVER:
        return "Waiver"
    if item.category == briefing_mod.CATEGORY_WATCH:
        return "Watch"
    if item.destination == "my_team":
        return "Roster"
    return _KIND_LABELS.get(item.category, "")


def _cta_label(item: briefing_mod.DailyBriefingItem, *, is_primary: bool) -> str:
    if item.destination == "trade_hub":
        return "Review in Trade Hub" if is_primary else "Open Trade Hub"
    if item.destination == "waivers":
        return "Open Waivers"
    if item.destination == "my_team":
        return "Open My Team"
    if item.destination == "rankings":
        return "Open League Rankings"
    return "Open workflow"


def _watch_headline(item: briefing_mod.DailyBriefingItem) -> str:
    headline = item.headline.strip()
    headline = re.sub(r"(?i)injured starters", "starters need attention", headline)
    headline = re.sub(r"(?i)injured starter", "starter needs attention", headline)
    return headline


def _presentation_dict(item: briefing_mod.DailyBriefingItem) -> dict:
    presentation = item.presentation
    if isinstance(presentation, Mapping) and presentation:
        return dict(presentation)
    return {}


def _has_trade_visual(item: briefing_mod.DailyBriefingItem) -> bool:
    presentation = _presentation_dict(item)
    send = presentation.get("send") or []
    receive = presentation.get("receive") or []
    return bool(send or receive)


def _has_player_visual(item: briefing_mod.DailyBriefingItem) -> bool:
    presentation = _presentation_dict(item)
    if item.category == briefing_mod.CATEGORY_WATCH:
        players = presentation.get("players") or []
        return bool(players)
    player = presentation.get("player")
    return isinstance(player, dict) and bool(player)


def _should_show_headline(item: briefing_mod.DailyBriefingItem) -> bool:
    if item.category == briefing_mod.CATEGORY_WATCH:
        return True
    if _has_trade_visual(item) or (
        item.category == briefing_mod.CATEGORY_WAIVER and _has_player_visual(item)
    ):
        return False
    if item.destination in {"trade_hub", "waivers"} and (
        _has_trade_visual(item) or _has_player_visual(item)
    ):
        return False
    return bool(item.headline)


def _should_show_reason(item: briefing_mod.DailyBriefingItem, visual_html: str) -> bool:
    reason = (item.reason or "").strip()
    if not reason:
        return False
    if item.category == briefing_mod.CATEGORY_WATCH and visual_html:
        # Existing injury notes are pipe-delimited identity dumps once portraits exist.
        if " | " in reason or " - " in reason:
            return False
    if reason.casefold() == (item.headline or "").casefold():
        return False
    return True


def render_todays_game_plan(
    plan: briefing_mod.DailyGmBriefing,
    *,
    open_item: Callable[[briefing_mod.DailyBriefingItem], None],
    key_prefix: str = "daily_gm_briefing",
    render_tappable_player_html: Callable[..., str] | None = None,
    open_player_quick_view: Callable[..., None] | None = None,
    render_interactive_html: Callable[..., dict] | None = None,
) -> None:
    """Render the compact executive morning brief."""

    inject_global_styles(DAILY_GM_BRIEFING_CSS)
    inject_global_styles(f"<style>{compact_fantasy_assets.COMPACT_FANTASY_ASSET_CSS}</style>")
    from modules import render_ownership

    render_ownership.claim(st.session_state, render_ownership.OWNER_DASHBOARD_HERO)
    age_label = ""
    try:
        from modules import game_plan_package

        package = st.session_state.get(game_plan_package.PACKAGE_KEY)
        age_label = game_plan_package.format_package_age_label(
            package if isinstance(package, dict) else None
        )
    except Exception:
        age_label = ""
    with st.container(key=f"{key_prefix}_header"):
        ui_primitives.render_section_header("Today's Game Plan", weight="primary")
        with st.container(key=f"{key_prefix}_lede"):
            st.caption("Your highest-impact moves right now.")
        with st.container(key=f"{key_prefix}_status_row"):
            if age_label:
                with st.container(key=f"{key_prefix}_utility"):
                    st.caption(age_label)
            try:
                from modules import game_plan_package

                if st.session_state.get("dg_show_dev_diagnostics"):
                    status = str(
                        st.session_state.get(game_plan_package.LAST_CACHE_STATUS_KEY) or ""
                    ).upper() or "UNKNOWN"
                    reason = str(
                        st.session_state.get(game_plan_package.LAST_MISS_REASON_KEY) or ""
                    )
                    sig = str(st.session_state.get(game_plan_package.PACKAGE_SIG_KEY) or "")[:12]
                    st.caption(
                        f"recommendation: {status}"
                        + (f" · {reason}" if reason else "")
                        + (f" · fp {sig}" if sig else "")
                    )
            except Exception:
                pass
            with st.container(key=f"{key_prefix}_refresh_row"):
                try:
                    from modules import game_plan_package

                    render_ownership.claim(
                        st.session_state, render_ownership.OWNER_REFRESH
                    )
                    if st.button(
                        "Refresh",
                        key=f"{key_prefix}_refresh_recommendations",
                        type="tertiary",
                        use_container_width=False,
                    ):
                        game_plan_package.invalidate_recommendation_packages(st.session_state)
                        st.rerun()
                except Exception:
                    pass

    if plan.quiet:
        render_html_fragment(
            "<div class='dg-daily-briefing-quiet' role='status'>"
            "<strong>No urgent roster issues right now.</strong>"
            f"<span>{escape(plan.quiet_reason)}</span>"
            "</div>"
        )
        return

    with st.container(key=f"{key_prefix}_cards"):
        for index, item in enumerate(plan.items, start=1):
            rank_html = ""
            if item.player_rank_context:
                rank_html = (
                    f"<div class='dg-daily-briefing-rank'>{escape(item.player_rank_context)}</div>"
                )
            is_primary = item.category == briefing_mod.CATEGORY_TOP_PRIORITY or index == 1
            card_class = "dg-game-plan-card"
            if is_primary:
                card_class += " dg-game-plan-card-primary"
            visual_html = _card_visual_html(item)
            headline = (
                _watch_headline(item)
                if item.category == briefing_mod.CATEGORY_WATCH
                else item.headline
            )
            headline_html = ""
            if _should_show_headline(item):
                headline_html = (
                    f"<div class='dg-daily-briefing-headline'>{escape(headline)}</div>"
                )
            reason_html = ""
            if _should_show_reason(item, visual_html):
                reason_html = (
                    f"<div class='dg-daily-briefing-reason'>{escape(item.reason)}</div>"
                )
            is_top_priority_trade = (
                item.category == briefing_mod.CATEGORY_TOP_PRIORITY and _has_trade_visual(item)
            )
            kind = _kind_badge(item)
            kind_html = ""
            if kind:
                kind_concept = {
                    "Trade": "trade",
                    "Waiver": "waiver",
                    "Roster": "roster",
                    "Watch": "health",
                    "League": "insights",
                }.get(kind, "more")
                kind_class = "dg-daily-briefing-kind"
                if is_top_priority_trade:
                    kind_class += " dg-gp-kind-pill"
                kind_html = (
                    f"<div class='{kind_class}'>"
                    f"{glyph_html(kind_concept, size='kicker')}"
                    f"<span>{escape(kind)}</span></div>"
                )
            kicker_html = _category_kicker(item.category)
            if item.category == briefing_mod.CATEGORY_WAIVER:
                kicker_raw = str(item.supporting_context or "").strip()
                if kicker_raw:
                    kicker_html = escape(kicker_raw)
            # Lightning-bolt kicker icon + opponent subtitle — only the real
            # Top Priority trade card (mobile Next Move reference); every
            # other kicker/kind combination is unchanged.
            if is_top_priority_trade:
                kicker_html = _PRIORITY_ICON_HTML + kicker_html
            opponent_html = ""
            if is_top_priority_trade:
                opponent_name = (headline or "").strip()
                if opponent_name:
                    opponent_html = (
                        f"<div class='dg-gp-opponent'>{escape(opponent_name)}</div>"
                    )
            cta = _cta_label(item, is_primary=is_primary)
            tier = "primary" if is_primary else "secondary"
            # Real, already-computed tier word for a Next Move priority-ladder
            # tile (roster need > injury pressure > future risk > upgrade
            # opportunity) — empty for every other tile. Not a fabricated
            # confidence score; see modules.dashboard_engine.NEED_TIER_LABELS.
            tier_badge_html = priority_tier_html(item.tier_label)
            with st.container(key=f"{key_prefix}_card_{index}"):
                card_html = (
                    f"<div class='{card_class}'>"
                    "<div class='dg-daily-briefing-kicker-row'>"
                    f"<div class='dg-daily-briefing-kicker'>{kicker_html}</div>"
                    f"{kind_html}"
                    f"{tier_badge_html}"
                    "</div>"
                    f"{headline_html}"
                    f"{opponent_html}"
                    f"{visual_html}"
                    f"{reason_html}"
                    f"{rank_html}"
                    "</div>"
                )
                handled_whole_card = _render_card_html(
                    card_html,
                    item,
                    key_prefix=f"{key_prefix}_card_{index}",
                    render_tappable_player_html=render_tappable_player_html,
                    open_player_quick_view=open_player_quick_view,
                    render_interactive_html=render_interactive_html,
                    open_item=open_item,
                )
                if not handled_whole_card:
                    # Fallback only — real traffic always wires
                    # render_interactive_html from app.py, so the card itself
                    # is the tap target (see _render_card_html above) and
                    # this separate CTA never renders.
                    with st.container(key=f"dg_cta_{tier}_{key_prefix}_{index}"):
                        st.button(
                            cta,
                            key=f"{key_prefix}_open_{index}_{item.category}_{item.source_id[:24]}",
                            use_container_width=True,
                            on_click=open_item,
                            args=(item,),
                        )


def _trade_assets_for_item(item: briefing_mod.DailyBriefingItem) -> list[dict]:
    """Raw send_assets + receive_assets dicts for a trade-visual card.

    Same shape Trade Hub's own trade-idea cards key their tap targets off
    (modules.trade_hub_ui.render_trade_html_with_player_taps) — each dict
    carries the real player_id the rendered give/get avatar's
    data-player-id attribute already exposes (compact_fantasy_assets.
    compact_asset_html), just not previously wired to anything that
    listens for a click.
    """

    presentation = _presentation_dict(item)
    send = presentation.get("send") or []
    receive = presentation.get("receive") or []
    return [asset for asset in (list(send) + list(receive)) if isinstance(asset, dict)]


def _tap_assets_for_item(item: briefing_mod.DailyBriefingItem) -> list[dict]:
    """Every real player dict this card's visual renders a tappable chip for.

    Trade-shaped cards (Top Priority/League Movement) already route through
    `_trade_assets_for_item` above. Watch (injury alert) and Waiver
    (single-player) cards render the exact same compact_asset_html chip —
    same data-player-id markup — via `_card_visual_html`'s watch/waiver
    branches, just without a send/receive pair, so they were previously
    excluded from `_render_card_html`'s tap-grid routing entirely. This
    widens that to cover those two shapes too (coridian_, 2026-10-14: "a lot
    of things need to be tappable like power ranking, stuff like that").
    """

    assets = list(_trade_assets_for_item(item))
    presentation = _presentation_dict(item)
    if item.category == briefing_mod.CATEGORY_WATCH:
        players = presentation.get("players") or []
        assets.extend(player for player in players if isinstance(player, dict))
    else:
        player = presentation.get("player")
        if isinstance(player, dict) and player:
            assets.append(player)
    return assets


def _render_card_html(
    card_html: str,
    item: briefing_mod.DailyBriefingItem,
    *,
    key_prefix: str,
    render_tappable_player_html: Callable[..., str] | None,
    open_player_quick_view: Callable[..., None] | None,
    render_interactive_html: Callable[..., dict] | None = None,
    open_item: Callable[[briefing_mod.DailyBriefingItem], None] | None = None,
) -> bool:
    """Render one Today's Game Plan card, wiring its give/get player avatars
    to Player Quick View on tap when it has any (Top Priority and League
    Movement trade teasers — both built from game_plan_trade_visual_html/
    game_plan_top_priority_trade_html, the same two visuals GM Plan's own
    Trade Opportunities card now routes through modules.trade_hub_ui.
    render_trade_html_with_player_taps for). Only the player chips inside
    actually become tappable (TAP_DELEGATION_JS delegates on
    data-player-id) — the headline/reason text around them stays inert,
    same as every other tappable card on the site. Watch (injury alert) and
    Waiver cards get the same tap-through for their single-player/player-list
    chip (see `_tap_assets_for_item`). Falls back to a plain, non-tappable
    render when this card has no player visual at all, or the caller didn't
    wire the tap callables.

    Whole-card tap-through (coridian_, 2026-10-14): when ``render_interactive_html``
    and ``open_item`` are wired, the ENTIRE card (not just its player chips)
    also becomes a route tap target for the card's own CTA destination, same
    render pass — the caller's separate "{cta} ->" st.button underneath it is
    then dropped. Returns True when this whole-card route handling applied
    (the caller should skip its own fallback button), False otherwise.
    """

    tap_assets = _tap_assets_for_item(item)
    if render_interactive_html is not None and open_item is not None:
        from modules.trade_hub_ui import render_trade_html_with_player_taps

        render_trade_html_with_player_taps(
            card_html,
            tap_assets,
            key_prefix=f"{key_prefix}_assets",
            source_label="Today's Game Plan",
            render_tappable_player_html=render_tappable_player_html,
            open_player_quick_view=open_player_quick_view,
            render_interactive_html=render_interactive_html,
            route=f"open_{item.source_id or key_prefix}",
            route_label=f"Open {item.destination or 'workflow'}".replace("_", " ").title(),
            on_route=lambda _route, _item=item: open_item(_item),
        )
        return True
    if tap_assets and render_tappable_player_html is not None and open_player_quick_view is not None:
        from modules.trade_hub_ui import render_trade_html_with_player_taps

        clicked_player_id = render_trade_html_with_player_taps(
            card_html,
            tap_assets,
            key_prefix=f"{key_prefix}_assets",
            source_label="Today's Game Plan",
            render_tappable_player_html=render_tappable_player_html,
        )
        if clicked_player_id:
            open_player_quick_view(
                clicked_player_id,
                source_label="Today's Game Plan",
                source_note="Inspect this player from today's game plan.",
            )
        return False
    render_html_fragment(card_html)
    return False


def _card_visual_html(item: briefing_mod.DailyBriefingItem) -> str:
    presentation = _presentation_dict(item) or None
    if item.category == briefing_mod.CATEGORY_WATCH:
        players = (presentation or {}).get("players") if presentation else None
        return compact_fantasy_assets.watch_attention_html(players)
    if item.destination == "waivers" or item.category == briefing_mod.CATEGORY_WAIVER:
        player = (presentation or {}).get("player") if presentation else None
        if isinstance(player, dict) and player:
            # Same ring + colored position pill primitives as the Top
            # Priority card (position_pill=True/avatar_ring=True are the
            # general compact_asset_html opt-ins, not Top-Priority-only) —
            # single-player card, so no give/get sides, confidence bar, or
            # value pill (those stay trade-specific).
            chip = compact_fantasy_assets.compact_asset_html(
                player,
                size="standard",
                show_value=False,
                position_pill=True,
                avatar_ring=True,
            )
            return f"<div class='dg-gp-identity-row'>{chip}</div>" if chip else ""
        return ""
    if item.destination == "trade_hub" or item.category == briefing_mod.CATEGORY_TOP_PRIORITY:
        if item.category == briefing_mod.CATEGORY_TOP_PRIORITY:
            # The one reference-matched Top Priority trade teaser (mobile
            # Next Move parity: colored position pill, avatar ring, 3-segment
            # confidence bar, value pill). Any other trade_hub-destination
            # card (secondary League Movement opportunities) keeps the
            # original, separately-tested give/get visual below.
            return compact_fantasy_assets.game_plan_top_priority_trade_html(presentation)
        # League Movement: same give/get structure (it IS a trade — can
        # carry more than one asset per side), with the same ring + colored
        # position pill primitives as Top Priority's give/get portraits.
        # Deliberately keeps its own radial confidence ring and plain
        # (non-pill) value edge rather than Top Priority's segmented
        # confidence bar/value pill — those stay the primary card's
        # distinguishing, higher-emphasis treatment.
        return compact_fantasy_assets.game_plan_trade_visual_html(
            presentation, position_pill=True, avatar_ring=True
        )
    return ""
