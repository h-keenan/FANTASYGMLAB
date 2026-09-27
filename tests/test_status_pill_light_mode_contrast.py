"""Regression test: dg-status-badge/dg-tier-chip/glyph-chip text stays legible in light mode.

Bug found in a web UI audit pass (2026-09-26): the status pills rendered on every
player card (modules/player_cards.PLAYER_STATUS_STYLES -> ``.dg-status-badge-*``
in modules/app_styles.py), the tier chips (``tier_chip_html`` -> ``.dg-tier-*``), the
glyph chips used for injury status (``glyph_chip_html`` -> ``.dg-glyph-chip-*``, e.g.
"Healthy" / "Injury Watch" in app.py), and the ``.player-support-chip-*`` family all
hardcoded near-white pastel hex literals (e.g. ``#99f6e4``, ``#fde68a``, ``#e9d5ff``,
``#cbd5e1``, ``#fecaca``) as their ``color:`` value. Those literals were tuned only
for readability against the app's near-black dark-mode surfaces. Once light ("Day")
mode shipped (PR #794 / modules/design_tokens.LIGHT_MODE_CSS), the same pastel text
sat on the corresponding pale/near-white soft-tint chip background, so status text
like "Injury Watch" and every player-card tier badge became very low contrast /
effectively invisible in light mode. None of these classes had a light-mode override.

The fix replaces every such hardcoded ``color:`` literal with the matching semantic
design token (e.g. ``var(--color-warning)``, ``var(--color-opportunity)``), each of
which already has an independently contrast-audited light-mode value in
modules/design_tokens.LIGHT_MODE_TOKENS. ``.player-support-chip-premium`` was also a
straight copy-paste bug: its background was the gold/premium family
(``rgba(250, 204, 21, ...)`` == ``--color-premium``/``--color-action``) but its text
was the *amber/warning* pastel (``#fde68a``) instead of the matching gold pastel --
now both resolve to ``var(--color-premium)``.

A second, separate bug in the same component family was found alongside the pastel
one: "UI Constitution + Interaction Reliability V1" (commit 41eae5c9, PR #366)
renamed the HTML markup ``player_status_pill_html`` emits from
``player-status-pill player-status-pill-{tone}`` to
``dg-status-badge dg-status-badge-{tone}``, but never renamed (or duplicated) the
matching CSS selectors in modules/app_styles.py. Every ``.player-status-pill*`` rule
-- the base shape/box-model rule, all 12 tone-color variants, and several responsive/
nested-context overrides -- became permanently unreachable dead code (confirmed: no
code anywhere emits the old class name; tests/test_ui_constitution_v1.py and
tests/test_player_cards.py even assert ``"player-status-pill" not in html``), while
the live ``.dg-status-badge``/``.dg-status-badge-*`` classes received no background,
border, padding, or tone color from anywhere -- only a bare ``border-radius: 0`` from
modules/component_family_styles.py's shared reset. Every player-card status badge
("Elite", "Starter", "Trade Candidate", etc.) has been rendering as unstyled plain
text, with no chip/pill treatment at all, since that commit. The fix renames every
``player-status-pill`` occurrence in modules/app_styles.py to ``dg-status-badge``,
reattaching the already-tokenized shape and color rules to the class the markup
actually emits.
"""

from __future__ import annotations

from modules.app_styles import APP_CSS
from modules.startup_coordinator import StartupPhase, startup_shell_html

# Every pastel/light literal that was hardcoded as a `color:` value for one of the
# affected chip/pill families. These were tuned for dark backgrounds only and must
# not reappear as raw text-color literals in APP_CSS.
_FORMER_DARK_ONLY_TEXT_HEX = (
    "#99f6e4",  # dg-glyph-chip-success / dg-tier-starter (teal-200)
    "#fef08a",  # dg-tier-elite (gold-200)
    "#e9d5ff",  # dg-glyph-chip-premium / dg-tier-star (purple-200)
    "#fef3c7",  # player-status-pill-elite / -contributor (amber-100)
    "#f3e8ff",  # player-status-pill-star (purple-100)
    "#dbeafe",  # player-status-pill-core (blue-100)
    "#ccfbf1",  # player-status-pill-starter / -rise (teal-100)
    "#fecaca",  # player-status-pill-risk / -drop / player-support-chip-risk (red-200)
    "#bbf7d0",  # player-support-chip-success (green-200)
    "#fdba74",  # player-support-chip-warning (orange-300)
)

