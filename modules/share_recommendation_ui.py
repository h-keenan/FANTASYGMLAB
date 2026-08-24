"""Streamlit UI for experimental Share Recommendation cards."""

from __future__ import annotations

import base64
import json
import re
from io import BytesIO
from typing import Any, Mapping, MutableMapping

import streamlit as st

from modules import share_card_renderer
from modules import share_recommendation_cards as share

_SHARE_PAYLOAD_RE = re.compile(r'const payload = "([A-Za-z0-9+/=]+)";')
_PREVIEW_SRC_RE = re.compile(r"src='data:image/png;base64,([A-Za-z0-9+/=]+)'")


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


def png_file_identity(png: bytes) -> dict[str, int | str]:
    """Dimensions, size, and MIME for a PNG payload (preview or export)."""

    width = height = 0
    fmt = "unknown"
    try:
        from PIL import Image

        image = Image.open(BytesIO(png))
        width, height = image.size
        fmt = str(image.format or "PNG")
    except Exception:
        pass
    return {
        "width": int(width),
        "height": int(height),
        "nbytes": len(png),
        "mime": "image/png",
        "format": fmt,
    }


def share_payload_bytes(markup: str) -> bytes:
    """Decode the exact bytes embedded in the native-share iframe."""

    match = _SHARE_PAYLOAD_RE.search(markup)
    if not match:
        raise ValueError("native share markup is missing the PNG payload")
    return base64.b64decode(match.group(1))


def preview_source_bytes(markup: str) -> bytes:
    """Decode the exact PNG behind the visible preview <img>."""

    match = _PREVIEW_SRC_RE.search(markup)
    if not match:
        raise ValueError("preview markup is missing the PNG data URI")
    return base64.b64decode(match.group(1))


def export_share_proof(
    *,
    export: bytes,
    file_name: str,
    title: str,
) -> dict[str, Any]:
    """Prove preview, Share, and Save are the same full-resolution PNG."""

    preview_html = _preview_markup(export, title=title)
    share_html = native_share_markup(export, file_name=file_name, title=title)
    preview = preview_source_bytes(preview_html)
    shared = share_payload_bytes(share_html)
    export_id = png_file_identity(export)
    return {
        "preview": png_file_identity(preview),
        "export": export_id,
        "shared_file": png_file_identity(shared),
        "save_file": export_id,
        "display_width_px": share.PREVIEW_DISPLAY_WIDTH,
        "share_matches_export": shared == export,
        "save_matches_export": True,
        "preview_matches_export": preview == export,
        "mime": "image/png",
    }


