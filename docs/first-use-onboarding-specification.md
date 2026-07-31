# First-Use Journey Validation and Onboarding Specification

## Scope and evidence

This specification evaluates the application at
`1e0ec378bfcdf0c4ba47fd995e1e214b8db0e4bc`. It is documentation only. It does
not change onboarding, startup, navigation, authentication, Premium, Trust, Trade
Hub, caching, or any UI component.

Evidence was drawn from:

- the production launch, account/guest, league-selection, route, Dashboard, Trade
  Hub, and Premium render paths;
- current navigation, onboarding, startup, entitlement, session-isolation, and UI
  regression tests;
- the merged comprehensive UX audit and controlled startup/navigation
  investigations;
- source-level walkthroughs of five defined personas.

No customer account, customer league, or organic session was used. A controlled
credentialed browser study was unavailable. Consequently, hesitation points below
are evidence-backed product hypotheses, not observed usability-study quotations.
The final section lists the browser study needed before implementation.

## 1. Executive summary

The pre-import flow is already understandable. It states the product category,
offers account or guest access, requests a league, and sends the user to Dashboard.
The primary context loss occurs immediately after successful league selection.
Dashboard supplies several useful outputs—team identity, strategy, ranks, needs,
trades, waivers, health, and Premium depth—but does not teach their relationship or
name one repeatable workflow.

The smallest intervention is a **dismissible post-import orientation card** mounted
on Dashboard after the application reaches `PAGE_READY`. It should explain a
three-step operating model:

1. read the Dashboard summary and choose one priority;
2. open the matching workspace to inspect evidence and alternatives;
3. treat recommendations as decision support, with Trust filtering evidence quality
   rather than guaranteeing outcomes.

The card should have one primary action, one secondary dismissal, no modal, no tour,
and no navigation lock. It should appear once per newly encountered league context,
not once per browser process or on every login. Dismissal should persist locally for
guests and with the existing account preference mechanism for authenticated users
only if that mechanism can be used without an authentication or schema change.

## 2. Current journey contract

### Before a league is selected

The launch screen shows:

- the DynastyGM name and an advanced dynasty-analysis value statement;
- a three-step account/guest → league import → Dashboard sequence;
- account creation/sign-in or fully usable guest mode;
- Sleeper as the recommended full-support import;
- ESPN as an explicitly limited experimental path;
- league cards and a shortcut to the last league when available.

The expected user decision is clear: choose identity mode, then choose a league.
The account copy also correctly explains that an account saves league context rather
than implying it is required for analysis.

### After a league is selected

Startup restoration completes behind a stable shell. The app restores route,
profile, entitlement, league, and strategy context, then mounts Dashboard. The
shell identifies league, team, platform, account, and plan. Dashboard immediately
presents operational intelligence and navigation.

The missing bridge is conceptual. The user must infer:

- Dashboard is a triage surface rather than the place to complete every task;
- My Team is roster diagnosis and roster operations;
- Trade Hub is idea discovery while Trade Analyzer tests a known package;
- Waivers is the action surface for adds and FAAB;
- League Overview explains comparative position;
- Trust filters unverifiable recommendations but does not predict outcomes;
- Premium expands depth rather than changing the basic workflow.

## 3. Persona validation

### Persona 1: brand-new dynasty player

**Expectation:** The product should tell them whether their roster is good and what
to do next without requiring dynasty vocabulary.

**Likely confidence:** High during import; low-to-medium on first Dashboard.

| Question | Discoverable without documentation? | Evidence and friction |
|---|---|---|
| What does the app do? | Yes | Launch value statement names analysis, trades, roster management, and league intelligence. “League leverage” and “dynasty value” may still be unfamiliar. |
| What page comes first? | Yes initially | Launch explicitly says Dashboard. After arrival, several page actions compete. |
| How do I evaluate my roster? | Partly | Dashboard and My Team expose ranks, needs, and strategy, but the novice does not know which indicators are foundational. |
| How do I use Trade Hub? | Partly | Purpose copy says discovery; board sections, fairness, confidence, and Trust require interpretation. |
| What does Trust mean? | No | Trust-aware output exists, but the governing concept is not introduced in the first journey. |
| Why believe recommendations? | Partly | Reasons and confidence are visible, but data provenance, Trust, model limits, and user judgment are not summarized together. |
| What does Premium unlock? | Yes mechanically | Gated cards and Premium page list features; outcome value is less obvious. |
| Where next? | Partly | “Next Moves” exists, but it does not teach the page workflow. |

