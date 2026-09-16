"""Restrained semantic glyphs for GM Orb and high-value Dashboard surfaces.

Presentation only. Inline SVG / CSS masks. No icon-font dependency, no remote
fetch, no emoji. Decorative marks are aria-hidden; callers keep text labels.
"""

from __future__ import annotations

from collections import defaultdict
from html import escape
from urllib.parse import quote


CONCEPTS = (
    "home",
    "roster",
    "trade",
    "waiver",
    "rankings",
    "draft",
    "league",
    "insights",
    "alerts",
    "health",
    "history",
    "more",
)

# Destination keys → concept. Unknown keys fall back to "more".
DESTINATION_CONCEPT = {
    "dashboard": "home",
    "alerts": "alerts",
    "my_team": "roster",
    "players": "rankings",
    "gm_targets": "roster",
    "rankings": "league",
    "league_recaps": "history",
    "trade_hub": "trade",
    "trade_analyzer": "trade",
    "waivers": "waiver",
    "startup_draft_center": "draft",
    "draft_summary": "draft",
    "live_draft": "draft",
    "premium": "more",
    "methodology": "more",
    "about_disclaimer": "more",
    "terms": "more",
    "privacy": "more",
    "subscription_terms": "more",
    "no_affiliation": "more",
    "founder_ops": "more",
    "founder_labs": "more",
}

# Aliases used by existing dashboard / tile copy.
KIND_CONCEPT = {
    "home": "home",
    "dashboard": "home",
    "game_plan": "home",
    "roster": "roster",
    "my_team": "roster",
    "team": "roster",
    "teams": "roster",
    "trade": "trade",
    "trade_hub": "trade",
    "waiver": "waiver",
    "waivers": "waiver",
    "opportunity": "waiver",
    "rankings": "rankings",
    "players": "rankings",
    "draft": "draft",
    "draft_summary": "draft",
    "league": "league",
    "insights": "insights",
    "analysis": "insights",
    "metric": "insights",
    "power": "rankings",
    "value": "rankings",
    "franchise": "draft",
    "capital": "draft",
    "strength": "insights",
    "pressure": "health",
    "need": "alerts",
    "injury": "health",
    "alerts": "alerts",
    "alert": "alerts",
    "news": "alerts",
    "health": "health",
    "risk": "health",
    "history": "history",
    "recap": "history",
    "recaps": "history",
    "storylines": "history",
    "more": "more",
    "settings": "more",
}

HEADER_CONCEPT = {
    "today's game plan": "home",
    "league insights": "insights",
    "team snapshot": "roster",
}

_STROKE = (
    "fill='none' stroke='currentColor' stroke-width='1.75' "
    "stroke-linecap='square' stroke-linejoin='miter'"
)

_PATHS = {
    "home": (
        f"<polygon {_STROKE} points='12 3 21 12 12 21 3 12'/>"
        f"<rect {_STROKE} x='9' y='9' width='6' height='6'/>"
    ),
    "roster": (
        f"<path {_STROKE} d='M8 4.5h3l1 2.2 1-2.2h3v15.5H8z'/>"
        f"<path {_STROKE} d='M10 12h4'/>"
    ),
    "trade": (
        f"<path {_STROKE} d='M4 8h14'/>"
        f"<path {_STROKE} d='M14 4l4 4-4 4'/>"
        f"<path {_STROKE} d='M20 16H6'/>"
        f"<path {_STROKE} d='M10 12l-4 4 4 4'/>"
    ),
    "waiver": (
        f"<circle {_STROKE} cx='12' cy='12' r='8'/>"
        f"<path {_STROKE} d='M12 8v8M8 12h8'/>"
    ),
    "rankings": (
        f"<path {_STROKE} d='M5 18V11'/>"
        f"<path {_STROKE} d='M12 18V6'/>"
        f"<path {_STROKE} d='M19 18v-5'/>"
    ),
    "draft": (
        f"<rect {_STROKE} x='6' y='5' width='12' height='14'/>"
        f"<path {_STROKE} d='M9 9h6M9 13h6'/>"
    ),
    "league": (
        f"<path {_STROKE} d='M12 3.5l7 3v5.2c0 4.2-2.8 7.2-7 8.8-4.2-1.6-7-4.6-7-8.8V6.5z'/>"
    ),
    "insights": (
        f"<path {_STROKE} d='M12 19v-2'/>"
        f"<path {_STROKE} d='M8.2 15.2a5.2 5.2 0 1 1 7.6 0'/>"
        f"<path {_STROKE} d='M5.4 12.4a8 8 0 1 1 13.2 0'/>"
    ),
    "alerts": (
        f"<path {_STROKE} d='M6 16h12l-1.2-2.2V10a4.8 4.8 0 0 0-9.6 0v3.8z'/>"
        f"<path {_STROKE} d='M10 16.5a2 2 0 0 0 4 0'/>"
    ),
    "health": (
        f"<path {_STROKE} d='M4 12h3l2-4 3 8 2-4h6'/>"
    ),
    "history": (
        f"<circle {_STROKE} cx='6' cy='12' r='1.4'/>"
        f"<circle {_STROKE} cx='12' cy='12' r='1.4'/>"
        f"<circle {_STROKE} cx='18' cy='12' r='1.4'/>"
        f"<path {_STROKE} d='M7.6 12h2.8M13.6 12h2.8'/>"
    ),
    "more": (
        f"<rect {_STROKE} x='5' y='5' width='5' height='5'/>"
        f"<rect {_STROKE} x='14' y='5' width='5' height='5'/>"
        f"<rect {_STROKE} x='5' y='14' width='5' height='5'/>"
        f"<rect {_STROKE} x='14' y='14' width='5' height='5'/>"
    ),
}


