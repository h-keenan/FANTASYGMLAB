"""Static user-facing methodology / trust surface.

Presentation only. This module must not import football providers, run
valuation, or load league player frames.
"""

from __future__ import annotations

from html import escape

from modules import brand_identity
from modules.html_rendering import inject_global_styles, render_html_fragment
from modules.methodology_page_styles import METHODOLOGY_PAGE_CSS
from modules.player_tier_identity import player_tier_legend_html


PAGE_KEY = "methodology"
NAV_LABEL = "How We Evaluate"
PAGE_TITLE = "How FantasyGM Lab Evaluates Players"
PAGE_KICKER = "HOW FANTASYGM LAB THINKS ABOUT VALUE"
PAGE_PURPOSE = (
    "How FantasyGM Lab evaluates players in league context, and how rankings "
    "differ from trade recommendations."
)
FOOTER_LABEL = "How We Evaluate"

HERO_SUMMARY = (
    f"{brand_identity.PRODUCT_NAME} values are built for a specific league and roster "
    "situation. They are not universal player grades, and they are not a promise "
    "about what will happen next week or next season."
)

LEAGUE_INTRO = (
    "The same player can be worth more or less once scoring, lineup rules, and "
    "league size are applied. Superflex and 2QB leagues raise quarterback value. "
    "Tight-end premium raises tight ends. PPR, half-PPR, and standard scoring "
    "shift running backs versus receivers. Deeper starting lineups and larger "
    "leagues increase demand for usable depth. Taxi squads can give a little "
    "extra room to stash young skill players."
)

#: Every skill-player value is a weighted composite of six fixed inputs —
#: percentages below are the actual production weights, copied here as
#: static text rather than imported, since this module must stay free of a
#: valuation-engine dependency (see module docstring). Keep these in sync by
#: hand if the underlying weighting changes.
FACTORS = (
    (
        "Market context (44%)",
        "Dynasty market prices are the largest single input. They reflect how the "
        "player is currently valued in dynasty formats, not a private forecast.",
    ),
    (
        "Age and career stage (18%)",
        "A position-specific age curve, not a flat penalty — running backs decline "
        "earliest and fastest, quarterbacks and tight ends hold value longest. "
        "Current points do not erase an aging curve.",
    ),
    (
        "Production (12%)",
        "Scoring over a meaningful sample is part of the evaluation. A hot week or "
        "a quiet week is not enough on its own, and missing stats are not treated "
        "as secret market confirmation.",
    ),
    (
        "Positional scarcity (10%)",
        "Players are compared with others at the same position, weighted by how "
        "replaceable that position is — tight end and running back count for more "
        "than a raw point total would suggest; kickers count for far less.",
    ),
    (
        "Opportunity (10%)",
        "Workload and target/touch share signals — evidence of usage, not just a "
        "role label.",
    ),
    (
        "Role (6%)",
        "Depth-chart role on its own. A backup with elite talent is not valued "
        "like a locked-in starter.",
    ),
    (
        "Availability (applied on top, not a weight)",
        "Injury and inactive status can reduce near-term usefulness. Dynasty value "
        "is not zeroed out for a typical injury, but current-season usefulness can "
        "be discounted more sharply.",
    ),
)

#: The age band shown on Player Detail ("Enters Prime" / "In Prime" / "Past
#: Prime") comes directly from the same age curve behind the 18% weight
#: above — the range where that curve stays within 90% of its own peak for
#: the position. Numbers copied here as static text for the same reason
#: FACTORS is (see its comment); keep in sync by hand if the underlying age
#: curve changes.
PRIME_WINDOW_NOTE = (
    "Every player's age band on Player Detail — \"Enters Prime,\" \"In Prime,\" or "
    "\"Past Prime\" — comes directly from the same age curve used in the weighting "
    "above, not a separate projection. It marks the age range where that curve "
    "stays within 90% of its own peak for the position: roughly 20-24 for running "
    "backs, 20-26 for receivers, 21-28 for tight ends, and 21-32 for quarterbacks, "
    "matching how much longer those positions typically stay productive. It is "
    "descriptive, not predictive — it does not forecast a specific player's "
    "career, only where they sit against their position's typical shape."
)

PRODUCTION_VS_DYNASTY = (
    "Season scoring is one ingredient, not the whole recipe. Dynasty value also "
    "weighs age, remaining window, role, scarcity, and how the market already "
    "prices the player. That is why a high-scoring veteran can rank behind a "
    "younger player with a longer runway, and why this year's points per game "
    "should not be read as a finished dynasty ranking."
)

STRATEGY_INTRO = (
    "Your team's direction can change whether an asset is attractive even when "
    "the league-wide player value stays similar. FantasyGM Lab can auto-read a "
    "direction from the roster or follow a manager override."
)