**Cognitive load:** strategy labels, power versus franchise rank, value lenses,
league-relative weakness versus need, confidence, Trust, and Premium all arrive
within one session.

**Unnecessary clicks:** exploratory switching among Dashboard, My Team, and League
Overview to learn which page answers “is my team good?”

### Persona 2: experienced dynasty manager

**Expectation:** Fast league import, credible inputs, transparent values, and direct
access to trades, roster shape, rankings, and settings.

**Likely confidence:** High after league identity is confirmed.

| Question | Discoverable? | Evidence and friction |
|---|---|---|
| What does the app do? | Yes | Domain vocabulary is familiar. |
| What page comes first? | Yes | Dashboard is a reasonable executive summary. |
| How do I evaluate my roster? | Yes, after scanning | Power, franchise value, roster rooms, strategy, and league context are available. |
| How do I use Trade Hub? | Mostly | Discovery versus Analyzer is explicitly explained; primary/secondary sections add scanning cost. |
| What does Trust mean? | Partly | Experienced users can infer evidence filtering, but need exact limits and reasons. |
| Why believe recommendations? | Partly | Values, fit, fairness, confidence, and reasons are exposed; methodology is distributed. |
| What does Premium unlock? | Yes | Feature inventory is explicit. |
| Where next? | Yes | Domain expertise compensates for weak product orientation. |

**Cognitive load:** duplicated setup controls, numerous experimental destinations,
and distributed methodology rather than football concepts.

**Unnecessary clicks:** settings/import/refresh/account actions are fragmented; the
user may open several surfaces to locate a specific control.

### Persona 3: returning user

**Expectation:** Restore their last league and page quickly, preserve settings, and
avoid onboarding repetition.

**Likely confidence:** High if identity header matches expected league.

| Question | Discoverable? | Evidence and friction |
|---|---|---|
| What does the app do? | Already known | Re-teaching would be noise. |
| What page comes first? | Yes | Saved route/default league restoration is established behavior. |
| How do I evaluate my roster? | Yes | Existing mental model applies. |
| How do I use Trade Hub? | Yes | Returning context should be preserved. |
| What does Trust mean? | Depends on prior exposure | A repeatable help affordance is useful; forced onboarding is not. |
| Why believe recommendations? | Partly | Evidence remains accessible in cards. |
| What does Premium unlock? | Yes | Plan appears in shell and content branches. |
| Where next? | Yes | Navigation and restored route supply continuity. |

**Cognitive load:** unexpected onboarding after refresh, logout/login, or ordinary
route restoration would be harmful.

**Unnecessary clicks:** none created by the proposed pattern because dismissed state
must be respected.

### Persona 4: Free user

**Expectation:** Receive a complete basic workflow and understand limits without
mistaking limited depth for poor generation.

**Likely confidence:** Medium-to-high where gating copy is explicit.

| Question | Discoverable? | Evidence and friction |
|---|---|---|
| What does the app do? | Yes | Core workflow remains useful. |
| What page comes first? | Yes | Dashboard. |
| How do I evaluate my roster? | Yes at preview depth | Basic team needs and core roster view exist. |
| How do I use Trade Hub? | Yes with exploration | Free preview reports visible versus approved ideas and only promotes when ideas are hidden. |
| What does Trust mean? | Partly | Approved-count copy references Trust without introducing it. |
| Why believe recommendations? | Partly | Reasoning exists; entitlement and evidence filtering may be conflated. |
| What does Premium unlock? | Yes | Upgrade surfaces and Premium inventory are explicit. |
| Where next? | Partly | Premium prompts and actual football actions compete for attention. |

**Cognitive load:** distinguishing “not generated,” “not Trust-approved,” and
“approved but Premium-hidden.”

**Unnecessary clicks:** opening Premium to learn whether a sparse result is gating or
genuine scarcity, although Trade Hub now handles this correctly in its summary.

### Persona 5: Premium user

**Expectation:** Immediate complete content, no upgrade prompts, and clear value
from deeper intelligence.

**Likely confidence:** High when the identity header and content confirm Premium.

