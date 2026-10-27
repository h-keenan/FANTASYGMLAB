# App vs web visual parity audit (pass 4, 2026-10-27)

Trigger: coridian_, "app UI still needs to be closer to web". Builds on the
2026-10-24 structural audit (`web-app-parity-audit-2026-10.md`), the module
inventories (`ui-module-inventory*.md`, owner picked all A) and parity passes
1-3 (#1536, #1537, #1538).

## Method and confidence

Code-and-token comparison only: `web-next/src/app/globals.css` and the web
components against `mobile/src/theme.ts`, `lib/glass.ts` and the mobile
screens/components, side by side. **Nothing was run or screenshotted** (no
simulator, build or Expo, per the RAM order), so every row marked "visual
unverified" needs an eyeball pass on a device before it is called done.
Size: S under half a day, M about a day, L multi-day or needs a decision.

Owner and standing rules applied: one shared module with variants, fixed
semantic colors (red send, green get), GM orb never redesigned per screen,
web/app parity, app analytics stay off.

## Token deltas

| Token | Web | App (before) | Status |
|---|---|---|---|
| Danger | `#ef4444` / light `#c81111` | `#FF4D4D` / `#D92D2D` | Fixed: synced |
| Success | `#22c55e` / light `#147337` | `#22C55E` / `#178A43` | Fixed: light synced |
| Warning | `#f59e0b` / `#8a5906` | no token | Fixed: `warning`, `warningMuted` added (unused yet) |
| Accent strong (solid-fill cyan) | `#22d3ee` / `#08616e`, used by primary Button | not present, Button used `accent` `#67e8f9` | Fixed: `accentStrong`; Button primary uses it |
| Card/panel radius | `--radius-panel` 20 | cards 14 | Fixed in `AnimatedCard`/`GlassCard` (visual unverified) |
| Input chrome | `.glass-input` fill + rim, radius 14 | solid surface, radius 10 | Fixed: `glassInput`/`glassInputBorder` tokens, `radii.input` |
| Position hues | `--color-position-*` | same values | Aligned, now asserted by test |
| Spacing / radii scale | 4/8/12/16/24; 10/14/20 | same | Aligned, now asserted by test |
| Text greys, neutral surface ramp, borders | neutral gray (`#1f2226` cards, `#e5e7eb` secondary, `#a8adb7` muted) | navy-tinted ramp | Fixed (pass 5, owner: "sync the palette to web"): see Pass 5 below |
| Premium gold text | `--color-premium` = `#facc15` | `#E8B13A` (richer amber, #1474) | Intentional, leave |

`mobile/src/lib/webTokenSync.test.ts` now reads `globals.css` and fails if the
semantic palette, position hues, spacing or radii drift.

## Per-screen deltas

| Screen | Element | Web vs app | Fix | Size | Status |
|---|---|---|---|---|---|
| All | Section titles | Web 21.6px/900 primary uppercase; app 12px/700 tertiary | `SectionHeading` 17/900 primary | S | Fixed (visual unverified) |
| Dashboard, Matchup | Page title | Web 24/900; app 22/800 | `PageTitle` 24/900 | S | Fixed |
| All | Status badges | Web 12/10px, 0.085em tracking; app 10/9 | `ToneBadge` 11/10, 0.9/0.85 tracking (same family as PositionBadge 11) | S | Fixed |
| Dashboard | Top priority give/get | App had local bar + "YOU GIVE" label; web `ExchangeSide` ("You send"/"You get", dot, 6% wash) | Shared `ExchangeSide` | S | Fixed |
| Dashboard, Portfolio | Briefing signal trade package | Local `YOU SEND/YOU GET` text labels | Same `ExchangeSide` | S | Fixed |
| GM Plan | Trade teaser sides | Local labels | Same | S | Fixed |
| Trade Hub / Finder | Idea card sides | Cyan-tinted boxed sides, "You Receive" on Finder; web 6% red/green wash, "You get" | Same | S | Fixed (visual unverified) |
| Trade Analyzer | Side labels | "You Send/You Receive"; web "You send/You receive" | `TRADE_SIDE_LABEL` | S | Fixed (copy). Interactive `TradeSide` card chrome unchanged |
| Nav, orb, quick actions | Labels | App "Trades", "Teams", "Rankings", "College Prospects"; web "Trade Hub", "League Rankings", "Players", "College Scouting" | Strings synced (screen titles, orb list, Dashboard tiles, More) | S | Fixed. Route names unchanged |
| Dashboard, My Team | Local trade/tier/outlook badges | Hand-rolled pills | `ToneBadge` | S | Fixed |
| All forms | Text input | Solid fill, radius 10 | `Input` glass chrome | S | Fixed |
| All | Primary button fill | `accent` light cyan | `accentStrong` | S | Fixed |
| All | Button disabled | Web muted surface fill + muted ink (outline: strong border); app 50% opacity | Per-variant disabled fill/ink/border; `loading` keeps the fade | S | Fixed (pass 5, visual unverified) |
| All | Button size `sm` | Web `size="sm"` | `size?: 'sm' \| 'md'` (36px min, 12px-class label) | S | Fixed (pass 5) |
| All | `EmptyState` | Web left-aligned glass card, bold 14 title, muted 12 subtitle, no icon, `sm` button | Shared component restyled onto `GlassCard`; props unchanged (`icon` accepted, not drawn); stretches full width | M | Fixed (pass 5, visual unverified). Per-screen copy not re-audited |
| ~28 files | Direct `colors.glass` reads | Mostly chips, grouped-row cards and sticky bars, token-identical to `GlassCard` but with own padding/radius | Migrate only true cards (PlayerDetail `card`, GmPlan watch card); the rest are not cards | M | Open, no visual delta expected |
| Player view | Quick view and detail hierarchy | Web `PlayerQuickView` vs app sheet; tabs match | Not re-audited this pass | S verify | Open |
| Waivers | Section order and copy | Matches web (Top target, More adds, Position Snapshot, All Free Agents, GM Targets) | none | - | Aligned |
| My Team | Section order | Snapshot, analysis, roster tabs, composition, keepers all present | none | - | Aligned |
| Premium / Onboarding / Auth | Buttons and inputs | Moved to shared `Button`/`Input` in passes 1-2; now also inherit the tokens above | none | - | Aligned |
| Settings / More | Identity card, Preferences card | Done in the 2026-10-24 follow-ups | none | - | Aligned |
| News, Rankings/Values | Matched-player identity | Done in #1506; Values lists use `PlayerIdentityRow` | none | - | Aligned |

Rows for section titles, page title, badges, card radius and Input ship in the second PR (typography and chrome), the rest in the first.

## Pass 5 (2026-10-27): palette sync and EmptyState

Neutral ramp synced to web (dark / light): `background` `#000000` / `#eef3f6`; `surface`, `surfaceSolid` `#1f2226` / `#ffffff`; `backgroundElevated` `#3d4248` (web raised) / `#e6edf1` (web muted; light raised is plain white and would erase chips and tracks); `border` `#2a2e35` / `#c7d3da`; `borderStrong` `#64748b` / `#5d6b77`; text `#f7f8fa`, `#e5e7eb`, `#a8adb7` / `#101820`, `#3b4a56`, `#57646f`; `textDisabled` = web `--color-muted` composited over background (`#777879` / `#8a9096`); light soft fills and `violet` synced. Left as intentional app divergences: glass fills, `cardBorder` cyan rim, premium gold text.

Contrast: every text step (primary, secondary, muted) clears AA (4.5:1) on background, surface and backgroundElevated in both themes, asserted in `webTokenSync.test.ts` and `glass.test.ts`. The tightest pair is dark muted on `#3d4248` at 4.50:1. No neutral value needed a lightness adjustment. Known shortfall, inherited from web and not adjusted (changing it would break the red-send parity the test asserts): semantic colors as small text on the lighter dark surfaces. Danger `#ef4444` is 4.24:1 on `#1f2226` and 2.69:1 on `#3d4248`; success 4.45:1 and violet 3.72:1 on `#3d4248`; light premium text 4.50:1 on `#e6edf1`. Large or bold uses pass 3:1 on surface. Follow-up if wanted: a lighter dark-mode `dangerText` token.

## Unverified visuals (need a device pass)

- Pass 5: dark cards are now neutral gray `#1f2226` (lighter than the old navy `#0D1117`), chips and tracks `#3d4248`; secondary and muted text steps sit closer together.
- Pass 5: EmptyState as a glass card on screens that centered it full-screen, and inside lists or other cards (double chrome risk). Per-screen empty-state copy was not re-audited.
- Pass 5: disabled buttons on black (dark muted fill is pure black, as on web).
- Section title at 17/900 in dense cards (one-line truncation) and in the Dashboard header at 24/900.
- 20px card radius against full-bleed children and `AccentCard`'s 3px left rail.
- `ExchangeSide` wash opacity (6%) on light glass; Trade Hub two-column sides at narrow widths.
- Glass input fill on light backgrounds.

## Remaining ranked

1. Dark-mode `dangerText` token (semantic text AA on lighter surfaces).
2. Per-screen EmptyState copy audit against web.
3. Migrate the genuine `colors.glass` cards to `GlassCard` (optional `padding="lg"`).
4. Player quick view vs detail hierarchy pass.
