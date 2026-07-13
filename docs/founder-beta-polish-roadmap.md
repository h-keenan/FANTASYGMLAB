# Founder Beta UX and Production Polish Audit

Audit baseline: `main` at merge commit `ad8ce45647562d78240c73425daf65082888ee6b` (PR #21).

This pass intentionally leaves fantasy calculations, rankings, trade and waiver logic, Premium semantics, Stripe, authentication, and Sleeper behavior unchanged.

## Critical

No source-verifiable Critical UX dead ends were found. Authentication, entitlement, league switching, route preservation, read-only Live Draft behavior, and error surfaces retain dedicated existing tests. A credentialed production account and active draft are still required for a true external end-to-end production walkthrough.

## High — fixed in this pass

| Area | Finding | Resolution |
| --- | --- | --- |
| Full app reruns | `app.py` forcibly reloaded 16 dependency modules on every Streamlit rerun, destabilizing module state and cached function identities. | Reloading is now disabled by default and available only through `DYNASTYGM_DEV_RELOAD_MODULES=true`. |
| League picker | A tapped card already displayed local loading, but the handler also opened a global Streamlit spinner and shifted the sheet. | Removed the second spinner; the selected card remains the single loading surface. |
| Floating controls | GM and Feedback could remain tappable underneath the League Actions or GM sheet. | Controls are now hidden and non-interactive while those blocking sheets are open, in addition to existing dialog handling. |
| Accessibility | Important card metadata used type as small as 0.56–0.69rem and league-card focus relied mainly on a border-color change. | Established a 0.75rem mobile metadata floor, explicit focus ring, and larger readable status badges. |
| Mobile forms | iOS could zoom text inputs because their computed text size was below 16px; first-use auth choices were cramped at narrow widths. | Mobile inputs now use 16px text and the primary first-use choice row stacks vertically. |
| Motion | Reduced-motion support covered only selected Trade Hub cards. | A centralized reduced-motion rule now applies to the full application shell. |

## Route audit

| Destination | Founder-beta assessment | Remaining issue |
| --- | --- | --- |
| Dashboard | Clear command-center hierarchy already prioritizes next moves and condenses explanations. | Medium: validate opportunity ordering with production founder accounts before changing presentation. |
| My Team | Shared player cards, explicit injury badges, and consolidated Roster Pressure are in place. | Low: review long-team-name wrapping with real imported leagues. |
| League Overview | Team cards and draft-capital cards use the shared shell. | Medium: detailed DataFrame views remain horizontally scrollable inside optional expanders. |
| Rankings | Warm navigation and shared player-data cache protections remain intact. | Low: add a browser-level dynamic-type visual snapshot later. |
| Trade Hub | Headline hierarchy, section filters, compact comparisons, shared headshots, value delta chips, and collapsed explanations are present. | Medium: production visual regression snapshots should cover unusually long multi-asset packages. |
| Waivers | Shared player presentation and explicit injury status are present. | Medium: confirm the densest FAAB explanations at 320px with live league data. |
| Startup Draft Center | Ranking cards, recommendation buckets, Quick View, and completed-draft review are present. | Medium: historical/detail tables remain optional DataFrames rather than mobile cards. |
| Live Draft | Card-based player rankings, team rankings, a single polling fragment, filter reuse, and failure-state preservation are protected. | Medium: Player Quick View still begins with a select control rather than direct row tapping. |
| Premium | Entitlement uses the canonical effective entitlement path and test-mode billing remains isolated. | Low: run checkout-return copy review before public advertising. |
| Workspace | Shared summary tiles and destination grouping are keyboard-enabled. | Low: continue reducing internal diagnostic tables visible only in debug contexts. |
| Settings / Account | Existing account, saved league, logout, and configuration flows remain reachable. | Medium: add browser automation with disposable Supabase test users. |
| Feedback | Global feedback remains available and now yields to blocking sheets/dialogs. | Low: verify soft-keyboard dismissal in iOS Safari. |
| Login / Signup | Explicit labels, generic secure errors, confirmation recovery, and Guest fallback remain. | Medium: credentialed browser QA is required for email confirmation and durable restore. |
| League picker | Directly tappable cards, Current/Default badges, route preservation, internal scrolling, and selected-card loading are present. | Resolved High: removed duplicate global spinner and control overlap. |

## Medium backlog

1. Convert optional Live Draft, completed Startup Draft, and draft-capital DataFrames to compact responsive detail cards after visual equivalence fixtures exist.
2. Add Playwright-style browser coverage at 320, 375, 390, 430, tablet, and desktop widths. The current repository relies mainly on route/static regression tests.
3. Add disposable Supabase/Stripe test identities for login, return-login, confirmation, entitlement, and checkout-return browser automation. No real credentials should enter CI.
4. Consolidate the historical layers in `modules/app_styles.py`. It contains multiple migration-era overrides; removal should be driven by selector-usage and screenshot tests rather than a blind rewrite.
5. Make Live Draft ranking rows directly open the existing Quick View while preserving fragment isolation and avoiding nested dialogs.
6. Add operation-specific skeletons only for measured operations over one second; avoid decorative loaders on warm interactions.

## Low backlog

1. Review microcopy consistency between “Open,” “View,” and “More” affordances.
2. Verify long translated/dynamic text even though localization is not currently supported.
3. Add automated contrast checks to complement the current semantic palette and source assertions.
4. Add production screenshot baselines for one representative player, team, trade, waiver, draft, empty, and error card.

## End-to-end QA boundary

Static route and architecture inspection covers every requested destination. Full external production actions involving a new account, durable login restoration, real league import, live draft polling, and Stripe test checkout require a deployed build plus disposable credentials. Those actions should not be simulated with private founder data or real billing secrets.