# #fde68a and #cbd5e1 and #e2e8f0 remain intentionally elsewhere (e.g.
# .app-degraded-state pairs its literal text with an equally fixed, theme-independent
# dark banner background), so this test checks the specific selector blocks rather
# than banning the hex globally.
_FIXED_SELECTOR_BLOCKS = (
    ".dg-glyph-chip-success",
    ".dg-glyph-chip-warning",
    ".dg-glyph-chip-premium",
    ".dg-tier-elite",
    ".dg-tier-star",
    ".dg-tier-starter",
    ".dg-tier-contributor",
    ".dg-tier-depth",
    ".dg-tier-developmental",
    ".dg-status-badge {",
    ".dg-status-badge-elite",
    ".dg-status-badge-star",
    ".dg-status-badge-core",
    ".dg-status-badge-starter",
    ".dg-status-badge-contributor",
    ".dg-status-badge-move",
    ".dg-status-badge-hold",
    ".dg-status-badge-risk",
    ".dg-status-badge-drop",
    ".dg-status-badge-neutral",
    ".player-support-chip {",
    ".player-support-chip-success",
    ".player-support-chip-warning",
    ".player-support-chip-premium",
    ".player-support-chip-hold",
    ".player-support-chip-risk",
)


def _rule_block(css: str, selector: str) -> str:
    start = css.index(selector)
    open_brace = css.index("{", start)
    close_brace = css.index("}", open_brace)
    return css[start : close_brace + 1]


def test_status_and_tier_chip_families_have_no_dark_only_pastel_text():
    for selector in _FIXED_SELECTOR_BLOCKS:
        block = _rule_block(APP_CSS, selector)
        for hex_value in _FORMER_DARK_ONLY_TEXT_HEX:
            assert hex_value not in block, (selector, hex_value)


def test_status_and_tier_chips_use_semantic_color_tokens():
    expected_tokens = {
        ".dg-glyph-chip-success": "var(--color-opportunity)",
        ".dg-glyph-chip-warning": "var(--color-warning)",
        ".dg-glyph-chip-premium": "var(--color-diagnostic)",
        ".dg-tier-elite": "var(--color-premium)",
        ".dg-tier-star": "var(--color-diagnostic)",
        ".dg-tier-starter": "var(--color-opportunity)",
        ".dg-tier-contributor": "var(--color-warning)",
        ".dg-tier-depth": "var(--color-text-secondary)",
        ".dg-tier-developmental": "var(--color-text-secondary)",
        ".dg-status-badge-elite": "var(--color-premium)",
        ".dg-status-badge-star": "var(--color-diagnostic)",
        ".dg-status-badge-core": "var(--color-accent)",
        ".dg-status-badge-contributor": "var(--color-warning)",
        ".dg-status-badge-move": "var(--color-warning)",
        ".dg-status-badge-hold": "var(--color-text-secondary)",
        ".dg-status-badge-risk": "var(--color-danger)",
        ".dg-status-badge-drop": "var(--color-danger)",
        ".dg-status-badge-neutral": "var(--color-text-secondary)",
        ".player-support-chip-success": "var(--color-success)",
        ".player-support-chip-warning": "var(--color-warning)",
        ".player-support-chip-premium": "var(--color-premium)",
        ".player-support-chip-hold": "var(--color-text-secondary)",
        ".player-support-chip-risk": "var(--color-danger)",
    }
    for selector, token in expected_tokens.items():
        block = _rule_block(APP_CSS, selector)
        assert f"color: {token};" in block, (selector, token)


