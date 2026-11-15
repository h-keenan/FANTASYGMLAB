# First-time-user ("noob") audit (2026-11)

Trigger (coridian_, ~95% of users are on a phone): "do a UI audit for noob user experience. Same with the footer. Do a general first user audit; what's easy to understand, what's difficult to navigate to."

Method: static walk of the first-run path in code, web phone shell (`web-next/`, ~390px) and the app (`mobile/`): landing, sign-in, onboarding carousel, connect league, warm-up, Today, footer pill + orb + More, Trades, Waivers, League Rankings, My Team, Fantasy Sim hub, paywall/limit walls, empty states, copy. The Playwright harness in `scripts/sim_layout_playwright/` was NOT run for this audit (no screenshots; tap-target statements come from code and from `running-findings.md`, not a fresh census). Nothing here changes app code. Earlier audits already cover header/footer geometry, module consistency and untappable facts (`2026-11-navigation-audit.md`, `2026-11-header-audit.md`, `running-findings.md`); this one only adds what a person who has never seen the product hits, and does not repeat those.

Standing rules the proposed fixes respect: shared components/tokens only (`docs/ui-patterns.md`), no band-aids (fix the source/registry, not the one screen), gold only for primary/premium, cyan structure, names "J. Surname" never ellipsized, no chevrons on fully tappable rows, Fantasy Sim shows letter grades not numeric OVR.

## 1. What already works for a newcomer (keep)

- Landing leads with one promise and one primary action: "Try a sample league" (no account, no card), and defines "dynasty" in a line (`app/page.tsx`). The sample league is a full, inert copy of the real pages with a persistent banner.
- Onboarding is two steps (experience picker first, value slides second); "Decide later"/"Skip" leave in one tap; the trial offer was moved AFTER the first league's Today (`FirstValueOfferCard`), nothing is blocked.
- Connect is one field ("Sleeper username", example placeholder, "Read-only. We never ask for your Sleeper password"), real warm-up steps ("Reading your roster / Valuing your players / Building trade ideas"), and a structured error per failure with a sample-league escape hatch.
- Free-vs-Pro is honest: Pro markers show on More rows before the tap; limit walls say what the limit is and when it resets.
- Empty states have a next step ("No trade ideas right now. Ideas appear when rosters move. Build your own in Trade Finder."), the Today hero kicker names the week ("THIS WEEK"), and `terms.ts` plus a test already enforce one name per concept for the retired terms.

## 2. Ranked findings

Severity: P0 = a new user can get stuck or leave; P1 = confuses most new users; P2 = polish / edge.

### F1 (P0) Footer: the only way to switch sections is an unlabeled logo orb
- Screen: web phone shell footer (`AppShellBar`, `PillOrb`, `lib/pageFamilyPill.ts`); app orb (`GmOrb`).
- Sees: on Team, Trades and League pages the pill is a logo circle plus that page's tabs (Roster / Players / Waivers / Matchup, or Hub / Finder / Analyzer / History, or Rankings / Recaps / Games). The five global tabs (Today / Team / Trades / League / More) are folded behind the logo. The header does not name the page either (rule 1 of `lib/appHeader.ts`: "the bottom pill already names the page").
- Why it confuses: a logo is not a menu. Nothing says "tap me for Today, More, search". Going from a Trades page to Today has no visible path; the user hunts for a back button or a hamburger. "Brand mark only" was chosen to avoid 9px caps clipping, but the cost is zero affordance. In the app there is no bar at all: a draggable floating "GM" orb ("Open GM menu"; hint "touch and hold, then drag") is the single navigation control, and "GM" does not say menu.
- Fix (principled): keep the single-orb decision, add the affordance in the shared control, not per page: (a) a one-time first-run coachmark anchored on the orb ("Tap for Today, Team, Trades, League, More"), reusing the `fd-help-seen:` seen-once pattern from `BeginnerHelp` and `HighlightTarget`; (b) a persistent "menu" cue in `PillOrb` that fits 48px (brand mark when folded, close glyph when unfolded, or a small grip tick on the rim), added once in the web and app `PillOrb`; (c) app: replace the "GM" caption with the same cue and drop "touch and hold to drag" from the primary hint.
- Parity: shared twin components `PillOrb` (web) / `PillOrb` + `BottomPill` (app). Change together.

