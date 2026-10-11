"""General News page (web counterpart to mobile's NewsScreen.tsx).

Route-owned, not baked into APP_CSS — injected only on current_page ==
"news" via inject_global_styles, same pattern as TRADE_ANALYZER_CSS. Keeps
the shared APP_CSS budget headroom intact for a route most sessions never
visit. Builds on the existing .news-card / .news-badge family already in
APP_CSS (modules/app_styles.py); this adds only the day/event-type grouping
chrome mobile's NewsScreen uses that the shared news card didn't need.
"""

from __future__ import annotations

GENERAL_NEWS_CSS = """
.news-date-header{color:var(--color-text-secondary);font-size:.78rem;font-weight:800;letter-spacing:.04em;margin:1.1rem 0 .4rem;text-transform:uppercase}
.news-date-header:first-of-type{margin-top:.2rem}
/* Mobile's NewsRow wraps the whole row in a TouchableOpacity (full-card tap
   target); this mirrors that, and this app's own dg-ui-card-link convention
   (modules/ui_primitive_styles.py), by making the whole card the link
   instead of just the headline text. Streamlit's own base stylesheet
   underlines every markdown-container anchor via a generated
   `.st-emotion-cache-* a` rule, whose specificity (one class + one type
   selector) beats a single-class override — the two-class selector here
   matches this card's own two classes (news-card news-card-link) and wins
   outright rather than racing injection order. */
.news-card.news-card-link{color:inherit;cursor:pointer;display:block;text-decoration:none}
.news-card-link:hover .news-card-title,
.news-card-link:focus-visible .news-card-title{color:var(--color-accent)}
.news-card-link:focus-visible{box-shadow:var(--focus-ring);outline:none}
.news-group-header{align-items:center;display:flex;gap:.45rem;margin:.7rem 0 .4rem}
.news-group-accent-bar{border-radius:var(--radius-pill);flex-shrink:0;height:.85rem;width:3px}
.news-group-label{align-items:center;display:inline-flex;font-size:.72rem;font-weight:800;gap:.3rem;letter-spacing:.04em;text-transform:uppercase}
/* Mobile pairs each event-type label with a colored Ionicons glyph (same
   hue as the label/accent bar). The shared glyph set's own per-concept
   default colors (modules/semantic_glyphs.py's .dg-glyph--trade etc.) are
   tuned for other surfaces (e.g. GM Orb nav rows) and would mismatch this
   row's own accent color, so this forces the icon to inherit the inline
   accent color set on news-group-label instead. */
.news-group-header .dg-glyph{color:inherit!important;margin-right:0}
"""
