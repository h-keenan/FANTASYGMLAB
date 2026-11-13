# Convolution audit, 2026-11

Status: audit and plan only. No product code changed in this PR. Prior navigation findings live in
`docs/mobile-ux-plan-2026-11.md` and are not repeated here; this document is about in-screen flows and
information architecture.

Owner directive (verbatim intent): "We're being way too convoluted with how we do all of this ... many places
where something is overcomplicated or convoluted to the point where you can consolidate that information and use
a pop-up or some other way to convey it." Principle: **the first thing somebody does to see more about something
is tap on it, so every number, label and chip should open its "why".** Mobile is 95% of users (native app and web
on a phone). Visual rule: keep the existing liquid-glass look (GlassCard / AccentCard, cyan accent, gold
highlights); everything below is "our current style, restructured".

## 0. TLDR

1. **The app has one "why" mechanism for numbers (stat rows -> `PercentileExplorerSheet`) and nothing else.** Value,
   OVR, rank, grade, verdict, win %, playoff odds, FAAB, balance, posture, confidence and every chip are inert
   `<span>`s. Their explanation is either an always-visible paragraph, a `BeginnerHelp "?"`, an `InfoTip`, a native
   `<details>`, or a `title=` tooltip that **never shows on a phone**.
2. **There is no shared Sheet, PickerSheet, FilterSheet, ConfirmInPlace or TapForWhy component on web.** Six
   sheets are hand-rolled copies of `.pqv-backdrop` + `.pqv-modal` + `SheetHandle` + `useSheetDragDismiss`. Mobile
   already has `FilterDropdownButton`, `SwipeDismissSheet`, `SegmentedTabBar`; the web (which the owner screenshots)
   has native `<select>`s and pill rows.
3. **Confirm patterns are inconsistent.** One matches the owner's ideal (Sim game trash icon expands in place,
   `SimGameContent.tsx:432-447`). Eleven destructive actions have no confirm at all (sign out x3, remove failed
   league, ESPN login, scouting report, GM target, shared trade delete, matchup lineup reset, trade team remove,
   trade asset remove); the Account league remove is a 2-step text-link panel.
4. **Same information in 3 to 5 places:** playoff odds (5), team rank/record/age snapshot (3), stance/direction
   (2 UIs), alerts (bell sheet, Alerts page, Dashboard Watchlist, Since-last-visit chips), league lists (header
   switcher, Portfolio, Account, mobile Home).
5. **Backend-generated copy is delimiter-joined data, not structure.** `modules/draft_center_cards.py:195` builds
   `"Team | Retool | Draft #10 | Future #10 | long sentence"` strings that the Draft Center renders as bullets.
   Same anti-pattern in 7 other generators (section 6).
6. **Trade assets are picked in a block at the bottom of the page** (`TradeAnalyzerContent.tsx:1129-1205`) with ~8
   position pills, one pill per league team and a scroll list; Trade Finder lists the entire roster with
   checkboxes and no filter.
7. **Verdict card is ~17 stacked blocks** (`TradeAnalyzerContent.tsx:332-624`); a Trade Hub idea is ~20 elements and
   its "View details" expander repeats the chips already shown.
8. **PQV has a "Value history" section that is just the value number's history** (`PlayerQuickView.tsx:364`); the Model
   radar is a bottom section that is just the OVR gauge's "why". Both belong behind a tap on the number.
9. **Account is 7 equal cards, Preferences alone is 18+ controls** (`AccountContent.tsx:307-390`); notification prefs
   are in two places inside it.
10. **Onboarding puts the paywall before connecting a league** (`OnboardingPaywall.tsx`, `LandingAuthIsland.tsx`):
    ~10-12 taps to the first league view.

Recommendation: build 6 shared components first (section 2), then do the work in three waves (section 9).

### How to read this document

- **Measured** = recorded by Playwright at 390x844 (touch) against `next dev` in a fresh worktree, or read from
  code with a deterministic count. **Inferred** = tap counts derived by reading routes/components; marked `I`.
  The mock harness only renders the static `/sample-league` route; the authenticated pages need a backend mock
  (the existing `scripts/sim_layout_playwright/simmock.mjs` mocks only `/v1/sim/*`; the "Open game" step did not
  render against it in this run), so almost all tap counts are inferred (`I`). Treat them as +-1 tap.
- Severity H/M/L = how much it hurts the user when hit. Impact = users hit x severity. Effort S (<1 day), M
  (1-3 days), L (>3 days, or needs backend).
- File paths are relative to `web-next/src/components/` unless they start with `app/`, `lib/`, `modules/`,
  `services/` or `mobile/`.

### Measured baseline (390x844, touch, dark)

| Screen | Height | Notes | Basis |
|---|---|---|---|
| `/sample-league` (Dashboard sample) | 1,948px = 2.31 viewports | 8 section headings, 22 tappable controls, 5 numeric values all inert (`#3`, `#2`, `#4`, `#7`, `25.8`), min font 11px | **measured** |
| Dashboard real (from `DashboardContent.tsx:147-231`) | about 13 stacked blocks | StartHere, SinceLastVisit, platform note, hero, DirectionCheckin, NeedsAttention, TodayModule, Trades, My Team strip, Guillotine, Watchlist, More (4 modules) | counted from code |

Screenshot: `docs/audits/2026-11-convolution-audit/dashboard-sample-390.png`. The Draft Center screenshot the
owner supplied (League Draft Decision Signals) was reviewed but not committed because it contains real league
team names; its content is quoted in anonymised form in section 6.

---

## 1. Anti-pattern census (what to hunt for)

| Code | Anti-pattern | Found | Replacement |
|---|---|---|---|
| A | Section that only expands a number/label shown elsewhere on the same screen | PQV Value history, PQV Model, Dashboard My Team strip, My Team Snapshot, TradeIdea "View details", Matchup Insights, Trade Hub Value Signals | TapForWhy |
| B | Inert numbers/chips/badges/ranks/grades/verdicts | SnapshotTile, Fact, PositionChip, CapitalCell, ToneBadge, ValueRing, OvrGauge, ValueStat, grade letters, win %, odds | TapForWhy |
| C | Same info reachable via 2+ pages | section 8 | one source + link |
| D | Long stacks of equal-weight cards | Dashboard (13), Account (7), VerdictCard (17), League Rankings (8), TradeIdeaCard (~20), Waiver top card (14), PQV (10) | SummaryCard->DetailSheet |
| E | Destructive actions without in-place confirm | section 7 | ConfirmInPlace |
| F | Flat endless pickers/lists | Trade Finder roster, Analyzer picker, College Scouting, News, Alerts, Connect league chooser, per-league notification selects, What-if roster | PickerSheet / FilterSheet |
| G | Lone `?` / InfoTip / Glossary / inline explainer paragraphs | 40+ (section 5) | TapForWhy / InfoTip |
| H | Settings scattered | notifications (Account Preferences + NotificationControls), stance (Dashboard + GM Plan), league type (Dashboard More), keeper (My Team) | Settings hub |
| I | Forms with more than 4 fields | Sim setup (~12), ESPN connect, Account Preferences (18+), Live Draft trade evaluator | StepFlow |
| J | Modals on modals | PQV -> PercentileExplorer, TradeOutcomePrompt under PQV, Matchup SwapSheet + PQV | one sheet at a time, back stack |
| K | Delimiter-joined data strings and long generated sentences | section 6 | StructuredRow |
| L | All-caps pill header bars that add chrome without function | Draft Center card labels, `SectionHeading` everywhere | section 7b |
| M | Equal visual weight lists (no hierarchy) | section 7c | top-3 + See all, emphasis tiers |
| N | Raw ids/enums shown to users | section 7d | humanise or hide |

---

## 2. Standard pattern library

All patterns render in the existing glass look (AccentCard/GlassCard surface, cyan accent, gold highlight, 120-300ms
motion, `prefers-reduced-motion` honoured). Each is built once for web (`web-next/src/components/ui/`) and once
for mobile (`mobile/src/components/`), with the same prop names so web and app ship together (web/app parity rule).

### 2.1 `Sheet` (foundation, not user-facing)
Extract the copy-pasted shell used by `PlayerQuickView.tsx:222-246`, `PercentileExplorerSheet.tsx:253-259`,
`ManagerProfileSheet.tsx:168`, `MultiTeamTradeContent.tsx:735`, `MatchupPlanner.tsx:293`, `AlertsDropdown.tsx:146-192`.
- Behaviour: bottom sheet on phone (max 88vh, drag handle via `SheetHandle` + `useSheetDragDismiss`), centred
  dialog >= 768px; one open at a time (a **sheet stack** with a "< Back" header instead of sheet-on-sheet, fixes
  anti-pattern J); focus trap; scroll lock; z-index managed centrally (fixes `TradeOutcomePrompt` z-30 under PQV).
- a11y: `role="dialog" aria-modal aria-labelledby`, Escape and backdrop close, focus returns to trigger.
- Implements: everything below. Mobile: wrap existing `SwipeDismissSheet`/`SheetModal`.
- **Build:** yes (wave 0).

