"""Streamlit UI for experimental Share Recommendation cards."""

from __future__ import annotations

import base64
import json
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


def native_share_markup(png: bytes, *, file_name: str, title: str) -> str:
    """Feature-detecting Web Share iframe document. Fallback is download-only."""

    payload = base64.b64encode(png).decode("ascii")
    safe_name = json.dumps(file_name)
    safe_title = json.dumps(title)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<style>
  body {{ margin: 0; font-family: ui-sans-serif, system-ui, sans-serif; background: transparent; color: #e5e7eb; }}
  button {{
    width: 100%; min-height: 44px; border: 0; border-radius: 0;
    background: #155e75; color: #ecfeff; font-weight: 600; cursor: pointer;
  }}
  button[hidden] {{ display: none; }}
  p {{ margin: 8px 0 0; font-size: 12px; color: #9ca3af; }}
</style>
</head>
<body>
<button id="shareBtn" type="button">Share via device</button>
<p id="status"></p>
<script>
const fileName = {safe_name};
const title = {safe_title};
const b64 = {json.dumps(payload)};
function toFile() {{
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  const blob = new Blob([bytes], {{ type: "image/png" }});
  return new File([blob], fileName, {{ type: "image/png" }});
}}
const canNavigatorShare = typeof navigator.share === "function";
const shareBtn = document.getElementById("shareBtn");
const statusEl = document.getElementById("status");
shareBtn.hidden = !canNavigatorShare;
statusEl.textContent = canNavigatorShare
  ? "On iPhone Safari this opens the system share sheet when the browser allows it."
  : "Native share is not available in this browser. Use Save image.";
shareBtn.addEventListener("click", async () => {{
  const file = toFile();
  try {{
    if (navigator.canShare && navigator.canShare({{ files: [file] }})) {{
      await navigator.share({{ files: [file], title: title, text: title }});
      statusEl.textContent = "Opened the system share sheet.";
      return;
    }}
    if (canNavigatorShare) {{
      await navigator.share({{ title: title, text: title }});
      statusEl.textContent = "Share sheet opened. Attach the saved image if the photo was not included.";
      return;
    }}
  }} catch (err) {{
    if (err && err.name === "AbortError") return;
  }}
  statusEl.textContent = "Native share was blocked. Use Save image.";
}});
</script>
</body>
</html>"""


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
    label = share.FEATURE_LABEL
    if share.EXPERIMENTAL_LABEL:
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
        st.caption(share.FEATURE_LABEL)
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
        try:
            import streamlit.components.v1 as components

            components.html(
                native_share_markup(png, file_name=file_name, title=card.title),
                height=88,
                scrolling=False,
            )
        except Exception:
            pass
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
            _track(
                "share_card_shared",
                state=session,
                source_surface=card.source_surface or "unknown",
                card_type=card.card_type,
            )
        st.caption(
            "On iPhone Safari, Share via device uses the native share sheet when "
            "the browser supports it. Otherwise save the image and attach it in "
            "Messages, Discord, Reddit, or X."
        )
        if st.button("Close share preview", key=f"{key}_share_close", type="tertiary"):
            session[f"{key}_share_active"] = False
