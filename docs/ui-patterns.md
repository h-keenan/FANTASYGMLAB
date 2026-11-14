# UI patterns (Wave 0 shared components)

The shared building blocks from `docs/audits/2026-11-convolution-audit.md` section 2. Each one is built
once for web (`web-next/src/components/ui/`) and once for mobile (`mobile/src/components/`) with the
same prop names, and the pure logic lives in a **lib twin** (`web-next/src/lib/x.ts` and
`mobile/src/lib/x.ts`, kept identical by `node scripts/check_lib_twins.mjs`).

Ground rules for every pattern here:

- Keep the liquid-glass look: existing tokens only (`--color-*`, `--radius-*`, `--space-*`), the
  cyan accent, gold highlight, `glass-surface` style cards. Nothing here introduces a new colour.
- 44px minimum tap target (padding or an expanded hit area, never a bigger visual).
- `prefers-reduced-motion` is honoured (web CSS media query; mobile has no decorative motion).
- Web and app ship together. Where a prop differs on mobile the difference is listed.
- Screenshots below are 390px wide, dark theme. "Before" is `origin/main`, "after" is this branch.

| Pattern | Web | Mobile | Lib twin | Status |
|---|---|---|---|---|
| `Sheet` | `ui/Sheet.tsx` | `Sheet.tsx` | `sheetStack.ts` | built; first users are TapForWhy, StructuredRow, FilterSheet |
| `ConfirmInPlace` | `ui/ConfirmInPlace.tsx` | `ConfirmInPlace.tsx` | `confirmInPlace.ts` | built and applied (see below) |
| `StoryCarousel` | `ui/StoryCarousel.tsx` | `StoryCarousel.tsx` | `storyCarousel.ts` | built; first user: Fantasy Sim weekly recap |
| `InsightLink` | `ui/InsightLink.tsx` (+ `StatStrip` `insight`/`league`) | `MetricCard` `onPress` via `lib/insightNav.ts` | `insightLinks.ts` | built; every stat about your league/team must resolve here, see `docs/audits/2026-11-navigation-audit.md` |
| `UndoToast` | `ui/UndoToast.tsx` | `UndoToast.tsx` | `confirmInPlace.ts` (timing) | built; used by GM targets |
| `PlayerBadge` | `ui/PlayerBadge.tsx` | `PlayerBadge.tsx` | `playerBadges.ts` | built; every player row tag, PQV header and Sim roster/draft list routes through it |
| Player anatomy (`PlayerAccordionRow`, `CompactPlayerCard`, `TradeCompactCard`, `RankRow`, `PlayerAvatarSlot`) | `ui/PlayerAccordionRow.tsx` etc. | same names in `components/` | `playerAnatomy.ts` | built; see "Player anatomy" |
| `LetterGrade` / `GradeBar` / `GradeLegendSheet` | `ui/LetterGrade.tsx` | `LetterGrade.tsx` | `simGrade.ts` | built; the Fantasy Sim's overall (replaces the OVR gauge there only), see "Fantasy Sim letter grades" |
| `CompactModule` | `ui/CompactModule.tsx` | `CompactModule.tsx` | `compactModule.ts` (+ `simSummaries.ts`, `simDraft.ts`) | built (Phase 1 of `docs/audits/2026-11-information-architecture.md`); Sim home folds and the Sim draft room use it; `Collapsible` is superseded (SimFold renders CompactModule) |

## Sheet

Open height (2026-11-14): every bottom sheet on a phone opens between 56% and 80% of the screen (web `.pqv-modal` in the 480px query, app `sheetHeight` in `mobile/src/theme.ts`), so it never opens up under the page header and does not jump while content loads. Chips in dense list rows use `ToneBadge truncate` (web) / `shrink` (app) so a long tag ends in an ellipsis instead of being clipped.

One bottom sheet on a phone and a centred dialog from 768px up. Replaces the hand-rolled copies of
`.pqv-backdrop` + `.pqv-modal` + `SheetHandle` + `useSheetDragDismiss`.

```tsx
import { Sheet } from "@/components/ui/Sheet";

<Sheet open={open} onClose={() => setOpen(false)} title="Filters" description="Optional one line" footer={<Button>Apply</Button>}>
  {/* body scrolls; footer is sticky and clears the home indicator */}
</Sheet>
```

Behaviour (web): portaled to `<body>`, `role="dialog" aria-modal aria-labelledby`, focus moves in on
open and **returns to the trigger on close**, Tab is trapped, Escape and a backdrop press close, body
scroll is locked (reference counted), safe-area aware, swipe-down to dismiss on touch (reuses
`useSheetDragDismiss`), `size` is `sm | md | lg` (desktop width only), near-opaque glass so dense
screens underneath never bleed through, rise animation off under reduced motion. The sheet stops
key events so a dialog underneath it (the Player Quick View) never reacts to them.

**Overlay rule (superseded detail below: see "Overlays"): sheets never stack.** Opening a second sheet hides the first (it stays mounted, so
its state survives) and closing the second brings the first back. The rule lives in
`lib/sheetStack.ts` and is shared with mobile. On mobile a hidden sheet's children are unmounted by
React Native's `Modal`, so keep anything that must survive in the caller's state.

Mobile: `<Sheet open onClose title ... />` wraps the existing `SheetModal` / `SwipeDismissCard` /
`SheetScrollView` (which own the gesture), so the swipe thresholds are unchanged.

Swipe-to-dismiss: see "Gestures" below (one shared state machine, web hook + app hook). Every web pop-up shell
(`Sheet`, `PlayerQuickView`, `SimSheet`, `ManagerProfileSheet`, Matchup `SwapSheet`, `TradePickerSheet`,
`PercentileExplorerSheet`, `AlertsDropdown`, checkout, `PopupShell`, GM orb) and the weekly recap `StoryCarousel` use
`useSheetDragDismiss`; every app pop-up uses `SwipeDismissCard` / `useSheetDismissGesture`. New shells must use the
hook (a handle without the hook is the bug this rule exists for). The PQV has bespoke chrome, so it stays a
hand-rolled shell around the same hook until a design pass decides what becomes a `Sheet` prop.

## Gestures (swipe down to dismiss, snap points)

ONE implementation of drag-to-dismiss on both platforms. The pure rules and a state machine live in the twin
`lib/sheetGesture.ts` (web `web-next/src/lib`, app `mobile/src/lib`, the app copy only adds the `'worklet'`
directive; both run the same `sheetGesture.test.ts` cases, including simulated touch sequences). The web hook
`lib/useSheetDragDismiss.ts` and the app `useSheetDismissGesture` (`SwipeDismissSheet.tsx`) only wire events to it.

- **Start zones**: the handle always drags. Anywhere else a drag starts only when the pull is downward AND every
  scroll area under the finger was at its top when the touch BEGAN (1px tolerance for fractional scroll offsets).
  Scrolling content back up to the top and carrying on never turns into a dismiss.
- **Axis lock**: past an 8px slop a clearly vertical pull (1.25x the horizontal travel) claims the gesture;
  horizontal swipes (tab strips, chip rows, carousels) and diagonals that never resolve (24px) stay with the page.
- **Follow + resistance**: the surface follows the finger 1:1 (from where the drag was claimed, no jump), then
  rubber-bands past the dismiss distance and when pulled above its top. Web writes `transform` straight to the
  element: no React render per touchmove (re-rendering the PQV 60 times a second was the stutter).
- **Release**: dismiss when pulled past a quarter of the sheet (80-160px) OR flicked down at >= 0.55px/ms and >= 40px.
  Velocity is averaged over the last 100ms (one jittery sample used to close a sheet pulled 24px), is 0 after a 100ms
  rest, and a release moving back up never dismisses. Otherwise it springs back / settles on a snap point.
- **Snap points** (the peek sheet): `useSheetDragDismiss({ snapPoints: [0.5, 1], snap, onSnapChange })` (fractions of
  the sheet that stay visible; `snapTo(f)` from code). The sheet is laid out full height and translated to its rest
  offset. Down from the lowest point dismisses; a flick from full lands on the peek first; below full a pull up from
  anywhere expands (the content is not scrollable until full). Pure side: `sheetStops`, `resolveSheetRelease`.
- **Story effect**: `effect: "story"` (full-screen card): translate + scale to 0.9 + fade to 0.45 with the pull.
- **Dismissal path**: `onDismiss` must close like the X. The story passes `overlay.closeAll` so the overlay stack pops
  its history entry. Under reduced motion it still follows the finger and closes, with no slide-out or spring.
- Opt a region out with `data-sheet-no-drag`. Touch only (mouse/keyboard keep X, Esc, backdrop).
- Check: `scripts/sim_layout_playwright/sheet_drag.mjs` (real CDP touches).

## StoryCarousel

A full-screen, story-style carousel for "moments": one glanceable page at a time, the way a story or a
recap reads. Web `components/ui/StoryCarousel.tsx`, app `components/StoryCarousel.tsx`; the pure logic
(page index, tap zones, swipes, keys) is the byte-identical twin `lib/storyCarousel.ts`.

```tsx
import { StoryCarousel, type StoryPage } from "@/components/ui/StoryCarousel";

const pages: StoryPage[] = [
  { key: "result", label: "Result", content: <Hero .../> },
  { key: "next", label: "Next week", content: <Next .../>, footer: <Button onClick={done}>Back to your team</Button> },
];
<StoryCarousel title="Week 4 recap" pages={pages} onClose={done} />
```

- **A page is glanceable**: a hero number plus at most three supporting items, no scrolling. Put the
  selection logic (which pages exist, what goes on each) in a pure `lib/` module with tests, like
  `lib/simRecapStory.ts` (`STORY_ITEMS = 3`). Pages with nothing to say are dropped, not shown empty.
