# New-user intake audit (October 2026)

Question from coridian_: what do we need to add to ease the intake of new
users, and is anything overwhelming or underwhelming?

Builds on [new-user-guidance-audit-2026-10.md](new-user-guidance-audit-2026-10.md)
(PR #1445, copy fixes in #1449), which covered beginner copy and "what do I do
this week". This one covers the **first-run funnel itself**: landing to first
value to paywall to return visit. It does not repeat those findings. Note that
audit's "This week" strip recommendation has since shipped (`ThisWeekStrip`).

## Method and limits

- Code-read of the whole path: `app/page.tsx`, `LandingAuthIsland`, `SignInForm`,
  `OnboardingCarousel`, `OnboardingPaywall`, `SleeperImportForm`,
  `app/dashboard/[leagueId]`, `DashboardContent`; mobile `OnboardingContext`,
  `OnboardingScreen`, `HomeScreen`, `DashboardScreen`, `pushNotifications`,
  `AuthContext`. Also `paywall-audit-2026-10.md` for free-tier limits.
- **Not driven in a browser.** No Playwright run at 390px was done for this
  pass, so nothing below claims a measured pixel height or timing. Statements
  about order and counts are from code. Verify with a 390px walk before
  committing to the larger items.
- No real data, secrets or `players.db` were touched.

## The journey as built

| Step | Web | Mobile |
|---|---|---|
| 1 Landing | H1 + screenshots + "Start free for 3 days" + 3 benefits + platform note | n/a (app opens on sign-in) |
| 2 Sign-in | Email / Google / Apple. No visible guest path (guest exists only as a silent fallback in the import form) | Login screen; guest exists |
| 3 Carousel | 8 feature slides, then "Connect Sleeper or ESPN", then experience-level question = 10 steps | Intro carousel, skippable |
| 4 Trial offer | `OnboardingPaywall` shown **before** a league is connected; skip is a small text link | Paywall screen |
| 5 Connect | Platform pills (Sleeper / ESPN / Fleaflicker / MFL), Sleeper username | Add League sheet, "no league?" explainer |
| 6 Warmup | `LeagueWarmupProgress` | same |
| 7 First Dashboard | ~9 modules (below) | similar |
| 8 Return | Auto-redirect to the single league's Dashboard, or Portfolio for 2+ | same, plus last-league sync |

## Findings

Severity: H = users likely drop or stall, M = confusing, L = polish.

### Overwhelming

1. **H. Ten steps before the first league is connected (web).** Eight feature
   slides teach modules the user cannot use yet, then a question, then a
   trial offer, then the one thing that unlocks everything (connect a league).
   The earlier audit flagged "8 feature screens before the one action"; it is
   still true. The feature slides duplicate the landing page showcase.
2. **M. First Dashboard stacks about nine modules** in this order: Guillotine
   (if applicable), 4-tile rank strip, This week, Today, Watchlist, League
   Activity, two Guess-the-Player games, Team Snapshot, league-type control.
   The two games sit above Team Snapshot, so a new user meets minigames before
   their own roster summary. For a first run the useful path is This week and
   Today; everything else is secondary.
3. **M. Jargon in tile labels with no first-run fallback.** Power Rank,
   Franchise Rank, Starter/Bench Strength are only explained for users who
   answered "New to dynasty" at the very end of onboarding. Anyone who
   skipped, signed in on another device before the preference synced, or
   picked "I know my stuff" while new to a module gets none of it.
4. **L. Platform choice up front.** Four pills before the user has typed
   anything. Sleeper is default, which is right, but ESPN/Fleaflicker/MFL are
   "public leagues, subset of features" and that caveat is only on the landing
   page, not at the pill.

### Underwhelming

5. **H. The trial offer comes before any value (web).** The paywall appears
   after the carousel and before connecting a league. The user is asked to
   start a trial having seen only screenshots. Skip is `text-xs` underlined.
   Better order: connect league, see the first Dashboard, then offer the trial
   at the first gated moment (the 3rd trade idea, GM Plan, a second league).
   Mobile should be checked for the same order.
6. **H. Users without a league hit a wall.** There is no sample or demo league.
   "Create a free one at sleeper.com" (web) and the mobile "no league" explainer
   are honest but end the session. Mobile's `ShowcaseModeContext` is a
   founder-only masking switch, not a demo. This is the largest unaddressed
   intake gap and the biggest effort (needs a read-only sample league payload).
7. **M. Free tier limits surface late and at the bottom.** GM Plan is a lock
   card, Trade Hub shows 2 ideas with the upsell after the list, Trade Analyzer
   caps at 3 per week, and the free account is capped at 1 league. None are
   mentioned before the user hits them.
8. **M. Trial copy can drift.** Landing hardcodes "Start free for 3 days";
   the paywall reads the trial length from the billing API. The prior audit
   still quotes "7-day" for the CTA. If the trial length changes, the landing
   promise is wrong.
9. **M. Notification permission is requested at sign-in on mobile.**
   `AuthContext` calls `syncPushToken()` on every session, which calls
   `requestPermissionsAsync()`. The OS prompt therefore appears before the
   user has seen any alert-worthy value, and a "Don't allow" is near-permanent
   on iOS. Move the ask to a value moment (after the first league loads, with
   one line of why).

### Missing

10. **First-win guidance.** Nothing says "do these three things first" once the
    Dashboard loads. (Small version shipped in this PR, see below.)
11. **Support and feedback entry.** The only contact path is
    `support@fantasydesk.app` inside the legal text. No in-app "Send feedback"
    or "Something wrong with my league?" link on the connect screen, the empty
    states, or Account/More.
12. **Privacy explainer at connect.** The import form says what it reads
    (Sleeper roster) but not what it does not do (no password, no lineup
    changes). The Matchup page already says "we can't change your Sleeper
    lineup"; say it once at connect.
13. **Glossary or tooltips.** `InfoTip` exists on web but is not used for the
    rank and strength tiles. One shared "What do these mean?" sheet would cover
    jargon for everyone, not only the beginner flag.
14. **Progressive disclosure.** All advanced modules (Manager Tendencies,
    Playoff Odds, Live Draft, College Scouting) are visible in nav from day
    one. No "unlocks later" grouping.
15. **Saved progress.** Onboarding state is session-only on web
    (`carouselDone`, `paywallDismissed` are React state). A refresh mid-flow
    replays the carousel. Mobile persists its flag locally.

## Ranked recommendations (impact vs effort)

| # | Change | Impact | Effort | Notes |
|---|---|---|---|---|
| A | Shorten web carousel to 3 steps: value line, connect league, experience level. Feature screenshots stay on the landing page | High | Low-Med | Keep step analytics keys; mobile carousel to be reviewed in the same pass |
| B | Move the trial offer to after the first Dashboard or the first gated moment | High | Med | Needs funnel-metric agreement with coridian_ first (trial starts may drop short-term) |
| C | Defer mobile notification permission to a value moment | High | Low | Remove `syncPushToken()` from auth listeners; call it from a one-time prompt card after first league loads. Existing granted users keep working (re-register on launch only if already granted) |
| D | Sample league for users without one (read-only, clearly labelled) | High | High | Needs fixture payloads served by the API; never real users' data |
| E | First Dashboard order for new accounts: This week, Today, Snapshot first; games and League Activity below | Med | Low | Same ordering on mobile |
| F | Show free limits before they bite ("2 trade ideas free today") | Med | Low | Server already returns counts |
| G | Landing trial line reads from the billing API | Med | Low | Removes drift (finding 8) |
| H | Single "What do these mean?" glossary sheet linked from the rank tiles | Med | Med | Shared copy map web + mobile |
| I | In-app Send feedback entry (Account/More + connect screen) | Med | Low | Mail link is enough to start |
| J | Privacy line at connect | Low-Med | Low | Mock below |
| K | Persist onboarding progress on web | Low | Low | Per-user localStorage like Start here |

## Mock copy (minimal, no fabricated data)

- Connect, under the username field: "We read your roster and league settings
  from Sleeper. No password needed, and we never change your lineup."
- No-league state: "No league yet? Sleeper is free, and leagues take a few
  minutes to set up. Come back once you have one." (Becomes "Try a sample
  league" if D ships.)
- Notification ask (after first league loads): "Get a heads-up when a player
  on your roster is hurt or a trade idea changes. You can turn this off in
  Settings." Buttons: "Turn on" / "Not now".
- Free limit line on Trade Hub: "Free shows your top 2 ideas each day. Each is
  weighed against your roster need, who else wants the player, and your
  rebuild or contend posture."

## Shipped in this PR (small, safe, web and mobile together)

**"Start here" first-run checklist on the Dashboard.**

- Three rows, each opens an existing destination and is ticked when opened:
  Check your lineup (Matchup), See your best trade idea (Trade Hub, "or a clear
  hold when trading is not the move"), Review waiver targets (Waivers).
- Shown only to accounts created within 14 days, until the user taps Hide or
  opens all three. Existing users never see it.
- Reuses `AccentCard`, `SectionHeading`, and the `thisWeekHref` /
  `thisWeekTarget` route helpers. No new endpoints, no schema change.
- State is per device and per user (`localStorage` on web with try/catch,
  `AsyncStorage` on mobile), key `fd:start-here:v1:{userId}`. It does not sync
  across devices; that is acceptable for a first-run hint.
- Shared logic and copy live in `lib/startHere.ts`, byte-identical on both
  platforms; the mobile test fails if the two copies drift.
- Files: `web-next/src/lib/startHere.ts`, `web-next/src/components/StartHereCard.tsx`,
  `mobile/src/lib/startHere.ts`, `mobile/src/components/StartHereCard.tsx`,
  wired into `DashboardContent` and `DashboardScreen`.

Not done here: anything touching the order of onboarding, the trial offer,
push permission timing, or the Dashboard module order (A, B, C, E). Each
changes funnel metrics or app-store behavior and needs a product call.

## Verification

- Web `tsc`: only the existing `satori/standalone` import errors (stale local
  `node_modules`, unrelated to this change). Web vitest: 831 passed, 2 failed
  in `shareCard/clientRender` for the same missing package.
- Mobile `tsc` clean; `npm test` 299 pass, 0 fail.
- The card was not visually checked at 390px or on a device.
