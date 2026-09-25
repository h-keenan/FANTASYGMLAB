"""Streamlit presentation for Team Situation (Decision Memory v1 gap, #232).

Standalone page — deliberately NOT embedded in My Team or Dashboard (both
get separate structural redesigns). Reuses modules.gm_targets' existing
`untouchable` flag for "protect this player" rather than a second, parallel
protect-list mechanism; the only new storage here is the stance value itself
(modules.team_stance).
"""

from __future__ import annotations

from typing import Any, Iterable, MutableMapping

import pandas as pd
import streamlit as st

from modules import gm_targets
from modules import team_stance


def render_team_stance_workspace(
    *,
    session: MutableMapping[str, Any],
    league_id: str,
    my_roster_player_ids: Iterable[str] | None,
    df_players: pd.DataFrame | None,
) -> None:
    league_key = str(league_id or "").strip()
    if not league_key:
        st.info("Select a league to set your Team Situation.")
        return
    if not team_stance.can_access_stance(session):
        st.info("Sign in to declare your Team Situation.")
        return

    current = team_stance.fetch_stance_for_league(session, league_id=league_key)
    st.caption(team_stance.SUPPORTING_COPY)

    options = list(team_stance.STANCE_OPTIONS)
    labels = [team_stance.STANCE_LABELS[key] for key in options]
    default_index = options.index(current) if current in options else 0
    chosen_label = st.radio(
        "Team Situation",
        labels,
        index=default_index,
        horizontal=True,
        key=f"team_stance_picker_{league_key}",
        label_visibility="collapsed",
    )
    chosen = options[labels.index(chosen_label)]
    if chosen != current:
        result = team_stance.set_stance(session, league_id=league_key, stance=chosen)
        if result.get("ok"):
            st.success(f"Team Situation set to {team_stance.STANCE_LABELS[chosen]}.")
        elif result.get("error"):
            st.warning(result["error"])

    st.divider()
    st.subheader("Protected Players")
    st.caption(
        "Mark players you don't want traded away. This is the same protection "
        "GM Targets' untouchable flag uses — toggling it here or there shows "
        "up in both places."
    )

    if not gm_targets.experiment_enabled() or not gm_targets.can_access_targets(session):
        st.caption("GM Targets is unavailable right now.")
        return

    roster_ids = {str(pid) for pid in (my_roster_player_ids or ()) if str(pid)}
    if not roster_ids or df_players is None or getattr(df_players, "empty", True):
        st.caption("No roster players found for this league.")
        return
    if "player_id" not in df_players.columns:
        st.caption("No roster players found for this league.")
        return

    gm_targets.ensure_membership_cache(session, league_id=league_key)
    untouchable_ids = gm_targets.cached_untouchable_ids(session, league_id=league_key)

    roster_rows = df_players[df_players["player_id"].astype(str).isin(roster_ids)]
    if "name" in roster_rows.columns:
        roster_rows = roster_rows.sort_values("name")

    for _, row in roster_rows.iterrows():
        pid = gm_targets.normalize_player_id(row.get("player_id"))
        if not pid:
            continue
        name = str(row.get("name") or "Player")
        position = str(row.get("position") or "").upper()
        team = str(row.get("team") or "")
        label = f"{name} — {position} {team}".strip()
        is_protected = pid in untouchable_ids

        def _toggle(pid: str = pid, was_protected: bool = is_protected) -> None:
            if not was_protected:
                if not gm_targets.is_targeted(session, league_id=league_key, player_id=pid):
                    gm_targets.add_target(
                        session,
                        league_id=league_key,
                        player_id=pid,
                        source_surface="team_stance",
                    )
                gm_targets.set_untouchable(
                    session, league_id=league_key, player_id=pid, untouchable=True
                )
            else:
                gm_targets.set_untouchable(
                    session, league_id=league_key, player_id=pid, untouchable=False
                )

        st.checkbox(
            label,
            value=is_protected,
            key=f"team_stance_protect_{league_key}_{pid}",
            on_change=_toggle,
        )
