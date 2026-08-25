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
.dg-gm-target-card{border-block-end:var(--border-width-default) solid var(--color-border);display:grid;gap:var(--space-2xs) var(--space-sm);grid-template-columns:minmax(0,1fr) auto;padding-block:var(--space-sm)}
.dg-gm-target-identity{align-items:center;display:flex;gap:var(--space-sm);min-width:0}
.dg-gm-target-meta{color:var(--color-text-muted);font:var(--type-supporting-metadata)}
.dg-gm-target-name{color:var(--color-text-primary);font:var(--font-card-title)}
.dg-gm-target-rank{color:var(--color-text-primary);font:var(--type-primary-metric);font-variant-numeric:tabular-nums;justify-self:end;text-align:right}
.dg-gm-target-status,.dg-gm-target-action,.dg-gm-target-change{grid-column:1/-1}
.dg-gm-target-status{color:var(--color-text-secondary);font:var(--type-supporting-metadata)}
.dg-gm-target-action{color:var(--color-text-primary);font:var(--type-caption-emphasis)}
.dg-gm-target-change{color:var(--color-text-muted);font:var(--type-supporting-metadata)}
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
            use_container_width=True,
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

    for card in ordered:
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
        html_rendering.render_html_fragment(
            "<article class='dg-gm-target-card' "
            f"data-gm-target='1' data-gm-target-player-id='{escape(card.player_id)}'>"
            "<div class='dg-gm-target-identity'>"
            f"{avatar}"
            "<div>"
            f"<div class='dg-gm-target-name'>{escape(card.name)}</div>"
            f"<div class='dg-gm-target-meta'>{escape(identity_bits)}</div>"
            "</div></div>"
            f"<div class='dg-gm-target-rank'>{escape(card.rank_line)}</div>"
            f"<div class='dg-gm-target-status'>{escape(card.ownership)}</div>"
            f"{action_html}"
            f"{change_html}"
            "</article>"
        )
        cols = st.columns(2)
        with cols[0]:
            if open_player_quick_view is not None:
                if st.button(
                    "Open player",
                    key=f"gm_targets_open_{card.player_id}",
                    use_container_width=True,
                ):
                    open_player_quick_view(card.player_id)
        with cols[1]:

            def _remove_target(player_id: str = card.player_id) -> None:
                gm_targets.remove_target(
                    session, league_id=league_key, player_id=player_id
                )

            st.button(
                gm_targets.REMOVE_ACTION_LABEL,
                key=f"gm_targets_remove_{card.player_id}",
                use_container_width=True,
                on_click=_remove_target,
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