| Question | Discoverable? | Evidence and friction |
|---|---|---|
| What does the app do? | Yes | Full workflow is available. |
| What page comes first? | Yes | Dashboard or restored route. |
| How do I evaluate my roster? | Yes | Full Next Moves and League Pulse are available. |
| How do I use Trade Hub? | Yes | Complete approved board is shown and count is explicit. |
| What does Trust mean? | Partly | More ideas increase the need to understand filtering and confidence. |
| Why believe recommendations? | Partly | Evidence is available but the mental model is distributed. |
| What does Premium unlock? | Yes | Current plan and full content demonstrate it. |
| Where next? | Yes for experts, partly for novices | Premium depth can amplify information overload. |

**Cognitive load:** Premium expands the number of valid paths without adding a
stronger first-use priority.

**Unnecessary clicks:** exploring full content categories before understanding which
one addresses the immediate goal.

## 4. First ten minutes: screen-by-screen information flow

Times are task windows, not measured latency.

| Window / screen | User goal | Information shown | Decision expected | Likely confusion | Confidence | Next likely click |
|---|---|---|---|---|---|---|
| 0:00–0:30, launch hero | Identify product | Analysis, trades, roster management, league intelligence; three setup steps | Continue as account or guest | Difference between analysis and action; whether account is required | High | Account or Guest |
| 0:30–2:00, identity mode | Decide whether to sign in | Saved-context benefit; guest is fully usable | Sign in/create or continue | Email confirmation and saved-league benefits may distract users wanting instant analysis | High | Continue / Log in |
| 1:00–3:00, import | Connect league | Sleeper full support, ESPN experimental, username field | Enter username/platform data | Two import surfaces exist on desktop; platform limitation details add load | High | Load My Leagues |
| 2:00–4:00, league chooser | Select context | League, team, format, draft state, record, size, season, last used | Open league | Similar leagues/seasons may require close reading | High | Open League |
| 3:00–5:00, startup shell | Wait with confidence | Stable staged loading status | None | Minimal; this is intentionally non-interactive | High | None |
| 4:00–6:00, Dashboard top | Confirm correct context | League/team/account/plan, strategy, ranks, team identity | Interpret roster state | Novice does not know power versus franchise rank or whether strategy is prescribed | Medium | Scroll / My Team |
| 5:00–7:00, Next Moves | Choose priority | Need, trade, waiver, health, pressure, Premium-dependent depth | Select one recommendation | Several actions can look equally primary; Trust is not introduced | Medium | My Team / Trade Hub / Waivers |
| 6:00–8:00, My Team | Diagnose roster | Rooms, lineup, pressure, advice, player decisions | Decide what roster issue matters | Major need, upgrade, risk, and roster protection require domain reading | Medium | Player detail / Trade Hub |
| 7:00–9:00, Trade Hub | Explore a move | Approved counts, sections, packages, fairness, confidence, fit | Choose a plausible idea | Trust-approved does not mean guaranteed; Free gating can be confused with scarcity without reading summary | Medium | Trade card / Analyzer |
| 8:00–10:00, supporting page | Validate next action | Waiver, League Overview, Player Detail, or Analyzer evidence | Compare alternatives | User lacks a remembered workflow tying summary → evidence → action | Medium | Return Dashboard / external platform |

### Exact context-loss point

The strongest context drop is between **Open League** and the first Dashboard
decision. The launch flow teaches setup, then stops. The Dashboard teaches current
state, but not how to operate the product. This is why a post-import handoff is more
targeted than a welcome modal or full guided tour.

## 5. Primary confusion points

1. Dashboard is both an executive summary and a collection of actions; its role as
   triage is implicit.
2. My Team, League Overview, and Dashboard each answer a different form of “how good
   is my roster?” without a first-use distinction.
3. Trade Hub discovery and Trade Analyzer evaluation are explained on the Analyzer,
   but not taught in the initial journey.
4. Trust is referenced in approved-board language before its purpose and limits are
   introduced.
5. Confidence, fairness, and Trust are separate concepts but can appear synonymous.
6. Free depth limits can be mistaken for recommendation scarcity.
7. Premium adds depth across several surfaces, increasing first-session choice.
8. Account, import, league settings, refresh, and billing ownership is distributed.
9. Startup leagues require a different workflow and are handled correctly, but this
   is another branch a new user must absorb.
