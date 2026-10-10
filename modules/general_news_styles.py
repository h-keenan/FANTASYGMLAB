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
.news-group-header{align-items:center;display:flex;gap:.45rem;margin:.7rem 0 .4rem}
.news-group-accent-bar{border-radius:var(--radius-pill);flex-shrink:0;height:.85rem;width:3px}
.news-group-label{font-size:.72rem;font-weight:800;letter-spacing:.04em;text-transform:uppercase}
"""