- **Navigation**: swipe, tap the left 30% (back) or the rest (forward), arrow keys / PageUp / PageDown,
  the page-progress segments (tap one to jump), desktop arrow buttons. Taps on a button, link or
  anything marked `data-story-interactive` never flip the page. The last page has no forward action:
  its `footer` is the finish CTA.
- **Close and the overlay rule**: it registers with THE overlay stack (`useOverlay` on web, `overlayStack` in the
  app; see "Overlays"), so only one pop-up is ever on screen: a player card (PQV) opened from a page REPLACES the
  story (it stays mounted/hidden with its page) and its "‹ Back to ..." returns to the same page. The X (top right)
  closes everything; Escape and the phone/browser Back go back one step. The stack owns the scroll lock, history and
  z-index: the carousel sets none of them. Swiping down out of it works like every sheet (see "Gestures"): the whole
  card follows the finger, shrinks and fades, and closes via `overlay.closeAll` (same as the X); horizontal swipes and tap
  zones are unchanged.
- **Look and motion**: glass over the page background, safe-area padding on all sides, a 240ms slide
  between pages that is off under `prefers-reduced-motion` (app: `useReducedMotion`), no horizontal
  overflow (every column is `min-w-0`).
- **Reuse**: a story is `{ title, pages[], onClose }`. First user: the Fantasy Sim weekly recap
  (`SimRecapStory`: Result, Matchup breakdown, Injuries and lineup, Around the league, Season complete (final week only), Next week; a
  "Full details" button opens the classic recap).
- **Recap page anatomy** (web `ui-recap*` classes in `ui.css`, app `HeroZone`): a hero zone that fills the top of the screen (min 34dvh, centered, a
  one-shot accent glow `HERO_GLOW`, never looping), then at most three supporting rows. Result: team avatars both sides, score with `CountUp`, tone glow,
  best/worst as `SimPlayerLine` rows (avatar, position badge, OVR gauge). Playoffs and the championship: trophy mark (`TrophyIcon`), headline from
  `simRecapOutcome` (Advancing / Eliminated / Playoff bye / Runner-up / Champions), `Confetti` only for the title and never under reduced motion.
  Matchup: efficiency ring, position-coloured chips (`positionColorVar`), top starters with OVR. Injuries: ONE marker per player (the OUT chip; the trailing text is
  only the duration). Season: champion crowned, your finish, awards the standings can back up. All variant logic is pure and tested in `lib/simRecapStory.ts`. Meant for the season recap, draft recap and offseason
  review next; those are not built yet.
## Motion

One motion vocabulary for web and app (coridian_: "I do like the animations, more of that wherever it's fitting"):
pure tokens and rules in `lib/motion.ts` (byte-identical twin), web CSS variables + classes in `globals.css`
("Motion library"), hooks in `lib/useMotion.ts`, components in `components/Motion.tsx` (app: `lib/useMotion.ts`,
`components/Motion.tsx` on Animated/native driver).

- **Durations**: `instant` 120, `fast` 180, `base` 240, `slow` 300ms (`MOTION_MS`, `--motion-*`). A count-up is the one
  deliberate longer one (450ms). Easings: `--ease-out` (entrances), `--ease-in-out` (sweeps), `--ease-in` (exits).
- **Rules**: opacity and transform only (the one exception is the hero OVR ring fill: a single custom property on md/lg
  rings, never in lists); no layout shift (a block waits invisible but in place); nothing animates a list over 24
  rows (`shouldAnimateList`, `MAX_ANIMATED_ROWS`); staggers add at most 240ms in total however many items
  (`staggerDelay`); entrances play when a block scrolls into view (`useInView`, an IntersectionObserver that disconnects),
  not all at page load.
- **Reduced motion is one switch**: `useReducedMotion()` (web: `prefers-reduced-motion`, live; app: OS Reduce Motion,
  live) plus a CSS `@media (prefers-reduced-motion: reduce)` block for every class. Under it nothing moves: content is
  simply there, counts show their final value, the score flash stays as a shorter colour change, confetti is not rendered.
- **Pieces**: `MotionIn` (entrance + stagger), `CountUp` (number counts up the first time it appears), `TickNumber`
  (follows changes: green flash up, red down), `PulseOnIncrease` (badge/bell pulse when a count goes up),
  `.motion-sweep` (advance-week light band across a block), `Confetti` (title only), `.enter-rise` / `.enter-pop` /
  `.sim-row-drafted` (existing: results landing, a drafted/claimed row sliding away), skeleton shimmer, Tabs slide, toast.
- **Where it is applied**: Scores cards (stagger, count-up, week sweep), recap hero score (count-up) and title confetti, trade
  offers (capped stagger in, verdict pop), tab count badges (pulse), hero OVR rings (fill), TickNumber everywhere it is used.
- **The ONE press feedback**: `PRESS` in `lib/motion.ts` (3% shrink, slight fade, 120ms; reduced motion keeps only the fade). Web: a single
  zero-specificity rule in `globals.css` ("Press feedback") covers every `button`, `[role=button|tab|menuitem]`, `summary`, `a[href]` and `[data-press]`;
  opt out with `data-no-press` only where a control animates itself. App: `components/PressableScale` is THE tappable (drop-in for
  `TouchableOpacity`; do not use `activeOpacity` or a hand-rolled `pressed` style). `AnimatedCard` already matches (.97 spring).
- **Transitions by surface**: `TRANSITION_MS` (page 240, sheet 300, tab 180, toast 240, list 180, press 120). **Success pulse**: `.motion-success` /
  `SUCCESS_PULSE` for a saved/added/claimed confirmation, `PulseOnIncrease` for counts. **Count-up**: `CountUp`. **Hero glow**: `HERO_GLOW`.
- **Adding motion**: use a class/hook above, never a new keyframe with its own duration; check the reduced-motion test
  (`components/Motion.test.tsx`) still describes your component's behaviour, and keep it off long lists.

## ConfirmInPlace

A destructive control that confirms **where it stands**. First tap morphs it in place (same
footprint, nothing below moves), second tap acts.

```tsx
import { ConfirmInPlace } from "@/components/ui/ConfirmInPlace";

// Quick, low-regret: the label changes to "Tap again to confirm"; reverts after 4 s.
<ConfirmInPlace label="Sign out" buttonVariant="secondary" onConfirm={signOut} />

// Loses data: the control is replaced in place by "Delete this game? [Delete] [Keep]".
<ConfirmInPlace variant="button" mode="ask" label="Delete game" prompt="Delete this game?" confirmLabel="Delete" onConfirm={deleteGame} />

// Icon-only trash in a list row; the panel covers the whole row at the row's own height.
<div className="relative flex items-stretch gap-2">
  <Card className="flex-1" />
  <ConfirmInPlace variant="icon" overlay="parent" label={`Delete ${name}`} prompt="Delete this game? It can't be undone." confirmLabel="Delete" onConfirm={() => remove(id)} />
</div>
```

Props: `variant` (`button | icon | row`), `mode` (`tap-again | ask`, default tap-again for `button`,
ask for `icon`/`row`), `label`, `prompt`, `confirmLabel`, `keepLabel`, `onConfirm`, `errorText`,
`disabled`, `buttonVariant`, `size`, `icon`, `overlay` (`self | parent`, web), `plain` +
`triggerClassName`/`triggerStyle`/`triggerRole` (web: keep a text link or menu-item look).

- **States:** idle, armed, busy (the confirm button shows the spinner, Keep is disabled, the
  request is never cancelled), error ("That did not work. Try again." with Retry / Cancel).
  `onConfirm` may return a promise; throw, reject or return `false` to show the error state.
  The state machine and the announcement copy are the lib twin `lib/confirmInPlace.ts`.
- **Same footprint:** tap-again keeps both labels in one grid cell (the width is the wider of the
  two); ask mode hides the trigger with `visibility` and paints the panel over it. A `self` panel
  grows toward whichever side has room, so a control near a screen edge never pushes its question
  off-screen. A thin countdown bar shows the 4 s revert (hidden under reduced motion).
- **a11y:** the trigger carries `aria-expanded` while armed; a polite live region announces the
  question, "Working" and errors; focus lands on the safe choice (Keep) in ask mode and returns to
  the trigger on cancel; Escape and a press outside cancel; the destructive button is never the first
  focus target.
- **Mobile differences:** React Native cannot paint over siblings, so a list row hands its own
  content in as `rowContent` and the panel replaces the whole row at the height the row had. Announcements go
  through `AccessibilityInfo`. There is no animation to reduce.

Before and after, Fantasy Sim saved-game delete (390px). Before: the trash opened a second card and
pushed everything below it down. After: the row itself becomes the question.

| Before idle | Before armed (layout jump) | After armed (same row) |
|---|---|---|
| ![](ui-patterns/sim-hub-1-idle-before.jpg) | ![](ui-patterns/sim-hub-2-confirm-before.jpg) | ![](ui-patterns/sim-hub-2-confirm-after.jpg) |

The other variants (tap-again, row ask, an inline link that asks, the error state):

| Tap again | Row ask | Inline ask | Error |
|---|---|---|---|
| ![](ui-patterns/confirm-2-tap-again.jpg) | ![](ui-patterns/confirm-3-row-ask.jpg) | ![](ui-patterns/confirm-4-inline-ask.jpg) | ![](ui-patterns/confirm-5-error.jpg) |

### Where it is applied

