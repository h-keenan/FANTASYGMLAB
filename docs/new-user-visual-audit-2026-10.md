# New-user visual and module audit (2026-10-25)

Ask from coridian_ (2026-10-25): "do another module and overall visual audit
for new users. If we need ChatGPT to do redesigns we can let you know."

Builds on `ui-organization-audit-2026-10.md`, `new-user-intake-audit-2026-10.md`,
`web-app-parity-audit-2026-10.md` and `ui-module-inventory.md`. It does not
repeat them. Findings already listed there are only referenced.

## Method and what is NOT verified

- **Rendered (web only):** headless Chrome (`chrome-headless-shell` from the
  local Playwright cache; no Playwright package is installed in the repo, so
  I drove the binary directly with `--screenshot`) against a local
  `next dev` at 390 px width, with dummy env values and the API pointed at a
  dead local port. No production or live service was contacted. Screenshots:
  `docs/screenshots/new-user-audit/` (landing fold and full page, sample
  league after the fix).
- **Not rendered:** every signed-in screen (Dashboard, Portfolio, Trades,
  Matchup, Waivers, News, More, onboarding steps, paywall, checkout, post-pay
  return). They need a real session or a mocked auth/API layer, which does not
  exist in the repo, and building one was out of scope. A signed-out request
  to those routes just renders the landing page, so those screenshots were
  discarded. Those rows are **code-read only**.
- **App (iOS/Android):** code-read only. No simulator, no builds.
- Contrast: tokens were checked by reading `globals.css` / `theme.ts`, not by
  measuring pixels. The shared tokens are already AA-tuned with documented
  ratios (muted text, accent, warning, danger, light and dark). I found no
  failing token. Contrast risk is in per-screen hard-codes, which I could not
  sweep in rendered output.
- Headless Chrome defaulted to a light scheme and ignored
  `--force-prefers-color-scheme=dark` on non-landing pages, so I have no
  rendered dark screenshot of the sample league. The landing page is
  always-dark by design.

## Per-screen table

Severity: P0 blocks or misleads a first-run user, P1 clear friction, P2
polish. Size: S under half a day, M about a day, L multi-day. Fix type:
**code** = safe with shared parts, **designer** = needs a real layout decision.