### 2.2 `TapForWhy`
Wraps any number, chip, badge, rank, grade or verdict. Renders the child unchanged plus a hit area (min 44x44 via
padding, not size change), a subtle dotted underline or chevron-dot affordance, and opens a `Sheet` with
**one structure**: headline (the number in words), "What drives it" (2-5 rows: input, value, effect), "How it is
computed" (one sentence, optional), actions (optional). Content comes from the same structured payload the number came
from (never new copy).
- Variants: `inline` (underlined number), `chip` (existing `ToneBadge` gets `onWhy`), `tile` (whole tile is the button).
- a11y: renders a `<button>` with `aria-haspopup="dialog"` and a label "Why: <number in words>"; keyboard Enter/Space.
- Telemetry: `why_open` with `metric` key, so we can see which numbers people actually ask about.
- Implements: `ToneBadge` (add `onWhy`; today `title=` only), `ValueStat` (has an unused `children` slot "e.g. a tappable
  score button"), `OvrGauge`, `ValueRing`, `PositionBadge`, `SnapshotTile`, `Fact`, `ConfidenceMeter`, `LeanBarMeter`.
- Replaces: `BeginnerHelp`, `GlossaryNote`, hover `title=`, `<details>` explainers, lone `?` icons.
- **Build:** yes (wave 0). Pilot: PQV Value + OVR (finding P1).

### 2.3 `PickerSheet` (single or multi, search, filters, Apply)
Replaces inline pickers and flat lists. Trigger is a summary row on the page ("You send: 2 players, 1 pick, 18.4k").
- Layout: header (title, count, Done), Segmented tabs (e.g. **Players | Picks**), search, a **Filter** button with a
  count badge that opens a `FilterSheet` (see 2.7), list with checkmarks, sticky footer "Apply (n)" / "Done (n)".
- Modes: `single` (tap closes), `multi` (stays open; Apply commits), `destination` step (optional second step, e.g.
  "Send to" in multi-team trades, `MultiTeamTradeContent.tsx:735-755`).
- a11y: `role="listbox"` with `aria-multiselectable`; each row `role="option" aria-selected`; announces count changes.
- Uses: trade assets per side, Trade Finder "players you'd trade away", What-if roster (`GamesContent.tsx:213-373`),
  Stance picker, per-league notification, connect-league chooser, protected players (GM Plan Core), College Scouting
  prospect filter, league switcher.
- Reference implementations to mine: `MatchupPlanner.tsx:261-345` SwapSheet (web), `FilterDropdownButton.tsx` (mobile).
- **Build:** yes (wave 0/1).

### 2.4 `ConfirmInPlace`
A trash (or "Remove", "Sign out", "Reset") control that **expands in place** to "Are you sure? [Yes, remove] [Keep]";
auto-collapses after 5s or on outside tap; the destructive button is danger-toned and not the first focus target.
- Reference: `SimGameContent.tsx:432-447` (trash -> danger card -> Delete / Keep it) and `SimActionBar.tsx:63`.
- Variants: `inline` (row grows), `typed` (type league/account name; account delete only, when self-service returns),
  `undo` (instant action + 5s Undo toast; for low-stakes: GM target remove, asset remove).
- a11y: trigger `aria-expanded`; confirm region `role="alertdialog"`-like with `aria-live="assertive"` announcement.
- **Build:** yes (wave 0, tiny).

### 2.5 `SummaryCard -> DetailSheet`
A card keeps hero number, status chip and **one** short line; "Details" (or the whole card) opens a `Sheet` holding
what used to be stacked below. Rule: a card shows at most 1 hero number, 1 chip, 1 line, 1 CTA.
- Uses: VerdictCard, TradeIdeaCard, Waiver top card, Dashboard blocks, Account hub rows, GM Plan overview, Draft Center.
- **Build:** pattern only; composes `Sheet` + existing `AccentCard`. Provide `<DetailSection>` for the sheet body.

### 2.6 `InlineEdit`
Tap a value or name to change it where it is (compare player B header, stance chip's current value, rename league,
DOB). Shows a caret-dot affordance; selecting commits immediately (no Save), with Undo toast for non-trivial changes.
- Uses: "Compare someone else" (`PlayerCompareContent.tsx:377-383`), league rename (mobile `HomeScreen.tsx:646`),
  What-you-want-back selector.

### 2.7 `FilterSheet`
A single **Filter (n)** button (count badge of active filters) -> `Sheet` with grouped chips or radio groups and
Apply / Reset. Replaces rows of native `<select>`s and pill rows. Active filters render as removable chips under the
button.
- Uses: Players (`PlayersContent.tsx:372-433`, 6 selects + sort), Waivers Explore, Trade Hub (`TradeHubFilters.tsx`),
  News, Alerts, College Scouting, League Recaps (3 nested pill rows), Live Draft position filter.
- a11y: sheet is a form (`fieldset/legend` per group); Apply announces "n results".
- Mobile: `FilterDropdownButton` already is the single-group version; extend to multi-group.
- **Build:** yes (wave 0/1).

### 2.8 `StepFlow`
For forms with > 4 fields or multi-decision flows: 2-4 steps, progress dots, Back/Next, final step is the result.
Each step is one decision on one screen of a `Sheet` or full page; state kept across steps.
- Uses: Sim setup, ESPN connect, Live Draft trade evaluator, onboarding reorder, Account Preferences split.

### 2.9 `Segmented` (sub-tabs)
One `PillRow` variant with a strict rule: max 4 segments, one level only (no pill row under a pill row).
Replace stacked sibling sections that are the same data re-sorted (League Rankings 5 boards -> one table + sort
segmented; Hub 2-team | 3-team). Exists: `PillRow.tsx`, mobile `SegmentedTabBar`. **Build:** add `maxSegments` lint.

### 2.10 `ExpandableRow`
A list row collapsed to rank/name/chip/one number; tap expands in place for secondary content (use `aria-expanded`;
only one open at a time in a list). Exists in `MyTeamSections.tsx:65-103`, `Collapsible.tsx`. Use for Trade History,
Portfolio leagues, commissioner evidence, Roundup sections.

### 2.11 `InfoTip` (kept, restricted)
Keep only for **non-numeric, screen-level** explanations ("How this page works"), rendered as an `ⓘ` that opens a
`Sheet` (not an inline paragraph). Never for a number that could be a `TapForWhy`. Max one per screen. Existing
`InfoTip.tsx` (inline expand) is changed to open a sheet on phone.

### 2.12 `StructuredRow` / `SignalRow`
The replacement for delimiter-joined strings and generated sentences. Anatomy: **crest/avatar + name (1 line,
truncate) + status chip + 2-3 metric pills + one short reason (<= 60 chars) + chevron**. Tap opens the `Sheet`
with the full reason and evidence. Lists: top 3 shown, "See all (n)". The API returns structured fields, never a
joined string (section 6).
- Components to unify: `TeamAvatar.tsx`, `ToneBadge.tsx`, `ValueStat.tsx`, `IconRow.tsx` -> `StructuredRow`.
- **Build:** yes (wave 0/1; Draft Center is the pilot).

### Build order (shared components)

| # | Component | Used by | Effort |
|---|---|---|---|
| 1 | `Sheet` (+ sheet stack) | all | M |
| 2 | `TapForWhy` (+ `ToneBadge.onWhy`, `ValueStat` slot) | 60+ call sites | M |
| 3 | `ConfirmInPlace` | 12 | S |
| 4 | `StructuredRow` | Draft Center, Hub, Recaps, Alerts | M |
| 5 | `PickerSheet` + `FilterSheet` | Trades, Players, Waivers, News, Account | L |
| 6 | `SummaryCard`/`DetailSection` helpers, `StepFlow` | Trades, Account, Sim | M |

---

## 3. Task inventory and tap counts

"Today" counts a visible control tap as 1, native `<select>` as 2 (open, pick), and excludes typing. `M` =
measured, `I` = inferred from code. Targets assume the patterns above.

### Today / Dashboard
| # | Task | Path today | Taps today | Target | Taps target | Basis |
|---|---|---|---|---|---|---|
| 1 | See my team's weakness | Hero chips are inert; "Improve X first" -> Trade Hub. Or My Team -> expand room -> InfoTip "Roster notes" | 3 | tap a position chip -> position sheet | 1 | I |
| 2 | Why is my power rank #N | Scroll to strip, "What do these mean?" lists all 5 terms | 1 + scroll | tap tile | 1 | I |
| 3 | Why are my playoff odds X | Dashboard caption -> League Rankings -> "Calculate playoff odds" -> wait | 2 | tap odds in hero -> sheet | 1 | I |
| 4 | Set direction/stance | Dashboard Game plan link -> GM Plan -> stance card (2 UIs exist) | 2 | stance chip -> PickerSheet | 2 | I |
| 5 | Check what changed since last visit | Since-last-visit chips -> Alerts | 2 | one Today row -> sheet | 1 | I |
| 6 | Dismiss the check-in card | X or keep or ghost dismiss (3 controls) | 1 | chip dot, no card | 0-1 | I |
| 7 | Scan the Dashboard | 2.31 viewports, 8 headings (sample) | n/a | summary + 3 rows ~1.2 viewports | n/a | M |

### Trades
| # | Task | Path today | Taps | Target | Taps | Basis |
|---|---|---|---|---|---|---|
| 8 | Evaluate a 2-for-1 | Analyzer: tap "You send", scroll to bottom picker, position pill, add, add, tap "You receive", team pill, scroll, add, Analyze | 8-10 + 2-3 scrolls | tap side -> PickerSheet -> multi-select -> Apply, other side, sticky Analyze | 5 | I |
| 9 | Understand a verdict | VerdictCard 17 blocks + "Read more" | 1-2 + long scroll | verdict chip -> "Why" sheet | 1 | I |
| 10 | See a team's trade history | Only League Rankings row -> ManagerProfileSheet; chips inert in Hub/Finder/Analyzer | 1 (from rankings only) | partner name/chip -> sheet from everywhere | 1 | I |
| 11 | Find trades for my player | Finder: check players (flat roster), picks (expand round group), want-back, Find | 5-6 | summary row -> PickerSheet -> Find | 4 | I |
| 12 | Open a Hub idea in Analyzer | no direct action found in `TradeIdeaCard.tsx`; re-enter by hand (verify) | 8-10 | "Analyze" button on the card | 1 | I |
| 13 | Filter Hub by position+impact | impact chip, select open, pick | 3 | Filter (n) -> Apply | 3 (1 for repeat) | I |
| 14 | Build an offer for a player | PQV -> Build an offer -> Open in Analyzer | 3 | same | 3 | I |
| 15 | Remove an asset from a trade | tap row (instant, no confirm, no way to open player) | 1 | trash -> confirm-in-place or undo | 1-2 | I |
| 16 | Remove a team from multi-team trade | Remove (instant, drops assets) | 1 | ConfirmInPlace if assets | 2 | I |
| 17 | Review a past trade | Trade History (only trades the user shared) expand rows | 1 + scroll | ExpandableRow | 1 | I |
| 18 | Answer "did this trade happen?" | 4 buttons + dismiss X | 1 | 3-way segmented | 1 | I |

### Players
| # | Task | Path today | Taps | Target | Taps | Basis |
|---|---|---|---|---|---|---|
| 19 | Why is a player valued X | Row -> PQV; value tile inert; scroll to 2nd-last "Value history"; "Model" last | 1 + scroll | row -> tap Value -> sheet | 2 | I |
| 20 | Compare two players | Players row Compare icon (full page load) -> picker (search/suggestion) -> 5 stacked sections | 3-4 | PQV Compare -> top verdict card, B swappable by tap | 2-3 | I |
| 21 | Filter players by pos+age+status | 3 selects x 2 taps | 6 | Filter sheet, 3 selections, Apply | 5 | I |
| 22 | See a stat's percentile | PQV -> stat tile -> explorer (stacked modal) -> player -> new PQV | 3 | same, sheet stack with Back | 3 | I |
| 23 | Open full profile | PQV -> Open Full Profile (6 tabs + the same 6 actions) | 2 | keep, dedupe actions | 2 | I |
| 24 | Look at a pick's value | Players -> Picks pill; rows inert | 2 | tap pick -> sheet | 3 | I |

### Waivers
| # | Task | Path today | Taps | Target | Taps | Basis |
|---|---|---|---|---|---|---|
| 25 | Claim a waiver | Waivers -> row -> PQV -> Sleeper link (claim is external) | 2-3 | row shows bid; "Open in Sleeper" on row | 2 | I |
| 26 | Why this FAAB bid | top card inline paragraph; rows: `title=` only, unreachable on touch | impossible | tap bid -> sheet | 1 | I |
| 27 | Pick who to drop | SuggestedDrop toggle, "Or cut instead" pills, "Why this cut" toggle | 2-4 | swap tile -> PickerSheet | 2 | I |
| 28 | Find any free agent | Explore tab: search + native select | 3 | Filter sheet | 3 | I |

### My Team / Matchup
| # | Task | Path today | Taps | Target | Taps | Basis |
|---|---|---|---|---|---|---|
| 29 | Why is my team value X | ring and value inert | n/a | tap ring -> sheet | 1 | I |
| 30 | Find my biggest need | InfoTip "Roster notes" | 1 + search | top "Biggest need" card | 0-1 | I |
| 31 | Win probability why | % inert, help is in header (far) | n/a | tap % | 1 | I |
| 32 | Edit and reset lineup | Edit, 2 per swap, Reset (instant, discards) | 1+2n+1 | Reset via ConfirmInPlace | +1 | I |
| 33 | See suggested moves | Suggested view toggle, plus Suggested Moves list (duplicate) | 1-2 | count chip -> sheet | 1 | I |

### League pages
| # | Task | Path today | Taps | Target | Taps | Basis |
|---|---|---|---|---|---|---|
| 34 | See league rankings | 8 stacked sections (5 boards each top-3 + Show all) | scroll 5+ | one table + sort segmented | 1 | I |
| 35 | Why was a trade graded B | Recaps -> History -> scroll; letter inert; why inline | 3 | tap letter | 1 | I |
| 36 | Pick a recap week/season | 3 nested pill rows + "More weeks" select | 2-3 | Filter sheet | 2 | I |
| 37 | Check a team's integrity evidence | Commissioner, per-team "Show the evidence" | 2 | row -> sheet | 2 | I |
| 38 | Look up a manager | Rankings row | 1 | same | 1 | I |

### Portfolio, leagues, connect
| # | Task | Path today | Taps | Target | Taps | Basis |
|---|---|---|---|---|---|---|
| 39 | Switch league | header switcher, pick | 2 | same + search when > 6 | 2 | I |
| 40 | Connect a league at sign-up | email, password, age gate, experience, value step, paywall skip, username, load, pick | 10-12 + 2 fields | paywall moved after first league | 8 | I |
| 41 | Add a second league | switcher -> Add league (or Portfolio) -> username -> Load -> pick | 4+ | multi-select Apply | 4 | I |
| 42 | Remove a healthy league | menu -> Account -> scroll past Identity, Billing -> "Not your league? Remove" -> Confirm | 4 + long scroll | league row trash -> confirm in place | 2 | I |
| 43 | Remove a failed league (Portfolio) | text link, instant, no confirm | 1 | ConfirmInPlace | 2 | I |
| 44 | Remove ESPN login | text link, instant | 1 | ConfirmInPlace | 2 | I |

### GM Plan / Draft / Live Draft / News
| # | Task | Path today | Taps | Target | Taps | Basis |
|---|---|---|---|---|---|---|
| 45 | Find which teams to trade picks with | Draft Center -> read 5 cards of pipe strings | 2 + read | StructuredRow top-3 + See all, tap for why | 2 | I |
| 46 | Start a draft board / watchlist | menu, Draft Center, Scouting tab, Scout per prospect, Watchlist | 5 | filter sheet + list | 4 | I |
| 47 | Protect a player ("won't trade") | GM Plan -> Core -> flat roster list toggle | 3 | PickerSheet with count | 3 | I |
| 48 | Evaluate a live-draft trade | Evaluator 4 checklists + Evaluate | 6+ | StepFlow 3 steps | 5 | I |
| 49 | Read news about my player | bell -> alert -> external; News page has no filter | 2-3 | News "My players" segmented | 2 | I |

### Account / billing / onboarding / games
| # | Task | Path today | Taps | Target | Taps | Basis |
|---|---|---|---|---|---|---|
| 50 | Change notification prefs | menu, Account, scroll (card 5 of 7), toggle; quiet hours = pause + 2 selects | 3-5 | Account row "Notifications" -> sheet | 3 | I |
| 51 | Cancel subscription | menu, Account, Manage Billing -> Stripe portal -> cancel -> confirm | 5-6 | Plan row -> Manage (Stripe) | 4 | I |
| 52 | Delete account | menu, Account, scroll, mailto support, compose email | 3 + outside app | ConfirmInPlace/typed when self-service is back | 3 | I |
| 53 | Sign out | menu, Sign out (no confirm); mobile 1 | 2 | ConfirmInPlace | 3 | I |
| 54 | Upgrade to Pro | Dashboard upsell -> /premium -> period -> subscribe; comparison hidden in `<details>` | 3 | price + CTA first, compare in sheet | 3 | I |
| 55 | Invite a friend | Account -> Referral card (always-visible, 2 paragraphs) | 1 + scroll | "Invite friends" row -> share sheet | 2 | I |
| 56 | Set up a Sim game | ~12 controls one form | 12+ | 4-step StepFlow | 6 | I |
| 57 | Delete a Sim game | trash -> Delete game | 2 | already the target pattern | 2 | I |
| 58 | Delete a shared trade (Community) | ghost button, instant, errors swallowed | 1 | ConfirmInPlace | 2 | I |
| 59 | See season odds (Games) | Games -> Season Sim; 42% inert; duplicates Fantasy Sim page | 2 | single odds source, tap % | 2 | I |
| 60 | Replay tour / export data | Account bottom buttons (5 equal actions) | 1 + scroll | Help/Privacy rows | 2 | I |

---

## 4. Findings by area

IDs are stable for the plan in section 9. Columns: where | today | replacement | impact (H/M/L) | effort | risk.
Risk: S = safe (additive), C = content/copy decision, B = needs backend.

### 4.1 Trades

| ID | Where | Today | Replacement | Imp | Eff | Risk |
|---|---|---|---|---|---|---|
| T1 | `TradeAnalyzerContent.tsx:1129-1205` | Picker inline at the bottom, below the verdict: Players/Picks pill, ~8 position pills (:1140), one pill per team (:1149), tendencies card (:1160), search (:1167), `max-h-80` list (:1178). "Tap to add" (:188-231) gives no hint to scroll down | `PickerSheet` per side (Players\|Picks segmented, FilterSheet for Position/Team, Apply, multi-add) | H | L | S |
| T2 | `TradeAnalyzerContent.tsx:1149-1157` | per-team pill (11+) | Team dropdown inside PickerSheet FilterSheet | M | S | S |
| T3 | `TradeAnalyzerContent.tsx:160-232` | Row tap removes asset; no confirm, no undo, `disableQuickView` (:208) | Row tap opens player; trailing trash -> ConfirmInPlace/undo | M | S | S |
| T4 | `TradeAnalyzerContent.tsx:1054-1062, :1126` | Two helper paragraphs for one disabled button | sticky CTA with count, drop paragraphs | L | S | S |
| T5 | `TradeAnalyzerContent.tsx:332-624` | VerdictCard ~17 blocks | `SummaryCard->DetailSheet`: verdict, balance, one-line why, counter CTA; rest in "Why this verdict" sheet | H | M | S |
| T6 | `TradeAnalyzerContent.tsx:462-471` | Value balance `deltaText` plain span + LeanBarMeter + BeginnerHelp | `TapForWhy` (send/receive totals, per-asset values, formula) | H | S | S |
| T7 | `TradeAnalyzerContent.tsx:375-392, :416` | Verdict label and band plain spans, band duplicates verdict, BeginnerHelp line | `TapForWhy` opens T5 sheet | H | S | S |
| T8 | `TradeAnalyzerContent.tsx:399`, `PostureChip.tsx:13-33` | Posture chip `title=` (hover-only) + why line + "Change" navigation | `TapForWhy` sheet with posture, confidence, why, Change | M | S | S |
| T9 | `TradeAnalyzerContent.tsx:400-414, :431-455` | N yellow caution / lineup warning blocks | one "N warnings" chip, only critical inline | M | S | S |
| T10 | `TradeAnalyzerContent.tsx:561-567` | ConfidenceMeter + BeginnerHelp | `TapForWhy` (assumptions from `VerdictTrust.tsx:45`) | M | S | S |
| T11 | `TradeAnalyzerContent.tsx:578-604, :497` | "Read more" `<details>`; rationale appears twice | fold into T5 sheet | M | S | S |
| T12 | `VerdictTrust.tsx:43-100` | assumptions `<details>` + "Was this wrong?" feedback with reason picker and cancel | assumptions into sheet; feedback = sheet footer | M | S | S |
| T13 | `TradeAnalyzerContent.tsx:523-554` | alternate packages as full cards | "Try instead (2)" rows -> package sheet; Apply loads builder | M | M | S |
| T14 | `TradeAnalyzerContent.tsx:607-612`, `ShareToCommunityToggle.tsx:34-60` | toggle + name input + Share button | fold into Share sheet | L | S | S |
| T15 | `TradeAnalyzerContent.tsx:614-617` | NextSteps + "Reply to partner" note | single Next row | L | S | S |
| T16 | `TradeAnalyzerContent.tsx:1070-1089` | planningNote + roleNotes cards | into Why sheet | L | S | S |
| T17 | `TradeAnalyzerContent.tsx:1021` | two-team/multi-team toggle; mobile has third "Quick Compare" web lacks (`mobile/src/screens/TradeAnalyzerScreen.tsx:585`) | parity gap, keep Segmented | L | S | S |
| T18 | `TradeIdeaCard.tsx:319-372` | "View details" expander repeats confidence/realism chips (:281-284) and balance (:308), 3 BeginnerHelps | chips are the taps; delete expander | H | M | S |
| T19 | `TradeIdeaCard.tsx:304-311, :294, :300` | Balance and side totals plain | `TapForWhy` | H | S | S |
| T20 | `TradeIdeaCard.tsx:259-261`, `ManagerTendenciesCard.tsx:76-90` | partner name plain h3, "Their history" chips inert/premium link; `ManagerProfileSheet` exists but mounted only from `LeagueRankingsContent.tsx:498` | partner name/avatar/chips open `ManagerProfileSheet` from Hub, Finder, Analyzer | H | S | S |
| T21 | `TradeIdeaCard.tsx:209-231, :269-271` | impact tags, posture, band plain + BeginnerHelp | `TapForWhy` | M | S | S |
| T22 | `TradeIdeaCard.tsx` (whole) | no Analyze action; user retypes in Analyzer (verify) | "Analyze" button deep-links with both sides loaded | H | S | S |
| T23 | `TradeHubContent.tsx:110-114, :40-49` | PageTitle `?` expands posture | posture chip -> sheet | L | S | S |
| T24 | `TradeHubFilters.tsx:41-68` | 4-6 chips + native Position select | `FilterSheet` | M | S | S |
| T25 | `TradeHubContent.tsx:119-141` | FreeLimitNote, DeadlineCard, HoldCard, filters before first idea | one status row -> sheet | M | M | S |
| T26 | `TradeHubContent.tsx:155-173` | full ~20-element cards, no paging | compact `StructuredRow` -> DetailSheet | H | M | S |
| T27 | `TradeHubContent.tsx:174`, `MultiTeamIdeasSection.tsx:41-195` | 3-team ideas as a second list | `Segmented` 2-team \| 3-team | M | S | S |
| T28 | `TradeHubContent.tsx:189`, `ValueSignalsCard.tsx:23-24` | buy-low/sell-high duplicates idea tags and filter chips | filter link | M | S | S |
| T29 | `TradeFinderContent.tsx:388-402` | flat roster with checkboxes, no filter/search | multi `PickerSheet` + "Selected (n)" row | H | M | S |
| T30 | `TradeFinderContent.tsx:404-424`, `PickGroupList.tsx:48-78` | year pills + collapsible round groups | same PickerSheet (Picks tab) | M | S | S |
| T31 | `TradeFinderContent.tsx:432-450` | "What you want back" in its own titled section | segmented next to CTA | L | S | S |
| T32 | `TradeFinderContent.tsx:479-486`, `TradeFinderNoResults.tsx:84-129` | summary paragraph + N full cards + stretch | compact rows (T26) | M | M | S |
| T33 | `TradeFinderNoResults.tsx:50-70` | warning list of long sentences | one summary + "Why" tap | L | S | S |
| T34 | `TradeOfferContent.tsx:127-176` | badge `title=` and same reason as paragraph | TapForWhy, remove paragraph | M | S | S |
| T35 | `TradeHistoryContent.tsx:36-104` | rows with header, callout, NetEdgeBar, full exchange + InfoTip; lists only user-shared trades | `ExpandableRow`; link to manager sheet for league history | M | M | S |
| T36 | `TradeOutcomePrompt.tsx:141-223` | floating sheet z-30, 4 buttons + X | 3-way segmented + "Not now"; z via Sheet stack | L | S | S |
| T37 | `MultiTeamTradeContent.tsx:527-559` | team Remove (:531, `dropTeam` :440) and asset Remove (:553) instant | ConfirmInPlace | M | S | S |
| T38 | `MultiTeamTradeContent.tsx:561-697` | 3 ways to add an asset; matrix hidden below `sm` | PickerSheet + destination step; drop matrix | M | M | S |
| T39 | `MultiTeamTradeContent.tsx:199-230, :127-162` | RankedRow duplicates Value, veto badge + advice in expansion | row -> sheet | L | S | S |

### 4.2 Players, PQV, Compare

| ID | Where | Today | Replacement | Imp | Eff | Risk |
|---|---|---|---|---|---|---|
| P1 | `PlayerHeroHeader.tsx:150-158`, `PlayerValueHistory.tsx:40-62`, `PlayerQuickView.tsx:364` | hero Value tile inert; separate "Value history" section near the bottom (owner's example); not on full profile at all | tap Value tile -> sheet (chart, changes, inputs, rank); delete section; same tap on profile | H | S | S |
| P2 | `PlayerHeroHeader.tsx:143-148`, `PlayerQuickView.tsx:295, :559-575` | OVR gauge inert + BeginnerHelp; Model radar is last section | tap OVR -> sub-rating radar sheet; delete bottom Model section | H | S | S |
| P3 | `PlayerHeroHeader.tsx:175-216, :167` | usage tile `title=` only | tap -> `PlayerUsageBlock` sheet | M | S | S |
| P4 | `PlayerHeroHeader.tsx:90-100, :162-168` | rank line and tier pill plain text | tap rank -> position list around him; tier -> definition | M | S | S |
| P5 | `PlayerQuickView.tsx:256-296` | 2 chips + mismatch caption + 3 BeginnerHelp before content | chips are taps; drop captions | H | S | S |
| P6 | `PlayerQuickView.tsx:301-364` | 10 stacked sections in a sheet | keep identity, value, OVR, decision fit, headline tiles; rest in Segmented inside the sheet or profile | H | M | S |
| P7 | `PlayerQuickView.tsx:371-402`, `PlayerLeagueActions.tsx:157-196` | up to 6 action links + status label | 1 contextual primary + More sheet | M | S | S |
| P8 | `PlayerProfileContent.tsx:244-294` | 6 tabs and the same 6 actions as PQV | profile only for "Open full profile"; dedupe | M | M | S |
| P9 | `StatRows.tsx:13-45`, `PercentileExplorerSheet.tsx:253-380` | percentile badge `title=`; explorer stacks on PQV with 3 hint paragraphs, 2 pill rows; picking player opens new PQV | back-stack sheet; hints into one InfoTip | M | M | S |
| P10 | `PlayersContent.tsx:372-462` | search + 5 selects + sort select + Raw/Percentile pills = 8 controls | `FilterSheet`; sort sheet (mobile already: `mobile/src/screens/PlayersScreen.tsx:370-373`) | H | M | S |
| P11 | `PlayersContent.tsx:112-255` | row has 5 numbers/chips + 2 icon links inert | value/OVR `TapForWhy`; icon links into PQV actions | M | M | S |
| P12 | `PlayersContent.tsx:101, :330` | top 60 cap, no paging | Load more + filters | L | S | S |
| P13 | `PlayersContent.tsx:358-368`, `PickRow.tsx:98` | pick rows inert | tap -> pick sheet | L | S | S |
| P14 | `PlayerCompareContent.tsx:266-459` | owner's "bare list": step 1 `OpponentPicker` (:151-223) flat suggestions; step 2 5 stacked sections (:404-443), all inert, no winner | top card "who wins" + 3 headline stats; rows tap for why; picker = PickerSheet; B header swappable | H | M | S |
| P15 | `PlayerCompareContent.tsx:377-383` | "Compare someone else" text button | `InlineEdit` on B header | L | S | S |
| P16 | `app/dynasty-rankings/[position]/page.tsx:106-118` | static table, footnote about "tops out around 10,000" | value header tap -> glossary sheet (SEO page, low priority) | L | S | S |

### 4.3 Waivers, Matchup

| ID | Where | Today | Replacement | Imp | Eff | Risk |
|---|---|---|---|---|---|---|
| W1 | `WaiversContent.tsx:531-553` | Priority Adds: headline, badges, NeedsBreakdown, limitedNote, InfoTip "How ranks", Sleeper note = 5 text blocks before a player | need badges tap -> `NeedsBreakdown` sheet; delete both InfoTips | H | S | S |
| W2 | `WaiversContent.tsx:209-257` | top card 14 pieces incl. 2 explainer paragraphs (:231, :237) | `SummaryCard->DetailSheet` | H | M | S |
| W3 | `WaiversContent.tsx:153-170, :157` | FAAB range `title=faab.why`, hover only | `TapForWhy` on bid | H | S | S |
| W4 | `WaiversContent.tsx:131-151` | reason/usage chips plain | `TapForWhy` | M | S | S |
| W5 | `WaiversContent.tsx:258-307` | RecommendedRow ~9 nested elements, drop outside button | collapsed row = rank, name, bid | M | M | S |
| W6 | `SuggestedDrop.tsx:182-318` | SwapBody, alternates pills, effect pills `title=`, compact variant duplicates | swap tile + PickerSheet for alternatives | M | M | S |
| W7 | `SuggestedDrop.tsx:355-396`, `WaiversContent.tsx:617` | "Players you could drop" list restates each pickup's drop | one sheet from a row | M | S | S |
| W8 | `WaiversContent.tsx:652, :669` | descriptive InfoTips | delete one, fold other | L | S | S |
| W9 | `WaiversContent.tsx:674-691` | search + native select, 60 cap | `FilterSheet` | M | S | S |
| M1 | `MatchupContent.tsx:184-206, :83-102` | win %, bar inert; 2 BeginnerHelps in the header, far from number | `TapForWhy` on % | H | S | S |
| M2 | `MatchupContent.tsx:218-239` | 4 tiles inert; "Proj margin" and "Value margin" similar | `TapForWhy`; rename or drop value margin | M | S | S |
| M3 | `MatchupContent.tsx:266-333` | Insights restates Scoreboard + Lineup Comparison | merge headline into scoreboard | M | M | S |
| M4 | `MatchupContent.tsx:455-640, :506-522` | lone `?` button; Suggested/Actual pills; Edit | `?` -> InfoTip label | M | S | S |
| M5 | `MatchupContent.tsx:733-785` | Suggested Moves duplicates suggested lineup view, 2 footnotes | count chip -> sheet | H | M | S |
| M6 | `MatchupContent.tsx:643-731` | MoveCard `<details>` range | gain taps range | M | S | S |
| M7 | `MatchupPlanner.tsx:380`, `MatchupContent.tsx:539` | Reset discards edited lineup instantly | ConfirmInPlace | M | S | S |

### 4.4 Today, Alerts, News, Notifications, My Team

| ID | Where | Today | Replacement | Imp | Eff | Risk |
|---|---|---|---|---|---|---|
| D1 | `DashboardContent.tsx:147-231` | ~13 stacked blocks (measured 2.31 viewports on the sample) | hero + 3 summary rows (Matchup, Moves, Alerts), each a DetailSheet | H | L | S |
| D2 | `SnapshotTile.tsx:92-132`, `StatStrip.tsx:19-28` | Power/Franchise/Starter/Bench/Age/Injured tiles plain divs | tile = button -> `TapForWhy` | H | M | S |
| D3 | `DashboardContent.tsx:176-208` | My Team strip duplicates My Team snapshot (`MyTeamContent.tsx:230-278`) and GM Plan tiles (`GmPlanSections.tsx:209-246`) | one rank+record line -> Team sheet | H | S | S |
| D4 | `DashboardContent.tsx:184-195, :206` | BeginnerHelp `?` and GlossaryNote "What do these mean?" on the same 5 terms | delete both | M | S | S |
| D5 | `TeamStatusHero.tsx:67-79, :192-258` | win chance, projection, record, odds, proj record plain `Fact`s; whole row is a link | `TapForWhy`; keep explicit "Open Matchup" | H | M | S |
| D6 | `TeamStatusHero.tsx:97-115, :244-258` | QB/RB/WR/TE chips plain, weakness drill-in is a text link | chip -> position sheet | H | M | S |
| D7 | `TeamStatusHero.tsx:229-231` | inline odds explainer | into odds sheet | M | S | S |
| D8 | `TodayModule.tsx:77-190` | status chips + 2-line why clamp + BeginnerHelp + empty-state paragraph | one-line rows -> sheet | M | M | S |
| D9 | `DashboardBlocks.tsx:25-87`, `DashboardContent.tsx:213-218`, `TodayModule.tsx` | Needs attention, Today's moves, Watchlist & Alerts overlap | one "Today" card with count -> unified sheet | H | M | S |
| D10 | `DashboardBlocks.tsx:149-167`, `DashboardContent.tsx:224-232` | "More" `<details>` hides Activity, 2 mini-games, LeagueTypeControl (a setting) | settings to league sheet, games to Games | M | S | S |
| D11 | `DirectionCheckinCard.tsx:90-108` | X, keep, N options, ghost dismiss (dismiss twice); same stance as GM Plan | stance chip + `PickerSheet`; check-in = dot on chip | H | M | S |
| D12 | `StartHereCard.tsx:97-130` | checklist card + dismiss | "Setup 2/5" chip -> sheet | M | S | S |
| D13 | `NextSteps.tsx:43-46` (Alerts :329, MyTeam ~:310, Rankings ~:509) | every page ends with 2-3 buttons repeating nav | remove or one contextual CTA | M | S | S |
| D14 | `SinceLastVisitStrip.tsx:83-95` | third path to alerts | merge into D9 | M | S | S |
| D15 | `LeaguePulseCard.tsx:131-150` | highlights + link | one row -> sheet | L | S | S |
| N1 | `AlertsDropdown.tsx:146-192` vs `AlertsContent.tsx` | bell is a sheet, page is a full copy, Dashboard Watchlist is a third | bell sheet is the one surface; page = same component full-height | M | M | S |
| N2 | `AlertsContent.tsx:305-325` | grouped by type, docstring (:39) promises filter pills that do not exist | `FilterSheet` + Unread/All | M | M | S |
| N3 | `AlertsContent.tsx:75, :141` | PositionBadge and "Your player" inert | tap opens PQV | M | S | S |
| N4 | `NewsContent.tsx:212, :262-271` | flat unfiltered league-wide feed; "owned players news is in Alerts" | "My players" segmented + FilterSheet; merge Alerts+News as one Inbox | H | M | S |
| N5 | `NewsContent.tsx:124-148` | type pills inert | tap filters | L | S | S |
| N6 | `AccountContent.tsx:344-383`, `NotificationControls.tsx:58-284` | 10 push toggles in Preferences + quiet hours, pause, urgent-through, cap, digest, digest hour, per-league select | one Notifications row -> sheet | H | M | S |
| N7 | `NotificationControls.tsx:216-270` | per-league `<select>` x N saved leagues | single row + PickerSheet | M | S | S |
| N8 | `NotificationControls.tsx:124-165, :216-235` | 3 native hour selects | time picker sheet | L | S | S |
| MT1 | `MyTeamContent.tsx:224-227` | 2 BeginnerHelp chips | delete | M | S | S |
| MT2 | `MyTeamContent.tsx:235-251` | ValueRing, archetype chip, Team Value inert | `TapForWhy` sheet (components, percentile, history, archetype) | H | M | S |
| MT3 | `MyTeamContent.tsx:230-278` | 6 tiles duplicate Dashboard + GlossaryNote (9 terms) | tile taps; delete glossary | H | S | S |
| MT4 | `MyTeamContent.tsx:284-312` | biggest-need text hidden behind tiny InfoTip "Roster notes" | promote to a top "Biggest need" card | H | S | S |
| MT5 | `MyTeamSections.tsx:45-103` | meter + status chip inside the accordion inert | row opens position sheet | L | S | S |
| MT6 | `MyTeamContent.tsx:319-362` | Roster, Composition, Starters Value as separate sections | fold composition into header | M | S | S |
| MT7 | `MyTeamContent.tsx:365-411`, `MyTeamSections.tsx:164-170` | keeper paragraph + round-penalty pills + inert "Keep" badges | Keeper settings row (sheet); badge taps | L | S | S |

### 4.5 League pages

| ID | Where | Today | Replacement | Imp | Eff | Risk |
|---|---|---|---|---|---|---|
| L1 | `LeagueRankingsContent.tsx:395-507` | 8 stacked sections: YourStanding, Standings, PlayoffOdds, 5 RankBoards (same teams re-sorted, top 3 + Show all) | one table + sort segmented (Power, Franchise, Starter, Bench, Picks) | H | M | S |
| L2 | `LeagueRankingsContent.tsx:96-134` | row opens manager sheet but rank, metric, badges, "+N" inert | metric taps -> rank why | M | S | S |
| L3 | `LeagueRankingsContent.tsx:347-366` | note, 2 BeginnerHelps, manual "Calculate playoff odds" | auto-compute, tap odds for explainer | M | M | B |
| L4 | `LeagueRecapsContent.tsx:256-264, :683-691, :1100-1110` | 4-view pills + weeks pills + "More weeks" select + season/filter pills = 3 nested rows | one `FilterSheet`; keep top tabs | H | M | S |
| L5 | `LeagueRecapsContent.tsx:475-577` | grade letters inert; "Why", "Watch", "Grade pending" paragraphs on every card | letter chip -> grade sheet | H | M | S |
| L6 | `LeagueRoundupTab.tsx:119-262` | 4 stacked sections, `Stat()` inert | summary + tap into each | M | M | S |
| L7 | `SeasonReviewSections.tsx:64-283` | `Collapsible` exists; StatTile, ReviewDeltaText, GameRow inert | TapForWhy | L | S | S |
| L8 | `CommissionerContent.tsx:162, :280-362` | 5 sections + `<details>` + inline "Show the evidence" | row + band chip -> Evidence sheet | M | M | S |
| L9 | `VetoCalculator.tsx:143, :207-228, :235-512` | Why list always visible, `<details>` how-calculated, OutrageMeter inert | tap meter/verdict -> sheet | M | M | S |
| L10 | `ManagerProfileSheet.tsx:57, :166, :233` | the sheet's own grade/tendency badges are inert | inline expansion (no sheet-on-sheet) | L | S | S |

### 4.6 Portfolio, connect, account, onboarding

| ID | Where | Today | Replacement | Imp | Eff | Risk |
|---|---|---|---|---|---|---|
| C1 | `PortfolioContent.tsx:265-371, :576-587` | tall card per league (avatar, record, win bar, rank, health, signals, full-width button) | compact row: avatar, name, record, rank chip, signal dot; overflow holds remove/rename | H | M | S |
| C2 | `PortfolioContent.tsx:542-550, :569` | Leagues/Exposure pills + GlossaryNote | rank chip `TapForWhy` | L | S | S |
| C3 | `PortfolioContent.tsx:165-262, :492-505` | 3 banner blocks; "Not your league? Remove" instant | "Needs attention (3)" row; ConfirmInPlace | H | S | S |
| C4 | `SavedLeaguesSection.tsx:71-100` | plain names; remove = text link -> paragraph + 2 buttons; third league list | one league manager, trash -> in-place confirm | H | S | S |
| C5 | `app/connect-league/page.tsx`, `SleeperImportForm.tsx:60-137` | 2x2 platform grid + "Also:" row | `Segmented` platform (Sleeper default) | M | S | S |
| C6 | `SleeperImportForm.tsx:350-377` | 3 always-visible explainer paragraphs | InfoTip "Why Sleeper?" | M | S | S |
| C7 | `SleeperImportForm.tsx:310-343` | flat list of full-width cards, one league per tap | checkbox rows + "Add N leagues"; season filter | H | M | S |
| C8 | `EspnImportForm.tsx:205-257, :322-348` | diagnostics + "Works/Not available" paragraphs, flat team radios, 2 fields | `StepFlow` (IDs, pick team, done) | M | M | S |
| C9 | `EspnLoginPanel.tsx:123` | Remove login instant | ConfirmInPlace | M | S | S |
| C10 | `LeagueLinkStep.tsx:25-31` | with 2+ leagues sends to /portfolio | inline league PickerSheet | M | S | S |
| C11 | `Header.tsx:38-135, :182, :235-275` | two dropdowns + lens button, flat lists, no search | one PickerSheet: leagues (recent first, search > 6) + lens | M | M | S |
| A1 | `AccountContent.tsx:487-512` | 7 equal cards | settings hub rows: Profile, Plan, Leagues, Notifications, Display, Privacy, Invite | H | L | S |
| A2 | `AccountContent.tsx:307-390` | Preferences: explanations level, goal, theme, density, college toggle, community opt-out, 10 push toggles, NotificationControls = 18+ controls in one card | split into Display / Notifications / Privacy sheets | H | M | S |
| A3 | `AccountContent.tsx:61-145`, `PremiumContent.tsx:164-208` | plan shown in Identity and Billing and Premium ManageBilling | one Plan row | M | S | S |
| A4 | `AccountContent.tsx:394-441` | 5 equal buttons; Sign out instant | rows; ConfirmInPlace on Sign out | M | S | S |
| A5 | `AccountContent.tsx:447-466` | permanent red card; self-service disabled (TEMPORARY, :445) | one row expanding in place; typed confirm when back | M | S | S |
| A6 | `ReferralCard.tsx:75-105` | always-visible card, 2 paragraphs, input + Copy | "Invite friends" row -> share sheet | L | S | S |
| A7 | `PremiumContent.tsx:245-262`, `PaywallParts.tsx:74-85` | highlights, `<details>` comparison, plans, legal, HelpLink | price + CTA first, compare in sheet | M | S | S |
| O1 | `OnboardingPaywall.tsx:167-198`, `LandingAuthIsland.tsx:62-298` | chain: sign-in, age gate, carousel, paywall, connect, choose; paywall before first league | connect league first, then paywall at the value moment | H | M | C |
| O2 | `SignInForm.tsx:66-97, :293-382` | multi-state form, age gate as a separate step, OAuth after email | OAuth first; inline DOB | M | M | C |
| O3 | `OnboardingCarousel.tsx:70-330` | already a stepper with Skip/back/dots | keep; make goal optional | L | S | S |

### 4.7 GM Plan, Draft, Games, Sim, Community

| ID | Where | Today | Replacement | Imp | Eff | Risk |
|---|---|---|---|---|---|---|
| G1 | `GmPlanContent.tsx:635-830` | 4 tabs; Overview stacks situation, 6-tile snapshot, deadline banner, ideas, outlook | stance chip + 3 summary rows | H | L | S |
| G2 | `GmPlanSections.tsx:76-170` | 3 big tab-cards, description, BeginnerHelp, InfoTip (:97), deadline banner = 4 explainers for 3 choices; duplicates DirectionCheckin | stance chip + PickerSheet, descriptions in sheet | H | M | S |
| G3 | `GmPlanSections.tsx:209-246`, `GmPlanContent.tsx:90-165, :224-229` | SnapshotCell and Rank/Record/Odds/Injury facts duplicate Dashboard | drop or `TapForWhy` | M | S | S |
| G4 | `GmPlanContent.tsx:594, :759-760` | InfoTip + flat list of every roster player (protect) | count summary + PickerSheet | M | M | S |
| G5 | `GmPlanContent.tsx:373-377` | Remove target instant | trash + undo toast | L | S | S |
| G6 | `app/team-situation/[leagueId]/page.tsx` | redirect only | none | L | S | S |
| R1 | `DraftCenterContent.tsx:91-105, :209-275` | 3 tabs; Overview = posture, 2 CapitalCells, 2 card sections of pipe strings | section 6 spec | H | M | B |
| R2 | `DraftCenterContent.tsx:116-119, :226-275, :289` | posture/firsts/picks badges, CapitalCell, card labels inert | tap "5 firsts" -> pick sheet | M | S | S |
| R3 | `DraftScoutingTab.tsx:62` vs `app/college-scouting` | scouting in two places | one entry point | L | S | S |
| R4 | `CollegeScoutingContent.tsx:352-421` | InfoTip, 2 pill rows, paragraph, flat endless list, no filter/sort/search; tags plain | `FilterSheet` + search | H | M | S |
| R5 | `CollegeScoutingContent.tsx:63-245` | card expands to 2 pill rows + textarea + Save + "Remove my report" (:236, no confirm) | grade sheet; ConfirmInPlace | M | M | S |
| R6 | `LiveDraftContent.tsx:493-565` | 5 stacked sections | recommendation on top, rest Segmented/sheets | H | M | S |
| R7 | `LiveDraftContent.tsx:139-205` | row has rank, pos/team, movement glyph, score button, OVR gauge, Compare = 5-6 controls at 390px | row tap -> player sheet; 2 numbers | H | M | S |
| R8 | `LiveDraftContent.tsx:295, :406` | native selects | FilterSheet / Segmented | L | S | S |
| R9 | `LiveDraftTradeEvaluator.tsx:119-330` | 4 CheckLists + Evaluate | `StepFlow` | M | M | S |
| S1 | `GamesContent.tsx:57-212`, `FantasySimContent.tsx:96`, `LeagueRankingsContent.tsx` | 3 things called "Sim/Odds" | one odds source, tap % | H | M | S |
| S2 | `GamesContent.tsx:140-155` | 42% and title odds big plain spans | `TapForWhy` | M | S | S |
| S3 | `GamesContent.tsx:213-373` | What-if: flat whole-roster list with Drop buttons, Remove on adds | PickerSheet + chips | M | M | S |
| S4 | `FantasySimContent.tsx:228-304` | always-visible notes; GameCard is a promo for /gm-game | tap bars; move promo to Games | M | S | S |
| S5 | `SimGameContent.tsx:560-684` | ~12 controls | `StepFlow` | M | M | S |
| S6 | `SimGameContent.tsx:706-893` | 6-tab pills; More tab = static rules bullets | rules to InfoTip | L | S | S |
| CM1 | `CommunityTradesContent.tsx:176-181` | InfoTip "Craziest trades this week" | keep (the one correct lone-help pattern) | L | S | S |
| CM2 | `SharedTradesFeed.tsx:51-56`, `app/community/page.tsx:86` | Delete and Report ghost buttons, no confirm, errors swallowed | ConfirmInPlace; Report -> reason sheet | M | S | S |

### 4.8 Mobile mirrors
| ID | Where | Today | Replacement |
|---|---|---|---|
| X1 | `mobile/src/screens/HomeScreen.tsx:466` | Sign out (red) one tap | ConfirmInPlace |
| X2 | `mobile/src/screens/HomeScreen.tsx:621-658, :839-855` | pencil rename per row opens modal; inline Sleeper help toggle (:726) | row overflow (rename/remove) |
| X3 | `mobile/src/screens/MoreScreen.tsx:203-225, :398-411` | `Alert.alert` for remove league / delete account | native alert is acceptable; align copy; use ConfirmInPlace when web ships it |
| X4 | `mobile/src/screens/TradeAnalyzerScreen.tsx:585` | has "Quick Compare" mode web lacks | web parity (T17) |
| X5 | all of section 4 | mobile screens only skimmed | every item ships web + app together (parity rule) |

---

## 5. Help, tooltip and explainer inventory (anti-pattern G)

Four stacked explainer layers hide the same kind of content: `PageTitle` `?` (info slot), `BeginnerHelp` (dismiss-once
line, localStorage), `InfoTip` (ⓘ inline expand), native `<details>`, plus ad-hoc `?` buttons (`MatchupContent.tsx:506`)
and hover-only `title=` tooltips (never visible on touch: `PositionBadge`, FAAB, usage tile, `ToneBadge`, posture,
effect pills). Several screens use 3 of the 5 at once (Trade Analyzer, Trade Idea card, PQV, Waivers).

Rule: any explanation of a **number or chip** becomes `TapForWhy`; any explanation of a **screen** becomes one `InfoTip`
(sheet). Delete the rest. Call sites to remove (all verified by grep):

`BeginnerHelp`: `TradeAnalyzerContent.tsx:416, :471, :567`, `TradeIdeaCard.tsx:225, :350, :368, :369`,
`TradeHubHoldCard.tsx:101`, `PlayerQuickView.tsx:295-296`, `WaiversContent.tsx:244, :253`, `MatchupContent.tsx:100`
(+ matchupIntro), `DashboardContent.tsx:184-195`, `TodayModule.tsx:77, :152`, `DashboardBlocks.tsx:121`,
`MyTeamContent.tsx:224-227`, `LeagueRankingsContent.tsx:347-366`, `GmPlanSections.tsx` (stance).
`GlossaryNote`: `DashboardContent.tsx:206`, `MyTeamContent.tsx:260-277`, `PortfolioContent.tsx:569`.
`InfoTip`: `WaiversContent.tsx:549, :652, :669`, `SuggestedDrop.tsx:388`, `TradeHistoryContent.tsx:100-104`,
`MyTeamContent.tsx:284-312`, `GmPlanSections.tsx:97`, `GmPlanContent.tsx:759-760`, `CollegeScoutingContent.tsx:352`.
Keep: `CommunityTradesContent.tsx:176-181`.
Hover `title=`: `PositionBadge.tsx`, `PostureChip.tsx`, `ToneBadge` consumers (`TradeOfferContent.tsx:135`,
`WaiversContent.tsx:157`, `PlayerHeroHeader.tsx:175-216`, `SuggestedDrop.tsx:94-110`).

---

## 6. Delimiter-joined strings and generated sentences (StructuredRow hunt)

### 6.1 Evidence

The owner's screenshot of Draft Center "League Draft Decision Signals" shows, per card, rows like (names anonymised):

> `Team A | Retool | Draft #10 | Future #10 | Draft rank #10 leaves too little flexibility for a retool build.`
> `Team B | Rebuild | Draft #9 | Future #9 | Draft rank #9 leaves too little flexibility for a rebuild build.`

Observed defects: team name, posture, two ranks and a sentence are one string; "Draft #10 | Future #10" repeat
the same number twice per row; the sentence restates the ranks again; "rebuild build" is a template artifact; the
unsized emoji and `?` characters in team names break the layout; the label bar ("BEST PICK BUYERS", all caps, full
width) plus a sub-title plus a bullet list gives 3 levels of chrome around 3 rows of text; every row has identical
weight; there is no tap target even though the arrow glyph implies one.

### 6.2 Root cause

`modules/draft_center_cards.py:158-196` (`_draft_workspace_team_lines`) returns `list[str]`; line 195 is
`team_name + (f" | {' | '.join(details)}" ...)`. `build_draft_decision_cards` (lines ~300-380) and
`build_draft_partner_cards` (:381) put those strings in `items`. `services/mobile_api_service.py:3925` serves them;
`DraftCenterContent.tsx:277-308` (`DraftCardSection`) renders each as `<IconRow icon="arrow">{item}</IconRow>`.
Mobile renders the same payload. Fix is at the API: return structured items.

### 6.3 Every instance found

| # | Where | Output | Replace with |
|---|---|---|---|
| K1 | `modules/draft_center_cards.py:195` (+ `build_draft_decision_cards`, `build_draft_partner_cards`; rendered `DraftCenterContent.tsx:277-308`, mobile twin) | `Team \| Strategy \| Draft #n \| Future #n \| sentence` | `StructuredRow` (spec 6.4) |
| K2 | `modules/draft_assistant.py:579` | `"{season} draft \| {status} \| {rounds} rounds \| Type \| {id[-6:]}"`, also exposes a raw draft id suffix (anti-pattern N) | label = season + type; status as chip; drop id |
| K3 | `modules/live_draft.py:1041` | `"QB 3 \| RB 2 \| WR 1"` recent position mix | position pills with counts |
| K4 | `modules/live_draft.py:983` | `"QB 3 · RB 2 ..."` roster positions | same pills |
| K5 | `modules/injury_ui.py:225` | `"Name (POS) - relevance \| Name (POS) - ..."` | one row per player: avatar + name + relevance chip |
| K6 | `modules/my_news.py:492` | `"detail \| detail \| Updated Mon dd, yyyy"` alert summary | headline + chips + timestamp field |
| K7 | `modules/rankings.py:3548, :3560` | injury impact summaries joined with `" \| "` | list of structured rows |
| K8 | `modules/canonical_recommendation_narrative.py:212, :251` | `action · target · reason` notification summary | notification title + body fields (reuse for N1) |
| K9 | `services/mobile_api_service.py:14842` | `bits` joined with `" · "`, fallback sentence "Best season-value option available for the {slot} slot." | structured chips + short reason |
| K10 | `modules/trade_offer_analyzer.py:941, :956, :1021` | `meta_bits` joined `" · "` (HTML) | structured meta |
| K11 | `modules/compact_fantasy_assets.py:465`, `modules/canonical_player_ranking.py:671`, `modules/daily_gm_briefing.py:236`, `modules/league_history.py:91`, `modules/player_history.py:406` | identity/meta/date strings joined `" · "` | fields (team, age, pos); client formats |
| K12 | `web-next/src/components/LeagueRecapsContent.tsx:380, :390, :721, :859`, `lib/leagueRecapsPresentation.ts:218` | pick lists and meta joined `" · "` | chips/rows |
| K13 | `web-next/src/lib/tradeHistoryPresentation.ts:64`, `lib/opponentProfile.ts:85`, `lib/myTeamPresentation.ts:192`, `lib/matchupPresentation.ts:183` | meta lines `a · b · c` | metric pills |
| K14 | `web-next/src/components/DraftCenterContent.tsx:187-191` | pick context `provenance · tier · range` | `PickRow` fields |
| K15 | `PickRow.tsx:92`, `TradeAssetExchange.tsx:45, :61`, `SuggestedDrop.tsx:41, :57, :189, :440`, `PortfolioContent.tsx:277`, `PortfolioExposureView.tsx:80, :176`, `LeagueRankingsContent.tsx:124`, `OpponentProfileCard.tsx:64`, `PercentileExplorerSheet.tsx:498, :545`, `SimGameTeam.tsx:506`, `seo/ValueTable.tsx:54`, `PlayerHeroHeader.tsx:164`, `MyTeamSections.tsx:107` | small `a · b` meta lines (team · age, record · rank) | acceptable as a single dimmed meta line **only** when <= 2 tokens; otherwise pills. Audit during each screen's pass |
| K16 | `web-next/src/lib/simGame.ts:1284, :1650, :1680`, `lib/simReview.ts:339`, `SimGameContent.tsx:422, :871` | sim setting summaries `scoring · teams · difficulty` | chips |

Long generated sentences from structured data (also anti-pattern K): `modules/draft_center_cards.py:150-200`
(`_classification_reason`: "...leaves too little flexibility for a retool build.", "...keep the board open."),
trade-idea rationale, recap grade "Why/Watch" text (`LeagueRecapsContent.tsx:475-577`), `TradeFinderNoResults.tsx:50-70`,
`TodayModule.tsx` why paragraphs, `WaiversContent.tsx:231, :237`. Rule: the API returns `reason_code` + `reason_short` (<= 60
chars) + `evidence[]` (rows); the long sentence is deleted or lives only in the TapForWhy sheet.

### 6.4 Draft Center redesign spec (wave 1)

Screen: `DraftCenterContent.tsx` Overview tab. Today: posture card, 2 `CapitalCell`s, then 2 sections
(`League Draft Decision Signals`: 5 cards; `Draft Partner Discovery`: N cards), each card = all-caps label bar + title +
3 bullet strings. About 25 text lines of equal weight.

Target (390px wide, glass style):
1. **Header summary card** (one `SummaryCard`): posture chip ("Retool"), hero number "5 firsts" (tap -> pick sheet),
   two metric pills "Draft #3" and "Future #5" (each `TapForWhy`), one line: "Best move: sell 2027 R2s".
2. **Signal tabs** (Segmented, max 4): `Buyers | Sellers | Pivot | Pick-rich`. Replaces 5 stacked cards; the 5th
   ("Pick-poor") appears under "See all". Delete the all-caps label bars and the sub-title paragraphs (the segment name
   plus a one-line `InfoTip` is enough).
3. **Rows** (`StructuredRow`), top 3 per segment, "See all (n)" expands in place:
   - crest (`TeamAvatar`) + team name (1 line, truncate; emoji/odd glyphs rendered in a fixed-size span)
   - status chip: posture (Retool / Rebuild / Contender), colour from the existing tone map
   - two metric pills: `Draft #10`, `Future #10` (collapsed into `Picks #10` when equal; this removes the doubled number)
   - one short reason, <= 60 chars, from `reason_short` ("Too few picks for a retool")
   - chevron; tap opens `Sheet`: full reason sentence, the evidence rows (draft rank, future rank, firsts count, age
     rank), and the actions "Open trade finder with this team" and "View team" (`ManagerProfileSheet`).
4. **Hierarchy**: the row for the user's own team is pinned and gold-outlined; rank 1 of a segment gets a larger row.
5. **Partner Discovery** merges into the same Segmented as `Partners` (it is the same teams). One screen, 1 scroll
   length (target <= 1.2 viewports vs about 3 today, inferred).
6. Empty state: segments with no teams are hidden, not shown as empty cards.

API change (`modules/draft_center_cards.py`, `services/mobile_api_service.py:3925`): keep `label`/`tone`; replace
`items: list[str]` with
`items: [{team_id, team_name, avatar, strategy, strategy_display, draft_rank, draft_rank_tied, future_rank,
future_rank_tied, firsts, reason_code, reason_short, evidence: [{key,label,value}], reason_long}]`. Keep sending
legacy `items` strings for one release so the shipping iOS binary (mid-review) and Android keep rendering; add a
`schema: 2` flag. Risk B (backend + both clients + a test update; `tests/` golden strings change). Web and mobile
ship in the same wave.

Acceptance: no `" | "` in the Draft Center response; every number/chip opens a sheet; row height <= 72px; top-3 +
See all; Playwright at 390 shows <= 1.2 viewports.

---

## 7. Cross-cutting findings

### 7a. Destructive actions and confirm patterns (anti-pattern E)

| Action | File:line | Today | Target |
|---|---|---|---|
| Delete Sim game (hub) | `SimGameContent.tsx:432-447` | trash -> danger card -> Delete / Keep it (**reference pattern**) | extract as `ConfirmInPlace` |
| Delete Sim game / Reset week (More) | `SimGameContent.tsx:863, :893` | two-step in place | adopt shared component |
| Sim auto-draft | `SimGameDraft.tsx:333-336` | in-place confirm | adopt |
| Sim advance with empty slot | `SimActionBar.tsx:63-70` | alertdialog bar | keep |
| Remove saved league (Account) | `SavedLeaguesSection.tsx:75-96` | text link -> paragraph + Confirm/Cancel | trash on league row -> ConfirmInPlace |
| Remove failed league (Portfolio) | `PortfolioContent.tsx:252, :492-505` | **none** | ConfirmInPlace |
| Remove ESPN login | `EspnLoginPanel.tsx:123` | **none** | ConfirmInPlace |
| Sign out (header) | `Header.tsx:522-530` | **none** | ConfirmInPlace |
| Sign out (Account) | `AccountContent.tsx:439` | **none** | ConfirmInPlace |
| Sign out (mobile) | `mobile/src/screens/HomeScreen.tsx:466` | **none** | ConfirmInPlace |
| Delete account (web) | `AccountContent.tsx:447-466` | disabled; mailto support | in-place row; typed confirm when enabled |
| Delete account / remove league (mobile) | `mobile/src/screens/MoreScreen.tsx:398-411, :203-225` | `Alert.alert` | acceptable native |
| Cancel subscription | `AccountContent.tsx:116-128`, `PremiumContent.tsx:202` | Stripe portal | keep |
| Remove my scouting report | `CollegeScoutingContent.tsx:236` | **none** | ConfirmInPlace |
| Remove GM target | `GmPlanContent.tsx:373-377` | **none** | undo toast |
| Delete shared trade | `SharedTradesFeed.tsx:51` | **none**, errors swallowed | ConfirmInPlace + error toast |
| Report shared trade | `SharedTradesFeed.tsx:55` | **none**, no reason | reason sheet |
| Reset lineup | `MatchupPlanner.tsx:380` | **none** (discards edits) | ConfirmInPlace |
| Remove trade asset / team | `TradeAnalyzerContent.tsx:160-232`, `MultiTeamTradeContent.tsx:531, :553` | **none** | undo / ConfirmInPlace if assets |
| Community feed opt-out toggle | `AccountContent.tsx:331-352` | toggle | fine |
| Dismiss StartHere / DirectionCheckin / outcome prompt | `StartHereCard.tsx:97`, `DirectionCheckinCard.tsx:90-94`, `TradeOutcomePrompt.tsx:151` | none (low stakes) | fine |

No `window.confirm` exists anywhere in `web-next/src`.

### 7b. All-caps header bars and chrome without function (anti-pattern L)

- `SectionHeading.tsx:43, :62` forces `uppercase` on every section heading; `uppercase` appears in 80 component files
  and 8+ places in `app/globals.css`. All-caps 18-24px headings are the loudest element on most screens (the
  Draft Center "LEAGUE DRAFT DECISION SIGNALS" is the screenshot case) and compete with hero numbers.
- `DraftCenterContent.tsx:277-308` renders each card as: all-caps `ToneBadge` full-width label bar ("BEST PICK
  BUYERS") + bold title sentence + bullets. The label bar and the title say the same thing; the bar has no function
  (not a filter, not tappable).
- Rule: section headings are sentence case at body-large weight; all-caps only for chip labels <= 12 chars.
  Pill bars become `Segmented` (functional) or are deleted.
- Same pattern: `ToneBadge ... wrap` used as a header (`DraftCenterContent.tsx:289`), "Priority Adds" label bars
  (`WaiversContent.tsx:531-553`), Recaps type headers (`LeagueRecapsContent.tsx`), News/Alerts `EventTypePill` headers
  (`NewsContent.tsx:124-148`, `AlertsContent.tsx:305-325`; these should be filters).

### 7c. Lists with identical visual weight (anti-pattern M)

No hierarchy between row 1 and row N, and no "top 3 + See all": Draft Center cards, Trade Hub ideas (`TradeHubContent.tsx:155-173`),
League Rankings boards (top 3 already, but 5 boards of the same weight), Alerts groups, News, Portfolio cards,
Waiver rows (`WaiversContent.tsx:258-307` except the top card), Commissioner team cards, Account cards, GM Plan Overview,
Dashboard blocks (D1; measured 6 equal-weight tiles in the sample).
Rule for each list: 1 emphasised leader row (larger, accent edge), rows 2-3 standard, remainder behind "See all (n)";
sort by relevance to the user's team, not alphabetically.

### 7d. Raw ids / enums shown to users (anti-pattern N)

- `modules/draft_assistant.py:579` appends `id_text[-6:]` (draft id tail) to the draft label.
- `MyTeamSections.tsx:113` `player.slot.replace("_", " ")` ("SUPER FLEX") for an enum; `SF` special-case only.
- Strategy/mode enums run through `tidy_label(row.get("mode"))` (`modules/draft_center_cards.py:~172`); `kind`/`mode`
  codes (`pick_rich`, `move_veterans`, `spend_future`) are mapped to sentences but fall back to the raw `implication`.
- `Team ${rosterId}` fallbacks for managers without a name (`TradeAnalyzerContent.tsx:716`, `VetoCalculator.tsx:535`).
- `liveDraftPresentation.ts:135` shows `"UNK"` and `"Unknown team"` literals.
- `SimGameContent.tsx:422` falls back to `g.difficulty` raw when no copy label exists.
- Follow-up scan needed: grep `String(` / `.replace(/_/g` across `lib/*Presentation.ts` during each screen's pass.

---

## 8. Duplicate information map (anti-pattern C)

| Information | Where it appears today | Single source |
|---|---|---|
| Playoff odds | `TeamStatusHero.tsx`, `LeagueRankingsContent.tsx`, `GmPlanContent.tsx`, `GamesContent.tsx` (Season Sim), `FantasySimContent.tsx` | hero chip (`TapForWhy`) opening one odds sheet; Games/Fantasy Sim merged |
| Rank / record / age tiles | `DashboardContent.tsx:176-208`, `MyTeamContent.tsx:230-278`, `GmPlanSections.tsx:209-246` | My Team only; Dashboard shows one line |
| Stance / direction | `DirectionCheckinCard.tsx`, `GmPlanSections.tsx:76-170` | one chip + `PickerSheet` |
| Alerts | `AlertsDropdown.tsx` (bell), `AlertsContent.tsx`, Dashboard Watchlist (`DashboardBlocks.tsx`), `SinceLastVisitStrip.tsx` | bell sheet component, one Inbox with News |
| Trade ideas | Trade Hub, Trade Finder, Dashboard Trades block, GM Plan "Trade ideas", Value Signals card | Hub; others link with a count |
| Lineup suggestions | Matchup Lineup Comparison (suggested view) and Suggested Moves | one, with a count chip |
| League lists | header switcher, Portfolio, Account SavedLeagues, mobile Home | one `PickerSheet` for switching, one manager for remove |
| Plan/billing | Account Identity, Account Billing, `PremiumContent.tsx:164-208` | one Plan row |
| Player detail | PQV sheet and full profile (same 6 actions) | PQV quick, profile for depth only |
| Team trade history | `ManagerProfileSheet` (Rankings only), `TradeHistoryContent` (user's shared trades only) | sheet reachable from every team name |
| Scouting | Draft Center Scouting tab and `/college-scouting` | one route |
| Value / OVR explanation | PQV Value history, Model radar, BeginnerHelp, GlossaryNote | tap on the number |
| Notification prefs | Account Preferences toggles + `NotificationControls` | one sheet |

---

## 9. Implementation plan

### 9.1 Ranking method
Score = impact (users hit x severity, 1-5) / effort (S=1, M=2, L=4). Wave 0 is the shared components; waves are
ordered so that each later item composes an earlier component. Items marked B need a backend change; C needs an
owner copy/product decision.

### Wave 0 (build first, 1 owner, ~1 week): shared components
Web `web-next/src/components/ui/` and mobile `mobile/src/components/`, same prop API.
1. `Sheet` + sheet stack (extract from 6 existing shells, fixes modal stacking).
2. `ConfirmInPlace` (extract `SimGameContent.tsx:432-447`).
3. `TapForWhy` + `ToneBadge.onWhy` + `ValueStat` child slot + `why_open` telemetry.
4. `StructuredRow` (crest, name, chip, pills, reason, chevron).
5. `FilterSheet` (multi-group, Apply, active chips); `PickerSheet` on top of it.
6. `SummaryCard`/`DetailSection` helpers and `InfoTip` -> sheet.
Tests: vitest for each (open/close, focus return, Escape); one Playwright 390px smoke.

### Wave 1 (highest impact/lowest effort; ~2 weeks, 4 parallel owners)
| Item | Findings | Owner area |
|---|---|---|
| PQV: Value and OVR taps, delete Value history and Model sections, trim chip stack | P1, P2, P3, P4, P5 | Players |
| Trade Analyzer: PickerSheet per side, verdict chip/balance taps, VerdictCard -> sheet | T1-T12 | Trades |
| Trade Hub/Idea: manager sheet from partner, Balance tap, Analyze button, FilterSheet | T18-T24, T22 | Trades |
| Destructive actions: ConfirmInPlace everywhere | section 7a (12 items), C3, C4, C9, M7, T3, T37, CM2 | Account/League |
| Draft Center redesign (section 6.4) incl. API schema 2 | R1, R2, K1 | Draft/Backend |
| Dashboard: delete duplicate My Team strip and explainers, tile taps | D2, D3, D4, D7 | Today |
| Waivers: FAAB tap, remove explainer stack, Priority Adds header | W1, W3, W4, W8 | Waivers |
| My Team: Biggest need card, tile taps, delete glossary | MT1-MT4 | My Team |
| Matchup: win % tap, Reset confirm, delete header helps | M1, M2, M4, M7 | Matchup |

### Wave 2 (structural; ~3 weeks)
| Item | Findings | Owner |
|---|---|---|
| Players FilterSheet, Compare redesign (verdict card + tap rows + picker) | P10, P11, P14, P15 | Players |
| Trade Finder PickerSheet, compact Hub rows, multi-team picker | T26, T29-T33, T38 | Trades |
| Account hub (7 cards -> rows), Notifications sheet, plan dedupe | A1-A7, N6-N8 | Account |
| Portfolio compact rows, league manager, connect chooser multi-select | C1, C5, C7, C10, C11 | Portfolio/Onboarding |
| Dashboard summary + Today unification (one Inbox with News) | D1, D9-D11, N1-N5 | Today |
| League Rankings one table, Recaps FilterSheet + grade sheet | L1-L5 | League |
| GM Plan stance picker + overview summary | G1-G5 | GM Plan |
| Waiver top card/RecommendedRow/SuggestedDrop sheets | W2, W5-W7, W9 | Waivers |
| Matchup Insights + Suggested Moves merge | M3, M5, M6 | Matchup |
| Other pipe-string generators (K2-K16) | section 6.3 | Backend |

### Wave 3 (polish and bigger bets; ~3 weeks)
Onboarding reorder (O1, O2; needs owner decision C), StepFlow for Sim setup / ESPN connect / Live Draft evaluator
(S5, C8, R9), Live Draft sections and rows (R6, R7), College Scouting filters (R4, R5), Games/Fantasy Sim odds merge (S1-S4),
Commissioner/Veto/Roundup sheets (L6-L9), PQV 10-section restructure (P6-P9), Trade History (T35), SEO ranking page (P16),
uppercase heading policy (7b) across `SectionHeading`.

### 9.2 Owner assignment (parallel agents)
- **Foundation**: Wave 0 components (1 agent; blocks the rest for ~2 days, then others can start with stubs).
- **Players/PQV/Compare**, **Trades**, **Waivers + Matchup**, **Today + My Team + Alerts/News**,
  **League (Rankings, Recaps, Commissioner)**, **Account/Portfolio/Onboarding**, **GM Plan + Draft + Live Draft**,
  **Games/Sim/Community**, **Backend copy (draft_center_cards, K2-K11)**.
- Per the standing rules: max 2-3 agents at a time, sonnet for subagents; web + mobile in the same brief; no
  per-page duplicates of shared components; GM orb is never redesigned per screen. Agents touching
  `TradeAnalyzerContent.tsx` / `DashboardContent.tsx` must serialise (the largest files, 1.2k and 285 lines with many
  owners).

### 9.3 Quick wins (each < 1 day, no shared component needed or trivially small)
1. Delete the two `BeginnerHelp`s in `MatchupContent.tsx:83-102` and the Dashboard `BeginnerHelp` + `GlossaryNote`
   (`DashboardContent.tsx:184-206`); delete `MyTeamContent.tsx:224-227, :260-277`.
2. Delete duplicate Dashboard My Team strip (`DashboardContent.tsx:176-208`) (D3).
3. Promote "Biggest need" text out of the `InfoTip` on My Team (MT4).
4. `ManagerProfileSheet` from `TradeIdeaCard` partner name (T20); it already exists.
5. Remove the duplicate reason paragraph in `TradeOfferContent.tsx:166` (T34).
6. Remove "Read more" duplication of rationale in VerdictCard (T11).
7. Add `aria-label` + `onClick` on `ValueStat` for Value tile -> open existing `PlayerValueHistory` in the existing PQV
   modal as a first step (P1, S).
8. Show Reset-lineup confirmation using the Sim confirm markup (M7).
9. Sign out confirm (3 places) and failed-league remove confirm with the Sim confirm markup (S each).
10. Delete the second WaiversContent InfoTip (`:669`) and "Place claims in Sleeper" repeated note (`:553`).
11. Remove `NextSteps` footers (`AlertsContent.tsx:329`, `MyTeamContent.tsx`, `LeagueRankingsContent.tsx`) (D13).
12. Fix `draft_assistant.py:579` to stop appending the draft id tail (anti-pattern N).
13. Draft Center: drop the all-caps `ToneBadge` label bar and sub-title, keep title (interim, 1 hour).
14. Rename "Value margin" vs "Proj margin" on Matchup (M2).
15. Move the `FreeLimitNote` in `TradeHubContent.tsx:119-141` below the first idea.
16. Make `AlertsContent` PositionBadge open PQV (N3).

---

## 10. Top 15 findings (ranked by impact/effort) with before/after taps

| # | Finding | Ids | Taps before | Taps after | Basis |
|---|---|---|---|---|---|
| 1 | Make every number/chip a `TapForWhy` (Value, OVR, rank, balance, odds, FAAB, win %, grades) | P1, P2, T6, D5, W3, M1, L5 | "why" unreachable or 1-3 + scroll | 1 | I |
| 2 | Trade asset picking as PickerSheet per side | T1, T2, T29, T38 | 8-10 + 2-3 scrolls | 5 | I |
| 3 | PQV: delete Value history/Model sections, tap Value/OVR | P1, P2, P5, P6 | 1 + 2 scrolls | 2, no scroll | I |
| 4 | Verdict card 17 blocks -> summary + "Why" sheet | T5, T7-T12 | 1-2 + long scroll | 1 | I |
| 5 | Draft Center StructuredRow redesign + API schema 2 | R1, R2, K1 | 2 + read ~25 lines | 2 | I |
| 6 | ConfirmInPlace on 11 unconfirmed destructive actions | section 7a | 1 (no safety) | 2 (safe) | I |
| 7 | Account: 7 cards -> settings hub; Notifications sheet | A1, A2, N6 | 3-5 + deep scroll | 3 | I |
| 8 | Dashboard: 13 blocks -> hero + 3 rows; dedupe snapshot/glossary | D1-D4, D9 | 2.31 viewports (M) | about 1.2 (target) | M before |
| 9 | Trade Hub idea: partner -> manager sheet, Analyze button, compact rows | T18-T22, T26 | 8-10 to reproduce an idea | 1 | I |
| 10 | Players/Waivers/News FilterSheet | P10, W9, N4, R4 | 6 (3 selects) | 5, fewer on repeat | I |
| 11 | League Rankings: 5 boards -> 1 table + sort | L1 | 5+ scrolls | 1 | I |
| 12 | Player Compare: verdict card, tappable rows, PickerSheet | P14, P15 | 3-4 + 5 stacked inert sections | 2-3 | I |
| 13 | Waivers: FAAB tap, drop explainer stack, summary top card | W1-W3 | impossible on touch | 1 | I |
| 14 | One league manager + compact Portfolio rows + multi-select connect | C1, C4, C7 | remove healthy league 4 + long scroll | 2 | I |
| 15 | Onboarding: connect league before paywall; OAuth first | O1, O2 | 10-12 + 2 fields | about 8 | I |

Honest note on measurement: only the Dashboard baseline (2.31 viewports, 22 tappable controls, 5 inert numeric
values) was measured. Every other count is derived from reading the code; treat as estimates.

---

## 11. Risks and decisions for the owner

1. **API schema 2 for Draft Center** (and later K2-K11): the iOS binary is mid-review and Android is live; keep legacy
   string `items` for one release.
2. **Onboarding paywall order (O1)** is a product/revenue decision (C).
3. **Typed confirm for account delete** depends on re-enabling self-service (`AccountContent.tsx:445` TEMPORARY).
4. **Auto-compute playoff odds (L3)** has a compute cost; needs caching.
5. **Telemetry**: `why_open` events will reveal which numbers matter; use them to prune.
6. Golden-value test fixtures drift (known); several Wave 1 items change copy and will touch snapshot tests.
7. Parity: every web item has a mobile twin; mobile already has `FilterDropdownButton`, `SwipeDismissSheet`,
   `SegmentedTabBar`, so mobile is closer than web for pickers.

## Appendix A. Method and limits

- Worktree from `origin/main` (83a80678), no product code changed; `next dev` on port 3291 with dummy Supabase
  vars in gitignored `web-next/.env.local`; Playwright 390x844, touch, DPR 2, chromium-1181.
- Measured: `/sample-league` (scroll height, headings, tappable controls, inert numerals, min font).
- The Fantasy Sim mock (`scripts/sim_layout_playwright/measure.mjs`) did not reach "Open game" in this environment
  (API base needed to be `http://localhost:8000`, set in the worktree env; step still timed out), so Sim screens are
  code-read only.
- Code scan: two read-only sweeps (trades/players/waivers/matchup; account/league/plan/draft/games) plus direct greps for
  `" | "` / `" · "` joins in `web-next/src`, `modules/`, `services/`. Line numbers were verified against the worktree;
  a few (flagged in the sweeps) are approximate by a few lines: PQV chip stack (P5), Matchup (M4-M6), Players row (P11).
- Not audited line by line: most `SimGame*.tsx` files, the Recaps/Storylines tabs of `LeagueRecapsContent.tsx`, mobile
  screens (skimmed for parity only).
