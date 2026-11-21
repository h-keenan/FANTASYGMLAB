# App UI audit, 2026-11-21 (static)

Scope: mobile theme tokens and shared components vs web-next.

## Tokens
Neutral ramp, text, borders, accent, status, money, opportunity and premium colors already mirror web-next
`globals.css` (enforced by `mobile/src/lib/webTokenSync.test.ts`). No token drift found. Remaining intentional
differences: `cardBorder` (cyan-tinted card rim, AnimatedCard only) and liquid-glass fills (`lib/glass.ts`).

## Fixed in this PR (shared components only)
- Stat tile labels truncated ("THIS SEA...", "STARTER..."): MetricCard centered labels now wrap to 2 lines;
  StatStripModule tiles use the same short nouns as its summary line (Starters, Bench).
- "Plan ahead" NextSteps buttons wrapped 2 + 1 at uneven widths: two steps share a row at equal width, three or more
  stack at full width.
- Header see-through and orb overlap: already handled in main (HeaderBackdrop blur + opaque wash on every stack header;
  useOrbClearance bottom padding on My Team, Dashboard and other scroll screens). Screenshot likely predates those
  builds; no further change needed.

## Open mismatches (not changed)
- Mobile card radius/shadow follows the glass recipe, web uses `--shadow-card` flat offset; keep (frosted look is a rule).
- Web `--color-prestige-*` / `--color-tier-*` / `--color-position-*` palettes should be re-verified against mobile
  `playerTier` / `PositionBadge` colors (position badge redesign already pending per owner).
- Type scale: mobile uses ad-hoc 12 / 12.5 / 13.5 / 15.5 sizes per component; web uses rem tokens. A shared
  mobile type-scale token would be the principled fix (larger change).
- TradesScreen has no direct orb clearance; relies on child screens.