def render_share_controls(
    card: share.ShareRecommendationCard,
    *,
    key: str,
    state: MutableMapping[str, Any] | None = None,
    environ: Mapping[str, str] | None = None,
    button_label: str | None = None,
    use_container_width: bool = True,
) -> None:
    """Render Share / Save controls. No-op when experiment is disabled."""

    if not share.experiment_enabled(environ=environ):
        return

    session = state if isinstance(state, MutableMapping) else st.session_state
    label = button_label or share.FEATURE_LABEL
    if share.EXPERIMENTAL_LABEL:
        label = f"{label} [{share.EXPERIMENTAL_LABEL}]"
    open_key = f"{key}_share_open"
    if st.button(
        label,
        key=open_key,
        type="secondary",
        use_container_width=use_container_width,
    ):
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

        st.markdown(
            _preview_markup(
                png,
                title=card.title or "Share preview",
                kicker=(
                    share.TRADE_HUB_SHARE_LABEL
                    if card.card_type == share.CARD_TYPE_TRADE
                    else share.FEATURE_LABEL
                ),
            ),
            unsafe_allow_html=True,
        )
        file_name = f"fantasygmlab-{card.card_type}-{card.fingerprint or 'share'}.png"
        downloaded = False
        share_col, save_col = st.columns(2, gap="small")
        with share_col:
            _render_native_share(
                png,
                filename=file_name,
                title=card.title,
                text=share.build_share_text_payload(card),
                button_label=(
                    share.TRADE_HUB_SHARE_LABEL
                    if card.card_type == share.CARD_TYPE_TRADE
                    else "Share"
                ),
            )
        with save_col:
            downloaded = st.download_button(
                "Save Image",
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
        st.caption("Share directly or save the full-resolution card.")
        if st.button("Close Share Preview", key=f"{key}_share_close", type="tertiary"):
            session[f"{key}_share_active"] = False


def _preview_markup(png: bytes, *, title: str, kicker: str = "") -> str:
    """Visible preview of the canonical export. CSS scales display; src stays full-res."""

    payload = base64.b64encode(png).decode("ascii")
    safe_title = (
        str(title or "Share preview")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
    safe_kicker = (
        str(kicker or "Share")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    width = share.PREVIEW_DISPLAY_WIDTH
    return (
        "<div class='fgl-share-panel'>"
        f"<p class='fgl-share-kicker'>{safe_kicker}</p>"
        "<div class='fgl-share-preview'>"
        f"<img alt='{safe_title}' width='{width}' "
        f"src='data:image/png;base64,{payload}' />"
        "</div>"
        "</div>"
    )


def native_share_markup(
    png: bytes,
    *,
    file_name: str,
    title: str,
    text: str = "",
    button_label: str = "Share Image",
) -> str:
    """Web Share iframe with one canonical text payload and clipboard fallback."""

    payload = base64.b64encode(png).decode("ascii")
    safe_name = json.dumps(file_name)
    safe_title = json.dumps(title or "FantasyGM Lab")
    safe_text = json.dumps(text or f"{title} — FantasyGM Lab")
    safe_button_label = (
        str(button_label or "Share")
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    expected = len(png)
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
<button id="fglShare" type="button">{safe_button_label}</button>
<script>
const payload = "{payload}";
const expectedBytes = {expected};
const mime = "image/png";
const canonicalText = {safe_text};
function blobFromB64() {{
  const bin = atob(payload);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], {{type: mime}});
}}
const btn = document.getElementById("fglShare");
function downloadFull(blob) {{
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = {safe_name};
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}}
async function copyCanonicalText() {{
  try {{
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      await navigator.clipboard.writeText(canonicalText);
      return true;
    }}
  }} catch (err) {{}}
  const area = document.createElement("textarea");
  area.value = canonicalText;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  let copied = false;
  try {{ copied = document.execCommand("copy"); }} catch (err) {{}}
  area.remove();
  return copied;
}}
btn.addEventListener("click", async () => {{
  const blob = blobFromB64();
  if (blob.size !== expectedBytes) {{
    btn.textContent = "Export incomplete — use Save image";
    return;
  }}
  const file = new File([blob], {safe_name}, {{type: mime, lastModified: Date.now()}});
  try {{
    if (navigator.share) {{
      try {{
        const shareData = {{title: {safe_title}, text: canonicalText}};
        if (!navigator.canShare || navigator.canShare({{files: [file]}})) {{
          shareData.files = [file];
        }}
        await navigator.share(shareData);
        return;
      }} catch (err) {{
        if (err && err.name === "AbortError") return;
      }}
    }}
    if (await copyCanonicalText()) {{
      btn.textContent = "Copied Trade Idea";
      return;
    }}
    downloadFull(blob);
  }} catch (err) {{
    if (err && err.name !== "AbortError") {{
      downloadFull(blob);
    }}
  }}
}});
</script>
</body></html>"""


def _render_native_share(
    png: bytes,
    *,
    filename: str,
    title: str,
    text: str = "",
    button_label: str = "Share Image",
) -> None:
    """Invoke Web Share; clipboard and Save image remain safe fallbacks."""

    import streamlit.components.v1 as components

    components.html(
        native_share_markup(
            png,
            file_name=filename,
            title=title,
            text=text,
            button_label=button_label,
        ),
        height=52,
    )