| Screen | What a new user sees | Issues | Sev | Size | Fix type |
|---|---|---|---|---|---|
| Landing (web, rendered) | Dark hero "Your fantasy front office, not just a stats app.", auto-advancing phone-screenshot carousel with dots and pause, "Start free for 3 days", sign-in card, 3 checks, platform note, store badges | Sign-in card sits below a ~330 px carousel so Continue is at about y=680 of 844 (visible, good). Carousel auto-advances while the user reads; dots are 44 px targets (fine). Subtitle under H1 is not in the 390 px render (hidden on small widths), so "what is this" rests on the H1 plus screenshots. Trial days hardcoded vs paywall reading the API (intake audit #8, still open). Page ends at about y=950, big empty tail on tall phones. "Mobile apps" row: App Store "Coming soon" next to a live Google Play; confusing next to the iOS review status | P1 | M | designer (hero and above-the-fold order); code for trial copy |
| Sign-in/up card | Glass card: Email, Continue, Google / Apple. No password field, no "sign up vs sign in" distinction until after Continue. No visible guest path | Single email field is clean. Copy "Enter your email to sign in or create an account" is clear. Guest/sample path is only a quiet link further down | P2 | S | code |
| Onboarding, 3 steps (web) | Value slide, "Connect Sleeper or ESPN", dynasty-level cards (shortened from 10 steps, intake audit A is done) | Step 2 headline says "Connect Sleeper or ESPN" but offers Fleaflicker/MFL later; level cards are good. Skip is a 44 px target. Progress is session-only (intake #15) | P2 | S | code |
| Trial / paywall (web `OnboardingPaywall`) | "Try Pro free for N days", one button, price line, "Skip for now" | **Skip was a 12 px underlined text link with no tap area (fixed here).** Offer still comes before any league value (intake #5, product call). "Full access to the GM toolkit" says nothing concrete: no list of what Pro unlocks vs Free | P1 | S done (tap) / M (value list) | code (tap, done); designer for the value list |
| Checkout container and post-pay return | Embedded Stripe modal, then "You're in. Pro is unlocked. Connect your league to get started." | Not touched (billing is out of scope). Code-read: return copy is clear and points to the right next step | P2 | - | - |
| Sample league (#1497, web rendered, app code) | Banner "Sample league" plus "Connect your real league", team name, Roster / Game Plan / Trade tabs, 8 players | **Rows had a bare number with no label and names misaligned by badge width (fixed here: `ValueStat` + fixed badge slot).** First row shows a stray top hairline. Sticky banner is good and clearly labels fake data. Gold standard for an empty-account first look but there is no sample Dashboard (This week / Today), which is the screen a real user lands on | P1 | S done / L (sample Dashboard) | code done; designer for a sample Dashboard |
| "Start here" card | Three rows (lineup, trade idea, waivers), Hide | Good, shared parts. It is the first module above the rank strip; correct. Only shown to accounts under 14 days | P2 | - | - |
| First Dashboard / Home (web, code) | Start here, Guillotine (if any), 4-tile rank strip (Record, Power, Franchise, Avg Age), This week strip, Today hero, Watchlist, League Activity/Pulse, two Guess-the-Player cards, Team Snapshot, league-type control | **No dominant module: the rank strip outranks Today.** Rank labels are jargon for a new player (Power Rank, Franchise Rank) with no inline help unless the beginner flag is set. Two mini-games sit above Team Snapshot. "View All" links and the GamePlan CTA were ~20 px tall (fixed here) | P1 | M (order) / S done (taps) | designer (module order); code (taps, done) |
| Home (app, code) | League cards, Add League sheet, sample-league entry on the no-league state, `PushPermissionPrompt` only after the first league loads (14-day "Not now") | Push pre-prompt is already correct. View All links were 12 px text with hitSlop 8 (fixed here with a shared `LINK_HIT_SLOP`) | P2 | S done | code |
| Empty: no league, Portfolio (web) | **Bare muted paragraph "Save a league to see it here." and a small "+ Add a league" text link** | A dead-end screen for exactly the user with no league. App already had a CTA button. Fixed here: shared `EmptyState` + "Connect a league" button + "Explore a sample league first" | P0 | S done | code |
| Empty: no league, Portfolio (app) | EmptyState with "Go to Home" ("Save a league from Home") | Said "save" not "connect", sent the user to Home with no sheet open, no sample path. Fixed here: opens the Add League sheet, adds sample secondary link | P1 | S done | code |
| Empty: no data / no players / no news | Shared `EmptyState` on News, Players, Alerts (Alerts has a Connect CTA) | Consistent. News empty has no next step, which is fine. Players "No players match" has a Clear filters button | P2 | - | - |
| Portfolio (populated) | League cards with team avatar, signals, "Open Dashboard" | Free accounts see the upsell card for the second league. Fine. Exposure tab verify (parity doc) | P2 | - | - |
| Trades (Hub, Finder, Analyzer) | Trade ideas with exchange, lean bar, share; free shows 2 ideas | Free limits only surface after the list (intake #7). Hub text links ("Open Trade Finder") were small taps (fixed here). Jargon: "lean", "package", "posture" unexplained | P1 | S done (taps) / M (limits line) | code; designer for limit/upsell placement |
| Matchup | Win odds, planner, rows with avatars; says it cannot change the Sleeper lineup | Web rows still not on shared `PlayerRow` (inventory follow-up) | P2 | M | code |
| Waivers | Tier avatars, confidence meter, FAAB help | `HighlightTarget` deep link on app unverified. No new-user explanation of "FAAB" beyond help text | P2 | S | code |
| News | General NFL news, not filtered to the user's rosters (stated in the header) | Clear. "Not filtered to your rosters" may disappoint users who expect a personalised feed | P2 | S | code (copy) |
| More (app) / Account (web) | Settings, legal, support | No "Send feedback" entry (intake #11) | P2 | S | code |
| Loading and error states | Shared `ErrorState`, skeletons, `LoadingScreen` brand pulse | Consistent. Portfolio reserves card height. No finding | - | - | - |
| Web vs app consistency | Shared module names on both sides | Parity gaps remain per `web-app-parity-audit-2026-10.md` (Dashboard rows without `BriefingItemPlayers`, local `LeaguePulseSection`) | P1 | M | code |

## Top 10 fixes, ranked

1. **Give Dashboard one dominant module for a first run** (Today hero above the
   rank strip, strip lower or collapsed, mini-games below Team Snapshot).
   M. Designer/product call, same order on app. **Done** (follow-up PR: Today
   first, rank strip second, mini-games last, web and app; no module removed).
2. **Portfolio no-league empty state with a real button and sample path**
   (web dead end). S. **Done.**
3. **Tap targets on first-run links**: Dashboard "View All", GamePlan CTA,
   Today link, paywall Skip, Trade Hub links, app View All links. S. **Done**
   (web `.tap-link`, app `LINK_HIT_SLOP`).
4. **Sample league rows labelled and aligned** (`ValueStat`, fixed badge
   slot), web and app. S. **Done.**
5. **Sample Dashboard**: a read-only "This week + Today" sample so the screen
   a real user lands on can be previewed. L, needs designer plus fixtures.
6. **Plain-language labels for Power / Franchise Rank and Starter/Bench
   Strength** for everyone, not only the beginner flag (one shared glossary
   sheet, `InfoTip` on the tiles). M. **Done** (`lib/glossary.ts` on web and
   app, `GlossaryNote` under the Dashboard, My Team and Portfolio rank labels).
7. **Paywall value list**: three concrete Pro benefits and what Free keeps,
   replacing "Full access to the GM toolkit". M, designer copy plus layout.
8. **Free limits shown before they bite** ("Free shows your top 2 ideas
   today") on Trade Hub, GM Plan and the connect step. S-M. **Done** (`FreeLimitNote`;
   every number comes from the API, not a client copy).
9. **Landing: trial length from the billing API, and the store-badge row**
   ("App Store: Coming soon" next to a live Google Play) reviewed once iOS
   is out of review. S.
10. **Landing above-the-fold**: put the one-line "what it does" under the H1
    on phone widths (currently hidden), and cap carousel auto-advance to one
    loop. M, designer.

## Designer brief list (for a designer or ChatGPT image tool)

Common to every brief: keep the existing shared modules and tokens
(`.glass-surface`, `AccentCard`, `SectionHeading`, `PillRow`/`SegmentedTabBar`,
`Button` dark ink on cyan, `PositionBadge`, `ToneBadge`, `EmptyState`); fixed
semantic colors (success green, danger red, warning amber, premium gold, accent
cyan `#67e8f9` dark / `#056e7c` light); UPPERCASE section titles; the GM orb is
never redesigned per screen. Design both dark and light, 390 px wide, 44 px
minimum targets, 4.5:1 text contrast. Avoid: new per-page card styles, nested
cards, a second primary button per module, fabricated stats or testimonials,
and anything implying real user data in sample content.

1. **First Dashboard (new account).** Goal: one obvious thing to do in the
   first 10 seconds. Must keep: Start here card, This week strip, Today hero
   with its single CTA, Watchlist, League Activity, Team Snapshot, the rank
   tiles (demoted, with plain-language captions), the two games (lowest). Show
   the order top to bottom at 390 px with the Today hero dominant. Avoid
   adding a new "welcome banner" on top of Start here.
2. **Landing above the fold.** Goal: in one screen the visitor knows what the
   product is, sees it, and can sign up without scrolling past the carousel.
   Must keep: H1, phone carousel (reduced motion safe), sign-in card with
   email/Google/Apple, platform note, store badges. Show the subtitle line on
   phones. Avoid autoplay that moves faster than reading speed.
3. **Paywall / trial offer.** Goal: say concretely what Pro adds over Free.
   Must keep: trial length from the billing API, one primary button, price
   line, Skip. Add a three-row benefit list and a "Free keeps..." line. Gold
   premium accent only on the button. Avoid urgency tricks.
4. **Sample league as a real preview.** Goal: a no-league user can see a
   Dashboard-quality "This week + Today" with clearly fake data. Must keep:
   the sticky "Sample league" banner and Connect CTA. Avoid real player names
   or any number that looks like a real recommendation.
5. **Free-limit and upsell placement (Trade Hub, GM Plan).** Goal: the user
   knows the limit before hitting it and sees one upgrade path. Must keep:
   `PremiumUpsellCard`, trade idea cards. Avoid a second upsell on the same
   screen.

## Fixes made in this PR (web and app together, shared parts only)

Web:
- `globals.css`: new `.tap-link` utility (44 px min height via
  `--touch-target-min`, no visual change).
- Applied to Dashboard `ViewAllLink`, `TodayModule` View All, `GamePlanCard`
  CTA, `OnboardingPaywall` Skip, two `TradeHubContent` links.
- `PortfolioContent` no-league state: shared `EmptyState`, `ButtonLink`
  "Connect a league", `SampleLeagueLink`. Page title is now "Your leagues".
- `SampleLeagueContent`: shared `ValueStat` for the number, fixed-width
  position-badge slot so names align.
- Tests: `PortfolioContent.test.tsx` updated (Connect a league link and
  sample link).

App:
- `theme.ts`: `LINK_HIT_SLOP` (14/12) used for Dashboard View All (x2),
  GM Plan View All, Paywall Skip and Close.
- `PortfolioScreen` empty state: "Connect a league" opens the Add League
  sheet (`Home { openAddLeague }`), adds "Explore a sample league first".
- `SampleLeagueScreen`: shared `ValueStat`, fixed badge slot.

Not changed (out of scope or a product call): billing/checkout logic,
analytics, auth, Dashboard module order, onboarding order, trial timing, the
`dev`-only Next error badge seen in screenshots.

## Verification

- Web: `tsc` shows only the existing `satori/standalone` errors (stale local
  `node_modules`, same as the intake audit); `eslint` 0 errors (3 existing
  warnings); `vitest`: 866 passed, 3 failed, all in `shareCard/*` for the same
  missing `satori` package. Touched suites (Portfolio, SampleLeague,
  OnboardingPaywall) pass.
- Mobile: `tsc` clean, `npm test` 367 pass, 0 fail.
- Rendered check: only the landing page and the sample league on web.
  Tap-target changes, Portfolio empty state and all app changes were not
  visually checked.