| Action | Web | Mobile | Pattern |
|---|---|---|---|
| Delete a Fantasy Sim saved game (hub) | `SimGameContent.tsx` | `GmGameScreen.tsx` | icon trash, ask, row |
| Delete game / Reset week (game More tab) | `SimGameContent.tsx` | `GmGameScreen.tsx` | ask / tap-again |
| Sign out (header menu, Account) | `Header.tsx`, `AccountContent.tsx` | `HomeScreen.tsx` | tap-again |
| Remove a failed league (Portfolio) | `PortfolioContent.tsx` | not in the app (Account uses a native alert, which the audit accepts) | ask |
| Remove ESPN login | `EspnLoginPanel.tsx` | `EspnLoginPanel.tsx` | ask |
| Remove my scouting report | `CollegeScoutingContent.tsx` | `ProspectScoutingDetailScreen.tsx` | ask |
| Delete a shared trade | `SharedTradesFeed.tsx`, `app/community/page.tsx` | `SharedTradesFeed.tsx`, `CommunityScreen.tsx` | ask; a failed delete now shows an error instead of being swallowed |
| Reset lineup to suggested | `MatchupPlanner.tsx` | `MatchupPlanner.tsx` | tap-again |
| Remove a team (with assets) from a multi-team trade | `MultiTeamTradeContent.tsx` | `MultiTeamTradePanel.tsx` | ask |
| Remove a GM target | `GmPlanContent.tsx` | `GmPlanScreen.tsx` | **UndoToast** (see below) |

Also applied after #1801 merged: **removing a team from a multi-team trade** (web `MultiTeamTradeContent.tsx`,
mobile `MultiTeamTradePanel.tsx`). Dropping a team takes every asset routed to or from it, so a team that
holds assets asks first ("Remove Team 3 and its assets?"); an empty team is removed straight away.

**Left alone on purpose:** removing a single asset from a trade side. After #1801 that is a chip with an x in
the side summary, and the asset is one tap away in the picker, so a confirm would only add friction. If it
ever needs a safety net it should use `useUndoableRemoval`, not a confirm.

### UndoToast

The low-stakes alternative: remove at once, show "Removed X. Undo" for 6 seconds, and only commit the
removal when the toast expires. A newer removal commits the previous one immediately and leaving the
page flushes it, so an undo window never loses a removal.

```tsx
const { schedule, toast } = useUndoableRemoval<Target>({
  message: (t) => `Removed ${t.name} from your targets.`,
  commit: (t) => api.removeGmTarget(leagueId, t.id),   // runs when the toast expires
  restore: (t) => setTargets((rows) => [t, ...rows]),   // runs on Undo or if commit fails
});
// onRemove: setTargets(filtered); schedule(target);   ...   {toast}
```

## TapForWhy

The first thing someone does to learn more about a number is tap it. `TapForWhy` wraps any number,
chip, badge, rank or grade and opens a small `Sheet` with its "why". It replaces always-visible
explainer paragraphs, `BeginnerHelp` "?" icons, hover `title=` tooltips (which never show on a phone)
and sections that only re-explain a number shown elsewhere on the same screen.

```tsx
import { TapForWhy } from "@/components/ui/TapForWhy";

// A tile: the button takes the tile's own class, so the layout does not change.
<TapForWhy metric="value" variant="tile" className="pqv-stat-tile" spoken={`Value ${score}`} chart={<ValueHistory playerId={id} bare />}>
  <span className="pqv-stat-tile-value">{score}</span>
  <span className="pqv-stat-tile-caption">Value</span>
</TapForWhy>

// An inline number or a chip
<TapForWhy metric="win_probability" spoken="Win probability 62%">62%</TapForWhy>
```

- Renders a real `<button aria-haspopup="dialog">` labelled "Why: Value 2,133" (`spoken`, or the
  registry title). The 44px target is an expanded `::after`, so the visible size does not change.
- Affordance is quiet: a dotted underline (`inline`) or a faint accent ring (`chip`, `tile`) on hover
  and keyboard focus, plus a pressed state. Nothing is added to the resting look. On mobile the
  pressed state is the whole affordance.
- The sheet has one structure: title, 1 to 3 plain sentences, an optional `chart` slot (rendered only
  while the sheet is open, so a heavy chart costs nothing until asked for), and a "learn more" link when
  the registry entry has one. Instance-specific lines go in `extra`.
- Fires a `why_<metric>` usage event (`trackUse`), so we can see which numbers people actually ask
  about.
- **Copy lives in one registry**, `lib/tapForWhyContent.ts` (lib twin): `value, ovr, rank, tier, grade,
  win_probability, playoff_odds, faab, balance, confidence, usage_trend, projection, age`. Entries reuse
  `BEGINNER_HELP`, so captions, the glossary and the popover can never disagree. Add a metric by adding
  an entry; a test fails if an entry has no title or more than three sentences.
- Mobile: `<TapForWhy metric spoken chart extra onLearnMore />`. The learn-more link only shows when the
  caller passes `onLearnMore` (the caller owns navigation so it can close its own modal first).

### Applied: Player Quick View (web + mobile)

Owner direction: consolidate. The standalone **Value history** and **Model** sections are gone; the
Value tile opens the value history chart and the Player score (OVR) tile opens the Model radar. The
Usage tile opens its explanation plus the engine's own detail line. `PlayerValueHistory` and
`SubRatingRow` gained a `bare` prop so the same components render inside the popover without a second
heading. The Player Profile page keeps its own Model tab; its tiles open the copy-only popover.

| Before: top | Before: two sections at the bottom | After: top (same layout) |
|---|---|---|
| ![](ui-patterns/pqv-1-top-before.jpg) | ![](ui-patterns/pqv-2-bottom-before.jpg) | ![](ui-patterns/pqv-1-top-after.jpg) |

| Tap the value | Tap the player score | Tap the usage trend |
|---|---|---|
| ![](ui-patterns/pqv-3-tap-value-after.jpg) | ![](ui-patterns/pqv-4-tap-ovr-after.jpg) | ![](ui-patterns/pqv-5-tap-usage-after.jpg) |

Follow-ups (60+ call sites per the audit; each is a one-line wrap now that the component exists):
`ToneBadge` (`onWhy`), `ValueStat`, `SnapshotTile`, win probability and playoff odds on Matchup and
Dashboard, FAAB on Waivers, trade balance and confidence on the verdict card, `projection` and `age`
wherever they appear. The registry already has copy for all of them.

## StructuredRow

The replacement for delimiter-joined strings and generated sentences. One row is **crest/avatar + name
(one line, truncated) + status chip + two or three metric pills + one short reason + chevron**, 64px
tall at most, and tapping it opens a detail `Sheet`. Every part is its own field, so nothing repeats
and nothing is parsed back out of text.

```tsx
import { StructuredRow, StructuredRowList } from "@/components/ui/StructuredRow";

<StructuredRowList
  items={rows}                       // top 3, then "See all (n)" expands the rest in place
  renderRow={(row) => (
    <StructuredRow
      lead={<TeamAvatar avatarUrl={row.avatar_url} name={row.team_name} size={36} />}
      title={row.team_name}
      chip={{ label: row.strategy_display, color: "var(--color-warning)" }}
      pills={signalPills(row)}       // "Picks #10", or "Draft #8" + "Future #6"
      reason={row.reason_short}      // <= 60 characters
      highlight={row.team_id === myRosterId}   // gold outline for the user's own team
      detailTitle={row.team_name}
      detail={<p>{row.reason_long}</p>}        // the long sentence lives only here
    />
  )}
/>
```

Without `detail` or `onOpen` a row is a plain, non-tappable row with no chevron. The pure helpers
(`signalPills`, `strategyTone`, `visibleSignalRows`, `seeAllLabel`, `cardRows`) are the lib twin
`lib/draftSignals.ts`. Mobile: `StructuredRow` and `StructuredRowList` take the same props (`testID`
instead of `testId`).

### API: Draft Center card schema 2 (backend, web, mobile)

`modules/draft_center_cards.py` used to return `items: ["Team | Retool | Draft #10 | Future #10 |
sentence", ...]`. Cards now also carry `schema: 2` and `rows` with these fields:

```json
{ "team_id": "2", "team_name": "...", "avatar_url": null, "strategy": "retool", "strategy_display": "Retool",
  "draft_rank": 10, "draft_rank_tied": false, "future_rank": 10, "future_rank_tied": false, "firsts": 0,
  "reason_code": "too_few_picks", "reason_short": "Too few picks for a retool",
  "reason_long": "Draft rank #10 leaves too little flexibility for a retool build.",
  "evidence": [{ "key": "draft_rank", "label": "Draft capital rank", "value": "#10" }] }
```

- **The legacy `items` strings are still sent, unchanged, for one release.** The iOS build in App Store
  review and older Android builds render them; a response without `rows` renders exactly as before.
  Delete `items` (and `_draft_workspace_team_lines`) once those builds are gone.
- `reason_long` is produced by the same function as the legacy string's sentence, so the two cannot
  drift. `reason_short` never repeats the rank numbers that the pills already show.
- `rows` keeps up to 6 teams per card (`CARD_ROW_POOL`); `items` stays at the top 3. Clients show 3 and
  offer "See all (n)".
- A team name that contains the old delimiter (`|`) is now safe, because nothing is split any more.
- Tests: `tests/test_draft_center_ui.py` (fields, 60-character cap, legacy/row alignment, delimiter in a
  name, partner cards) and `tests/test_mobile_api_service.py` (served schema).

### Applied: Draft Center "League Draft Decision Signals" and "Draft Partner Discovery"

| Before: one joined string per team | After: rows, top 3 + See all, own team outlined | After: tap a row |
|---|---|---|
| ![](ui-patterns/draft-1-signals-before.jpg) | ![](ui-patterns/draft-1-signals-after.jpg) | ![](ui-patterns/draft-2-detail-after.jpg) |

Also fixed on the way: `TeamAvatar` built its initials from UTF-16 units, so a team name ending in an
emoji produced half a surrogate pair (a broken glyph, and a server/client HTML mismatch that failed
hydration). It now uses `lib/teamInitials.ts` (code points; lib twin), on web and mobile.

