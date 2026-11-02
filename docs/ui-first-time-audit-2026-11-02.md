# First-time-user UI readability and navigation audit, 2026-11-02

Request (coridian_): "another UI readability audit from the user's perspective, especially a first-time user: is everything easy to read, easy to navigate, easy to get to the page you want?"

Screenshots are in `docs/assets/ui-first-time-audit-2026-11-02/` (downscaled copies). Full-resolution originals: `/private/tmp/claude-501/ftaudit-shots/` (local to the audit machine).

## Method and honest limits

- Built the web app from `origin/main` (`next build` + `next start`) and ran the real FastAPI backend against real Sleeper data (league "Disqualify FF", 12 teams, week 8). Only Supabase was faked (a small local stand-in for sign-up and the saved-leagues table), so every number and sentence on screen is the real engine output.
- Walked it as a stranger: landing, email sign-up, onboarding carousel, connect Sleeper (including a bad username), dashboard, My Team, Matchup, Waivers, Trade Hub / Analyzer / Finder, Players and Quick View, League Rankings, GM Plan, Alerts, Games, Recaps, Draft Center, Commissioner, News, Community, Account, Trade History, 404, the MENU button, the GM orb sheet, league switcher, valuation-lens menu and search. 390px (phone, 2x) and 1280px (desktop; sidebar also checked at 1280x720).
- A DOM scan on every page counted: controls under 44px, text under 12px, WCAG AA contrast failures (computed from the rendered colors), ellipsis truncation, horizontal overflow.
- The mobile app was not run (no device, and the react-native-web harness was not set up). App findings are from reading `mobile/src` and comparing it with web; they are marked "code only".
- Not verifiable here: `/premium` and billing while signed in (the stand-in Supabase returns fake plans, so the page errored; the signed-out version was covered on 2026-11-01), the Account page's email row and referral link (stand-in data), real Pro/Premium states. The free tier was the account tested, so Pro-only screens show their paywall.
- "Free: 2 of 1 league" on the connect page is an artifact of the stand-in database (it kept duplicate rows) and is not a finding.
- Contrast: zero AA failures found on any page at rest. The only failures the scan reported were on panels that were see-through (finding F1). 11px caps labels are legible but small.

## Status of the 2026-11-01 proposals (verified against current `origin/main`)