### F2 (P0) App sign-in is an account wall with no promise and no way to look around
- Screen: `mobile/src/screens/LoginScreen.tsx`; web default front door (`lib/landingFrontDoor.ts` is "email").
- Sees (app): logo, "FantasyDesk", "Sign in to your account", Apple/Google, email + password. No sentence about what the app does and no "try a sample league", though `SAMPLE_TRY_LABEL` and `SampleLeagueScreen` already exist. Web: the landing hero is good, but "Create account and connect league" goes to an email-then-password form BEFORE the one-field Sleeper connect that the code already has behind `NEXT_PUBLIC_LANDING_FRONT_DOOR=connect`.
- Why it confuses: a store visitor (and an App Store reviewer) must hand over an email and password before seeing any value. Sleeper-username-first is the lower-friction path and is already built (guest-first).
- Fix: app LoginScreen gets the same one-line promise (a shared copy constant in a lib twin) plus the shared sample-league button above the fold; for web, product decides whether to flip the front-door default to "connect" (decision 1 below; the form, tests and guest flow exist).
- Parity: LoginScreen <-> `LandingAuthIsland` / `SignInForm`.

### F3 (P1) Today's first screen stacks three prompts before the briefing
- Screen: `DashboardContent.tsx` order: `StartHereCard` (3-step checklist, "Hide", "See everything FantasyDesk can do"), `SinceLastVisitStrip`, hero, `DirectionCheckinCard` (asks whether the declared direction still fits), `DecisionQueue`, `TodayModule`, then `FirstValueOfferCard` (gold trial offer), then trades, My Team strip, Watchlist & Alerts, League pulse.
- Why it confuses: a brand-new account on a phone sees a checklist, possibly a question about a "direction" it never set, and a Pro pitch around its first real answer. Each is fine alone; together they bury "what should I do today".
- Fix: one shared first-run prompt slot with a priority order (Start here > direction check-in > trial offer) and a hard cap of one non-briefing prompt above the fold; suppress the direction check-in until a stance exists (the server already decides timing in `modules/direction_checkin.py`, so add the "has a stance" input there and both platforms inherit it). Verify on a fresh fixture account; the code order is the evidence, not a screenshot.
- Parity: `StartHereCard`, `FirstValueOfferCard`, `DirectionCheckinCard` all have app twins; the slot rule belongs in the `firstRunFlow` lib twin.

### F4 (P1) Rank jargon on Today and My Team has no always-on explanation
- Screen: Today "My Team" strip ("Power #3 / Franchise #5 / Starters #2 / Bench #7", "Avg Age"); My Team snapshot; League Rankings boards ("Franchise", "Roster Power", "Starter Quality", "Bench Depth"); Draft Center "Roster Power / Franchise".
- Why it confuses: "Power" vs "Franchise" are two different ranks with no visible difference. The explanations exist (`BEGINNER_HELP.powerRank`, `franchiseRank`) but only appear as a "?" for new/beginner/unset users, once, and "Got it" removes them for good. Picking "Veteran dynasty manager" (the third card) removes them entirely, and people pick the third card to look competent. The shared `TapForWhy` registry (`lib/tapForWhyContent.ts`, 14 ids) has no power rank, franchise rank, starter strength, bench strength, posture, buy low or sell high entry, and is wired only on player rows, not on these strips.
- Fix: add those ids to the registry (the copy already lives in `BEGINNER_HELP`) and wrap the strip tiles in `TapForWhy` so the explanation is one tap for everyone; experience level then decides only whether the inline line also shows. Consider plainer labels in `lib/terms.ts` ("This season" / "Long term") (decision 3).
- Parity: registry is a lib twin. The tiles are already insight links (tile tap opens the board), so the "why" needs its own small 44px target; see decision 2.