def test_startup_splash_text_is_not_hardcoded_white():
    # Bug: the app's startup/loading splash (modules/startup_coordinator, shown on
    # every app boot via StartupCoordinator._render -> startup_shell_html) hardcoded
    # `color: #f8fafc` (near-white) on ``.dg-startup-card`` and
    # ``.dg-startup-badge-wrap .dg-founder-badge__copy strong`` while its own
    # background resolves through the theme-adaptive ``var(--color-bg, ...)`` /
    # ``var(--color-shell, ...)`` tokens. In light mode those tokens resolve to a
    # near-white background, so the splash text became white-on-white (its sibling
    # rule, ``.dg-startup-status``, already used ``var(--color-text-secondary, ...)``
    # correctly -- these two were simply inconsistent with it).
    html = startup_shell_html(StartupPhase.PAGE_READY)
    assert "color: #f8fafc;" not in html
    assert html.count("color: var(--color-text-primary, #f8fafc);") >= 2


def test_player_support_chip_premium_no_longer_mismatches_its_own_gold_background():
    # Regression for the copy-paste bug: background was the gold/premium family
    # (rgba(250, 204, 21, ...) == #facc15 == --color-premium) but text was the
    # amber/warning pastel (#fde68a) instead of the matching gold token.
    block = _rule_block(APP_CSS, ".player-support-chip-premium")
    assert "rgba(250, 204, 21" in block
    assert "color: var(--color-premium);" in block
    assert "#fde68a" not in block


def test_free_agent_tag_emphasis_uses_token():
    # Same dark-only-pastel bug in one more live, single-instance selector:
    # .free-agent-tag-emphasis (modules/app_styles.py, used on the Waivers page).
    tag_block = _rule_block(APP_CSS, ".free-agent-tag-emphasis")
    assert "color: var(--color-opportunity);" in tag_block
    assert "#99f6e4" not in tag_block


def test_app_degraded_state_keeps_fixed_light_text_on_its_fixed_dark_banner():
    # NOT a bug: every .app-degraded-state background rule in APP_CSS (the
    # circuit-breaker/degraded-mode banner rendered by modules/draft_center_ui.py
    # and app.py) is a fixed near-black gradient with `!important`, in both
    # themes -- there is no light-mode override anywhere for its background.
    # Its text must stay a fixed light literal; swapping it for the semantic
    # --color-warning token (which resolves dark in light mode) would make the
    # banner's text unreadable against a card that never lightens.
    assert (
        ".app-degraded-state {\nborder-color: rgba(245, 158, 11, 0.24);\n"
    ) in APP_CSS
    block = _rule_block(APP_CSS, ".app-degraded-state {\nborder-color")
    assert "color: #fde68a;" in block
    assert "var(--color-warning)" not in block


def test_dg_glyph_chip_success_important_override_uses_token():
    # modules/app_styles.py redeclares .dg-glyph-chip-success later in the file
    # (a `!important` "founder beta consistency" pass, ~line 5600) which wins
    # the cascade over the earlier, already-tokenized declaration near the top
    # of the file. That later block still hardcoded `color: #bbf7d0 !important`,
    # so the fix above the fold had no real effect on rendering: the "Healthy"/
    # opportunity glyph chip was still pastel-green-on-pastel-green in light
    # mode. Same bug, same fix, in the rule that actually wins.
    idx = APP_CSS.rindex(".dg-glyph-chip-success {")
    block = APP_CSS[idx : APP_CSS.index("}", idx) + 1]
    assert "color: var(--color-success) !important;" in block
    assert "#bbf7d0" not in block


def test_draft_review_grade_family_uses_semantic_tokens():
    # .draft-review-grade.grade-{strong,watch,risk,muted} hardcoded the same
    # dark-only pastel literals as the chip families above; only grade-solid
    # was already tokenized, indicating the others were a copy/paste that
    # never got updated when the token system landed. modules/app_styles.py
    # declares this family twice (an earlier, plain pass with no `color:` at
    # all, and a later `!important` pass that actually wins the cascade) --
    # use the last (winning) declaration of each.
    expected = {
        "grade-strong": ("var(--color-success)", "#bbf7d0"),
        "grade-watch": ("var(--color-warning)", "#fde68a"),
        "grade-risk": ("var(--color-danger)", "#fecaca"),
        "grade-muted": ("var(--color-experimental)", "#c7d2fe"),
    }
    for suffix, (token, old_hex) in expected.items():
        selector = f".draft-review-grade.{suffix} {{"
        idx = APP_CSS.rindex(selector)
        block = APP_CSS[idx : APP_CSS.index("}", idx) + 1]
        assert f"color: {token} !important;" in block
        assert old_hex not in block


