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
    button_label: str | None = None,
) -> None:
    """Render Share / Save controls. No-op when experiment is disabled."""

    if not share.experiment_enabled(environ=environ):
        return

    session = state if isinstance(state, MutableMapping) else st.session_state
    label = button_label or share.FEATURE_LABEL
    if share.EXPERIMENTAL_LABEL:
        label = f"{label} [{share.EXPERIMENTAL_LABEL}]"
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
        st.caption(label)
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

        preview = share_card_renderer.preview_png_bytes(png)
        st.markdown("<div class='fgl-share-preview'>", unsafe_allow_html=True)
        st.image(
            preview,
            caption=f"{card.title} preview",
            width=share.PREVIEW_DISPLAY_WIDTH,
        )
        st.markdown("</div>", unsafe_allow_html=True)
        file_name = f"fantasygmlab-{card.card_type}-{card.fingerprint or 'share'}.png"
        _render_native_share(png, filename=file_name, title=card.title)
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
            "On iPhone, use Share to open the system share sheet (Messages, AirDrop). "
            "Otherwise save the image, then attach it in Messages, Discord, Reddit, or X."
        )
        if st.button("Close share preview", key=f"{key}_share_close", type="tertiary"):
            session[f"{key}_share_active"] = False


def native_share_markup(
    png: bytes,
    *,
    file_name: str,
    title: str,
) -> str:
    """Feature-detect Web Share in the iframe; Save image remains the fallback."""

    import base64
    import json

    payload = base64.b64encode(png).decode("ascii")
    safe_name = json.dumps(file_name)
    safe_title = json.dumps(title or "FantasyGM Lab")
    safe_text = json.dumps(f"{title} — FantasyGM Lab")
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  html,body{{margin:0;background:transparent;font-family:system-ui,sans-serif}}
  button{{
    width:100%;min-height:44px;border-radius:0;border:1px solid #2a2e36;
    background:#15181d;color:#eceef2;font-size:15px;font-weight:650;cursor:pointer;
  }}
  button[disabled]{{opacity:.45;cursor:default}}
</style></head><body>
<button id="fglShare" type="button">Share</button>
<script>
const payload = "{payload}";
function blobFromB64() {{
  const bin = atob(payload);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], {{type: "image/png"}});
}}
const file = new File([blobFromB64()], {safe_name}, {{type: "image/png"}});
const btn = document.getElementById("fglShare");
const canShare = !!(navigator.canShare && navigator.share);
const canFiles = !!(canShare && navigator.canShare({{files: [file]}}));
if (!canShare) {{
  btn.textContent = "Share sheet unavailable — use Save image";
  btn.disabled = true;
}} else {{
  btn.textContent = canFiles ? "Share image" : "Share";
}}
btn.addEventListener("click", async () => {{
  try {{
    if (canFiles) {{
      await navigator.share({{files: [file], title: {safe_title}, text: {safe_text}}});
    }} else {{
      await navigator.share({{title: {safe_title}, text: {safe_text} + " https://fantasygmlab.com"}});
    }}
  }} catch (err) {{
    if (err && err.name !== "AbortError") {{
      btn.textContent = "Share cancelled — use Save image";
    }}
  }}
}});
</script>
</body></html>"""


def _render_native_share(png: bytes, *, filename: str, title: str) -> None:
    """Invoke Web Share when the browser/iframe allows it; otherwise no-op UI."""

    import streamlit.components.v1 as components

    components.html(
        native_share_markup(png, file_name=filename, title=title),
        height=52,
    )
