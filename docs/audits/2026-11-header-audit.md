# Header audit (2026-11-14): phone shell, league switcher, Sim header

Requested by coridian_ ("header redesign audit, at least the league switcher"). Method: `scripts/sim_layout_playwright/header_audit.mjs` (shell header at 320/360/390/430, dark and light, long / short / no league name, 12 saved leagues, plus the Fantasy Sim game header from the sim fixture) and a read of `Header.tsx`, `ShellHeader.tsx`, `AlertsDropdown.tsx`, `SimGameHeader.tsx` and the app's `LeagueSwitcherHeaderButton`. The app (React Native) was read, not rendered. Mockups (V1/V2/V3, 390px): `docs/audits/ui-pass-6/ui-header-switcher.html` and `ui-header-bars.html`.

## Findings (measured unless marked code)

| # | Sev | Finding | Evidence | Status |
|---|---|---|---|---|
| 1 | High | Switcher menu clipped off the left edge at 320px (left -38px) | `LeagueLensPicker` menu `right-0 w-64` anchored to a chip that ends 102px from the right | Fixed in this PR (fixed panel under the header on phones) |
| 2 | High | Menu 775px tall with 12 leagues, no scroll: the last lens options sat under the bottom pill, unreachable | `scrolls:false`, bottom 827 of 844 with the pill over it | Fixed (max-height, scrolls inside) |
| 3 | High | Bell unread badge: white text on the cyan accent (contrast fail, the rule says never white on cyan) and 10px text (floor is 11) | `AlertsDropdown.tsx` badge `color: #fff; fontSize: 0.625rem` | Fixed (on-accent ink, 11px) |
| 4 | Med | League name ellipsized in the chip at every width (106px at 320, 216px at 430 for a 55-char name); the rule is that names never ellipsize | `truncate` on the chip's name span | Needs decision (switcher V1/V2/V3) |
| 5 | Med | Menu rows have no league avatar/crest, no platform, no record, no search, 11px text; current league is only a colour change | code + capture | decision |
| 6 | Med | No sample league and no Sim saves in the switcher; "+ Add another league" is the only extra | code | decision |
| 7 | Med | Switcher list comes from `supabase.from("saved_leagues")` with no order, no error or loading state: a failed load looks like "No other saved leagues" (also shown when the only row is the current league) | `HeaderLeagueControls` | decision (fold into the redesign) |
| 8 | Med | No keyboard support: menu is `role=menu` but has no arrow-key navigation, Escape or focus return (outside tap works through a hidden full-screen button) | code | decision (a shared `Sheet` gives all of it) |
| 9 | Med | Dropdown (not a sheet) on phone, while every other pop-up and the app's own switcher are sheets (app: `SheetModal`, 60% max height, `numberOfLines={1}` names) | code | decision |
| 10 | Low | Switcher chip has square corners next to 14px icon buttons; lens line was gold (fixed by D5, #1950) | capture | rides the redesign |
| 11 | Med | Sim game header is 97px tall at every width (icon row + full-width team row + status chips) vs the 52px desk shell header; team name wraps below its crest | `sim-game-header` capture | decision (Sim V3) |
| 12 | Low | Sim "S8 2033" season label only appears once the dynasty has more than one season, and the week label has no season context in a first season | `simCompactSeason` | decision |
| 13 | OK | No horizontal overflow at any width; shell header is 52px; icon targets are 44px; header band identical in light and dark | `header_audit.mjs` | - |
| 14 | Open | Safe areas / dynamic island: the shell header is `position: sticky; top: 0` with no `env(safe-area-inset-top)` padding in the web view (iOS PWA/standalone); app uses native header insets | code, not testable headless | verify on device |
| 15 | Open | Scroll behaviour: header is sticky and never collapses; the page tab strip pins under it (two sticky bars on phones with page tabs) | code | decision with V2 |

## Variants and recommendation

- **League switcher** (sheet 10): V1 bottom sheet with league cards (recommended), V2 fixed panel with crests and search, V3 league as the header title.
- **Page / Sim headers** (sheet 11): V1 one row with a crest chip for Desk (recommended), V2 title row plus league strip, V3 Sim header on one row (recommended for Sim: 97px to 52px).
- Both need a league avatar source (Sleeper avatar id, or the generated crest `TeamAvatar` already falls back to).

## What shipped here

Items 1 to 3 only (clipping and the badge), as obvious bugs. Everything else waits for a pick.