10. Experimental destinations add product breadth before the core workflow is learned.

## 6. Information gaps

The first journey needs only five pieces of missing context:

1. **Dashboard is triage:** start here to choose one priority.
2. **Workspaces provide evidence:** My Team, Trade Hub, Waivers, and League Overview
   explain the priority from different angles.
3. **Recommendations are advisory:** they do not execute Sleeper actions.
4. **Trust is evidence filtering:** it blocks ideas that cannot be supported by
   current identity, ownership, eligibility, and source context; it is not a
   prediction guarantee.
5. **Premium expands depth:** it reveals more approved intelligence, not a different
   valuation or a guarantee of more valid results.

No multi-page product tour is required to communicate these points.

## 7. Onboarding options evaluated

| Pattern | Benefit | Complexity | Maintenance | Intrusiveness | Mobile | Accessibility | Verdict |
|---|---|---:|---:|---:|---|---|---|
| Welcome modal | Forces visibility | Medium | Medium | High; blocks first useful content | Constrained | Focus trapping/restoration required | Reject |
| Dismissible orientation card | Places workflow at context-loss point | Low | Low | Low | Strong if compact | Native heading/buttons work well | **Select** |
| Progressive hints | Teaches in context | Medium | High across changing pages | Medium cumulative | Can crowd cards | Repeated announcements/focus issues | Reject for first phase |
| Checklist | Makes progress concrete | Medium | Medium | Medium; implies mandatory completion | Long on mobile | Manageable | Reject; workflow is not linear completion |
| Guided tour | Demonstrates controls | High | High; brittle to layout | High | Weak | Complex focus and positioning | Reject |
| Contextual help icons | Repeatable reference | Medium | Medium | Low | Touch-target risk | Requires labels/tooltips | Defer as follow-up |
| Empty-state education | Excellent when empty | Low | Low | Low | Strong | Strong | Complementary, not sufficient |
| Embedded explanation on every page | Always available | Medium | High content footprint | Medium | Adds scroll | Strong if semantic | Reject as repetitive |

## 8. Recommended onboarding pattern

### Pattern

One **dismissible post-import orientation card** on Dashboard.

### Placement

- Render after `PAGE_READY`, the league identity header, and confirmation that a
  selected league maps to a roster.
- Place before Dashboard's first decision stack (`Next Moves`), not in the startup
  shell, sidebar, modal, or navigation sheet.
- Startup-mode leagues should receive a draft-specific variant only if the same
  three-step contract can point to Startup Draft Center; otherwise suppress it until
  normal roster mode. Do not invent a separate onboarding system.

### Audience

- New league contexts for guests and authenticated users.
- Both Free and Premium users see the same workflow explanation.
- Copy may mention that Premium expands depth, but entitlement must not select a
  different onboarding path.
- Returning users who have dismissed the card for that league do not see it.

### Content contract

Maximum:

- one short heading, no more than 45 characters;
- one orienting sentence, no more than 140 characters;
- three numbered steps, each with a label of at most 24 characters and explanation
  of at most 90 characters;
- one compact Trust note, at most 140 characters;
- one primary action and one dismissal action;
- approximately 80–110 total words.

The primary action should open the first evidence surface associated with the
current top priority only if that destination is already known without new business
logic. Otherwise use the stable, generic action “Review My Team.” Do not create a
recommendation router.

### Why this pattern

- It appears at the proven context-loss boundary.
- It leaves useful content visible and navigation available.
- It is compatible with Streamlit's normal rerun model.
- It works as a normal responsive card.
- It requires no tour library, private API, overlay, or auth rewrite.
- It can be tested as a pure visibility/state contract.
- It has a one-component rollback boundary.

## 9. Trigger conditions and first-use definitions

### First-time user

For onboarding purposes, “first-time” means:

> The current browser/account has not dismissed or completed the orientation for
> the current product onboarding version and current league context.

It must not be inferred solely from account creation date, login state, process
start, missing route, or lack of Premium.

### Returning user

A returning user has a completion/dismissal record for the current onboarding
version and league context. They should not be interrupted, regardless of whether
startup restored a session or they imported manually.

### Trigger matrix