def normalize_concept(kind: object) -> str:
    key = str(kind or "").strip().lower().replace(" ", "_").replace("-", "_")
    if key in CONCEPTS:
        return key
    if key in DESTINATION_CONCEPT:
        return DESTINATION_CONCEPT[key]
    if key in KIND_CONCEPT:
        return KIND_CONCEPT[key]
    stem = key.split("_", 1)[0]
    if stem in KIND_CONCEPT:
        return KIND_CONCEPT[stem]
    return "more"


def concept_for(kind: object) -> str:
    return normalize_concept(kind)


def concept_for_destination(page_key: object) -> str:
    key = str(page_key or "").strip().lower()
    return DESTINATION_CONCEPT.get(key, "more")


def concept_for_header(title: object) -> str:
    return HEADER_CONCEPT.get(str(title or "").strip().casefold(), "")


def svg_inner(concept: str) -> str:
    return _PATHS.get(normalize_concept(concept), _PATHS["more"])


def svg_markup(concept: str) -> str:
    name = normalize_concept(concept)
    return (
        f"<svg class='dg-glyph__svg' viewBox='0 0 24 24' aria-hidden='true' "
        f"focusable='false' data-dg-glyph='{escape(name, quote=True)}'>"
        f"{svg_inner(name)}</svg>"
    )


def glyph_html(
    kind: object,
    *,
    size: str = "row",
    decorative: bool = True,
    extra_class: str = "",
) -> str:
    concept = normalize_concept(kind)
    size_key = size if size in {"row", "header", "card", "kicker"} else "row"
    classes = f"dg-glyph dg-glyph--{concept} dg-glyph--{size_key} dg-semantic-icon"
    if extra_class:
        classes += f" {extra_class}"
    hidden = " aria-hidden='true'" if decorative else f" role='img' aria-label='{escape(concept)}'"
    return f"<span class='{classes}'{hidden}>{svg_markup(concept)}</span>"


def route_row_glyph_html(page_key: object) -> str:
    """Legacy overlay markup. GM Orb rows no longer inject this."""

    return (
        "<span class='dg-gm-route-glyph' aria-hidden='true'>"
        f"{glyph_html(concept_for_destination(page_key), size='row')}</span>"
    )


def glyph_mask_data_uri(concept: object) -> str:
    """CSS mask data URI from the canonical SVG path set. Local, no fetch."""

    inner = svg_inner(normalize_concept(concept)).replace("currentColor", "#000")
    svg = (
        "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none'>"
        f"{inner}</svg>"
    )
    return f'url("data:image/svg+xml,{quote(svg, safe="")}")'


