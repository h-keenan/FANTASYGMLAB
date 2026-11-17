# Bad-day states and words audit (2026-11-17)

Owner-approved audits 7 (bad-day states, including offline) and 9 (words and labels), web-next and mobile.
Screenshots (real production build, 390px, mocked API): `docs/audits/2026-11-bad-day-and-words/`.
Mobile cannot be rendered here: it was verified with `tsc`, the node test suite and `expo lint` only.

## A) Bad-day states

### Findings (before)

| # | Finding | Surface |
|---|---|---|
| A1 | A 5xx showed the raw client fallback, "Request failed with status 502." (web) / "Request failed (502)." (app), under the shared ErrorState. | web + app, every screen |
| A2 | No offline indicator at all. A dead network only surfaced as a per-screen error after the 30s request timeout. | web + app |
| A3 | A page skeleton could sit for up to 30s (the request timeout) with no words and no retry. Pages draw `SkeletonRegion` directly as well as `SkeletonPage`, so a fix at page level alone would have missed most of them. | web + app |
| A4 | An API 401 ("Not signed in.") rendered as a generic error with "Try again", which cannot fix it. No path to sign in again. | web + app |
| A5 | A deleted or archived league ("League not found.") rendered the same generic error, with no way to pick another league. | web + app |
| A6 | Offline copy used an em-dash ("Couldn't connect, check ...") and two different sentences existed for the same state ("Could not reach the server..." web, "Couldn't connect..." app). | web + app |
| A7 | Last-good data: the backend serves last-known Sleeper/FantasyCalc data (#2054) but sends no per-response "as of" field, so no client can say "data as of X" from the server. The app has a persisted React Query cache (24h) and paints from it, but never said how old it was. Web has no client cache at all. | web + app |
| A8 | Direct deep link `/dashboard/<leagueId>` at phone width logs a React hydration error (#418) on `main` too. Not introduced here, not fixed here (see "Remains"). | web |

### Fixed

- **Shared copy + classifier**, byte-identical lib twin `lib/badDayCopy.ts` (web and app, registered in `check_lib_twins.mjs` IDENTICAL):
  `friendlyStatusMessage` (5xx/429/503 become a sentence, a server-written detail is kept, 4xx keep the old fallback so Sim call sites
  that detect it still work), `classifyErrorMessage` (session / league gone / offline / server), `asOfLabel` / `staleNote`, the offline,
  slow-load, session-ended and league-gone strings, and the 8s / 15s thresholds. No em-dashes.
- **API clients** (`web-next/src/lib/api.ts`, `mobile/src/lib/api.ts`) build messages through `friendlyStatusMessage`; web uses the shared
  offline sentence.
- **One offline banner per platform.** Web: `OfflineBanner` (navigator.onLine via `useSyncExternalStore`, root layout, sticky and opaque so
  it never covers the header, "Back online" for 3s). App: `OfflineBanner` (root, `App.tsx`) driven by `lib/connectivity.ts`.
  `@react-native-community/netinfo` is NOT installed (adding a native module needs a new build), so the app infers connectivity from
  the requests it already makes: a transport failure with no response raises the banner, any HTTP response (even a 5xx) clears it, a
  timeout alone is "slow", not "offline", and while offline the banner polls `GET /health` to clear itself. When NetInfo is added, call
  `setOffline(!state.isConnected)` from its listener and keep the rest.
- **No frozen skeletons.** `SlowLoadNote` lives inside `SkeletonRegion` (so every page and region skeleton, web and app): after 8s
  "Still loading. This is taking longer than usual.", after 15s a "Try again" (web reloads; app takes an optional `onRetry` on
  `LoadingScreen`/`SkeletonPage`/`SkeletonRegion`). The request still gives up at 30s and the screen then shows the shared ErrorState
  with its retry. Skeleton shimmer is unchanged (motion drop 1).
- **Expired auth gets a clean re-login.** Shared ErrorState (web + app) shows "Your session ended" with "Sign in again" (signs out and goes
  to the landing/sign-in, never a blank page).
- **Deleted/archived league.** "This league is not available. It may have been deleted or archived on Sleeper." with "Choose another
  league" (web `/leagues`, app Home).
- **"As of" note.** App: `StaleNote` under Today, from the React Query `dataUpdatedAt`; quiet when fresh and online, "As of 3:42 PM" when
  offline, when the last refresh failed, or when the data is over 10 minutes old.
- **Guards/tests extended.** `errorStateGuard` (web vitest, app node:test) now also fails when the root has no `OfflineBanner`, a skeleton
  has no slow-load note, the shared ErrorState loses the session/league branches, or the API client stops using
  `friendlyStatusMessage`. New unit tests: `badDayStates.test.tsx` (banner, slow note, session, league gone, 5xx), `badDayCopy.test.ts` +
  `connectivity` (app). **new-user-smoke scenario 7** (390px, production build, all API mocked): 5xx then Try again recovers, expired
  session, deleted league, slow API (the 8s note shows, then content lands), partial data (no items, no `this_week`), offline banner with
  content kept and "Back online". 23/23 checks pass locally.

### Surface matrix (Desk and Sim)

| Bad day | Desk (web) | Desk (app) | Sim (web/app) |
|---|---|---|---|
| Slow >5s | skeleton, note at 8s, retry at 15s | same | same (`SkeletonRegion`) |
| 5xx | ErrorState, "Our servers hit a snag..." + Try again | same | Sim `SIM_LOAD_ERROR` titles + the same body (Sim call sites keep their own sentence for 4xx) |
| Partial data | renders (scenario 7e) | renders from cache | not scenario-tested |
| Sleeper down | backend last-known; **no "as of"** | StaleNote from cache age | same as Desk |
| Offline | banner; content on screen stays | banner; cached content paints; StaleNote | same |
| Auth expired | "Your session ended" + Sign in again | same | same |
| League deleted | "This league is not available" | same | n/a (Sim leagues are ours) |

### Remains (A)

1. **Web has no last-good cache**, so it cannot show "as of" after a refresh fails; it shows the error instead of stale content. Needs
   a small client read cache (or React Query) plus a backend `as_of` field on responses served from last-known (backend contract change, out
   of scope for a copy/UI pass).
2. **App StaleNote is on Today only.** Other `useQuery` screens (Matchup, My Team, Teams, Commissioner) should add the same one-line
   component; it is a one-line change each.
3. **App connectivity is request-inferred**, not NetInfo. A device with no traffic never learns it is offline until the next request.
4. Hydration error #418 on direct `/dashboard/<id>` at phone width (finding A8). Needs its own investigation.
5. Playwright screenshots of "stale" on web are not possible until (1) lands.
6. Partial-data and 5xx are only smoke-tested on Today; the other Desk and Sim pages rely on the shared ErrorState and skeleton.

## B) Words and labels

### Findings (before)

| # | Finding |
|---|---|
| B1 | **Em-dashes** in UI copy: 95 sentences across 50 files, web and app (the casing PR set the rule, nothing enforced it). |
| B2 | **One concept, four names:** "Posture" (Trade Hub, Draft Center, manager profile), "GM stance" (Today, GM Plan), "Team stance" (GM Plan tabs), "Team Situation" (page). Users cannot tell they are one setting. |
| B3 | "Watching list" survived the Watchlist rename in one explainer. |
| B4 | Jargon with no explanation in one place: "Dynasty lens" (header chip) vs "Evaluation lens" (sheet), "Value", "Market ADP", "Est. SF", "FAAB". Definitions existed in four different registries (`BEGINNER_HELP`, `tapForWhyContent`, inline notes, backend `est_sf_note`). |
| B5 | Same message, different words per client: "Could not reach the server..." vs "Couldn't connect..."; ErrorState "Couldn't load this" vs Sim "Could not load ..." (left as is: the Sim twin is a named, guarded copy). |
| B6 | Leftover dev-ish copy: "Durable: Supabase" / "Host-local only" on Founder Analytics (admin only, left), "This page is still being tested end-to-end against a real live draft" on Live Draft (a real beta notice, left, flagged below). No "TODO"/"lorem"/"TBD" in visible strings. |
| B7 | "Power" / "Power Rank" is the retired name for "This season", already blocked by `terms.ts`; no new hits. |

### Fixed

- **Em-dashes**: every spaced em-dash in a user-visible string on web and app rewritten (period, or colon for label-style lines). New guard
  `web-next/src/lib/copyDashes.test.ts` fails on a new one (scans both trees, same scan as `terms.test.ts`). The lone "—" empty-value glyph
  and "en dash" number ranges are deliberately out of scope. Code that splits backend text on " — " (`ContentSections`, matchup context) is
  unchanged.
- **Team stance** is now the one user-facing name (`TERMS.teamStance`, retired: "Posture", "draft posture", "GM stance", "Watching list" in
  `RETIRED_TERMS`, enforced by `terms.test.ts` on both clients). Rewritten: Trade Hub explainer and "What team stance means" sheet, Hold card
  factor, manager profile signal, Draft Center ("Your draft stance"), nav catalog, feature catalog, paid previews.
- **One glossary.** `lib/glossary.ts` (lib twin, feeds every `InfoMark glossary=[...]`) gained: Team stance, Evaluation lens, Value, Market
  ADP, Est. SF (reuses `EST_SF_NOTE`), FAAB. Definitions reuse `BEGINNER_HELP` text where it exists, so the beginner caption and the "?"
  sheet cannot disagree. Plain-English definitions:
  - **Team stance**: how you are building the team: competing now, building for later, or in between.
  - **Evaluation lens** (header chip "Dynasty lens"): Dynasty weighs future upside with this year, Rebuild weights youth and picks most,
    Redraft counts this season only.
  - **Value**: a player's worth under this league's settings and your lens, one scale across the app, higher is better.
  - **Market ADP**: where players are actually picked in public drafts; "our rank" is where we value the same player.
  - **Est. SF**: an estimate of superflex ADP (1QB ADP re-ordered with our superflex values); no approved source publishes real superflex ADP.
  - **This season** (formerly Power / Roster Power) and **Long term** (formerly Franchise): unchanged, already in the glossary.
- Shared error copy now lives in `badDayCopy.ts` (A6).

### Remains (B)

1. Multi-line JSX paragraphs and backend-generated strings (Python modules, `detail`/`headline` fields) can still contain em-dashes; the guard
   only sees one-line strings. Backend copy is out of scope.
2. "Evaluation lens" (sheet) vs "Dynasty lens" (header chip) is intentional (the chip names the active lens) but the "?" explainer is not
   yet attached to the chip. `InfoMark glossary=["evaluationLens"]` next to the control would finish it.
3. "Value", "Market ADP" and "Est. SF" are defined but only Est. SF has a "?" at the point of use today; adding `glossary` marks to the
   Player Quick View ADP section (app: `PlayerQuickViewSheet` "Market ADP") is a follow-up.
4. Wording difference between ErrorState ("Couldn't load this") and Sim ("Could not load ...") is left on purpose.
5. Live Draft beta notice copy is accurate; revisit when the page is no longer a preview.
