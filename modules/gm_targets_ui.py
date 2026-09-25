"""Streamlit presentation for GM Targets."""

from __future__ import annotations

from html import escape
from typing import Any, Callable, Mapping, MutableMapping

import pandas as pd
import streamlit as st

from modules import gm_targets
from modules import html_rendering
from modules import performance
from modules import player_profile_ui
from modules import ui_primitives


GM_TARGETS_CSS = """
<style>
.dg-gm-targets-badge{color:var(--color-text-muted);font:var(--type-supporting-metadata);letter-spacing:var(--letter-spacing-badge);text-transform:uppercase}
.dg-gm-targets-shell{display:flex;flex-direction:column;gap:var(--space-sm);max-width:40rem}
/* One grouped surface with hairline row dividers per group — matches the
   dashboard/My Team Magna Carta pattern (a single bordered panel, not a
   bordered card per player). */
div[class*="st-key-dg_gm_targets_group_"]{background:var(--surface-1);border:var(--border-width-default) solid var(--border-standard);border-radius:var(--radius-panel);margin-bottom:var(--space-md);max-width:40rem;padding:var(--space-2xs) var(--space-md) var(--space-sm)}
div[class*="st-key-dg_gm_targets_group_untouchable"]{border-inline-start:var(--border-width-semantic) solid var(--color-premium)}
/* Card is a simple top row (identity + reference rank) over a stacked body
   (decision info, in priority order) — replaces the old two-column CSS grid,
   whose implicit auto-placement made "what to do" order-dependent on rank's
   markup position. Flex stacking lets render order alone express hierarchy. */
.dg-gm-target-card{border-block-end:var(--border-width-default) solid var(--color-border);display:flex;flex-direction:column;gap:var(--space-2xs);padding-block:var(--space-sm)}
.dg-gm-target-card:last-of-type{border-block-end:0}
.dg-gm-target-top{align-items:flex-start;display:flex;gap:var(--space-sm);justify-content:space-between}
.dg-gm-target-identity{align-items:center;display:flex;flex:1 1 auto;gap:var(--space-sm);min-width:0}
.dg-gm-target-body{display:flex;flex-direction:column;gap:var(--space-2xs)}
.dg-gm-target-meta{color:var(--color-text-muted);font:var(--type-supporting-metadata)}
.dg-gm-target-name{color:var(--color-text-primary);font:var(--font-card-title)}
/* Rank is reference metadata, not the decision — it sits in the top row next
   to identity but never competes with the action/why below for the
   strongest type treatment in the system. */
.dg-gm-target-rank{color:var(--color-text-secondary);flex-shrink:0;font:var(--type-caption-emphasis);font-variant-numeric:tabular-nums;text-align:right}
.dg-gm-target-status{color:var(--color-text-secondary);font:var(--type-supporting-metadata)}
/* The canonical "what to do" call — same weight as the player's name and the
   same accent (primary/interactive) color the Waivers card action row uses,
   so this is the strongest, most legible line on the card. */
.dg-gm-target-action{color:var(--color-accent);font:var(--font-card-title)}
.dg-gm-target-change{color:var(--color-text-secondary);font:var(--type-supporting-metadata)}
.dg-gm-targets-quiet{display:flex;flex-direction:column}
.dg-gm-targets-quiet strong{color:var(--color-text-muted);font:var(--font-card-title)}
.dg-gm-targets-quiet span{color:var(--color-text-secondary);font:var(--font-body);max-width:40rem}
@media (max-width:430px){.dg-gm-target-change{-webkit-box-orient:vertical;-webkit-line-clamp:2;display:-webkit-box;overflow:hidden}}
</style>
"""


def _workflow_handoff_destination(ownership: str) -> tuple[str, str] | None:
    """Map ownership status to a single core workflow — no second engines."""

    text = str(ownership or "").casefold()
    if "free agent" in text or "waiver" in text:
        return ("waivers", "Open Waivers")
    if "rostered by" in text:
        return ("trade_hub", "Open Trade Hub")
    return None


# Recommendation-clarity audit (same class of finding as mobile PR #761):
# GmTarget.source_surface already tells the story of *why* a player is on
# this list, was already fetched by enrich_target, and was never rendered —
# every card looked identical regardless of how it got here. The only two
# real callers today are render_pqv_target_control ("Player Quick View", the
# web add/remove pill wired from app.py's PQV dialog) and team_stance_ui's
# "Protect" checklist. Mirrors mobile's TARGET_ORIGIN_LABEL exactly for the
# team_stance copy so the same real backend distinction reads identically on
# both platforms. Unknown/legacy values render nothing rather than a guess.
TARGET_ORIGIN_LABELS: dict[str, str] = {
    "player_quick_view": "Added from Player Quick View",
    "team_stance": "Protected via Team Situation",
    "gm_targets": "Added from GM Targets",
}


