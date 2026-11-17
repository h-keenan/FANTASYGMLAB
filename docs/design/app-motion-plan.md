# App motion plan: going further than web

Status: PLAN for owner review (no code ships with this PR). Date: 2026-11-17.
Owner direction: "for the app, we need to really go crazy with graphics and animations to make it look as sleek as possible because we have much more headroom with an app over a website." This is an explicit, standing exception to web/app parity: the app may exceed web. Web keeps its current motion; nothing here is required on web.

## 0. Where we start (verified in the repo)

- Libraries installed (`mobile/package.json`): Expo 54, RN 0.81.5, `react-native-reanimated ~4.1.1`, `react-native-worklets 0.5.1` (babel plugin wired), `react-native-gesture-handler ~2.28`, `expo-haptics ~15`, `expo-blur ~15`, `expo-linear-gradient`, `react-native-svg 15.12`, `expo-image`. NOT installed: Skia, Lottie, a bottom-sheet lib.
- 16 files already use Reanimated (AppBackground, GmOrb, BottomPill, Skeleton, SwipeDismissSheet, StoryCarousel, PlayerAvatar, PremiumGlow, Tabs, ...). Legacy RN `Animated` remains in places (20 `useNativeDriver: true`; two documented `useNativeDriver: false` exceptions in the allowlist of `scripts/check_motion_usage.mjs`: Presence collapse, SegmentedTabBar indicator).
- Shared layer (`mobile/src/lib/motion.ts`, twin of web): `MOTION_MS` 120/180/240/300, `EASE`, `PRESS`, `SPRING {press, settle, sheet}`, `MOTION_ROLE`, `COUNT_MS`, `MAX_ANIMATED_ROWS` 24, `MAX_STAGGER_MS`, `acquireTween` cap of 12, confetti rules (`confettiAllowed`). Components: `Motion`/`MotionIn`, `PopIn`, `TickNumber`, `Presence`/`Collapse`/`PresenceSwap`, `ProgressFill`, `RankChip`, `ReorderRow`, `SuccessCheck`, `PressableScale`, `Skeleton`.
- Already shipped from `docs/audits/2026-11-motion-audit.md` (do not redo): press feedback, route fade, trade accepted/declined morph, draft pick landing, grade reveal, TickNumber rollout (matchup, FAAB, trade value), standings FLIP/RankChip, week-advance stagger, onboarding on tokens, ProgressFill, SuccessCheck, swipe-to-change-tabs (#2056).
- Look to preserve: `AppBackground` (one ambient field mounted at the nav root: static SVG lines + two UI-thread translateX loops, static under Reduce Motion), frosted `GlassCard`/`GlassPanel`, `PremiumGlow`.
- Haptics today: 7 files, ad hoc (`impactAsync Light` x4, `selectionAsync` x2, one Medium in the orb drag). `lib/footerHaptics.ts` is the only shared wrapper (`tabChangeHaptic`, `selectionHaptic`). No vocabulary.
- Nav reality: the app mounts `GmOrb` once at the root (`RootNavigator.tsx`, hidden on some screens). `BottomPill` also exists in the app, but only as the Sim/draft in-flow action row that carries an orb; it is not the global nav.

## 1. Ranked moment list

Score = impact (1-5, how often seen and how premium it feels) x ease (5 = hours, 1 = weeks), so higher is better. Effort: S = under 1 day, M = 1-3 days, L = 4+ days. "Lib" is what must be added.

| # | Moment | Impact | Ease | Score | Effort | Lib |
|---|---|---|---|---|---|---|
| 1 | Haptics map (one vocabulary, wired to every tap/commit/success) | 5 | 5 | 25 | S-M | none |
| 2 | Skeleton shimmer everywhere instead of spinners | 4 | 5 | 20 | S | none (Skeleton exists) |
| 3 | Animated number tickers: extend TickNumber to scores, win %, values, standings points | 4 | 5 | 20 | S | none |
| 4 | Spring sheet physics (rubber-band, velocity handoff, snap, backdrop blur ramp) | 5 | 4 | 20 | M | none (SwipeDismissSheet is Reanimated) |
| 5 | Pull-to-refresh with branded glass indicator + haptic tick | 4 | 4 | 16 | M | none |
| 6 | Chart draw-in (sparklines, trend lines, percentile, win-probability) | 4 | 4 | 16 | M | none (SVG `strokeDashoffset` on UI thread via Reanimated `useAnimatedProps`) |
| 7 | Live-score pulses (score change glow + number tick + haptic, capped) | 4 | 4 | 16 | S | none |
| 8 | Celebration moments: trade accepted, win, draft pick, Sim championship | 5 | 3 | 15 | M | none for v1 (confetti rules exist); Skia only for the championship |
| 9 | Matchup "versus" reveal | 4 | 3 | 12 | M | none |
| 10 | Orb micro-interactions (inside the existing orb, no redesign) | 4 | 3 | 12 | M | none |
| 11 | Shared-element transition (avatar to player card) | 5 | 2 | 10 | L | none; Reanimated 4 shared transitions are experimental, so prefer our own measure-and-morph |
| 12 | Parallax glass on scroll (header blur ramp, hero parallax) | 3 | 3 | 9 | M | none (`expo-blur` wrapper opacity, `useScrollViewOffset`) |
| 13 | Tab-swipe physics polish (#2055/#2056: finger-follow, rubber band, indicator spring) | 3 | 3 | 9 | M | none |
| 14 | "Crazy" tier (Phase 4): Skia aurora/shader background, hero card 3D tilt, GPU championship particles | 5 | 1 | 5 | L | `@shopify/react-native-skia` (decision 3) |

Top 8 by score: haptics map, skeleton shimmer, number tickers, spring sheet physics, pull-to-refresh, chart draw-in, live-score pulses, celebrations. Matchup versus, orb micro-interactions and shared-element follow in Phase 3.

### Moment details

1. **Haptics map.** Looks like: nothing visual; every commit feels physical. Where: every tab change, toggle, selection, sheet snap, success/error, long-press, drag pickup/drop, pull-to-refresh threshold. Primitive: new `haptic.ts` (section 2.4) replacing ad hoc calls and `footerHaptics.ts`. Lib: none. Respects the OS haptic setting plus an in-app Settings toggle.
2. **Skeleton shimmer.** A single diagonal glass sweep (compositor translateX of a gradient; one shared clock for all skeletons on screen so 30 skeletons cost one animation). Where: every loading state still using `ActivityIndicator` (grep and convert). Primitive: existing `Skeleton` plus `useShimmerClock`. Frozen under Reduce Motion.
3. **Tickers.** Roll (digit wheel) or count for scores, win %, projections, value totals, standings points. Primitive: `TickNumber` (add a `roll` variant using per-digit translateY on the UI thread, honoring the `acquireTween` cap of 12). Haptic `tick` only on user-initiated changes, never on live pushes.
4. **Spring sheet physics.** Sheets follow the finger 1:1, rubber-band past the top snap, release with velocity into a spring (`SPRING.sheet`), backdrop dim and blur ramp with sheet progress, page beneath scales to 0.98. Where: `SwipeDismissSheet`, `Sheet`, PQV snap points, quick view, pickers. Primitive: one `useSheetPhysics` worklet hook shared by all sheets. The header-phases agent owns sheet chrome, so this is sequenced after their merge and only touches physics behind that API.
5. **Pull-to-refresh.** Replace the native spinner on the 7 `RefreshControl` screens with a glass orb that stretches with the pull, ticks a haptic at threshold, spins on release, and settles with `SPRING.settle`. Primitive: `<GlassRefresh>` using a `useScrollProgress` shared value. Falls back to native `RefreshControl` under Reduce Motion.
6. **Chart draw-in.** Lines draw left to right over 600ms ease-out, area fill fades after, end dot pops, bars grow with `scaleY` from the baseline. One-shot on first appearance in view, never on re-render. Primitive: `<DrawIn>` plus `useDrawProgress`.
7. **Live-score pulses.** On a score change the cell gets a one-shot glow ring (accent up, danger down, existing `flashDirection`), number ticks, optional light haptic only if the user is on that screen. Capped at 3 concurrent pulses per screen.
8. **Celebrations.** Tiered: small (success check + haptic, exists), medium (glass shimmer burst + confetti from existing `confettiPieces`, 1.2s), epic (Sim championship: full-screen light sweep, trophy rise, staged confetti, haptic crescendo). One `<Celebrate level>` primitive; callers pass only the level. Confetti is transform/opacity on at most 24 views until Skia.
9. **Versus reveal.** Entering Matchup: two team plates slide in from opposite edges with `SPRING.pop` overshoot, a center "VS" glass chip scales in, projections tick up, win-probability bar fills (`ProgressFill`). Once per session per matchup, skippable by tap. Composition of `MotionIn` + `PopIn` + `TickNumber`, no new engine.
10. **Orb micro-interactions.** Inside the existing orb only: press squish (`SPRING.press`), soft idle "breath" glow (compositor opacity, 4s, off under Reduce Motion and when backgrounded), badge dot pop when a count rises (`PulseOnIncrease`), menu items fan out with staggered springs (cap 8 items, <= 240ms stagger), haptic `select` per target during drag. Orb art and geometry are not touched.
11. **Shared element.** Avatar in a list row lifts, scales and travels into the player card / quick view header while the background dims. Implementation: measure the source on the UI thread (`useAnimatedRef` + `measure`), render a transient overlay avatar animating transform only, hand off to the destination avatar at the end. Highest effort and reach; Players list, roster rows and Trade assets first.
12. **Parallax glass.** Page headers gain a blur/opacity ramp tied to scroll offset, hero cards translate at 0.85x. At most one animated BlurView per screen; animate its wrapper opacity, not intensity, on Android.
13. **Tab-swipe polish.** Finger-follow 1:1 pan, rubber band at ends, indicator spring, haptic `select` on commit. Builds on #2056 and `SegmentedTabBar`; move the indicator to transform and delete its `useNativeDriver: false` allowlist entry.
14. **Crazy tier.** Only after phases 1-3 and owner approval of Skia: Skia living aurora behind the glass (same palette and speed as today), shader refraction on the orb menu, GPU particles for the championship, 3D-tilt hero cards from device motion.

## 2. Shared motion primitives

Principle: screens never contain raw durations, springs, curves or `Haptics.*`. They import tokens and hooks. Extend `mobile/src/lib/motion.ts` (twin of web where meaningful; app-only block marked `// app-only`) and add the files below. The existing motion guard stays authoritative and is extended (2.5).

### 2.1 Durations

`instant 120`, `fast 180`, `base 240`, `slow 300` stay. Add app-only `hero 600` (draw-ins, versus reveal, ticker roll) and `epic 1400` (championship only). Ambient loops (background 14s, shimmer 1.6s, orb breath 4s) live in a separate `AMBIENT_MS` table and must be compositor transform/opacity only.

### 2.2 Springs and easing

```ts
export const SPRING = {
  press:  { damping: 18, stiffness: 320, mass: 0.6 },   // existing
  settle: { damping: 20, stiffness: 220, mass: 0.8 },   // existing
  sheet:  { damping: 26, stiffness: 180, mass: 1 },     // existing
  pop:    { damping: 12, stiffness: 260, mass: 0.7 },   // new: overshoot for celebration/reveal
  rubber: { damping: 30, stiffness: 400, mass: 1 },     // new: over-scroll snap-back
  fling:  { damping: 22, stiffness: 140, mass: 1 },     // new: velocity handoff after release
} as const;
```

Keep `EASE`. Add `EASE.emphasized` = cubic-bezier(0.2, 0, 0, 1) for hero entrances. Hand-written curves are banned; the guard fails on `Easing.bezier(` outside `motion.ts`.

### 2.3 Hooks and components (proposed APIs)

```ts
useMotion(): { reduced: boolean; ms(role): number; spring(name): SpringConfig }
withMotion(value, to, opts?: { spring?: SpringName; ms?: MotionSpeed })   // worklet; collapses to a plain set under Reduce Motion
useEnter({ kind: 'fade' | 'rise' | 'pop' | 'versus-left' | 'versus-right', index?, count? })  // stagger capped
useDrawProgress({ ms?: number, once?: boolean }): SharedValue<number>     // 0..1 for charts
useScrollProgress(ref): SharedValue<number>                               // parallax, refresh, header blur
useShimmerClock(): SharedValue<number>                                    // one clock for all skeletons
<Celebrate level="small" | "medium" | "epic" onDone? />
<DrawIn />, <GlassRefresh onRefresh refreshing />, <SharedAvatarTransition id />
```

Every hook returns a final static style when `reduced` is true; no per-moment "if reduced" in screens.

### 2.4 Haptic vocabulary (`mobile/src/lib/haptic.ts`)

One function, named intents, never throws, global kill switch, throttled (min 60ms between fires so 20 ticking numbers cannot buzz):

| Intent | expo-haptics call | Use |
|---|---|---|
| `tap` | impact Light | press that navigates or lightly toggles |
| `select` | `selectionAsync` | tab change, segmented control, picker detent, orb menu target |
| `toggle` | impact Light | switches, checkboxes |
| `commit` | impact Medium | submit, add/drop confirmed, set lineup |
| `lift` | impact Medium | drag pickup (orb drag, reorder) |
| `drop` | impact Light | drag release / snap |
| `snap` | impact Rigid | sheet reaches a snap point, refresh threshold |
| `success` | notification Success | trade accepted, claim landed, draft pick |
| `warn` | notification Warning | lineup warning, deadline |
| `error` | notification Error | failed action |
| `epic` | Heavy, then Success 120ms later | championship, title win |

`footerHaptics.ts` becomes a re-export shim and is then deleted. The guard fails any direct `expo-haptics` import outside `haptic.ts`. Settings gets one "Haptics" toggle (default on). Haptics are independent of Reduce Motion (visual only) unless the user turns them off.

### 2.5 Guard additions (extend `scripts/check_motion_usage.mjs`)

Fail on: direct `expo-haptics` import outside `haptic.ts`; `Easing.bezier(` or numeric spring objects outside `motion.ts`; new RN `Animated.` use in files not on the allowlist (new code is Reanimated only); `setInterval`/`requestAnimationFrame` driving a style. The existing "no new `useNativeDriver: false`" rule stays; phases 1 and 2 burn down the two existing entries.

## 3. Constraints

- **60fps on mid-range devices.** All animation is Reanimated worklets on the UI thread, transform and opacity only (plus animated SVG props, also UI thread). No JS-thread animation: no `setState` per frame, no `setInterval`/rAF-driven styles, no layout-property animation except the documented Presence/Sheet exceptions. Budgets: 12 concurrent number tweens (existing cap), 24 animated rows, 24 confetti pieces (until Skia), 1 animated BlurView per screen, 3 concurrent pulses per screen, one shared shimmer clock. Device matrix: one low-end Android, one iPhone 11-class. Acceptance: no hitch spikes over 2 frames in Perf Monitor while running each moment, and Xcode Animation Hitches on a TestFlight build.
- **Reduce Motion for every moment.** `useMotion().reduced` is read inside the shared hooks, so every moment has a defined reduced form: entrances become 120ms fades or nothing, springs become instant sets, shimmer freezes to a static tint, confetti, parallax and ambient loops are off, pull-to-refresh falls back to the native control, tickers set the final value. The motion guard test checks each new primitive references `reduced`. Manual QA with iOS Reduce Motion and Android "Remove animations".
- **Stay inside the look.** New surfaces use `GlassCard`/`GlassPanel` and theme tokens (fixed semantic colors, less gold per prior UI decisions). The animated background keeps its identity (if Skia is approved it replaces the engine behind the same palette and speed, as a gated experiment). The GM orb is not redesigned: section 4 and moment 10 add behavior and micro-feedback inside its current form only.
- **Battery and thermal.** Ambient loops run only while the screen is focused and the app is foregrounded (AppState + navigation focus pause); no GPU effects while a sheet fully covers the page; shimmer stops when content loads; confetti and epic effects are one-shot and self-terminating; Skia (if added) capped at 30fps ambient and paused off-screen. A "Reduced effects" downgrade (low-power mode or a Settings toggle) turns off ambient loops, parallax and blur animation. Budget: no more than +5% energy vs the previous TestFlight on the same 5-minute script (Xcode Energy gauge).
- **Bundle and disk.** Phases 1-3 add zero native dependencies. Skia adds roughly 3-6 MB per platform and a native rebuild, which is why it is its own gated phase.

## 4. Nav gaps from #2058 mapped onto the orb

#2058 and `e64e2063` delivered hide-on-scroll, reselect-to-top, More badges and long-press shortcuts to the web pill footer and the app `BottomPill` (the Sim/draft action row). The global app nav is `GmOrb`, which has none of them. Mapping:

| Pill feature | Orb equivalent | Notes |
|---|---|---|
| Hide on scroll | Orb shrinks to a 70% dimmed mini state while scrolling down (translate toward its docked edge, scale, opacity 0.55), restores on scroll up, after 600ms idle, or at the top. Never fully hidden: it is the only navigation. | Shared scroll-direction value that screens publish through the existing `bottomPillStore` pattern. Honors the user's dragged position (`orbPosition`/`orbLayout`). Opacity only under Reduce Motion. |
| Tap-to-top (reselect) | Recommended: double-tap the orb scrolls the current screen to top (`snap` haptic, brief up-arrow glyph flash); single tap still opens the menu. | Alternative: single tap scrolls to top first when scrolled past one viewport, then opens the menu (changes the meaning of the primary tap). Screens register a `scrollToTop` callback (the reselect registry from #2058). |
| More badge | The orb already carries `unreadCount`/`hasNew`. Extend to per-item badges in the menu (Trade inbox, Alerts, lineup warnings) and one aggregate dot on the orb that pops (`PulseOnIncrease`) when any count rises. | Counts from the same source as `bottomTabBadgeText`. |
| Long-press shortcuts | Long press is the drag pickup today (350ms `activateAfterLongPress`); keep it. Add a swipe-up flick that reveals the 4 most-used shortcuts (My Team, Matchup, Waivers, Trade) as a mini arc without opening the full menu, with a `select` haptic per target. | A long-press shortcut would conflict with drag; owner pick in decision 4. |
| Selection mode | When a screen enters selection mode, the orb glyph morphs to a close/check affordance and `SelectionActionBar` slides up. Orb stays in place. | Reuses `SelectionActionBar.tsx`. |

None of this redraws the orb: it is state, badges, a scroll-driven transform and gestures.

## 5. Phased rollout (TestFlight-sized drops)

The owner sees app changes only on TestFlight and builds are limited, so each drop is a coherent bundle felt within a minute of opening the app. Each is preceded by static verification (tsc, expo-doctor, unit tests for pure rules, a Reduce Motion pass) and a Perf Monitor pass. No build is pushed without explicit instruction.

- **Drop 1, "Feel" (Phase 1, ~1 week).** `motion.ts` additions (springs, `useMotion`, guard additions), `haptic.ts` and conversion of the 7 existing haptic sites plus tap/commit/success wiring, skeleton shimmer clock and spinner sweep, TickNumber roll on score/win %/values, live-score pulses. No new native deps. Visible win: the whole app feels physical and alive.
- **Drop 2, "Surfaces" (Phase 2, ~1.5 weeks).** Spring sheet physics (after the header-phases agent merges), `GlassRefresh`, chart draw-in, tab-swipe polish and SegmentedTabBar indicator to transforms, orb badge/aggregate dot, orb scroll-shrink, orb double-tap-to-top.
- **Drop 3, "Moments" (Phase 3, ~2 weeks).** `<Celebrate>` (trade accepted, win, draft pick, Sim championship v1 with confetti), matchup versus reveal, orb micro-interactions (breath, menu fan, swipe-up shortcuts), parallax glass headers, shared-element avatar transition for Players and roster.
- **Drop 4, "Crazy" (Phase 4, gated on decision 3).** Skia: living aurora background behind the glass (A/B against current `AppBackground`), orb-menu refraction, GPU particle championship, hero-card tilt. Needs a native rebuild and a battery review.

Parallel-agent boundaries: do not touch the perf agent's lazy-sheet/startup files or the header-phases agent's sheet/detail chrome. Run at most 3 concurrent sonnet agents per drop.

## 6. Open decisions for the owner

1. **Scope of "crazy".** Phases 1-3 first with zero new native deps, or straight to Skia? Recommendation: 1-3 first; they deliver most of the felt change across three TestFlights.
2. **Web parity exception.** Confirm the app may exceed web and web gets no catch-up work. Recommendation: yes; record it in `docs/ui-patterns.md` as a standing exception.
3. **Add `@shopify/react-native-skia`?** Recommendation: yes, but only in Drop 4, behind a "Premium visuals" Settings toggle (default on for capable devices), with a native rebuild. Lottie: no (Skia and Reanimated cover it; one fewer renderer).
4. **Orb gestures.** Tap-to-top: double-tap (recommended) vs tap-when-scrolled. Shortcuts: swipe-up flick (recommended) vs long-press (conflicts with drag). Hide-on-scroll: shrink-and-dim, never fully hidden (recommended).
5. **Haptics defaults.** On by default with a Settings toggle (recommended); `epic` reserved for championships; no haptics on passive live updates.
6. **Performance floor.** Recommendation: iPhone 11 and a 4 GB Android, with an automatic "Reduced effects" downgrade on low-power mode.
7. **Celebration intensity.** Epic only for championship/title wins, medium for trade accepted and draft pick, small elsewhere (recommended). Same for all users; Premium glow stays as is.
8. **Versus reveal frequency.** Once per matchup per session, tap to skip (recommended) vs every entry.
9. **Shared-element transition.** Build our own measure-and-morph for Players, roster and Trade (recommended) vs waiting for Reanimated's stable shared transitions. Confirm it deserves Drop 3 given its effort.
10. **Sound.** None (recommended); sound design is a separate product decision.
11. **Drop cadence.** Four TestFlights over roughly 5 weeks (recommended) vs two bigger builds given the upload limit. You choose when each is pushed; nothing is pushed autonomously.
12. **Prototypes.** Want 2-3 dev-flagged Reanimated prototypes (haptic vocabulary, shimmer clock, DrawIn) before approving Drop 1? Recommendation: not needed; Drop 1 is low risk.
