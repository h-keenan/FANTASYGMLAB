# New-user guidance audit (October 2026)

Question: does a first-time user, or someone new to fantasy football and
dynasty, get told clearly **what moves to make**? Primary surface is web-next
at 390px (the owner uses the site on a phone). Mobile was read in code only.

## Method and evidence

- Read: `docs/first-use-onboarding-specification.md`, `experienceCopy.ts`,
  `BeginnerHelp`, `OnboardingCarousel`, `DashboardContent`, `GamePlanCard`,
  `WaiversContent`, `TradeHubContent`, `MatchupContent`, `matchupPresentation`,
  `notReadyMessages`, mobile `DashboardScreen`.
- Walked in headless Chromium at 390x844 (2x) against a mock API and a sample
  league. The harness is outside the repo.
  Screenshot dir: `/private/tmp/claude-501/-Users-turbo-dev-FANTASYGMLAB/deb66d78-91dd-4a35-a695-410d86619e13/scratchpad/newuser/`
  (the files below are in it).
- Limits: sign-up/Sleeper import were read in code, not driven (no real
  Supabase/Sleeper). My Team and Trade Analyzer hit the generic error boundary
  in the harness because the mock roster payload is empty. That is a harness
  gap, not a verified product bug, so those two pages are code-read only.
  Experience level was forced with the `/v1/preferences` mock.

Severity: H = a beginner can stall or mis-act, M = confusing, L = polish.

## Quick wins shipped in this PR (copy only, web + mobile)

| # | Finding | Fix |
|---|---|---|
| 1 | H. Beginner Dashboard: the explanations were rendered inside the four 390px columns, making the stat strip about 450px tall. "Today" (the one clear next action) started roughly 700px down. Before: `dash_beg_before.png` | Web now renders the explanations as short `Term: help` lines under the strip, as mobile already did. Today now starts about 400px higher. After: `dash_beg.png`. Added the missing Average Age line, and the Team Snapshot lines |
| 2 | M. Beginner help said "Game Plan lists..." under a heading titled "Today" | Reworded to "Today lists the roster moves..." (web and mobile maps stay byte-identical) |
| 3 | H. Dashboard dead end: "No urgent roster issues right now." gave a beginner no instruction, so they don't know whether to do nothing or look elsewhere. See `dash_quiet.png` | Beginner-only line: "No move is needed right now. Before game day, check Matchup to confirm your lineup is set in your league app." (web EmptyState and mobile empty card) |
| 4 | M. Web Waivers showed bids like `$12-$18 of $100 remaining` and a bare "FAAB" tile with no explanation. `BEGINNER_HELP.faab` existed but only mobile rendered it. See `waivers_beg.png` | Web Waivers now shows the FAAB explanation for beginners when the league uses FAAB |

Tests: new `DashboardContent.beginner.test.tsx`; updated
`ExperienceLevelContext.test.tsx`. Web vitest `src/components`, `src/context`
and `experienceCopy` pass (530 tests), as does the mobile experienceCopy test.

## Per-flow findings (not fixed here)

### 1. Landing, sign-up, onboarding (`landing.png`, `connect.png`)

- M. The landing page says "Your fantasy front office... Trade Hub, Waivers,
  and Next Move" but never says what a beginner does first or that the app
  reads a Sleeper league they already have. The Sleeper requirement is the
  small print line.
- M. Onboarding's level question is "How much dynasty experience do you
  have?" A newcomer to fantasy football in general is not told it covers them,
  and the pick "New to dynasty" does not say "or new to fantasy". Suggested
  copy: "New to dynasty (or fantasy)".
- M. The last step's CTA is "Start my 7-day free trial", sitting directly under
  a preference question. A beginner may think the choice is a purchase step.
- M. `/connect-league` and the import form assume the user has a Sleeper
  league. The only help is "Create a free one at sleeper.com". There is no
  answer for ESPN-only or Yahoo users beyond the ESPN tab.