| Event | Show? | Reason |
|---|---|---|
| First successful league import | Yes | Primary context-loss point |
| New account, before league | No | Setup screen already explains the next action |
| New account with first league restored | Yes | No orientation record for that league |
| Browser refresh | No if dismissed/completed | Refresh is not first use |
| Logout then login | No if persisted | Auth transition must not reset product learning |
| New league import | Yes for that league | Team context and workflow are newly encountered |
| Switch to previously oriented league | No | League-scoped record exists |
| League changed without prior orientation | Yes | New context |
| Route restored directly to a non-Dashboard page | Do not redirect or block | Preserve route; expose a repeatable help entry later or wait until Dashboard |
| Premium upgrade/downgrade | No | Entitlement is not onboarding state |
| Onboarding version materially changes | Yes once | Version permits intentional re-orientation |
| Expired session | No by itself | Authentication failure is not product first use |

## 10. Dismissal behavior

- Provide an explicit “Dismiss” or “Got it” control with an unambiguous accessible
  name.
- Dismissal is immediate and must not navigate.
- Do not require completing the primary action.
- Do not reappear during the same session after dismissal.
- Offer a future non-blocking “How DynastyGM works” help entry from an existing
  support surface; this is not required in the first implementation.
- A repeated selection of the same league must remain dismissed.
- Do not use an X-only icon.

## 11. Persistence strategy

### Required key

Persist a versioned, league-scoped completion identifier conceptually equivalent to:

`onboarding:<version>:<platform>:<league-identity>`

The league identity must use the existing normalized league context. Do not log or
display it and do not place it in query parameters.

### Guests

Use browser-local persistence through an existing supported durable client-state
mechanism if available. If none exists without adding a component, a session-scoped
fallback is acceptable for the first implementation but must be disclosed as less
durable. Do not use a global process cache.

### Authenticated users

Prefer an existing account preference/profile JSON field only if it already supports
arbitrary versioned preferences. Do not add a Supabase column or change
authentication for onboarding. If no suitable field exists, use the same
browser-local strategy as guests.

### Session state

Session state may mirror the persisted result for current-rerun efficiency, but
must not be the sole durable definition if refresh-safe local storage already exists.

### Invalidation

- Change the onboarding version only for a materially changed operating model.
- Do not invalidate on deploy, process restart, valuation refresh, entitlement
  change, league data refresh, or recommendation changes.

## 12. Copy guidelines

This specification intentionally does not provide final marketing copy.

- **Tone:** calm, practical, transparent, and football-literate without assuming
  dynasty expertise.
- **Voice:** direct second person; active verbs; no hype or guarantees.
- **Reading level:** approximately grade 7–8.
- **Length:** 80–110 total words, with scannable steps.
- **Vocabulary:** define Trust once in plain language; avoid “engine,” “canonical,”
  “enforcement,” “pipeline,” “model output,” and “entitlement.”
- **Claims:** say filters, compares, suggests, or highlights—not predicts, proves,
  guarantees, wins, or knows.
- **Actions:** one primary action and one dismissal only.
- **Premium:** describe greater depth, never greater accuracy or guaranteed quantity.
- **Trust:** distinguish evidence quality from confidence, fairness, and outcome.

## 13. Accessibility considerations

- Use a semantic region with a heading associated by `aria-labelledby`.
- Place it in normal document order before Next Moves.
- Use native Streamlit buttons or semantic buttons; no clickable `div`.
- Maintain logical focus order: heading/content → primary action → dismiss.
- Dismissal should return focus to the Dashboard's next meaningful heading.
- Do not auto-focus or announce the entire card on every rerun.
- If announced on first insertion, use a restrained `aria-live="polite"` status,
  then remove live behavior after initial render.
- Do not communicate step meaning through color alone.
- Preserve 200% zoom, reduced motion, and keyboard-only operation.
- Primary and dismissal labels must make sense outside visual context.

## 14. Mobile considerations

- Render as one vertical card; never as a modal, carousel, or horizontal stepper.
- Keep the full card visible without horizontal scrolling at 320 CSS pixels.
- Use existing mobile spacing and minimum touch-target tokens.
- Put the primary action above dismissal only if this matches established button
  hierarchy; both must remain visible without sticky positioning.
- Avoid illustrations, animation, and large hero treatment.
- Three steps should remain short enough to avoid pushing Next Moves excessively
  below the fold.
- Verify long league/team names do not alter card width.
- The card must not overlap the mobile navigation trigger or destination sheet.

