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
| `UndoToast` | `ui/UndoToast.tsx` | `UndoToast.tsx` | `confirmInPlace.ts` (timing) | built; used by GM targets |

## Sheet

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

**Stacking rule: sheets never stack.** Opening a second sheet hides the first (it stays mounted, so
its state survives) and closing the second brings the first back. The rule lives in
`lib/sheetStack.ts` and is shared with mobile. On mobile a hidden sheet's children are unmounted by
React Native's `Modal`, so keep anything that must survive in the caller's state.

Mobile: `<Sheet open onClose title ... />` wraps the existing `SheetModal` / `SwipeDismissCard` /
`SheetScrollView` (which own the gesture), so the swipe thresholds are unchanged.

Not migrated yet (low-risk later, one at a time): `PlayerQuickView`, `PercentileExplorerSheet`,
`ManagerProfileSheet`, `MultiTeamTradeContent`, `MatchupPlanner` SwapSheet, `AlertsDropdown`,
`SimSheet`, `TradePickerSheet`. They keep working as they are; each can be swapped for
`Sheet` in its own PR. The PQV in particular has bespoke chrome (field/sweep textures, header
layout), so it stays a hand-rolled shell until a design pass decides what becomes a `Sheet` prop.

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
