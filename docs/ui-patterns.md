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