- L. Onboarding teaches 8 feature screens before the one action ("connect a
  league") that the user needs.

### 2. First Dashboard / Game Plan (`dash_beg.png`, `dash_adv.png`)

- Good: one Top Priority card with a plain "why" and a CTA ("Review in Trade
  Hub").
- M. The CTA labels are destination names ("Review in Trade Hub", "Open
  Waivers"), not the move. For a beginner "Upgrade your RB2" followed by "Review
  in Trade Hub" skips the question "what do I actually do?".
- M. Nothing on the Dashboard mentions the weekly basics (set lineup, check
  waivers before the deadline). They only appear on Matchup. The Dashboard
  should be the place that says "this week: lineup, waivers, hold".
- M. Dashboard leads with four rank tiles, then Today. For beginners the
  action should come first and the ranks second (not done here: layout).
- L. "Dynasty" pill and league pill sit in the header with no explanation.

### 3. Game Plan (GM Plan) (`gmplan.png`)

- H (free tier). The page opens with the stance picker (REBUILDING / COMPETING /
  BALANCED) and then the main content is a lock card, "GM Plan is a Premium
  feature". A beginner on the free plan lands on a page that offers no
  next step but "Upgrade". The picker is also the only place the app asks
  for posture, with no plain-English definition of "rebuilding" vs "competing"
  at the choice.
- L. Subtitle "Roadmap, stance, and watched players" is jargon for a newcomer.

### 4. Waivers (`waivers_beg.png`)

- Good: one "Top Waiver Target", a need line, and an explicit
  "Place claims in Sleeper, we don't submit them".
- M. (Fixed, see #4.) Before the fix the bid range was unexplained.
- M. The orphan line "The average value of every free agent currently
  available" appears with no label above it.
- M. Nothing says when a claim must be made (waiver run time) or whether to
  spend FAAB on this player versus saving it. A beginner gets a bid range but
  no "is this worth it?" read tied to roster need and competition.
- L. "Stash", "Watch", "Add" chips are undefined.

### 5. Trade Hub (`tradehub_beg.png`, `tradehub_empty.png`)

- Good: beginner intro explains You send / You get. Empty state offers Trade
  Finder.
- M. "Values here reflect a Fringe Contender strategy... What does this mean?"
  is strong jargon sitting above the first idea.
- M. Cards show "Value 3,100", "Balance +800" and "High Impact" with only a
  confidence tag as the why. There is no explicit "hold" option or
  "do nothing is also fine" guidance, so a beginner reads every idea as a
  suggestion to trade.
- L. Free-tier limit copy ("N more trade ideas available on Premium") appears
  at the bottom of the list, not before.

### 6. Matchup (`matchup_beg.png`, `matchup_off.png`)

- Good: the best page for "what to do this week". It has win probability,
  Suggested Moves ("Start Garrett Wilson over Ladd McConkey, +3.3 pts") and
  the line "FantasyDesk can't change your Sleeper lineup, so make any swap in
  Sleeper".
- M. No beginner help on the page at all (no `BeginnerHelp` usage). "Proj
  margin", "Value margin" and "Position edges" are unexplained.
- H (dead end). Not-ready states give no next step: "This league hasn't started
  a week yet." (offseason / pre-draft), "Couldn't build this week's matchup...",
  and "Link your Sleeper account and join this league from Home" (there is no
  "Home" nav item). These strings are intentionally byte-identical between web
  and mobile, so they are listed here, not changed.

### 7. My Team and Playoff Odds (`playoff_beg.png`; My Team code-read)

- M. Neither page uses `BeginnerHelp`. Playoff Odds explains the method
  ("Monte Carlo simulation...") rather than the use: it never says what to do
  with a 41% (check your trade/waiver posture, or the standings math).
- M. Standings list "Win%", "PF", "PA" without expansion.
- L. My Team: empty-slot copy "Nobody here yet." has no action.

### 8. Empty and gated states

- No league: handled (connect form). Empty roster/pre-draft on Dashboard:
  "Your roster doesn't have any players yet. This is expected if your draft is
  still in progress." is good but has no action (point to Draft Center).
- Offseason: Dashboard shows the generic quiet line; Matchup shows "hasn't
  started a week yet". Neither says what is useful to do now (rookie draft prep,
  trades). Offseason is the longest period a dynasty beginner will use the app.
- Free-tier limits: "N more moves available on Premium" appears, and is
  clear. It does not say what the free user should do meanwhile.

## Jargon without a plain explanation (beginner mode still unexplained)

FAAB (fixed on web Waivers only), PQV / Player Quick View, tiers on cards,
"Value" numbers without scale, Fringe Contender / Rebuilding / Retool,
Juggernaut / archetype badges, Roster Power vs Franchise vs Starter-Weighted
Score on League Rankings, "Stash", "Taxi", "Partner Acceptance", Proj margin,
Value margin, Position edges.

## Does the app tell a beginner what to do this week?

Partly. Matchup answers lineup; Waivers answers claims; Dashboard names one
priority. Missing: a single "this week" checklist that combines lineup, waivers
and hold-vs-trade, weighed by context (week, bye/injuries), competition (who
else needs the same player, standings) and posture (contender vs rebuilder).
Each page gives one signal in isolation; the beginner is left to merge them.
Trade ideas also never say "hold" explicitly.

## Recommended product changes

1. **"This week" strip on Dashboard.** Three rows: Lineup (from Matchup
   suggested moves, or "set"), Waivers (top add and whether to bid), Trades
   (best idea or "hold"). Each row states the why in one line using need,
   competition and posture. Replaces the idea of "Today" as a destination
   link.
2. **Action-phrased CTAs.** Change "Review in Trade Hub" to the move itself
   ("See the RB trade that fixes this"), keyed on category.
3. **Explicit "hold" verdict** in Trade Hub and the Analyzer, with the why, so
   not-trading is a first-class answer for beginners.
4. **Season-phase aware empty states** (offseason, pre-draft, bye): one next
   action each (Draft Center, rookie ranks, trade targets), shared across web
   and mobile, replacing the generic "nothing urgent".
5. **Free-tier GM Plan preview** and a plain definition of the stance choices
   at the picker, so the first Premium touchpoint teaches before it sells.

## Parity notes

Web and mobile `BEGINNER_HELP` maps were edited together; the sync test passes.
Mobile Dashboard already used under-strip help lines, so the web change brings
web in line. Mobile Waivers already rendered the FAAB help on its card.