STRATEGY_ITEMS = (
    ("Contender", "Leans toward present production and useful starters, and treats future picks a bit more cheaply."),
    ("Fringe contender", "Looks for lineup upgrades without spending the entire future."),
    ("Retool", "Keeps a blend of current production, young starters, and draft capital."),
    ("Rebuild", "Favors youth and draft capital, and is slower to pay up for aging veterans."),
    ("Tank / rebuild", "Puts even more weight on picks and young players over short-term scoring."),
)

LENS_NOTE = (
    "Separately, a valuation lens can lean Dynasty, Rebuild, or current-season. "
    "That lens changes how much long-term value versus this-year usefulness is "
    "emphasized. The current evaluation philosophy is a balanced dynasty approach; "
    "additional philosophies are not selectable yet."
)

PICKS_COPY = (
    "Draft picks are valued as future assets, not as named prospects. Round "
    "matters most. Expected range — early, middle, or late in the round — is "
    "estimated from the original team's current standing, and later-year picks "
    "are treated with more uncertainty. Superflex and 2QB formats raise early-round "
    "pick value. Tight-end premium can lift early picks slightly. Larger dynasty "
    "leagues make picks a bit more important. Rebuild-oriented teams treat picks as "
    "more valuable; contenders treat them as a little cheaper. In redraft, picks "
    "are discounted heavily. A pick is not a guarantee of a specific player."
)

RECS_VS_RANKS = (
    "Rankings order eligible skill players by the league-adjusted evaluation. "
    "Trade recommendations start from those values, then ask a different question: "
    "is this a realistic deal for these two rosters right now?"
)

RECS_BULLETS = (
    "Roster fit and positional need on your team",
    "Whether the other manager has a reason to do the deal",
    "Whether the headline players and picks look fair enough to be taken seriously",
    "Team direction — contending versus collecting future value",
    "Protected or core players that should not be shopped casually",
    "Whether current player-status evidence is strong enough to show the idea",
)

CONFIDENCE_COPY = (
    "Confidence is not a prediction score. It describes how complete the current "
    "evidence is. Incomplete identity or status information can lower confidence "
    "or keep a recommendation off the board instead of guessing. Injury notes can "
    "qualify an otherwise strong-looking trade. Opportunity reads also carry their "
    "own confidence when workload evidence is thin."
)

DOES_NOT_CLAIM = (
    "It does not predict the future or guarantee wins, playoff odds, or trade outcomes.",
    "It does not claim perfect accuracy, complete injury news, or up-to-the-minute reporting.",
    "It is not gambling, betting, or financial advice.",
    "It does not replace league rules, film study, or your judgment.",
    "A ranking, a value, and a trade recommendation are related tools — not identical answers.",
)

FAQ = (
    (
        "Why might two leagues show different values for the same player?",
        "Scoring, quarterback format, tight-end premium, starter counts, league size, "
        "and taxi or bench depth all change how positions are priced. Values are "
        "rebuilt for the active league's settings.",
    ),
    (
        "Why might two managers in the same league see different trade ideas?",
        "Each roster has a different mix of needs, direction, protected players, and "
        "partners. A win-now team and a rebuilding team should not get the same shopping list.",
    ),
    (
        "If a player is scoring a lot, why isn't that the ranking?",
        "Production is included, but age, role, scarcity, and market context still "
        "matter. Dynasty value is about the remaining asset, not only this season's box score.",
    ),
    (
        "Can a recommendation disappear even if the values look close?",
        "Yes. Guardrails can withhold or qualify ideas when player identity, ownership, "
        "or current status cannot be trusted, or when a package would move a protected core piece without a clear upgrade.",
    ),
)

REQUIRED_USER_PHRASES = (
    "Value is league-specific",
    "Superflex",
    "tight-end premium",
    "age",
    "production",
    "draft picks",
    "rankings",
    "trade recommendations",
    "confidence",
    "does not predict the future",
)

FORBIDDEN_USER_SUBSTRINGS = (
    "apply_valuation",
    "dynasty_score",
    "value_score",
    "FantasyCalc",
    "COMPOSITE_WEIGHT",
    "Trust Engine",
    "st.session_state",
    "AI-powered",
    "artificial intelligence",
    "guarantees wins",
)


def _card(title: str, body: str, *, extra_class: str = "") -> str:
    klass = "methodology-card dg-preset-secondary"
    if extra_class:
        klass = f"{klass} {extra_class}"
    return (
        f"<article class='{klass}'>"
        f"<h3 class='methodology-card-title'>{escape(title)}</h3>"
        f"<p class='methodology-copy'>{escape(body)}</p>"
        "</article>"
    )


