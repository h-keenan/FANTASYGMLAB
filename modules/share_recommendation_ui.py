"""Streamlit UI for experimental Share Recommendation cards."""

from __future__ import annotations

from typing import Any, Mapping, MutableMapping

import streamlit as st

from modules import share_card_renderer
from modules import share_recommendation_cards as share


def _track(event: str, *, state: MutableMapping[str, Any] | None, source_surface: str, card_type: str) -> None:
    try:
        from modules import launch_analytics
        from modules.app_config import config_bool

        props = launch_analytics.build_context_props(
            state,
            source_surface=source_surface,
            extra={
                "item_kind": card_type,
                "experiment_share_cards": bool(
                    config_bool(share.EXPERIMENT_ENV_KEY, default=False)
                ),
            },
        )
        launch_analytics.track_event(event, props=props, state=state)
    except Exception:
        return


def render_share_controls(
    card: share.ShareRecommendationCard,
    *,
    key: str,
    state: MutableMapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
) -> None:
    """Render Share / Save controls. No-op when experiment is disabled."""

    if not share.experiment_enabled(environ=environ):
        return

    session = state if isinstance(state, MutableMapping) else st.session_state
    label = f"{share.FEATURE_LABEL} [{share.EXPERIMENTAL_LABEL}]"
    open_key = f"{key}_share_open"
    if st.button(label, key=open_key, type="secondary", use_container_width=True):
        _track(
            "share_card_opened",
            state=session,
            source_surface=card.source_surface or "unknown",
            card_type=card.card_type,
        )
        session[f"{key}_share_active"] = True

    if not session.get(f"{key}_share_active"):
        return

    if not card.is_shareable:
        st.info(card.decline_reason or "This recommendation cannot be shared right now.")
        return

    with st.container():
        st.caption(f"{share.FEATURE_LABEL} · {share.EXPERIMENTAL_LABEL}")
        try:
            png = share_card_renderer.render_share_card_png(card)
            _track(
                "share_card_generated",
                state=session,
                source_surface=card.source_surface or "unknown",
                card_type=card.card_type,
            )
        except Exception:
            st.warning("Could not generate the share image. Try again in a moment.")
            return

        st.image(png, caption=f"{card.title} preview", use_container_width=True)
        file_name = f"fantasygmlab-{card.card_type}-{card.fingerprint or 'share'}.png"
        downloaded = st.download_button(
            "Save image",
            data=png,
            file_name=file_name,
            mime="image/png",
            key=f"{key}_share_download",
            use_container_width=True,
            type="primary",
        )
        if downloaded:
            _track(
                "share_card_downloaded",
                state=session,
                source_surface=card.source_surface or "unknown",
                card_type=card.card_type,
            )
            # Download is the reliable Streamlit share path; native Web Share
            # file sheets are not available from Streamlit server components.
            _track(
                "share_card_shared",
                state=session,
                source_surface=card.source_surface or "unknown",
                card_type=card.card_type,
            )
        st.caption(
            "Save the image, then attach it in Messages, Discord, Reddit, or X. "
            "Native OS share sheets are not available from this Streamlit surface."
        )
        if st.button("Close share preview", key=f"{key}_share_close", type="tertiary"):
            session[f"{key}_share_active"] = False