def test_degraded_state_semantic_icon_keeps_fixed_light_color():
    # Same "always-dark card" exception as .app-degraded-state's own text
    # (see test_app_degraded_state_keeps_fixed_light_text_on_its_fixed_dark_banner):
    # this icon was split into its own rule so it keeps the fixed light
    # literal instead of --color-experimental, which resolves dark in light
    # mode and would be unreadable against this permanently-dark banner.
    block = _rule_block(APP_CSS, ".app-degraded-state .dg-semantic-icon {")
    assert "color: #c7d2fe;" in block
    assert "var(--color-experimental)" not in block

    # The other three selectors that used to share this rule sit on
    # token-backed (theme-aware) card surfaces, so they keep the token.
    shared_block = _rule_block(APP_CSS, ".home-command-card-draft .dg-semantic-icon,")
    assert "color: var(--color-experimental);" in shared_block
    assert "app-degraded-state" not in shared_block


def test_player_status_pill_class_name_is_fully_retired():
    # The Aug-2026 "UI Constitution" rename (commit 41eae5c9) moved the HTML markup
    # from player-status-pill to dg-status-badge but left the CSS selectors behind.
    # Guard against the dead name reappearing (e.g. a future edit copy-pasting from
    # git history) and against a partial rename that leaves some rules orphaned again.
    assert "player-status-pill" not in APP_CSS


def test_dg_status_badge_tone_variants_are_reachable_and_styled():
    # The core regression: modules/player_cards.player_status_pill_html emits
    # `dg-status-badge dg-status-badge-{tone}` for every tone in
    # modules/player_cards.PLAYER_STATUS_STYLES. Before the fix, none of these
    # tone-specific classes existed anywhere in APP_CSS (only a bare
    # `border-radius: 0` reset matched the base class), so every player-card status
    # badge rendered as unstyled plain text with no background/border at all.
    from modules.player_cards import PLAYER_STATUS_STYLES

    tones = {style["tone"] for style in PLAYER_STATUS_STYLES.values()}
    assert tones  # sanity: the source dict still has entries
    for tone in tones:
        block = _rule_block(APP_CSS, f".dg-status-badge-{tone}")
        assert "background" in block, tone
        assert "border-color" in block, tone

    # And the base class (shared shape: display/padding/border) is present too.
    base_block = _rule_block(APP_CSS, ".dg-status-badge {")
    assert "display: inline-flex;" in base_block
    assert "padding:" in base_block


def test_dg_smoke_card_glass_tokens_are_theme_aware():
    # Bug: --dg-smoke-dark/-mid/-border (the only three --dg-smoke-* custom
    # properties actually consumed via var(), by the shared "glass" background
    # rule for .home-command-card, .summary-tile, .decision-panel, .trade-card,
    # .free-agent-card, .roster-limit-stat, .platform-sidebar-card, and others)
    # were fixed near-black rgba literals with no light-mode counterpart, even
    # though --dg-smoke-light-ready / -light-border-ready sit right next to
    # them, unused -- clear evidence a light variant was prepared and never
    # wired in. Every one of those "smoke glass" cards rendered dark-tinted
    # regardless of the active theme. Fixed by deriving the three consumed
    # properties from existing surface/text tokens via color-mix(), so they
    # resolve per-theme automatically instead of needing a second literal.
    root_block = _rule_block(APP_CSS, "--dg-smoke-dark:")
    assert "color-mix(in srgb, var(--color-bg) 72%, transparent)" in root_block
    assert "color-mix(in srgb, var(--color-surface-secondary) 54%, transparent)" in root_block
    assert "color-mix(in srgb, var(--color-text-secondary) 13%, transparent)" in root_block
    assert "rgba(7, 8, 11, 0.72)" not in root_block
    assert "rgba(24, 25, 29, 0.54)" not in root_block

    # The consuming rule itself is untouched -- still reads through var(), so
    # every card in its selector list benefits without a per-card patch.
    glass_rule = _rule_block(APP_CSS, ".home-command-card,\n.team-identity-card,")
    assert "var(--dg-smoke-mid)" in glass_rule
    assert "var(--dg-smoke-dark)" in glass_rule
    assert "var(--dg-smoke-border)" in glass_rule
