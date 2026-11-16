# Motion audit, 2026-11-14

Scope: web (Desk + Sim) and app. Method: grep of every `transition` / `animation` / `Animated` / `LayoutAnimation` use, a read of the shared motion layer (`lib/motion.ts`, `Motion.tsx`, `Presence`), and the sample-league / Sim flows on the phone harness. The spec that came out of it is "Motion spec" in `docs/ui-patterns.md`.

## What already moves well (do not redo)

Press feedback everywhere (`PRESS`), `MotionIn` entrances, `CountUp` (recap and scores), `TickNumber` (live lineup numbers, PQV), `PulseOnIncrease` (tab and bell badges), `Presence`/`Collapse`/`PresenceSwap` (toasts, banners, every expander, Sim League view swap, pill page segment), skeletons (shimmer stops under reduced motion), confetti for a title only, the one-shot hero glow.

## 1. Places that still popped (before this PR)

| Place | What happened | Status |
|---|---|---|
| Progress bars (snapshot tiles, GM Plan, League Rankings, achievements, Sim progress, game progress, win probability) | fill set by `width`: jumped, or animated `width` (layout) | fixed: `ProgressFill` / `scaleX` (web + app) |
| Standings after a week | rows swapped places instantly; rank change only visible as a number | fixed: `useFlipList` / `ReorderRow` + `RankChip` |
| Success notices ("Trade done", claim landed) | static glyph; `.motion-success` existed but had no users | fixed: `SuccessCheck` in `SimNotice` |
| Number tweens | uncapped: every `TickNumber` could run its own rAF loop | fixed: `acquireTween` cap of 12 |
| Route changes (page to page) | hard cut; the new page's skeleton is the only continuity | fixed: `app/template.tsx` opacity fade (web), `animationDuration` on the token scale (app) |
| Tab content inside a page (Roster/Top moves/Trade in the sample) | content swapped instantly | fixed in the sample league (`PresenceSwap`, web + app); route-based family tabs are a route transition, still open |
| Fairness meter and Toggle knob (web) | glided `left`/`width` (layout) | fixed: transform only, allowlist entries removed |
| Trade accepted / declined state on a trade card | card is replaced by a notice; no state morph | fixed: `TradeResolvedRow` via `PresenceSwap` (`TradeCompactCard resolved`, Sim inbox keeps the answered offer 2s) |
| Draft pick landing / auto-pick | row slides away (`sim-row-drafted`), the pick itself does not land | fixed: the player pops into Your roster (`enter-pop` / `PopIn`) with an `Auto-picked` `PulseChip` (the board and roster are separate pill tabs, so no cross-list FLIP) |
| Week advance | `motion-sweep` band only; standings/scores update with no staging | fixed: scores already stagger in (`MotionIn`); standings rows now glide with a capped stagger (`useFlipList { stagger }` / `ReorderRow delay`) |
| Offseason transitions, onboarding steps | per-surface keyframes (0.28s/0.5s, own curves) | onboarding fixed (tokens, web + app); offseason keyframes already on the scale |
| Pull-to-refresh | native `RefreshControl` only (8 screens); no web equivalent | accepted |
| Grade reveal | `LetterGrade` appears fully formed | fixed for the big (lg) grade: `enter-pop` web / `PopIn` app |
| Pill/orb morphing | pill page segment now exits; orb morph is bespoke | partly |

## 2. Inconsistencies found

