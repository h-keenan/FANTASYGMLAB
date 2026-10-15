"""League Rankings invite CTA: "Send rankings to your league" — surfaces the
signed-in user's referral link with a one-tap copy action.

Copy-to-clipboard: this app's only existing clipboard pattern
(``modules.share_recommendation_ui.native_share_markup``) is a JS-only
iframe button with no Python round-trip at all, which is why that module
tracks its share analytics off the nearest reliable Python-visible proxy
(the Save Image download) instead of the actual click. ``referral_sent``
needs to fire reliably off *this* CTA's own action, so this renders a real
``st.button`` — a genuine Python click event — and, only once clicked,
mounts a tiny ``components.html`` snippet that writes the link to the
clipboard client-side (the same ``navigator.clipboard.writeText`` /
``execCommand("copy")`` fallback ladder as share_recommendation_ui's
``copyCanonicalText``). The button click is the single trigger for both the
clipboard write and the analytics event — no custom bidirectional component
needed.

No new CSS: every element here is a plain Streamlit primitive, so this adds
nothing to modules/app_styles.py's byte-budgeted APP_CSS.
"""

from __future__ import annotations

import json
from typing import Any, MutableMapping

import streamlit as st

from modules import app_config
from modules import auth_supabase
from modules import referrals

INVITE_CTA_TITLE = "Send rankings to your league"
INVITE_CTA_BODY = (
    "Share your league's power rankings with your leaguemates. For every 3 "
    "friends who connect their Sleeper account through your link, you earn "
    "a free month of GM Pro — up to 3 free months total."
)


def _safe_secrets() -> Any:
    try:
        return st.secrets
    except Exception:
        return None


def _copy_link_markup(link: str) -> str:
    safe_link = json.dumps(link)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head><body style="margin:0">
<script>
(async () => {{
  const text = {safe_link};
  try {{
    if (navigator.clipboard && navigator.clipboard.writeText) {{
      await navigator.clipboard.writeText(text);
      return;
    }}
  }} catch (err) {{}}
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  try {{ document.execCommand("copy"); }} catch (err) {{}}
  area.remove();
}})();
</script>
</body></html>"""


def render_invite_cta(*, session_state: MutableMapping[str, Any]) -> None:
    """Render the League Rankings invite CTA. No-op when signed out — a
    referral link only exists for an authenticated Supabase user_id."""

    user_id = auth_supabase.current_user_id(session_state)
    if not user_id:
        return
    link = referrals.referral_link(user_id, base_url=app_config.app_base_url(secrets=_safe_secrets()))
    if not link:
        return

    with st.container():
        st.markdown(f"**{INVITE_CTA_TITLE}**")
        st.caption(INVITE_CTA_BODY)
        link_col, button_col = st.columns([3, 1])
        with link_col:
            st.text_input(
                "Your referral link",
                value=link,
                key="league_overview_referral_link_display",
                disabled=True,
                label_visibility="collapsed",
            )
        with button_col:
            copied = st.button(
                "Copy link",
                key="league_overview_referral_copy_button",
                use_container_width=True,
            )
        if copied:
            import streamlit.components.v1 as components

            components.html(_copy_link_markup(link), height=1)
            st.toast("Referral link copied.")
            try:
                from modules import launch_analytics

                launch_analytics.track_event(
                    "referral_sent",
                    props=launch_analytics.build_context_props(
                        session_state, source_surface="league_overview_invite_cta"
                    ),
                    state=session_state,
                )
            except Exception:
                pass