def methodology_page_html() -> str:
    factors = "".join(
        _card(title, body, extra_class="methodology-factor") for title, body in FACTORS
    )
    strategies = "".join(
        (
            "<div class='methodology-strategy'>"
            f"<div class='methodology-strategy-label'>{escape(label)}</div>"
            f"<p class='methodology-copy'>{escape(body)}</p>"
            "</div>"
        )
        for label, body in STRATEGY_ITEMS
    )
    rec_items = "".join(f"<li>{escape(item)}</li>" for item in RECS_BULLETS)
    limits = "".join(f"<li>{escape(item)}</li>" for item in DOES_NOT_CLAIM)
    faqs = "".join(
        (
            "<details class='methodology-faq-item'>"
            f"<summary>{escape(question)}</summary>"
            f"<p class='methodology-copy'>{escape(answer)}</p>"
            "</details>"
        )
        for question, answer in FAQ
    )
    return (
        "<article class='methodology-page'>"
        "<header class='methodology-hero dg-preset-command'>"
        f"<p class='methodology-kicker'>{escape(PAGE_KICKER)}</p>"
        f"<h1 class='methodology-title'>{escape(PAGE_TITLE)}</h1>"
        f"<p class='methodology-lede'>{escape(HERO_SUMMARY)}</p>"
        "</header>"
        "<section class='methodology-section' aria-labelledby='methodology-league'>"
        "<h2 id='methodology-league' class='methodology-heading'>Value is league-specific</h2>"
        f"<p class='methodology-copy'>{escape(LEAGUE_INTRO)}</p>"
        "</section>"
        "<section class='methodology-section' aria-labelledby='methodology-factors'>"
        "<h2 id='methodology-factors' class='methodology-heading'>What goes into a player evaluation</h2>"
        f"<div class='methodology-factor-grid'>{factors}</div>"
        "</section>"
        "<section class='methodology-section' aria-labelledby='methodology-player-tiers'>"
        "<h2 id='methodology-player-tiers' class='methodology-heading'>Player tiers</h2>"
        "<p class='methodology-copy'>Portrait frames on Player Quick View and My Team show how important a player is. Role and opportunity labels still describe how they are used.</p>"
        f"{player_tier_legend_html(disclosure=False)}"
        "</section>"
        "<section class='methodology-section' aria-labelledby='methodology-production'>"
        "<h2 id='methodology-production' class='methodology-heading'>Production vs dynasty value</h2>"
        f"<p class='methodology-copy'>{escape(PRODUCTION_VS_DYNASTY)}</p>"
        "</section>"
        "<section class='methodology-section' aria-labelledby='methodology-prime-window'>"
        "<h2 id='methodology-prime-window' class='methodology-heading'>Prime window</h2>"
        f"<p class='methodology-copy'>{escape(PRIME_WINDOW_NOTE)}</p>"
        "</section>"
        "<section class='methodology-section' aria-labelledby='methodology-strategy'>"
        "<h2 id='methodology-strategy' class='methodology-heading'>Team strategy matters</h2>"
        f"<p class='methodology-copy'>{escape(STRATEGY_INTRO)}</p>"
        f"<div class='methodology-strategy-list'>{strategies}</div>"
        f"<p class='methodology-copy'>{escape(LENS_NOTE)}</p>"
        "</section>"
        "<section class='methodology-section' aria-labelledby='methodology-picks'>"
        "<h2 id='methodology-picks' class='methodology-heading'>How draft picks are treated</h2>"
        f"<p class='methodology-copy'>{escape(PICKS_COPY)}</p>"
        "</section>"
        "<section class='methodology-section' aria-labelledby='methodology-recs'>"
        "<h2 id='methodology-recs' class='methodology-heading'>Why trade recommendations differ from rankings</h2>"
        f"<p class='methodology-copy'>{escape(RECS_VS_RANKS)}</p>"
        f"<ul class='methodology-list'>{rec_items}</ul>"
        "</section>"
        "<section class='methodology-section' aria-labelledby='methodology-confidence'>"
        "<h2 id='methodology-confidence' class='methodology-heading'>Confidence and uncertainty</h2>"
        f"<p class='methodology-copy'>{escape(CONFIDENCE_COPY)}</p>"
        "</section>"
        "<section class='methodology-section methodology-limits' aria-labelledby='methodology-limits'>"
        "<h2 id='methodology-limits' class='methodology-heading'>What FantasyGM Lab does not claim</h2>"
        f"<ul class='methodology-list'>{limits}</ul>"
        "</section>"
        "<section class='methodology-section' aria-labelledby='methodology-faq'>"
        "<h2 id='methodology-faq' class='methodology-heading'>Common questions</h2>"
        f"<div class='methodology-faq'>{faqs}</div>"
        "</section>"
        "</article>"
    )


def render_methodology_page() -> None:
    inject_global_styles(METHODOLOGY_PAGE_CSS)
    render_html_fragment(methodology_page_html())