- **Layout-property transitions** (jank): `.pqv-avatar-glow`, `.pqv-peek-fold`, `.pqv-modal` (deliberate, sheet snap), onboarding dot width, `.pe-marker` left/bottom, PillRow underline `width` (two copies), `FairnessMeterRow`, `Toggle` knob `left`, plus the progress bars fixed here. Now guarded; the rest are allowlisted with a reason in `scripts/check_motion_usage.mjs`.
- **Durations off the token scale** (not 120/180/240/300): `160ms` tabs-slide x2, `150ms` portfolio-row-in, `140ms` confirm-in, `220ms` sheet-rise and tps-rise, `260ms` pill-fan / pill-context-in / action-bar-in, `0.28s` and `0.5s` onboarding, `0.2s`/`0.4s` legacy bars. None is wrong enough to break, but each should become a `--motion-*` var when touched.
- **Easings**: three hand-written beziers (`0.2,0.9,0.3,1` is `--ease-out`; `0.22,1,0.36,1` onboarding is not), plus bare `ease` / `ease-out` / `linear` in 40+ places.
- **Reduced motion**: every keyframe class has an `@media` block; the gaps were the new fills (now covered) and `useNativeDriver: false` paths in the app (Presence collapse, SegmentedTabBar indicator), which do respect `useReducedMotion` but run on the JS thread.
- **Long durations / loops**: ambient only (background field 14s, onboarding sweep 7-9s, glows 2.5s, shimmer 1.6s). All compositor-only after #1943/#1948; keep it that way.
- **LayoutAnimation**: two app uses remain (`animateRowExpand` for the Sim Move strip and the trade tweak toggle); layout-driven, allowlisted by the presence scan.

## 3. Built in this PR

`ProgressFill`, `RankChip`, `useFlipList` (web) / `ReorderRow` (app), `SuccessCheck`, `MOTION_ROLE`, `SPRING`, `acquireTween` cap, `progressScale` / `flipOffset` / `rankChange` pure rules (twin tests), the motion guard, the spec. Wired into: 8 web and 6 app progress bars, Sim standings (both layouts, web + app), every success `SimNotice`, `TickNumber` (both).

## 4. Ranked candidates (highest value first)

1. **Tab-content cross-fade** for page families and the sample league (`PresenceSwap` over the panel): the most visible remaining hard cut, ~12 pages, low risk.
2. **Route transition**: an opacity-only fade on the page container (no transform: it would break `position: fixed` chrome). Needs a `template.tsx` and care with the flex chain; highest reach, medium risk.
3. **Trade accepted / declined morph** on `TradeCompactCard` and the Sim inbox: card collapses into a `SuccessCheck` row (Presence + SuccessCheck, no new primitive).
4. **Draft pick landing**: the picked row lands in "My picks" (FLIP between lists) and the drafted row's exit already exists; the auto-pick needs a one-line "Auto-picked" chip via `RankChip`-style pulse.
5. **Grade reveal**: `LetterGrade` pops with `enter-pop` the first time it is shown in a recap (one-shot, in view).
6. **`TickNumber` rollout**: FAAB balance, projections, score totals on Matchup, trade value totals in the Trade Analyzer (cap already protects the main thread).
7. **Players / Rankings re-sort**: `useFlipList` when the sort or filter changes the top 24 (not the whole list).
8. **Fairness meter and Toggle knob to `transform`** (remove two allowlist entries); PillRow underline once the PillRow work lands.
9. **Onboarding step and offseason transitions onto the token scale** (0.28s/0.5s/own bezier): consistency, not new motion.
10. **Week-advance staging**: stagger the standings/scores refresh (`MotionIn` with the existing cap) behind the sweep so the numbers settle in order.

## 5. Rollout notes (candidates 6 and 7)

- `TickNumber` now takes `format` (money, signed gains, "Proj 12.3"); wired into Matchup score and projection (web + app) and the Trade Analyzer value balance (web `TradeAnalyzerContent`, app `TradeValueHero`). FAAB balance is not wired: it renders inside the shared `StatStrip`/`SnapshotTile` as a string (the Today work owns those); do it when the tile accepts a node.
- Re-sort: web `useFlipList` on League Rankings boards and the Players list (first 24 rows marked; positions are now container-relative and refreshed every render, so scroll and expanders no longer cause a stray slide). App: FlatList cells report a cell-local y, so a per-row FLIP cannot see a reorder there; Players and Teams use `ReSettle` (180ms opacity settle) instead.