## 15. Future implementation checklist

### State contract

- [ ] Define an immutable onboarding-version constant in a focused onboarding module.
- [ ] Define a pure visibility function using version, league context, and persisted
      completion state.
- [ ] Keep user-specific state out of Streamlit global caches.
- [ ] Confirm guest and authenticated persistence without auth/schema changes.
- [ ] Mirror current visibility in session state only as an optimization.

### Rendering

- [ ] Add one reusable orientation-card renderer outside `app.py`.
- [ ] Add minimal Dashboard orchestration wiring after `PAGE_READY`.
- [ ] Render before Next Moves and after valid roster context.
- [ ] Preserve direct-route restoration; never redirect to Dashboard.
- [ ] Support normal roster mode and explicitly decide startup-mode suppression.
- [ ] Use one primary action and one dismissal.

### Behavior tests

- [ ] New league shows the card once.
- [ ] Dismissed league remains dismissed after rerun and refresh.
- [ ] New league shows independently.
- [ ] Returning to an oriented league stays dismissed.
- [ ] Logout/login does not reset completion.
- [ ] Free/Premium behavior is identical except existing content depth.
- [ ] Direct routes are not overridden.
- [ ] Missing roster and malformed league states do not mount the card.
- [ ] Startup Coordinator lifecycle and mount count are unchanged.
- [ ] No Trade Hub, Trust, Premium, auth, navigation, or cache contract changes.

### Browser validation

- [ ] Keyboard-only completion and dismissal.
- [ ] Screen-reader heading, region, button names, and focus restoration.
- [ ] Desktop widths at 1024 and 1440.
- [ ] Mobile widths at 320 and 390.
- [ ] Tablet at 768.
- [ ] 200% zoom and reduced motion.
- [ ] Refresh, back/forward, logout/login, and league switching.
- [ ] Controlled Free and Premium accounts.

### Performance

- [ ] No new network request before first page render.
- [ ] No extra explicit rerun for display.
- [ ] Dismissal causes at most the normal widget-triggered rerun.
- [ ] No new player, league-summary, Team Needs, trade, or entitlement calculation.
- [ ] Card payload remains small and static.

## 16. Why competing patterns were rejected

- **Modal:** blocks the very Dashboard context users need to understand and adds
  focus-management risk.
- **Guided tour:** couples onboarding to unstable element positions, grows
  maintenance cost, and performs poorly on mobile.
- **Checklist:** implies required setup tasks even though the correct next action
  varies by roster.
- **Progressive hints:** spreads state and copy across many pages before one compact
  operating model has been tested.
- **Permanent explanations:** add recurring density for returning users.
- **Empty-state-only education:** cannot orient users who have healthy populated
  recommendations.

## 17. Browser validation gaps

The following require a controlled test environment before implementation approval:

1. Observe at least five first-time participants, including two dynasty novices.
2. Measure time from league selection to the first correctly chosen workspace.
3. Record which Dashboard concepts participants explain incorrectly.
4. Ask participants to distinguish Trust, confidence, fairness, and Premium gating.
5. Compare current flow with a non-functional orientation-card prototype.
6. Validate that experienced and returning users dismiss without frustration.
7. Validate Free and Premium users interpret the same workflow correctly.
8. Measure mobile scroll displacement caused by an 80–110-word card.
9. Test screen-reader reading order and focus after dismissal.
10. Confirm no controlled user expects DynastyGM to execute transactions.

Success criteria for the future implementation:

- at least 80% of controlled first-time users choose the correct workspace for a
  stated goal without facilitator help;
- at least 80% can explain Trust as evidence filtering rather than an outcome
  guarantee;
- median time from Dashboard mount to a purposeful workspace selection improves;
- returning users can dismiss in one action and do not see the card again for that
  league;
- no startup, route, or page-mount regression occurs.

## 18. Recommended implementation boundary

Future implementation should affect only:

- one focused onboarding/orientation module;
- focused state and rendering tests;
- a few orchestration lines at the Dashboard boundary, if necessary.

It must not alter Startup Coordinator phases, routing, authentication, Supabase
schema, entitlement resolution, Trade Hub, Trust semantics, caches, recommendation
logic, or existing page layouts.

Rollback should be a single focused commit that removes the renderer and its
visibility wiring while leaving any safely namespaced completion preference inert.