def _target_origin_label(source_surface: str) -> str:
    return TARGET_ORIGIN_LABELS.get(str(source_surface or "").strip(), "")


def _player_row_lookup(
    df_players: pd.DataFrame | None, player_id: str
) -> dict[str, Any] | None:
    pid = gm_targets.normalize_player_id(player_id)
    if not pid or df_players is None or getattr(df_players, "empty", True):
        return None
    if "player_id" not in df_players.columns:
        return None
    matched = df_players[df_players["player_id"].astype(str) == pid]
    if matched.empty:
        return None
    return matched.iloc[0].to_dict()


def render_pqv_target_control(
    *,
    session: MutableMapping[str, Any],
    league_id: str,
    player_id: str,
    source_surface: str = "player_quick_view",
    headshot_url: str = "",
    compact: bool = False,
) -> None:
    """Canonical Add/Remove control for Player Quick View."""

    if not gm_targets.experiment_enabled():
        return
    league_key = str(league_id or "").strip()
    pid = gm_targets.normalize_player_id(player_id)
    if not league_key or not pid:
        return

    if gm_targets.can_access_targets(session):
        gm_targets.ensure_membership_cache(session, league_id=league_key)

        def _toggle_pqv_target() -> None:
            if gm_targets.is_targeted(session, league_id=league_key, player_id=pid):
                gm_targets.remove_target(
                    session, league_id=league_key, player_id=pid
                )
            else:
                gm_targets.add_target(
                    session,
                    league_id=league_key,
                    player_id=pid,
                    source_surface=source_surface,
                )

        targeted = gm_targets.is_targeted(
            session, league_id=league_key, player_id=pid
        )
        if compact:
            label = "Remove" if targeted else "GM Targets"
        else:
            label = (
                gm_targets.REMOVE_ACTION_LABEL
                if targeted
                else gm_targets.ADD_ACTION_LABEL
            )
        st.button(
            label,
            key=f"gm_targets_pqv_{league_key}_{pid}",
            use_container_width=False,
            type="secondary",
            on_click=_toggle_pqv_target,
        )
        return

    # Guests: no PQV lock spam — discovery lives on the GM Targets route only.
    return


def render_discovery_panel(*, render_premium_lock: Callable[..., None] | None) -> None:
    """Single restrained guest discovery — use on GM Targets destination only."""

    title, body = gm_targets.discovery_copy()
    html_rendering.inject_global_styles(GM_TARGETS_CSS)
    html_rendering.render_html_fragment(
        "<div class='dg-gm-targets-quiet' role='status' data-gm-targets-discovery='1'>"
        f"<strong>{escape(title)}</strong>"
        f"<span>{escape(body)}</span>"
        "</div>"
    )
    if render_premium_lock is not None:
        render_premium_lock(
            "Sign in to save GM Targets",
            "Free accounts can save a short board. Premium unlocks a full Targets list.",
            feature=gm_targets.FEATURE_LABEL,
        )