### F5 (P1) One concept, several names
- Watchlist (Waivers tab), Watching (GM Plan tab) and "GM Targets" (Waivers empty state, route `gm-targets`) are the same list. In Waivers the row labelled "Bench Depth" is `watchlist_candidates`, while "Bench" is also a team rank on Today.
- "Fantasy Sim" (the sandbox game, `/gm-game`) vs "Season Outlook" (real-league forecast, route `/fantasy-sim`, also a Games tab and a GM Plan tab) vs the Games tab "Pick'em". "GM Plan" vs the "GM" orb vs "GM menu" vs "GM Targets". Today vs Home (outside-league tab 1) vs Dashboard (URL/code). "Hub" (Trade Hub's first tab) names nothing.
- Why it confuses: the user cannot tell whether they are looking at one list or three, or whether Fantasy Sim touches their real league (the hub does say "Nothing here touches your real leagues", but inside a collapsed section after the first game).
- Fix: extend `lib/terms.ts` (plus `RETIRED_TERMS`, which a test already enforces) with one name for the watch list, "Home" outside a league renamed to what it is ("Your leagues"), "Season Outlook" always shown with its parent, the Waivers shortlist row renamed to its real meaning, and a clearer first tab than "Hub" (the pill has a `short` label slot).
- Parity: `terms.ts`, `navCatalog.ts`, `pageFamilies.ts` are byte-identical twins, so one edit covers both platforms.

### F6 (P1) Trades: the question a newcomer arrives with is the third tab
- Screen: Trades family (`Hub | Finder | Analyzer | History`).
- Sees: "Hub" first (a board of generated ideas), "Finder" (Pro; the More menu shows the Pro marker, the pill tab does not), then "Analyzer". The most common first question is "someone offered me this trade, is it fair?", which is the Analyzer, and "Analyzer" is not how people ask it.
- Fix: relabel by intent in the shared family/catalog data (for example "Grade a trade" long, "Grade" short), keep routes and ids stable; show the existing `NavProMarker` on the Finder pill tab so gating is visible before the tap, same as More. `BEGINNER_HELP` verdict lines (Accept / Counter / Decline / Fair) already explain well; show the one-line help under a user's first verdict by default.
- Parity: `pageFamilies.ts` twin; the app `BottomPill` tab needs the same marker support as web `BottomTabBar`.

### F7 (P1) Onboarding step 1 asks one thing and offers another, and is heavy at 390px
- Screen: `OnboardingCarousel` step 0 (`EXPERIENCE_LEVEL_OPTIONS`).
- Sees: "How familiar are you with fantasy football?" with answers "New to fantasy football / New to dynasty / Veteran dynasty manager" (two of three answers are about dynasty), then the dynasty note, three tall cards, a goal prompt with 5 pills plus an "optional" note, a disabled Continue with no stated reason, and "Decide later" top right.
- Why it confuses: the first thing a newcomer meets is a quiz, and the disabled primary button looks broken until a card is picked. "Tunes how much explanation shows up" is meta.
- Fix: reword the question to match the answers; move the goal pills out of step 0 (ask later as a dismissible chip on first Today, or in Account) so the step is one decision; show "Pick one to continue" while Continue is disabled (a disabled-reason prop on the shared `Button` serves every form).
- Parity: `OnboardingCarousel` <-> `OnboardingScreen`; copy comes from the shared `experienceCopy.ts` twin.

### F8 (P1) Hidden-until-tapped destinations: GM Plan, Draft Center, Alerts, Commissioner
- Screen: More sheet (`navCatalog.ts` groups) and the footer families.
- Sees: 6 of 14 league pages (GM Plan, Draft Center, Live Draft, League Recaps, Commissioner, Alerts) exist only in More or from the bell; none is in a family strip. The flagship Pro surface (GM Plan) is never offered by the bar. The More list leads with 7 core pages the bar already offers.
- Fix: in the More sheet lead with the pages the bar does NOT show and fold the duplicates into one "Sections" group (derived from `pageFamilies` so it cannot drift); surface GM Plan as a standing step in Today's `NextSteps` or as a Team-family tab (decision 4).
- Parity: `ShellMoreSheet` <-> app `MoreScreen` / orb sheet; both read `navCatalog.ts`.

### F9 (P1) Pro is clear on the paywall, not at the boundary
- Screen: Portfolio is tab 2 of 5 outside a league and is Pro; Draft Center, Live Draft, Commissioner, Finder, Playoff Odds and Season Outlook are Pro too. A free user taps Portfolio and lands on `PremiumUpsellCard`.
- Why it confuses: the bar gives no Pro cue, so a first tap on a primary tab can read as a broken page. The real Free limits live on `/premium`, not where the limit bites.
- Fix: carry the existing `NavProMarker` to bar and pill tabs (a shared `pro` field in `lib/bottomNav.ts`), and let Portfolio's free state show the first league's standing with the Pro part locked instead of a pure upsell; gold stays on the marker and the one primary CTA only.
- Parity: `BottomTabBar` / `BottomPill`, same `bottomNav.ts` twin. (Rendered state not verified, read from code.)

### F10 (P1) Connect: a user who does not know their Sleeper username has no help
- Screen: `SleeperImportForm`. "What is Sleeper? +" is a small secondary link; the expanded text says what Sleeper is and offers sleeper.com sign-up, not how to FIND the username. ESPN / Fleaflicker / MFL sit under "More ways to connect", and "Full tools run on Sleeper leagues today" appears only in step 3 of the landing's "How it works".
- Fix: one line in the expander ("Sleeper app > profile > your username, not your email") from the `connectFlow.ts` twin; when a non-Sleeper platform is chosen, state up front what is limited (reuse `platform_notice`, which Today already shows).
- Parity: `connectFlow.ts` is shared; the app add-league sheet in `HomeScreen` uses the same constants.

### F11 (P2) Fantasy Sim entry copy for a first-timer
- Screen: `SimHub`. "What is this" is open only for the first game (good). The empty state says "Tap New game and pick Quick. It takes about 10 minutes." but "Quick" is a preset the user has not seen. When New game is blocked (free season used) the reason is a small muted caption beside "Go Pro".
- Fix: name the presets in the empty state; make the block reason a full sentence with one gold CTA row. Letter grades only (rule).
- Parity: `SimHub` <-> `GmGameScreen`.

### F12 (P2) Small or oddly styled targets on first-run surfaces
- Known open: inline labelled `BeginnerHelp` rows ("? waiver value", "? playoff odds", "? this matchup page") are about 16px tall (`running-findings.md`, goes away with D3). The `StartHereCard` "See everything FantasyDesk can do" link carries a top border meant as a card divider, so it reads as an underlined inline link inside the card.
- Fix: finish D3; render that footer link as a `StructuredRow` footer.

### F13 (P2) Alerts lights the Today tab
- The bell lives in the header and `alerts` maps to the Today tab (`LEAGUE_SEGMENT_TAB`), so after tapping the bell the bar still says Today. Fix: let `shellActiveTab` light More (or no tab) for `alerts` and confirm the detail header names it.

### F14 (P2) No "what you are looking at" line after warm-up
- After "Building trade ideas" the user lands directly on Today. `StartHereCard` helps only for 14 days and only if not hidden. One first-visit line under the hero through the existing `BeginnerHelp` seen-once pattern would orient without a new module.

### F15 (P2) The experience level cannot be corrected in context
- Choosing "Veteran" hides all explanations; the way back is Account > Explanations. Add a "Show explanations" link in the `TapForWhy` sheet footer and the "Got it" line so recovery is where the confusion is.

## 3. Top-10 fix order

1. F1 Orb affordance + first-run coachmark (web `PillOrb` and app orb together).
2. F2 App LoginScreen: promise line + sample-league button; decide the web front-door default.
3. F3 One first-run prompt slot on Today (cap one; direction check-in only after a stance exists).
4. F5 Vocabulary pass in `terms.ts` / `navCatalog.ts` / `pageFamilies.ts` (watch list, Hub, Home, Season Outlook, Bench Depth row).
5. F4 `TapForWhy` entries for the rank/posture terms and wire the strips.
6. F6 Trades tab labels by intent + Pro marker on the Finder pill tab.
7. F7 Onboarding step 0: question matches answers, goal pills moved out, disabled-Continue hint.
8. F9 Pro marker on bar tabs; Portfolio free state shows value, not only an upsell.
9. F8 More sheet leads with pages the bar does not show; GM Plan surfaced.
10. F10 Sleeper-username help line + non-Sleeper limits stated up front.

Why this order: 1 to 3 are the first 60 seconds (get around, get in, not be buried); 4 and 5 remove the most-seen confusing words; 6 to 10 are second-session discoverability and trust.

## 4. Decisions needed (product)

1. Flip the web front-door default from "email" to "connect" (Sleeper username first, guest-first)? Everything is built; it is one env/default.
2. On Today's rank tiles, does a tap go to the board (current insight link) or explain the number? Proposal: tile goes to the board and a small 44px "why" target inside the tile explains (the no-chevron rule removes the usual cue).
3. Names: "Power / Franchise" to "This season / Long term"? "Hub" to "Ideas"? "Analyzer" to "Grade a trade"?
4. GM Plan: add to the Team family strip (5 tabs, scrolls at 360) or keep it More-only with a Today step?

## 5. Not verified / limits

- No runtime pass: tap targets, wrapping at 320px and the real look of the first-run screens were not measured. Suggested follow-up: run `module_scan.mjs` (controls under 43px) and `pill_geometry.mjs` against the dev build with fixture leagues, and re-capture `docs/audits/first-run-paywall-after-connect/*.png` to check F3.
- Free-user Portfolio and Playoff Odds states (F9) were read from code (`PremiumUpsellCard`), not rendered.
- App screens read: LoginScreen, OnboardingScreen, HomeScreen (connect), MoreScreen, BottomPill, GmOrb. Other app screens are assumed to mirror web per the parity rule.
