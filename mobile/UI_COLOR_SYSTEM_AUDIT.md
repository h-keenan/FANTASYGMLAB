# FantasyGM Lab — Color System + Dark/Light Mode Audit

> Sent by coridian_ via Discord, 2026-09-25. Required before finalizing the UI overhaul. Applies
> to both the mobile app's `theme.ts` and the web app's `modules/design_tokens.py`.

FantasyGM Lab must have a deliberate, accessible color system in both dark mode and light mode. Do
not assume a color that works on the dark theme automatically works on the light theme.

## 1. Audit the tokens, not just individual screens

Inspect the global theme/style system and identify the canonical tokens for: app background,
elevated surface, secondary surface, card surface, interactive surface, primary text, secondary
text, muted text, subtle border, strong border, primary cyan, positive green, amber/caution,
red/injury/negative, purple/analytics, disabled state, selected state, hover/pressed state, focus
state, chart colors, percentile colors. There should be explicit values for both dark and light
themes — do not rely on one palette with only the background swapped.

## 2. Dark mode audit

Check that: cards do not disappear into the background; borders are visible without glowing
everywhere; muted text remains readable; inactive controls remain distinguishable; cyan does not
bleed into similarly colored surfaces; green does not become indistinguishable from cyan; amber
remains readable against dark surfaces; red status states remain visible without becoming overly
aggressive; disabled elements still look intentionally disabled rather than broken. Avoid multiple
dark surfaces that are so similar they visually merge.

## 3. Light mode audit

Light mode must be designed intentionally, not derived by inverting dark mode. Check that: cyan
accents remain visible on white/light backgrounds; pale cyan does not disappear; green remains
readable; amber has sufficient contrast; red retains strong contrast; secondary text is not too
faint; neutral borders are visible; cards can be distinguished from the page background; disabled
controls are identifiable; selected chips/tabs do not become washed out.

## 4. Semantic color consistency

Preserve one meaning per color family, in both themes:
- **Cyan** = primary interaction, active navigation, GM intelligence
- **Green** = positive, healthy, upside, favorable value
- **Amber/Gold** = opportunity, pending, caution, draft/FAAB context
- **Red** = injury, urgent risk, negative state
- **Purple** = secondary analytics / informational category
- **Gray/Slate** = neutral, secondary, inactive

Do not let the light theme reinterpret semantic colors.

## 5. Contrast requirement

Audit text and interactive-state contrast (standard accessibility contrast). At minimum verify:
body text, secondary text, small labels, text inside colored chips, text inside buttons,
selected/unselected tabs, disabled text, chart labels, percentile labels, injury/status badges. Do
not rely on color alone to communicate injury, selected state, rank trend, positive/negative
movement, or warning state — pair color with icon, label, shape, or typography where appropriate.

## 6. State matrix

For each shared component, validate default, selected, pressed, disabled, positive, warning,
negative, and informational states in both dark mode and light mode. Pay special attention to:
buttons, chips, segmented controls, navigation rows, player rows, metric cards, recommendation
cards, alerts, dropdowns, text inputs.

## 7. Visual separation

Every major surface should have enough separation from adjacent surfaces. Avoid: dark-on-dark
blending, white-on-light-gray blending, border colors that are nearly invisible, muted text that
looks disabled, selected states that barely differ from unselected states. Use a combination of
surface tone, border, shadow, fill, and typography rather than relying only on brightness.

## 8. Cyan brand color

`#00D4FF` remains the primary brand cyan. It does not need to be used at full intensity everywhere
— create theme-appropriate variants (primary cyan, cyan hover/pressed, cyan muted, cyan
tint/background, cyan border) so the brand remains recognizable without overwhelming either theme.

## 9. Charts + analytics

Charts, percentile bars, value indicators, and trend graphics must also be audited in both themes.
Ensure neighboring series remain distinguishable, grid lines are visible but subtle, percentile
colors remain distinct, labels remain readable, and positive/negative states are not ambiguous. Do
not use nearly identical colors for adjacent data series.

## 10. Screenshot audit

After theme work is complete, check representative surfaces in both themes for at least: League
Overview, Player Detail, My Team, Waivers, Trade Hub, Matchup, Next Move, Navigation Sheet.
Compare readability, hierarchy, card separation, active states, semantic colors, and muted
information. If any screen relies on colors that disappear or visually blend in one theme, update
the shared token rather than fixing only that screen.

## 11. Report the audit

After completing the audit, report: dark-mode tokens changed, light-mode tokens changed, contrast
issues found, components affected, semantic colors adjusted, screens visually checked, any
remaining exceptions.

**No page-specific color patching unless absolutely necessary. If a color fails in multiple
places, fix the shared token.** (Also added to `UI_HIERARCHY_DIRECTIVE.md` §25.)