def render_gm_targets_workspace(
    *,
    session: MutableMapping[str, Any],
    league_id: str,
    roster_id: str = "",
    df_players: pd.DataFrame | None = None,
    my_roster_player_ids: list[str] | set[str] | tuple[str, ...] | None = None,
    roster_player_map: Mapping[Any, Any] | None = None,
    roster_team_names: Mapping[Any, str] | None = None,
    scoring_format: str = "",
    open_player_quick_view: Callable[..., None] | None = None,
    open_destination: Callable[[str], None] | None = None,
    cached_headshot_data_url: Callable[[str], str] | None = None,
    render_premium_lock: Callable[..., None] | None = None,
    title: str = "GM Targets",
) -> None:
    """Compact GM Targets surface — answers who/status/change/next."""

    html_rendering.inject_global_styles(GM_TARGETS_CSS)
    heading = str(title or "").strip()
    if heading:
        ui_primitives.render_section_header(heading, weight="primary")
    badge = gm_targets.EXPERIMENTAL_LABEL.strip()
    shell_badge = (
        f"<div class='dg-gm-targets-badge'>{escape(badge)}</div>" if badge else ""
    )
    html_rendering.render_html_fragment(
        "<div class='dg-gm-targets-shell'>"
        f"{shell_badge}"
        f"<p class='dg-gm-target-status'>{escape(gm_targets.SUPPORTING_COPY)}</p>"
        "</div>"
    )

    if not gm_targets.experiment_enabled():
        st.caption("GM Targets is not enabled for this environment.")
        return

    if not gm_targets.can_access_targets(session):
        if gm_targets.can_show_discovery(session):
            render_discovery_panel(render_premium_lock=render_premium_lock)
        else:
            st.caption("Sign in to use GM Targets.")
        return

    league_key = str(league_id or "").strip()
    if not league_key:
        st.info("Import a league to save GM Targets.")
        return

    with performance.time_block("gm_targets_workspace_open", category="render"):
        targets = gm_targets.fetch_targets_for_league(session, league_id=league_key)

    if not targets:
        html_rendering.render_html_fragment(
            "<div class='dg-gm-targets-quiet' role='status'>"
            "<strong>No GM Targets yet</strong>"
            "<span>Add players you're considering from Player Quick View.</span>"
            "</div>"
        )
        if open_destination is not None:
            if st.button(
                "Open Players",
                key="gm_targets_empty_open_players",
                use_container_width=True,
            ):
                open_destination("players")
        return

    owner_map = gm_targets.build_owner_map_from_roster_player_map(
        roster_player_map, roster_team_names=roster_team_names
    )
    cards: list[gm_targets.EnrichedTargetCard] = []
    with performance.time_block("gm_targets_card_enrichment", category="render"):
        for target in targets:
            row = _player_row_lookup(df_players, target.player_id)
            cards.append(
                gm_targets.enrich_target(
                    target,
                    session=session,
                    player_row=row,
                    my_roster_player_ids=my_roster_player_ids,
                    owner_by_player_id=owner_map,
                    scoring_format=scoring_format,
                    roster_id=roster_id,
                )
            )
    ordered = gm_targets.sort_enriched_targets(cards)
    cap = gm_targets.max_targets_for_session(session)
    st.caption(f"{len(ordered)} / {cap} targets saved for this league.")

    def _render_target_card(card: gm_targets.EnrichedTargetCard) -> None:
        image_url = ""
        if cached_headshot_data_url is not None:
            try:
                image_url = cached_headshot_data_url(card.player_id) or ""
            except Exception:
                image_url = ""
        avatar = player_profile_ui.avatar_html(
            image_url,
            (card.name[:1] or "P").upper(),
            css_class="player-avatar",
        )
        identity_bits = " · ".join(
            part for part in (card.position, card.team) if part
        )
        # Recommendation gets the strongest hierarchy (Magna Carta §29) — the
        # action line stays the loudest text on the card. Origin caption
        # reuses .dg-gm-target-meta (same weight as team/position — real
        # rationale, not a headline claim).
        origin_label = _target_origin_label(card.source_surface)
        origin_html = (
            f"<div class='dg-gm-target-meta'>{escape(origin_label)}</div>"
            if origin_label
            else ""
        )
        action_html = (
            f"<div class='dg-gm-target-action'>{escape(card.action)}"
            + (
                f" — {escape(card.action_summary)}"
                if card.action_summary
                else ""
            )
            + "</div>"
            if card.action
            else "<div class='dg-gm-target-status'>No current action</div>"
        )
        change_html = (
            f"<div class='dg-gm-target-change'>{escape(card.material_label)}"
            + (
                f" · {escape(card.material_detail)}"
                if card.material_detail
                else ""
            )
            + "</div>"
            if card.material_label
            else ""
        )
        # Body order follows decision importance (Magna Carta §4): what to do
        # → what changed → reference ownership context, last. Rank is
        # reference metadata and lives in the top row next to identity, not
        # stacked ahead of the actual decision info.
        html_rendering.render_html_fragment(
            "<article class='dg-gm-target-card' "
            f"data-gm-target='1' data-gm-target-player-id='{escape(card.player_id)}'>"
            "<div class='dg-gm-target-top'>"
            "<div class='dg-gm-target-identity'>"
            f"{avatar}"
            "<div>"
            f"<div class='dg-gm-target-name'>{escape(card.name)}</div>"
            f"<div class='dg-gm-target-meta'>{escape(identity_bits)}</div>"
            f"{origin_html}"
            "</div></div>"
            f"<div class='dg-gm-target-rank'>{escape(card.rank_line)}</div>"
            "</div>"
            "<div class='dg-gm-target-body'>"
            f"{action_html}"
            f"{change_html}"
            f"<div class='dg-gm-target-status'>{escape(card.ownership)}</div>"
            "</div>"
            "</article>"
        )

        def _open_player_action() -> None:
            if open_player_quick_view is None:
                return
            if st.button(
                "Open player",
                key=f"gm_targets_open_{card.player_id}",
                use_container_width=True,
            ):
                open_player_quick_view(card.player_id)

        def _toggle_untouchable_action() -> None:
            def _toggle_untouchable(
                player_id: str = card.player_id, next_state: bool = not card.untouchable
            ) -> None:
                gm_targets.set_untouchable(
                    session,
                    league_id=league_key,
                    player_id=player_id,
                    untouchable=next_state,
                )

            # Reversible flag toggle — deliberately distinct wording from the
            # destructive "Remove from GM Targets" label one action over, so
            # the two "Remove ___" verbs are never sitting side by side.
            st.button(
                "Unmark untouchable" if card.untouchable else "Mark untouchable",
                key=f"gm_targets_untouchable_{card.player_id}",
                use_container_width=True,
                type="primary" if card.untouchable else "secondary",
                on_click=_toggle_untouchable,
            )

        def _remove_target_action() -> None:
            def _remove_target(player_id: str = card.player_id) -> None:
                gm_targets.remove_target(
                    session, league_id=league_key, player_id=player_id
                )

            # Canonical destructive-CTA tier (component_family_styles.py) —
            # same danger-red convention as account_ui.py's "Log out" — so
            # this irreversible action is never visually indistinguishable
            # from the reversible untouchable toggle beside it (recommendation-
            # clarity audit finding, same class as mobile PR #761).
            with st.container(
                key=f"dg_cta_destructive_gm_targets_remove_{card.player_id}"
            ):
                st.button(
                    gm_targets.REMOVE_ACTION_LABEL,
                    key=f"gm_targets_remove_{card.player_id}",
                    use_container_width=True,
                    on_click=_remove_target,
                )

        if open_player_quick_view is not None:
            ui_primitives.render_action_row(
                _open_player_action,
                key=f"gm_targets_actions_{card.player_id}",
                secondary_action=_toggle_untouchable_action,
                destructive_action=_remove_target_action,
                primary_first=True,
                horizontal_alignment="distribute",
            )
        else:
            ui_primitives.render_action_row(
                _toggle_untouchable_action,
                key=f"gm_targets_actions_{card.player_id}",
                destructive_action=_remove_target_action,
                primary_first=True,
                horizontal_alignment="distribute",
            )
        handoff = _workflow_handoff_destination(card.ownership)
        if handoff is not None and open_destination is not None:
            dest_key, dest_label = handoff
            if st.button(
                dest_label,
                key=f"gm_targets_handoff_{dest_key}_{card.player_id}",
                use_container_width=True,
            ):
                open_destination(dest_key)

    # Untouchable is the one real GM decision already encoded on a saved
    # target (modules/gm_targets.py GmTarget.untouchable, read directly by
    # the trade engine) — group by it so "who's protected from a trade"
    # outranks "who am I just watching," matching the same real backend
    # distinction mobile's GM Targets screen groups by (PR #697). No
    # fabricated categories: everything else here already comes straight off
    # the enriched card.
    untouchable_cards = tuple(card for card in ordered if card.untouchable)
    watching_cards = tuple(card for card in ordered if not card.untouchable)

    if untouchable_cards:
        with st.container(key="dg_gm_targets_group_untouchable"):
            ui_primitives.render_section_header(
                "Untouchable", heading_level=3, weight="secondary"
            )
            # Recommendation-clarity audit: a bare "Untouchable" heading
            # doesn't tell a new user what the flag actually does. This is
            # the real backend behavior it triggers (modules/trade_ideas.py
            # _is_core_or_protected_starter) stated in one plain sentence.
            st.caption("Kept out of auto-generated trade suggestions.")
            for card in untouchable_cards:
                _render_target_card(card)

    if watching_cards:
        with st.container(key="dg_gm_targets_group_watching"):
            ui_primitives.render_section_header(
                "Watching", heading_level=3, weight="secondary"
            )
            st.caption("Tracked here — no trade protection applied.")
            for card in watching_cards:
                _render_target_card(card)