def gm_orb_row_css() -> str:
    keys_by_concept: dict[str, list[str]] = defaultdict(list)
    for page_key, concept in DESTINATION_CONCEPT.items():
        keys_by_concept[concept].append(str(page_key))
    mask_rules: list[str] = []
    for concept, keys in keys_by_concept.items():
        selectors = ",".join(
            (
                f'div[class*="st-key-mobile_sheet_nav_{key}"] [data-testid="stButton"] button,'
                f'div[class*="st-key-mobile_sheet_nav_{key}"] button[data-testid^="stBaseButton"]'
            )
            for key in keys
        )
        mask_rules.append(f"{selectors}{{--dg-orb-glyph-mask:{glyph_mask_data_uri(concept)}}}")
    masks = "".join(mask_rules)
    return f"""
div[class*="st-key-mobile_sheet_row_"]{{
    --dg-orb-glyph-gap:var(--space-sm);
    --dg-orb-glyph-inset:var(--space-sm);
    --dg-orb-glyph-slot:1.25rem;
}}
div[class*="st-key-mobile_sheet_row_"] [data-testid="stVerticalBlock"]{{
    gap:0!important;
}}
div[class*="st-key-mobile_sheet_nav_"] [data-testid="stButton"] button,
div[class*="st-key-mobile_sheet_nav_"] button[data-testid^="stBaseButton"]{{
    --dg-orb-glyph-mask:{glyph_mask_data_uri("more")};
    align-items:center!important;
    display:flex!important;
    justify-content:flex-start!important;
    text-align:left!important;
}}
{masks}
div[class*="st-key-mobile_sheet_nav_"] [data-testid="stButton"] button::before,
div[class*="st-key-mobile_sheet_nav_"] button[data-testid^="stBaseButton"]::before{{
    background-color:currentColor!important;
    content:""!important;
    display:block!important;
    flex:0 0 var(--dg-orb-glyph-slot)!important;
    height:var(--dg-orb-glyph-slot)!important;
    margin:0 var(--dg-orb-glyph-gap) 0 0!important;
    -webkit-mask:var(--dg-orb-glyph-mask) center/contain no-repeat!important;
    mask:var(--dg-orb-glyph-mask) center/contain no-repeat!important;
    pointer-events:none!important;
    width:var(--dg-orb-glyph-slot)!important;
}}
div[class*="st-key-mobile_sheet_nav_"] [data-testid="stButton"] button p,
div[class*="st-key-mobile_sheet_nav_"] [data-testid="stButton"] button span,
div[class*="st-key-mobile_sheet_nav_"] [data-testid="stButton"] button div,
div[class*="st-key-mobile_sheet_nav_"] [data-testid="stButton"] [data-testid="stMarkdownContainer"],
div[class*="st-key-mobile_sheet_nav_"] button[data-testid^="stBaseButton"] p,
div[class*="st-key-mobile_sheet_nav_"] button[data-testid^="stBaseButton"] span,
div[class*="st-key-mobile_sheet_nav_"] button[data-testid^="stBaseButton"] div{{
    display:block!important;
    flex:1 1 auto!important;
    justify-content:flex-start!important;
    margin:0!important;
    max-width:none!important;
    padding:0!important;
    padding-inline:0!important;
    text-align:left!important;
    width:auto!important;
}}
"""


SEMANTIC_GLYPH_CSS = """
.dg-glyph{
    align-items:center;
    color:inherit;
    display:inline-flex;
    flex:0 0 auto;
    height:1.25rem;
    justify-content:center;
    line-height:0;
    margin-right:var(--space-xs);
    vertical-align:middle;
    width:1.25rem;
}
.dg-glyph--header{height:1.35rem;margin-right:var(--space-sm);width:1.35rem}
.dg-glyph--card{height:1.25rem;width:1.25rem}
.dg-glyph--kicker{height:1rem;width:1rem}
.dg-glyph--row{height:1.25rem;width:1.25rem}
.dg-glyph__svg{display:block;height:100%;width:100%}
.dg-glyph--trade{color:var(--color-information)}
.dg-glyph--waiver{color:var(--color-success)}
.dg-glyph--health{color:var(--color-warning)}
.dg-glyph--alerts{color:var(--color-information)}
.dg-glyph--alerts.is-unread{position:relative}
.dg-glyph--alerts.is-unread::after{
    background:var(--color-accent);
    border-radius:50%;
    content:"";
    height:0.35rem;
    position:absolute;
    right:-0.12rem;
    top:-0.12rem;
    width:0.35rem;
}
.dg-semantic-icon{
    align-items:center;
    background:transparent;
    border:0;
    color:inherit;
    display:inline-flex;
    flex:0 0 auto;
    justify-content:center;
    line-height:0;
    margin-right:var(--space-xs);
    min-width:0;
    padding:0;
    vertical-align:middle;
}
.dg-alert-warning .dg-semantic-icon,
.home-command-card-risk .dg-semantic-icon,
.summary-tile-risk .dg-semantic-icon,
.decision-panel-risk .dg-semantic-icon,
.roster-limit-stat-danger .dg-semantic-icon{color:var(--color-warning)}
.home-command-card-need .dg-semantic-icon,
.summary-tile-weakness .dg-semantic-icon,
.analysis-card-weakness .dg-semantic-icon,
.roster-limit-stat-warning .dg-semantic-icon{color:var(--color-warning)}
.home-command-card-trade .dg-semantic-icon,
.home-command-card-waiver .dg-semantic-icon,
.trade-idea-positive .dg-semantic-icon,
.free-agent-card-tone-core .dg-semantic-icon,
.free-agent-card-tone-rise .dg-semantic-icon,
.summary-tile-opportunity .dg-semantic-icon,
.decision-panel-strength .dg-semantic-icon{color:var(--color-success)}
.home-command-card-draft .dg-semantic-icon,
.draft-review-pick-card .dg-semantic-icon{color:var(--color-information)}
"""