| Old # | Item | Status today |
|---|---|---|
| F1-F4, F10 | Section-heading action targets, landing footer, pricing de-dup, Sign in link, Trending badge | Fixed (#1595); re-scanned, no regressions |
| F5 | Premium entry in the web menu | Still open (not in `navDestinations.ts`) |
| F6 | "More" vs "Account" naming | Still open (app: More; web: Account under MENU) |
| F8 | Playoff Odds findability on web | Partly: League Rankings has a "Calculate playoff odds" button; still no nav row (app has one) |
| F9 | Community missing from the app nav | Still open (no Community row in `GmOrb.tsx`) |
| F11 | Trade History three labels | Still open |
| F12 | "--" in /premium intro, redundant kicker | Still open (`PublicPricingContent.tsx` lines 60-65) |
| F13 | Landing form far down the page | Still open, and worse once signed in (see F2 below) |
| F14 | Jargon tooltips on Players / Trade Analyzer | Still open |
| F15 | Commissioner row for non-commissioners | App now conditional (`GmOrb.tsx` line ~230); web shows it to everyone and free users get a paywall card |
| Correction | "MENU opens the GM orb menu" | Wrong. Header MENU opens an account + legal list; navigation is the GM orb (bottom-centre logo). See F3 |

## Findings, ranked

Severity: H = blocks or misleads a main flow, M = friction a typical first-timer hits, L = polish. Effort: S under 1h, M half day, L multi-day. Platform: W web, A app (code only unless stated).

| # | Sev | Plat | Where | Finding | Effort | Status |
|---|---|---|---|---|---|---|
| F1 | H | W | Every glass panel: MENU dropdown, GM orb sheet, league switcher, lens menu, Player Quick View sheet, frosted cards (`06-glass-before-after.jpg`, `15-menu-button-390.jpg`) | On Chrome, Firefox and Android the panels had no blur: page text ghosted through menus and the Quick View sheet ("Any age" filters visible behind Jahmyr Gibbs' stats). Cause: hand-written `-webkit-backdrop-filter` twins made the CSS optimizer ship only the prefixed property (confirmed in the live production CSS). | S | **Fixed, PR #1610** |
| F2 | H | W | Landing after sign-up (`02-signed-in-landing-390.jpg`) | A user who just created an account lands on the marketing page: headline still "Create your account. Get the trade your leaguemate would actually accept.", "Try a sample league", a 7-slide carousel, "Start free for 3 days / needs a card", and only then "Your league is on Sleeper / ESPN..." about 3 screens down (y=990 of 2000). The one thing they must do next (connect a league) is the least prominent. | M | Proposal P1 |
| F3 | H | W | Header "MENU" (`15-menu-button-390.jpg`) | MENU opens How We Evaluate / Account / About / Terms / Privacy / Subscription Terms / Sign out. Real navigation (Dashboard, Waivers, Trade Hub...) is the unlabeled round logo orb at bottom-centre. A first-timer taps MENU expecting the nav and gets legal links. The orb has an aria-label but no visible word. | S-M | Proposal P2 |
| F4 | M | W | League Rankings (390px) | The page is about 15,500px tall (~18 screens): standings, playoff odds, then five more full 12-team lists (Roster Power, Franchise Value, Draft Capital, Starter Quality, Bench Depth), no jump links, no collapse. | M | Proposal P3 |
| F5 | M | W | Dashboard Today card | A free user saw "No urgent roster issues right now." directly above "1 more move available on Premium." and a header "showing 4 of 5 next moves". Two opposite statements. | S | **Fixed, PR #1612** |
| F6 | M | W | Dashboard Watchlist rows (`05-dashboard-before-after.jpg`) | Reason text cut to one line at 390px: "Jordyn Tyson (WR)...", "Starter and depth coverage identif...", and the Trending row reads just "Usage...". | S | **Fixed, PR #1612** |
| F7 | M | W | Tap targets (scan at 390) | Under 44px: every ⓘ info button (16px), FantasyCalc credit link on most pages (15px), Forgot password (16px), News player rows (28px), Trade Analyzer You send / You receive selectors (16px, the control that picks the side being edited), Guess the Player X (11x20), Replay tour / Copy link (38px), Waivers View details (36px), GM Plan roster line (38px). App: ScreenInfoNote (about 34pt) and Forgot password. | S | **Fixed, PR #1611** (web + app) |
| F8 | M | W | Connect a league, bad username (`11-connect-error-before-after.jpg`) | "Try a sample league" appeared twice, with "Load my leagues" wedged between them. The error text itself is excellent (names the problem, says where to find the username). | S | **Fixed, PR #1613** |
| F9 | M | W+A | Jargon with no explanation | "Fringe Contender", "Sell High", "FITS YOUR PLAN", the "Redraft" chip (and Dynasty / Rebuild lens), "Franchise Rank" vs "Power Rank", "Future Asset Health Watch" (a 4-line red tile), Waivers "Stash / Watch / Waiver claim / Rolling waivers / no FAAB", Matchup "Your value / Their value / Value margin" next to "Proj margin". The glossary and "What do these mean?" exist only under the dashboard tile grid. Beginner mode only partly covers this. | M | Proposal P4 |
| F10 | M | W | Two numbers per player | Every row shows a big "VALUE 5313" plus a ringed "84" with no legend on that screen (Quick View calls them Value and Player Score). Players/Trade lists are a wall of ring digits (8.96px). | M | Proposal P5 |
| F11 | M | W | Alerts vs Dashboard | Dashboard chip says "ALERTS 3 to watch"; Alerts page says "All quiet. No relevant news for your roster right now." (the chip counts trade/health/watch signals; the page lists news). | S | Proposal P6 (copy) |
| F12 | M | W | Page titles | Header kicker shows the page ("Players", "Waivers") but the on-page H1 is the league name on Players, Waivers, Alerts, Rankings, Trade Hub ("Disqualify FF" + a subtitle) while Matchup says "Matchup". Trade History H1 is "Did it work out?", Community's "Craziest trades this week". Hard to confirm where you are after a tap. | S-M | Proposal P7 |
| F13 | M | W | Players filters (`09-players-rankings-390.jpg`) | Five plain white native selects (first one just says "ALL", no label) above a 6th sort control, unstyled next to the rest of the glass UI; filter purpose is guessable only from the values. | S-M | Proposal P8 |
| F14 | L | W | Desktop sidebar | Sidebar scrolls internally with no hint: at 1280x720, Commissioner, Home, Portfolio, News, Trade History, College Scouting and Community are below the fold (4 hidden at 1280x900). (`12-desktop-sidebar-1280x720.jpg`) | S | Proposal P9 |
| F15 | L | W+A | Locked features | Commissioner and Draft Center show only a paywall card for free users (no preview of what is behind it); Commissioner shows two headings ("COMMISSIONER" then "Spot tanking..."). Copy says "Pro feature" while the account, dashboard and pricing say "Premium" (tier names Pro / Front Office are deliberate, so wording needs a product call). | S | Proposal P10 |
| F16 | L | A | GM orb subtitles | League Rankings, Trade Hub and GM Plan rows described differently on web and app. | S | **Fixed, PR #1615** (app) |
| F17 | L | W | Injury badge | Out showed as a bare "O" (the app spells it out). Hover text does not exist on a phone. | S | **Fixed, PR #1612** |
| F18 | L | A (code) | Type scale | `theme.ts` defines badge 9pt, caption/kicker 11pt, and `fontSize` 8-11 appears 240 times across screens. Web has the same 11px caps labels. Legible but under common 12px guidance. | L | Proposal P11 |
| F19 | L | W | Valuation-lens menu open | Page gains 6px of horizontal overflow (scrollWidth 396 at 390). | S | Open |
| F20 | L | W | Player rows | 40px tall tap rows (My Team, Trade Hub, Players) via the shared PlayerIdentityTrigger; raising it changes row height on dozens of lists. | M | Proposal P12 |
| F21 | L | W | Onboarding carousel | Skip is dim grey text; dots are small; 4 slides before the first useful action. Fine, but F2 means it is the only guidance before landing on a marketing page. | S | Note |

Checked and fine: no horizontal overflow at 390 or 1280 on any page (except F19); zero AA contrast failures at rest in light theme; empty/error states read clearly (Alerts "All quiet", Community "Nothing shared yet", Trade History "No trade history yet", 404 with a way back, bad Sleeper username); Trade Hub tabs, position and lens controls are 44px; the Sleeper error copy; start-here checklist.

## Navigation: taps to reach each destination from the dashboard (phone)

| Goal | Web | App | Note |
|---|---|---|---|
| Analyze a trade | 1 (Analyze a trade) | 1 | good |
| Lineup / best trade / waivers | 1 (Start here cards) | 1 | good, but the card disappears after Hide |
| Matchup, Waivers, My Team, Players, League Rankings, GM Plan | 2 (orb then row) | 2 | needs the orb (F3) |
| Trade Finder / Analyzer | 3 (orb, Trade Hub, tab) | 3 | intentional (2026-10-17) |
| Player detail | 2-3 (Players then row; search icon is 2) | 2-3 | good |
| Playoff Odds | 3 (League Rankings then button) | 2 | F-parity (not in web nav) |
| Account / settings | 2 (MENU then Account) | 2 (orb, More) | MENU wording F3 |
| Premium / billing | 3 (Account then Upgrade) | 2 (orb Premium) | no web menu entry |
| Alerts | 1 (bell) | 1 | good |
| Back | Browser back works on all pages; no in-app back affordance on web phone | native | OK |

## Proposals for coridian_ to decide (navigation / IA / copy; none implemented)

- **P1 (F2) Signed-in landing.** Once signed in with no league, replace the hero with "Connect your league" at the top (Sleeper username first, sample link secondary); keep the carousel and trial text for signed-out visitors. W+A (app onboarding already goes straight to connect). Effort M.
- **P2 (F3) Name the nav.** Options: rename header MENU to "Account" and add a visible "Menu" label next to the orb; or make the header MENU open the same destinations list as the orb and move legal links into Account. Recommend option 1 (smaller). Effort S-M.
- **P3 (F4) League Rankings.** Jump chips (Standings, Playoff odds, Power, Value, Picks, Starters, Bench) plus default-collapse the five ranking lists after the top 3 rows. Effort M.
- **P4 (F9) Jargon.** Reuse `InfoTip` and the existing glossary for: posture labels, lens names, Franchise vs Power Rank, Value vs Player Score, Value margin vs Proj margin, Stash/Watch/FAAB, and rename "Future Asset Health Watch" in `modules/injury_ui.py` / `rankings.py` (shared by web and app, so a backend vocabulary decision). Effort M.
- **P5 (F10) Value vs score.** Add one short legend under the first list on each screen, or drop the ring on dense lists. Effort S-M.
- **P6 (F11) Alerts count wording.** Chip "3 to watch" -> "3 signals" and Alerts page copy "News on your rostered players" so they stop contradicting; or make Alerts list the same items. Effort S.
- **P7 (F12) One H1 rule.** H1 = page name, league name as the small kicker (as Matchup already does). W+A. Effort S-M.
- **P8 (F13) Players filters.** Chip row for position + one "Filters" sheet for the rest, using the existing PillRow. Effort M.
- **P9 (F14) Sidebar.** Scroll fade, or collapse GM Tools / General into groups. Effort S.
- **P10 (F15) Locked-feature copy.** Decide Pro vs Premium wording; show a 2-3 line preview of what is inside. Effort S.
- **P11 (F18) Type floor.** Raise the app's `badge/kicker/caption` tokens to 12 and sweep sub-12 literals; do web 11px caps labels at the same time. Effort L.
- **P12 (F20) 44px player rows** through one change to `PlayerIdentityTrigger` plus a visual pass on every list. Effort M.
- **Carried over:** F5 Premium nav entry, F6 "More" vs "Account", F9 Community in the app, F11 Trade History labels, F12 pricing "--".

## What shipped from this audit (not merged)

| PR | Change | Platform |
|---|---|---|
| #1610 | Restore blur on glass panels (Chrome/Firefox/Android) | W |
| #1611 | Tap targets under 44px | W + A |
| #1612 | Dashboard: no "nothing urgent" beside an upsell, 2-line watchlist reasons, OUT badge | W |
| #1613 | One sample-league button in the connect error state | W |
| #1615 | App nav subtitles match web | A |