Not done in this pass (the audit's full Draft Center redesign, section 6.4): merging the five cards into a
Buyers / Sellers / Pivot / Pick-rich segmented control, deleting the all-caps label bars, merging Partner
Discovery into the same control, and the detail sheet's "Open trade finder with this team" and "View team"
actions (the Draft Center page does not have the league id wired into the card component yet). The rows
and the API are the foundation for all of those.

## FilterSheet

One **Filters** button (with a count badge) that opens a `Sheet` of grouped chips, committed with
Apply. Replaces a row of native `<select>`s and pill rows. Active filters show as removable chips next
to the button.

```tsx
import { FilterSheet } from "@/components/ui/FilterSheet";
import { singleValue, valuesFromSingles, type FilterGroup } from "@/lib/filterSheet";

const groups: FilterGroup[] = [
  { id: "position", label: "Position", anyValue: "ALL", options: [{ value: "ALL", label: "Any" }, { value: "QB", label: "QB" }] },
  { id: "tags", label: "Tags", multi: true, options: [...] },
];

<FilterSheet
  groups={groups}
  values={valuesFromSingles(groups, { position })}      // what the page is filtering by now
  resultCount={(draft) => countMatches(draft)}          // optional: "Show 24 results" / "No results"
  onApply={(next) => setPosition(singleValue(groups[0], next))}
/>
```

- The sheet edits a **draft**. Nothing on the page changes until Apply, and closing (Escape, backdrop,
  swipe) discards. Reset clears the draft. Apply is disabled when the draft would match nothing.
- Single-select groups behave like radios (tap a chip to choose, tap it again or "Any" to clear);
  multi-select groups toggle. A group can be `hidden` (for example Roster when ownership is unknown).
- a11y: the sheet is a form (a `fieldset` and `legend` per group); single groups are `radiogroup` /
  `radio` with `aria-checked`, multi groups are toggle buttons with `aria-pressed`; the trigger's
  accessible name carries the count ("Filters, 2 active"); the footer count is a polite live region;
  each active chip has its own "Remove Position filter: RB" button.
- The model (`toggleFilterValue`, `activeFilterCount`, `activeFilterChips`, `applyButtonLabel`, ...) is the
  lib twin `lib/filterSheet.ts`. Mobile: `<FilterSheet groups values onApply resultCount />` is the
  multi-group version of `FilterDropdownButton` (which stays for one-group pills elsewhere).

### Applied: Players and Waivers (web + mobile)

- **Players:** the five selects become a one-tap position pill row plus one Filters button (age, status, health, roster). Sort by
  stays a select (it is a sort, not a filter). The live count uses the same filter function as the page
  (including the IDP pool switch), so Apply reads "Show 1 result".
- **Waivers:** the All Free Agents position select is a one-group FilterSheet, so the same control, count
  badge and chips appear everywhere. The Add / Stash / Watch pill row is a segmented control (4 options,
  one level) and stays.

| Before: five selects | After: one button | The sheet | Applied: badge and chips |
|---|---|---|---|
| ![](ui-patterns/players-1-bar-before.jpg) | ![](ui-patterns/players-1-bar-after.jpg) | ![](ui-patterns/players-2-sheet-after.jpg) | ![](ui-patterns/players-3-applied-after.jpg) |

Position is the filter people use most, so it is not behind Apply: a pill row (All / QB / RB / WR / TE / K, plus the
defender positions in IDP leagues) sits above the Filters button and applies on one tap. Filters keeps the rest
(age, status, health, roster) with the count badge.

### Not done: TradePickerSheet extraction

The trade picker (`TradePickerSheet`, merged in #1801) already has the same panel: a Filters button with a
count, position and condition chips, committed with Apply. It renders that panel **inline inside its own
sheet**, on purpose, because opening a `FilterSheet` from there would hide the picker (sheets never stack).
So the extraction is not "swap in the component"; it is a small follow-up that adds an `inline` rendering mode
to `FilterSheet` (same groups, same draft model from `lib/filterSheet.ts`, panel instead of a sheet) and moves
the picker onto it, then swaps the picker's shell for `Sheet`. The model already supports both groups
(`position`, `condition`). Left for its own PR so the just-merged picker is not edited alongside this work.
Other planned users: Trade Hub filters, News, Alerts, College Scouting, League Recaps, Live Draft.
## Phone game shell (Fantasy Sim) and BottomTabBar

Phase A of `docs/mobile-ux-plan-2026-11.md`. In the game on phones (`/gm-game`, below 768px):

- The global header and the global GM orb button step aside (`pathOwnsPhoneChrome` in `lib/bottomNav.ts`; the orb's sheet stays mounted so search still opens).
- `SimGameHeader`: one sticky glass line. Back arrow, `Wk 3/14 S1/5`, the team as a tappable chip (opens the team sheet), search, and the overflow menu (rules, reset week, delete). The pre-advance notes are `SimStatusChips`, tappable and scrolling with the content.
- `SimGameOrb`: the game's own navigator, replacing the global orb inside the game. Brand mark plus the current page name and a badge for trade offers. One tap opens Home, Team, Players, Trades, League, More with the current page lit, plus search, All games and a way home.
- The footer is Advance only (`SimActionBar` / `SimOffseasonBar`, `.action-pill`). Auto-set lives on Home, "What to do this week".
- The six top tabs and the "This week | League" strip are gone on phones (`max-md:hidden`); the league cards are a collapsed "League" section on Home.

Layout rule (immune to iOS Safari fixed-position drift): nothing here is `position: fixed` or JS-positioned. The game is a `min-height: 100dvh` flex column and the footer is a `position: sticky; bottom: 0` `.bottom-stack` at the end of it with `env(safe-area-inset-bottom)` padding. The orb is `position: absolute` inside that stack (`.game-orb-dock`), so it can never disagree with the pill.

`BottomTabBar` (`components/ui/BottomTabBar.tsx`, lib twin `lib/bottomNav.ts`) is the site shell's footer (Phase B); it lives inside the same `.bottom-stack`. It is not used in the game.

### The smart floating pill (approved: option B base + variant V2, `docs/audits/2026-11-footer-options.html`, `2026-11-smart-pill-options.html`)

- **Look**: a detached glass capsule 12px off the screen edges and above the safe-area inset (`--bar-side-inset`, `--bar-pill-bottom-gap` + `env(safe-area-inset-bottom)`), frosted glass tokens only (translucent surface, blur, lit top hairline, soft shadow). The Fantasy Sim bar (`.action-pill`, `SimActionBar` / `SimOffseasonBar`) uses the same glass and capsule radius so the two chromes match; the orb badge hugs the orb.
- **No page context**: the global tabs. The lit tab expands to icon + label in the cyan glass capsule (gold hairline), the rest are icon-only with `aria-label`s, 44px+ targets.
- **With page context** (V2): ONE row. The global tabs fold into two icon buttons (the section you are in + a menu button, `aria-expanded`); the page segment (page tabs as a `tablist`, one primary chip) takes the rest. The menu button unfolds the full global row (Today / Team / Trades / League / More) in the same pill; picking a tab, Escape or tapping outside folds it back. The lit page tab is one capsule that slides between tabs (transform + width, measured). More still opens the shared sheet.
- **API**: a page calls `useBottomPillContext({ id, label, tabs, activeKey, onSelect, primary })` (`lib/useBottomPillContext.ts`, store `lib/bottomPillStore.ts`, types and `normalizePillContext` in the `lib/bottomNav.ts` twin) and drops its own page-tab row only when the hook returns true (the pill is on screen and showing that context). Consolidate, never remove: desktop, the flag off and signed-out pages keep the in-page tabs. At most `PILL_MAX_TABS` (5) tabs; one primary; the tab strip scrolls inside the pill if it must.
- **Motion** (lib/motion.ts tokens, opacity/transform only): entering a page slides the segment in; the menu cross-fades the layers and fans the global tabs out; the primary chip pulses once on mount. Reduced motion: crossfade only (no slide, scale, fan or pulse).
- **One sticky mechanism**: both layers share one grid cell, so the pill is one row tall in every mode and the stack height is the content clearance. Never `position: fixed`. Guards: `lib/bottomChrome.test.ts`, `lib/bottomBarMetrics.test.ts`, `components/ui/BottomTabBar.test.tsx`, `scripts/sim_layout_playwright/footer_pin.mjs`.
- **Wired contexts**: `PageTabBar` (every Team / Trades / League page: Team = Roster | Players | Waivers | Matchup, Trades = Hub | Finder | Analyzer | History + primary "New trade", League = Rankings | Recaps | Games) registers its family as `family:<key>`; each tab is a route (`PillContextTab.href`, rendered as a link) and the strip steps aside only while the pill is on screen. Fantasy Sim: the draft room (`sim-draft`: Players | Queue | Roster | Picks + Auto-pick) and Sim Team (`sim-team`: Auto-set). In the game `SimPillHost` marks the pill present and `PillMorph` (in `SimActionBar` / `SimOffseasonBar`) folds Sim to | orb | Advance into the page segment; with no bar mounted (the draft) `PillContextOnly` shows the segment alone. A page swap keeps the context for `PILL_CLEAR_DELAY_MS` so the global tabs never flash between two pages of one family. Not moved yet: the Waivers filter sheet (it owns its own open state), real-league Roster has no auto-set action to promote.
- **App**: no tab bar (GM orb + More), so `components/BottomPill.tsx` hosts the screen's action row (Sim to | orb | Advance) and morphs to the page segment (Reanimated, `useReducedMotion`); the Sim bars use the same glass. `lib/bottomPillStore.ts` / `useBottomPillContext.ts` are mirrored twins.

## Phone site shell (Phase B, flagged)

Below 768px, for signed-in users with the flag on, the floating GM orb and the crowded header are replaced by:

- `AppShellBar` (`components/AppShellBar.tsx`): in-flow sticky `.bottom-stack` at the end of the app column (no `position: fixed`, no JS placement, `env(safe-area-inset-bottom)`). Inside a league: Today / Team / Trades / League / More. Outside: Home / Portfolio / Fantasy Sim / News / More. More opens the full grouped menu from the shared `navCatalog.ts` (groups, glyphs, Pro markers).
- `ShellActionSlot` (`<ShellAction>`): a page renders its primary action into the slot above the tab bar (page-aware action strip). Renders nothing where the slot is absent.
- `ShellHeader`: one standard header: back labelled with the parent page ("< Players"), title, league chip, search, alerts bell (only exists inside a league). Search stays the orb sheet's search.
- Fantasy Sim keeps its own header and game orb (`pathOwnsPhoneChrome`); the sign-in/onboarding root `/` keeps the orb where no bar can render.
- Route to tab mapping lives in `lib/shellNav.ts` (`shellActiveTab`), covered by tests.

Flag (`lib/shellNav.ts`, `lib/useShellNav.ts`): `NEXT_PUBLIC_BOTTOM_NAV` = `founder` (default: founder/owner account only), `on` (everyone), `off` (kill switch for everyone, nothing overrides it). `?nav=bottom` turns it on and `?nav=off` turns it off for that browser (remembered in localStorage `fgl:nav`). Naming: "Dashboard" is **Today** everywhere user-facing (route and code names keep `dashboard`); **Fantasy Sim** is the game; **Season Outlook** is the forecast (GM Plan and Games tab; "Season Sim" is a retired term).


## Overlays (one pop-up at a time)

Rule (coridian_, approved): ONE pop-up on screen at a time.

- Opening a pop-up from inside another one REPLACES it on screen. The first stays mounted but hidden (`hidden` /
  `display:none`; on mobile its Modal is not visible), so its scroll, typed text and selections survive.
- The newer pop-up shows **‹ Back to <previous title>** (`OverlayBack`). The phone back gesture / browser Back (web;
  Android back on mobile) goes back one step. The **X closes everything** and returns to the page. Tapping the scrim
  equals the X; Escape equals Back.
- Confirms happen in place inside the pop-up (`ConfirmInPlace`), never by opening another. Toasts are not pop-ups and
  sit above everything. A real dialog (`kind: "dialog"`, e.g. sign out) sits ON TOP of the visible sheet without hiding
  it, and closing it returns to the sheet underneath.
- Layers (one place, `OVERLAY_Z` / `--z-overlay-*`): sheets 70, dialogs 90, toasts 100. No pop-up picks its own z-index.
  This is what fixes "quick view opens behind a picker": there is no longer a second visible layer to be behind.

Pieces (web; mobile uses the same stack):

| Piece | File |
|---|---|
| Pure stack: entries, hidden / top / previous sheet, back, close-all, history plan | `lib/overlayStack.ts` (byte-identical twin in mobile) |
| Hook every pop-up shell calls once (`useOverlay({ title, onClose })` -> `hidden`, `backTitle`, `back`, `closeAll`, `zIndex`) | `lib/useOverlay.ts` |
| Browser-history sync (one entry per open overlay; Back dismisses the newest; X pops its entries once; route change forgets them) | `lib/overlayHistory.ts` |
| One runtime: body scroll lock, history, close-all on route change | `components/OverlayRuntime.tsx` (mounted in `app/layout.tsx`) |
| Back button | `components/OverlayBack.tsx` (mobile: inside `Sheet.tsx`) |
| Swipe down to dismiss (per pop-up, unchanged) | `lib/useSheetDragDismiss.ts` |

A shell does: `const overlay = useOverlay({ title, onClose })`; renders its backdrop with `hidden={overlay.hidden}`;
renders `<OverlayBack overlay={overlay} />` at the top; wires the X and scrim to `overlay.closeAll` and Escape to
`overlay.back`; and focuses itself when `!overlay.hidden`. It must NOT lock body scroll, push history or set a
z-index itself. Hand-rolled `.pqv-backdrop` shells keep their markup and only gain those lines.

Migrated (all of them): web `Sheet` (and everything built on it: TapForWhy, FilterSheet, StructuredRow, the game
navigator), `PlayerQuickView`, `SimSheet` (claim, team and every Fantasy Sim sheet), `TradePickerSheet`, and through
`PopupShell` (the shell for hand-built `.pqv-backdrop` pop-ups) `ManagerProfileSheet`, Matchup `SwapSheet`,
`PercentileExplorerSheet` and the multi-team "Send to" sheet; `AlertsDropdown`, the GM orb menu and
`EmbeddedCheckoutModal` call `useOverlay` directly. `PasswordRecoveryGate` is a blocking gate (not dismissible, so not on
the stack) but takes its layer from `--z-overlay-dialog`. Mobile: `Sheet`, and every `SheetModal` registers itself
(`lib/useOverlay.ts`), so all ~30 Modal-based pop-ups replace each other instead of fighting (RN cannot present two
Modals reliably); `Sheet` also draws the Back row.

Not overlays (left as they are): header and sidebar dropdown menus (`role="menu"`), the privacy-mode pill, the Beginner
Help popover, in-picker filter panels and in-place confirms (`ConfirmInPlace`), toasts.

New pop-ups: use `ui/Sheet`, or `PopupShell` for a hand-built layout. Never hand-roll a backdrop, set a z-index, lock
body scroll or push history.

Tests: `lib/overlayStack.test.ts`, `lib/overlayHistory.test.ts`, `components/OverlayManager.test.tsx` (replace, Back,
selection survives, X), `components/OverlayRuntime.test.tsx` (the one scroll lock). Real-browser check:
`scripts/sim_layout_playwright/overlay_back.mjs` (browser Back closes a pop-up without leaving the page; a card opened
from the trade picker replaces it and Back returns with the selection intact; the X closes everything).

## CompactModule (the one compact / expandable module)

One card for every dense block, so a page is a short stack of these instead of a wall of cards. It is **never an empty
header when collapsed**: line 1 is a small title, line 2 (at most two lines) is a dense summary of the key numbers and
status, and an optional single trailing `action` (a button such as "Draft Gibbs") works without expanding.

```tsx
<CompactModule
  id="draft.clock" title="Draft clock" tone="action" persist={false}
  parts={simDraftSummaryParts(draft, teams, needs)}   // "R1 P2 · You pick now · need RB/WR · 1/192"
  action={<Button size="sm">Draft Gibbs</Button>}
>
  {/* expanded body: needs, best available, auto-pick */}
</CompactModule>
```

- `parts` is `CompactPart[]` (`{ key, text, tone?, strong? }`), composed by pure helpers in the lib twin
  (`compactModule.ts` for the primitives; `simSummaries.ts` for the Sim home modules; `simDraft.ts` for the draft).
  Empty parts are dropped and the line is capped at six, so a summary stays a summary. Every module that can be
  collapsed MUST pass `parts` (or the test for its page fails the "not an empty header" rule); `summary` (a node) is the
  legacy right-aligned fallback only.
- `expandIn="inline"` (default) opens the body under the header; `expandIn="sheet"` opens it in the shared `Sheet` for long
  bodies. The open state is remembered per `id` (`persist={false}` for live state such as the draft clock).
- Header is one 44px-minimum button with `aria-expanded` and a name of "title: summary. Expand/Collapse"; the action is a
  sibling button so it never nests inside it. 44px targets, tokens only, no new colour.
- Mobile twin: same props (`testID` instead of `testId`); tone colours come from the theme.

Not-yet-migrated pages keep working; migrate one page per PR (the plan's later phases). `SimFold` already renders it.

## PlayerBadge (symbols, not words)

coridian_ (phone, 2026-11-14): *"why is there only one rookie tag on one player, even though this is a fully rookie draft... I don't
think a rookie draft should even have a rookie tag because it's obvious; if they do need tags we need some sort of symbol like Sleeper
has (a purple R). We need symbols so we can stop using full words that take up all the space."*

Every status a player can carry is ONE glyph on a 20px tinted circle (capsule for two characters), never a word chip. Web
`ui/PlayerBadge.tsx` (`PlayerBadge`, `PlayerBadges`, `BadgeLegendSheet`, `BadgeLegendButton`), app `components/PlayerBadge.tsx`, rules and
registry in the byte-identical twin `lib/playerBadges.ts`.

| Glyph | Kind | Tone | Glyph | Kind | Tone |
|---|---|---|---|---|---|
| O | Out | danger | FA | Free agent | success |
| IR | Injured reserve | danger | $ | On the trade block | action |
| D | Doubtful | danger | ◎ | Trade target | accent |
| Q | Questionable | warning | C | Captain | action |
| T | Taxi squad | warning | ★ | Your player | accent |
| By | On bye | muted | S / F | Starter / Fill-in | success / accent |
| R | Rookie | accent | BN / BU | Bench / Backup | muted |
| N | New | action | | | |

- **Tones are the six existing tokens** (success, danger, warning, muted, accent, action). Same tint recipe as `ToneBadge`; no new colour.
- **Accessible name**: each badge is `role="img"` with `aria-label` and `title` (the long-press / hover tooltip) = the full word
  ("Out: 2 wks"). The visible glyph is `aria-hidden`. Weeks and other detail show **only** in the quick view header
  (`showDetail`) or the tooltip, never in a list row.
- **Legend**: `BadgeLegendSheet` lists every symbol and what it means. A strip that is not inside a tappable row takes
  `onLegend` (the PQV header: 44px tap target); list headers can place a `BadgeLegendButton` ("ⓘ Key").
- **Context suppression** (`contextSuppressed`, `simSuppressedBadges`): a kind that EVERY row of the list carries (3+ rows) is not
  drawn. A rookie draft board shows no Rookie badge, a free-agent board no FA, the IR group no IR. Health badges (Out, D, Q) are
  never suppressed. A mixed list (a startup draft with vets and rookies) still tags rookies.
- **Cap**: at most `BADGE_MAX` (3) per row in severity order (health, reserve, bye, rookie/new, ownership, role), the rest as "+n"
  (named in the strip's aria-label). The quick view header allows 6.
- **One strip**: `PlayerListRow` merges its `chip`, its status-like `tags` (Free agent, On block, Your team, fill-in, IR...) and its
  `badges` into one strip after the name; only non-status tags (an AI team's name, "Hot streak") remain text pills on line 3.
  `badgeFromTag` is the bridge, so existing callers did not change.
- **Routed through it**: `PlayerListRow` (all of FantasyDesk and Sim lists), `SimDraftRow` / `SimPlayerLine` / `SimRosterLine`,
  Sim roster, IR/taxi groups and move sheet (`SimPlayerChips`), the Sim Players / draft / rookie-draft lists, the Player Quick View
  header tags and Health chip, the hero ROOKIE badge, the Sim trade "Your block" mark, and web `PlayerInjuryBadge`.
- **Not yet routed** (follow-ups, listed so they are not forgotten): app `PlayerIdentityRow` injury pill and `PlayerCard` injury
  dot (already short-code pills, solid when ruled out), `WeatherReasonChip`, trade-asset rows, waiver/briefing chips that use `PlayerInjuryBadge` on the real side (web done, app not).

## Visual identity

Not a new look: the liquid-glass style we already have, written down so every page reads as one product. Apply it page by page
(first: the Fantasy Sim offseason). A page that cannot name its hero or its modules is not done.

1. **Rhythm: one hero, then dense modules.** Each page has exactly one hero (the thing the user came for: a draft clock, a score,
   the stepper) and below it a short stack of `CompactModule`s (`gap-2`, 8px, on a phone). No stand-alone prose cards. A module
   is informative collapsed (summary line of counts and status) and may carry one icon action.
2. **Glass surfaces with a subtle accent**: `AccentCard` / `glass-surface` only, the 3px left rail carries the module's tone (or the
   position colour on a player). Surfaces never get a second border style or a new fill.
3. **Section headers carry an icon**: 14px line glyph + small uppercase title (the `CompactModule` title). A page's step names are
   never repeated as module titles (the stepper says "Draft", the module says "On the clock").
4. **Symbols over words** for status (PlayerBadge); counts over sentences in summaries (`14/12 spots · cut 2 · QB2 RB5`).
5. **Avatar and OVR are one thing everywhere**: `PlayerAvatar` + `OvrGauge` (`PlayerListRow` stat), same size per density; a player
   never gets a second rating number.
6. **Spacing scale** (`--space-*`, mobile `spacing`): 4 / 8 / 12 / 16 / 24. 8 between modules, 12 inside a card, 16 page gutter. No dead
   space: a card with one line of text becomes a module summary.
7. **Actions**: the obvious ones are 44px icon buttons with an `aria-label` (trade, open team, draft), words only where the action
   is not guessable ("Cut"). One primary action per module.
8. **Motion** is the existing vocabulary only (`lib/motion.ts`): rise on entrance, count-up on numbers, nothing on lists over 24 rows.

### Applied: Fantasy Sim offseason (`SimGameOffseason`, app twin)

Before: a flat header card (kicker, three word chips REVIEW / ROOKIE DRAFT / ROSTER CHECK, a sentence), then full-height cards of prose,
IR / ROOKIE / OUT chips on every row and two text buttons. After: one hero (heading + 3-node icon stepper with a connector, done steps
get a check, the current step is ringed), then modules with a header icon and a counts summary: `2026 season` (9-5 · 3rd · Semifinal),
`Retirements` (2 retired · 1 yours), `Aging` (3 up · 2 down), `Your picks`, `On the clock` (R2 P5 · You pick now · 38 left, glows on
your turn), `Draft log`, `Roster` (14/12 spots · cut 2 · QB2 RB5, with a trade icon action), `Future picks`. The rookie board has no
Rookie badge (context suppression). The summary builders are the lib twin `simOffseasonSummary.ts`; `SimCollapse` is now a thin
adapter over `CompactModule`, so the Team tab and dynasty screens got the same module for free.
## Module templates (the catalog every page is built from)

Direction (coridian_): the data points exist; the problem is how they are represented. Every page is a short stack of a
small set of templates, and the Fantasy Sim uses the same templates through thin adapters. No module may be an empty
header when collapsed. The catalog lives in code, `lib/moduleTemplates.ts` (byte-identical web + app twin, listed in
`IDENTICAL` in `scripts/check_lib_twins.mjs`): `MODULE_TEMPLATES` (purpose, required props, collapsed-form rule, density
tier, min/max height, web and app component) and `SIM_TEMPLATE_ADAPTERS`.

| Template | Web | App | Collapsed form must show | Tier / height |
|---|---|---|---|---|
| Hero | `ui/ModuleTemplates#Hero` | `ModuleTemplates#Hero` | always open: big value + one context line + signed trend (sparkline from 2+ points, none otherwise) | T2, 88-120 |
| CompactModule / CompactSummary (the base) | `ui/CompactModule` | `CompactModule` | title + 1-2 line summary (`parts`), optional one action | T0, 56-96 |
| StatStrip | `StatStrip` inside `ui/ModuleTemplates#StatStripModule` | `DashboardStatRow` inside `StatStripModule` | "Power #3 · Starters #5 · Age 26.1" built by `statStripParts` | T3 |
| LinkModule (a CompactSummary that navigates) | `ui/ModuleTemplates#LinkModule` | `LinkModule` | same summary, arrow instead of +/- | T0 |
| Row (player / team / pick / trade asset) | `PlayerListRow`, `PickRow`, `StructuredRow` | `PlayerListRow`, `DraftPickAssetRow` | name + chip line; right edge = one action or number | T1, 56-72 |
| Section header | `SectionHeading` | `SectionHeading` | title + count/context; never alone | T0 |
| ActionBar | `SimActionBar`, `.bottom-stack` | `QuickActionsGrid` | max 3 labelled 44px actions; hidden if none | T0 |
| List + FilterRow | `PillRow` + `ui/FilterSheet` | `FilterSheet` | ONE 44px control row; the rest behind Filters | T0 |
| TabPage shell | `PageTabBar` | `SegmentedTabBar` | one tab row, 2-5 tabs, never a second | T0 |
| Empty / Error / Loading | `EmptyState`, `ErrorState`, `Skeleton` | `EmptyState`, `ErrorState` | title + reason + one next step | T1 |
| TrendChart usage | `ui/TrendChart` | `TrendChart` | `variant="compact"` sparkline beside a number | T2 |
| InsightLink | `ui/InsightLink` | `InsightRow` | the stat itself, tappable | T0 |

Pure builders in the lib twin keep the two platforms identical: `statStripParts`, `listSummaryParts` ("3 alerts · Gibbs out"),
`trendModel` (delta, direction, tone; `higherIsBetter=false` for ranks), `heroParts`, `collapsedVerdict`.

**The collapsed-form rule (lint-style, enforced).** A collapsed module renders at least `MIN_COLLAPSED_CHARS` (12) characters of
real data; placeholders ("—", "Loading…") do not count and a title never counts. Enforced three ways:
`collapsedVerdict` (lib), `collapsedModuleProblems(container)` in `ui/assertCompactInformative.ts` (page tests assert
`expect(collapsedModuleProblems(container)).toEqual([])` on Today and My Team), and a source scan in
`ui/ModuleTemplates.test.tsx` that fails if any `<CompactModule>` in `web-next/src` or `mobile/src` lacks `parts`/`summary`.

**Fantasy Sim adapters** (no template of their own): SimFold (CompactModule + `simSummaries`), SimDraftHero (Hero + bar),
SimDraftRow / SimPlayerLine / SimRosterLine (Row), SimDraftBoard filters (List + FilterRow), SimActionBar (ActionBar),
SimNotice (state), SimGameHome modules (CompactModule via `simInboxParts` etc.), SimGameTeamSheet / SimPlayerSheet (Sheet tabs).

**Row rule for repeated facts.** A fact every row of a list repeats (the same drop candidate, the same "of $81 remaining") is said once
for the group (`lib/waiverGroups.ts`: `sharedDropCandidate`, `sharedBidNote`), and a row only states it when it differs. A row whose whole
surface is tappable has no chevron.

**Phone-only chrome.** `md:hidden` is guarded globally in `globals.css` (an unlayered `display` rule used to beat the Tailwind utility and showed
the phone header on desktop, stacked above the real one).

**Trade ideas** (Trade Hub, Trade Finder, GM Plan) are `CompactModule`s: the partner is the title, the summary is
`lib/tradeIdeaSummary.ts` ("+450 · J. Gibbs for C. Olave +2 · Fair · High confidence", names already `J. Surname`), and the
former card (tags, posture, package, odds, meters, share) is the expanded body. Trade History rows, Trade Analyzer's secondary
verdict blocks, Games league odds / what-if / leaderboard, Draft Center posture / picks / signals and the Live Draft sections follow
the same rule.

Rollout status per page: `docs/audits/2026-11-module-templates-rollout.md`.

## Player anatomy (2026-11-14: row, compact card, trade card, bar row, peek sheet)

coridian_ picked these from `docs/audits/2026-11-module-variant-sheets.md` (sheets 1 and 3). One set of templates serves
FantasyDesk (`mode="desk"`) and Fantasy Sim (`mode="sim"`); the logic is the byte-identical lib twin `lib/playerAnatomy.ts`
(`playerRowModel`, `fairnessMeter`, `barFractions`, `nextOpenId`, `nextSheetSnap`, `orderPlayerSheetTabs`, `AVATAR_SIZE`).

| Template | Web (`components/ui/`) | App (`components/`) | Where it is used |
|---|---|---|---|
| `PlayerAvatarSlot` | `PlayerAvatarSlot.tsx` | `PlayerAvatarSlot.tsx` | inside every template below; never placed by hand |
| `PlayerAccordionRow` + `usePlayerAccordion` | `PlayerAccordionRow.tsx` | `PlayerAccordionRow.tsx` | Players, My Team roster (web + app) |
| `CompactPlayerCard` | `CompactPlayerCard.tsx` | `CompactPlayerCard.tsx` | trade sides, bar rows |
| `TradeCompactCard` | `TradeCompactCard.tsx` | `TradeCompactCard.tsx` | Trade Hub, Trade Finder, GM Plan ideas (`TradeIdeaCardView` web, `TradeIdeaCard` app) |
| `RankRow` (bar row) | `RankRow.tsx` | `RankRow.tsx` | Waivers add rows (web bar), standings next |
| Peek sheet (PQV) | `PlayerQuickView` + `SheetHandle snap/onSnap` | `PlayerQuickViewSheet` grip | every player sheet |

- **Compact row (V1 inline accordion)**: two lines. Line 1: avatar, name, position pill, glyph badges. Line 2 (muted): TEAM · Age · BYE. Trailing: ONE
  key number (PROJ, else VALUE) or the sim letter grade. No chevron: the whole row is the tap target (Row rule).
- **Expanded (V2 tile)**: the tapped row swells in place into a glass tile (cyan border for the selection, no gold) with PROJ / VALUE / TREND /
  OVR / page facts, then actions. Gold only on the single primary action (`primaryAction`); the secondary is "Open profile" (the PQV). **One open at a time**
  (`usePlayerAccordion`, `nextOpenId`). Never remove information: anything the old row showed (OVR, position rank, sorted stat, IDP basis, compare link)
  is in the tile.
- **Sim**: `mode="sim"` shows GRADE / ADP / PROJ only. The sim branch of `playerRowModel` has no path to a numeric OVR or the trade value (unit-tested), and
  trade cards use plain words (`fairnessMeter(..., "sim")`: "A better deal for you").
- **Trade card**: title (partner + balance), a compact player card per asset on a give and a get side (avatar included, tap opens the sheet), a fairness
  meter row (marker on a centre-anchored track, label from the server band or the meter), details ("Show details") expand in place.
- **Bar rows**: `barFractions` turns bids / points-for into 0..1 shares of the largest, drawn as a mini bar under the row; one trailing number.
- **Peek sheet (1b)**: the player sheet opens at half height (`SHEET_SNAP_PCT.peek` 56%) with the header and the pill row; dragging the handle up
  (or tapping it) goes full (92%); a fixed height means switching pills never moves the sheet. Pills are the one `Tabs` row in the order Overview, Stats,
  Outlook, History, Scouting (then Profile) via `orderPlayerSheetTabs`; sim hides Scouting when it has none. Sticky tabs and the min-height rule of
  "Sheet tabs" are unchanged; drag-down from peek is still the dismiss gesture.

**The avatar is REQUIRED (coridian_: "properly implemented, not a band-aid").** A template takes a `player` (`PlayerRef`) and draws the avatar itself in
`PlayerAvatarSlot`: always the first, leading slot, sized by tier (`AVATAR_SIZE`: dense 28, row 36, card 44, sheet 56), tier ring, and initials when
there is no photo or it fails to load (generated Fantasy Sim players have none). No module may render `<PlayerName>` outside a template that provides the
avatar. Enforced by `lib/playerAvatarRule.test.ts` (source scan of web and app: a file that renders `PlayerName` must reference an avatar template, or be
on the explicit allowlist; an allowlist entry that now has an avatar fails so the list only shrinks) and `ui/PlayerTemplates.test.tsx` (each template renders the slot).
Allowlist kinds: TEXT (a sentence, headline or tooltip where a picture makes no sense) and TODO (not yet on the templates).

Not yet on the templates (TODO allowlist plus pages): Waivers app add rows and web Explore tiles, Live Draft rows, News, Trade Analyzer pickers (`TradePickerSheet`),
Draft Center, League Recaps, Matchup lineup, Standings (RankRow exists, page not yet moved), Sim roster / draft board / inbox (`SimDraftRow`, `SimPlayerLine`, `SimRosterLine`
should become `PlayerAccordionRow mode="sim"`, and the Sim trade inbox `TradeCompactCard mode="sim"`), Manager profile, Opponent profile, Sim team card / history / draft grid.

## Player row anatomy (shared by FantasyDesk and the Fantasy Sim)

`PlayerListRow` is THE row: line 1 name (+ the one status chip), line 2 muted meta (TEAM, age, bye), line 3 the **chips
under the name**: labeled stat chips (PROJ / OVR / ADP / EDGE; in the Fantasy Sim the OVR slot is a LetterGrade and there is no EDGE) then page tags (max 2 plus "+N"), then optional
`chipsExtra` (small inline controls such as a Queue toggle). The chip line is indented to the name, **wraps instead of
clipping**, and nothing sits at the far right except **one trailing action** (`actions`). The Sim reuses it through
`SimDraftRow`, `SimPlayerLine` and `SimRosterLine`; do not build another row.

## Fantasy Sim: no internal rating, ever

The model's trade value is the sim's own rating, so it is never shown: no "Value"/"Trade value" label, chip or tile, no numeric OVR, no
overall / position rank and never a sort by it. coridian_ (2026-11-14): a numeric OVR is a tell ("I just draft the highest value players
and it works"), so the sim shows **letter grades** like Madden / 2K. Trades describe a deal in plain words (`simDealWords`), never numbers.

### Fantasy Sim letter grades (web + app)

- **`LetterGrade`** (`ui/LetterGrade.tsx`, app `components/LetterGrade.tsx`, rules in the byte-identical twin `lib/simGrade.ts`): 12 bands
  A+ .. F in a tinted capsule (same recipe as `PlayerBadge`). The ramp is five existing tokens: **green** (`success`, A), **cyan**
  (`accent`, B), **gold** (`action` / app `premium`, C), **orange** (`warning`, D), **red** (`danger`, F); +/- share the tone. The letter
  keeps the primary text colour (lightly mixed with the tone) so contrast holds in both themes. A "?" marks a scouting estimate (rookies);
  `size="lg"` also prints the range ("B-/B+"). The accessible name is the full read: "Grade B plus, strong starter. Scouts are unsure: B to
  A minus." No grade renders an invisible placeholder with the same footprint so list columns align.
- **`PlayerListRow`**: a stat with `grade` (even `null`) renders `LetterGrade` instead of the `OvrGauge` ring; the Sim reaches it only through
  `simListStats` (PROJ, GRD, ADP; the EDGE chip is gone: it compared model value rank with ADP). The real FantasyDesk keeps `OvrGauge` and its
  numbers.
- **`GradeBar`**: one position attribute (label, coarse bar tinted by the grade tone, letter), in the sim quick view's "Attributes" section
  with the line "From usage and history. Graded on their own: they do not add up to the overall grade."
- **`GradeLegendSheet` / `GradeLegendButton`**: every band and what it means, what "?" means, what the attributes are. The hero `GradeTile`
  opens it.
- **Player Quick View in the sim**: `simSections.heroGrade` replaces the Player score ring; the Value tile, the overall / position rank line
  and the model radar do not show (`PlayerHeroHeader` `gradeTile` / `hideValue`). The Overview tile reads "Grade".
- Where it shows: draft room and board, Players / waivers, rosters and team sheets, league rosters, trades and the block, recap
  players, carousel rows, the draft hint, team cards (top assets), the quick view hero.
- Tests: `lib/simGrade.test.ts` (web vitest + app node:test), `ui/LetterGrade.test.tsx`, `SimPhoneLayout.test.tsx`, `SimPlayerSheet.test.tsx`;
  server: `tests/test_sim_grades.py` (including "no API response contains the raw overall"). Calibration: `docs/audits/2026-11-sim-letter-grades.md`.

## Notice toast (auto-dismiss)

`SimNotice` is the shared notice. A confirmation the player caused ("Trade completed") removes itself after ~4s, a warning
after ~7s, an error never (`noticeDismissMs` in `lib/compactModule.ts`, same on web and app). A new message restarts the timer.

## One tab row, one filter row

A page has ONE tab row. `PillRow variant="scroll"` shares a short row's width equally (no empty bordered box after the
last tab) and scrolls only when its labels overflow; the app's `SegmentedTabBar scrollable` does the same. Filters and sort
share one compact row (`draft-filters`: position pills plus a sort control), never one strip each.

**One tab row, one control row (2026-11 pass 3).** When a page already shows its family strip, the page's own views
(Waivers: Recommended / Explore / Watchlist; Games: Season Outlook / Pick'em; Recaps: Recaps / Roundup / History / Storylines)
are a `ui/ViewSelect` (a 44px native select) in ONE compact control row together with that view's filters (Waivers: the
All/Add/Stash/Watch select, or search + Filters), never a second tab row. App twin: `FilterDropdownButton` labelled "View"
(+ "Show" / `FilterSheet`) in a `controlRow`. Pages with no family strip (Draft Center, GM Plan) keep their one `PillRow`.

## Page tab families and glass chrome (2026-11)

Related pages are tabs of one page family (`lib/pageFamilies.ts`: Trades, Team, League), rendered by `PageTabBar` over
`PillRow glass` (sticky, scroll-snap, cyan glass active pill). Each tab keeps its route. App: `components/PageFamilyTabs`
(SegmentedTabBar scrollable over the same `lib/pageFamilies.ts`; `lib/pageFamilyRoutes.ts` maps a tab to its screen, imported
leagues only get the tabs they can open) on MyTeam, Players, Waivers, Matchup, Trades (Hub/Finder/Analyzer switch in place,
History opens its screen), Teams, Recap and Games. The phone footer
(`BottomTabBar`) uses the same glass tokens. Plan: `docs/audits/2026-11-menu-consolidation.md`.

## Sheet tabs (quick views that would otherwise scroll long)

Rule: a pop-up that scrolls past about one and a half screens groups its content under the shared `Tabs`
(`components/Tabs.tsx`, app `components/Tabs.tsx`), never one long page. The pop-up shell is unchanged (it still goes
through `useOverlay` / `PopupShell` / `Sheet`, so the one-pop-up-at-a-time, Back and X rules in "Overlays" hold).

- **Plans live in a lib twin**: `lib/sheetTabs.ts` (byte-identical web + app, listed in `IDENTICAL` in
  `scripts/check_lib_twins.mjs`) decides which tabs a real-league sheet has, so both platforms group the same content
  under the same names. A tab with nothing to show is dropped; the first tab always exists and carries loading /
  upsell / empty states. Tests: `lib/sheetTabs.test.ts` (both trees), `Tabs.test.tsx`,
  `ManagerProfileSheetTrades.test.tsx`, `PercentileExplorerSheet.test.tsx`.
- **Sticky strip**: web `Tabs` wraps the strip in `.tabs-sticky` (position sticky, top 0, frosted glass, so content slides
  under it). Opt out with `sticky={false}`. App: `useTabs()` returns `{ bar, panel }`; a sheet makes the bar a direct
  child of its `SheetScrollView` and pins it with `stickyHeaderIndices` (Player Quick View: index 2 = top bar, hero,
  strip), or puts the bar above its ScrollView (Manager profile) so only the panel scrolls. `<Tabs>` is the unpinned
  stack of the same two pieces.
- **No layout jump**: the panel keeps the tallest height it has shown as its minimum (`nextPanelMinHeight`), so a short
  tab after a long one never pulls the sheet or the strip.
- **State**: the open tab is remembered per surface id for the session (`lib/sessionTab.ts`); anything that must survive a
  tab switch (search text, scrubbed bucket, selection) lives in the sheet's own state, not inside a panel, because panels
  are lazy and unmount when hidden. The slide between panels is off under reduced motion (CSS media query / OS setting).
  Swipe-to-dismiss is untouched (a drag still starts from the handle, or the body only at scroll top); tabs are tapped,
  not swiped, so they never fight it.
- **Fantasy Sim isolation**: sim sheets (SimPlayerSheet, SimGameTeamSheet, sim sections of the PQV) keep their own plans;
  `sheetTabs.ts` knows nothing about the sim and the sim tabs never render real news.

| Sheet | Tabs | Web | App |
|---|---|---|---|
| Player Quick View (real) | Overview, Outlook, Stats, Profile | yes | yes (sticky strip) |
| Player Quick View (sim) | Overview, Outlook, Scouting, History, plus Stats/Profile for real-backed | yes | yes |
| Sim team sheet | Overview and more | yes | yes |
| Manager profile | Overview, Tendencies, Trades | yes | yes (strip pinned above the scroll) |
| Percentile explorer | chart + comparison stay on top; tabs In this bucket, Find a player, My roster | yes | yes |

Left as they are (short or already segmented): trade picker (Players / Picks segmented control), Matchup swap sheet,
share previews, filter sheets, alerts dropdown.

## Charts: one module (web `ui/TrendChart` + mobile `TrendChart` + `lib/chartSeries.ts` twin)

Every line / area chart goes through `TrendChart`; never hand-roll an SVG path or add a charting library for a trend.
Data rules live in `lib/chartSeries.ts` (byte-identical twin, tested in `chartSeries.test.ts`):
- A bye / missed / injured week is a gap row (`y: null`, optional `gap`): the line breaks, a dashed bridge crosses it and a
  muted hollow marker sits on it (tap for "Bye week"). Never a blank hole.
- One played point renders a labelled stat with a mini bar ("Not enough weeks yet for a trend"), not a lone dot; no data
  renders a short sentence. 2-3 points get value labels and bigger dots.
- Axes: nice ticks, optional zero baseline, `clamp` (ratings 0-99), exact `yDomain` + `invertY` for ranks; monotone smoothing.
- `variant="compact"` is the axis-free sparkline for compact modules. Tap / hover / focus a point for the tooltip.
- Draw-in animation only under `prefers-reduced-motion: no-preference`. Tokens only.
Adapters: `WeeklyPointsChart` (weekly points, optional projection band), `RatingHistoryChart`, the season-review rank journey.
Not trend charts (left as is): `ModelRadarChart` (radar), `CircularProgressRing`, progress bars.

## Bottom chrome: one sticky mechanism

Everything pinned to the bottom of a phone screen (tab bar + action strip, Fantasy Sim bar + orb, GM orb) is an in-flow
`position: sticky; bottom: 0` element: `.bottom-stack` (full-width) or `.bottom-rail` (zero-height rail, orb absolute in it).
Never `position: fixed`, never JS-placed. Sticky is clamped to its parent's box, so the parent must span the whole document:
html/body never get a fixed height (body is `min-height: 100dvh`), and the column chain uses `flex-auto`, not `flex-1`/`min-h-0`.
`lib/bottomChrome.test.ts` guards this; `scripts/sim_layout_playwright/footer_pin.mjs` checks it in a browser.

## Fantasy Sim UI pass (2026-11-14)

Audit and status: `docs/audits/2026-11-sim-ui-pass.md`. New shared pieces: `SimProgressBar` (web + app `SimGameParts`), `lib/simHub.ts`
(saved-game rows), `reviewSectionParts` (every Season in Review section is a `CompactModule`, never a bare header), `simHeroTiles` /
`simOutlookTiles` / `simProfileRead` (the sim player sheet: the hero shows This week + ADP, never Value or Usage; Outlook tiles + an
always-drawn projection chart; a "Scouting read" for players without a generated scouting report), `simLineupParts` / `simBenchParts` /
`simStandingHero` / `simMenuHero` / `simRulesParts` (Team tab, Standings hero, Game menu), and `SimTeamCard dense` for pickers.

## Players-first stacks (2026-11-14, coridian_ picks from the variant sheets)

Picks: `docs/audits/2026-11-module-variant-sheets.md`. Shared by FantasyDesk and Fantasy Sim, web + app via lib twins
(`statusHeader.ts`, `recapCard.ts`, and additions to `matchupModules.ts`, `simDraft.ts`). Cyan is the one primary action
colour in these modules (`Button` primary); gold is premium meaning only. The sim never shows a numeric rating or Value:
projection, ADP and letter grades only. Every player render uses the shared `PlayerAvatar`.

### StatusHeader (hero + module stack, V2 "players-first")
`ui/StatusHeader` / app `StatusHeader`: status ring (`StatusRing`: pct + centre text), up to **3** mini stats, "Needs your
attention" list of up to **3** player rows (`PlayerRow` + avatar; a row with `detail` expands inline with an Open link; the
right edge is one figure or one letter grade), then the one primary action, then `children` (CompactModules). The page
passes a `StatusHeaderModel` from the pure builders in `lib/statusHeader.ts`:

| Page | Builder | Ring | Rows |
|---|---|---|---|
| Today (`TeamStatusHero`) | `buildTodayStatusHeader` | win chance | `splitTodayAttention`: lineup holes (`lineupAttentionItems`) + single-player Needs-attention items |
| My Team | `buildTeamStatusHeader` | team value percentile | `rosterAttentionItems` (starters out / bye / injured) |
| Sim Home | `buildSimStatusHeader` | this week's win chance | `simHomeAttentionItems` (starters out, uncovered byes, best waiver target) |

Nothing is dropped: an entry leaves the plain "Needs attention" card only when a player row now says the same thing;
the Lineup / Standing / Position rooms modules stay under the header. Rows reuse the existing `PlayerRow`; when the compact
V1/V2 `PlayerRow` lands, swap it inside `AttentionRow` only.

### Stat strip (V1 compact + V2 expanded)
`StatStripModule` (web `ui/ModuleTemplates`, app `ModuleTemplates`): compact = one row of small glass tiles always visible,
each an `InsightLink` to what explains it; "Rank bars" expands the same stats into labelled `FillBar` rows (`fill` 0..1 from
`rankFill` / win share; items with no honest scale list their value). The old collapsed-summary header is gone; the tiles
are the informative collapsed form (the aria group name keeps the "Power #3 · Starters #5" sentence).

### Matchup hero and ticker (6)
`ui/MatchupModule`: `MatchupHeroCard` (week + LIVE/FINAL, win chip, both scores, win bar, "Proj final ... · N players left",
two swing players with avatars = widest projection range still to play on each side, tap opens the player peek, one cyan
"Open lineup") and `MatchupTicker` ("WK 7 · You 112.4 - 98.1 Mike · 71%", links to the Matchup page). Model: `matchupCardModel`
(`matchupSwingPlayers`, `matchupTickerParts`, sim adapter `simMatchupCardModel` using floor/ceiling). Used on the Matchup page and the
Sim Home matchup card; the ticker is the form to use wherever matchup is one module in a stack.

### Sim draft clock bar (7a)
`CompactModule` gained `preview` (always-visible line under the header, outside the toggle button). `SimDraftBar` is the
clock's preview: best-available avatar, name, position and letter grade (ADP when the game has no grade), tap opens the
player; expanding shows the existing on-the-clock module. `simDraftBarModel` in `lib/simDraft.ts`. The grade is read from
the player's `grade` once the letter-grades change lands.

### Recap card (7b V2)
`ui/RecapCard` + `lib/recapCard.ts`: kicker, optional grade/finish badge, three label/value rows, extra rows behind "More".
Used on the StoryCarousel Around the league / Season complete / Next week pages and as the Season in Review stats cards.
Player-line pages (Result, Matchup, Injuries) keep their avatar rows.
