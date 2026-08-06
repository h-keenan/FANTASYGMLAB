# Founder Beta First-User Experience Audit (PR #139)

| Field | Value |
| --- | --- |
| Baseline | `05815d537c70c89a41de2d3ca20b591cc67da13b` (post PR #138 cold-start) |
| Scope | Usability / presentation only — wording, discoverability, empty/loading education |
| Explicit non-changes | Football logic, Trust, rankings, valuations, recommendation generation/ordering, auth, entitlements, Stripe, Supabase schema, Sleeper semantics, caching, startup architecture |
| Method | First-time dynasty GM simulation (zero product knowledge) |

## Simulation stance

Walked FantasyGM Lab as a brand-new manager who has never heard of Trade Hub, League Intelligence, Value change, Trust, or the Menu control. Every label was asked: *Would a new user understand this? What should I do next?*

## Top 25 usability issues (found → addressed)

| # | Issue | Why it hurts a first-time user | Fix shipped |
| --- | --- | --- | --- |
| 1 | **“Value delta”** on trade cards | Sounds like engineering; users ask “is this good for me?” | Relabeled **Value change** |
| 2 | **“Active lens” / “Team Lens”** | Internal strategy jargon | **Strategy focus** / **Team Focus** |
| 3 | **“Premium unlock”** CTA | Reads like a system flag, not an action | **Unlock with Premium** |
| 4 | **“All Destinations”** mobile sheet | Abstract navigation speak | **Where to go** |
| 5 | **GM Orb labeled “GM”** | Cryptic brand orb without purpose | Label **Menu** + help listing Trade Hub, Waivers, My Team |
| 6 | **“Full Next Moves” / “Expanded League Pulse”** | Unclear what is locked | **More next moves** / **Full League Pulse** |
| 7 | **“Finish loading a league…”** empty notes | Sounds broken mid-load | **Import your Sleeper league…** |
| 8 | **“Search limits:”** captions | Diagnostic tone | Plain-language “fewer matching partners…” |
| 9 | **“clears the engine”** secondary-path copy | Developer mental model | “weaker backups — less likely to close” |
| 10 | Trade Hub entitlement / “Trust approved” captions | Trust is an internal gate; users hear “approved” as endorsement | GM language: “trade ideas that passed fairness checks” |
| 11 | Empty Trade Hub blamed “recommendation rules” | No next step in GM words | Fairness empty state + try another focus / player search |
| 12 | **“Save your league context”** | Engineering “context” | **Save this league to your account** |
| 13 | **“Lowest-utility”** cut language | Utility scoring jargon | Clearest / lowest-impact cut language |
| 14 | Orientation said **“Trust details” / “workflow”** | Invisible product concepts | “Open a package for the full why” |
| 15 | Quick Actions said **“major workflow”** | Internal process word | “next decision area” |
| 16 | League Intelligence empty / headers | “actionable league context” / evidence thresholds | News → move mapping; buyer/seller posture in plain English |
| 17 | Notification empty / sample alerts | Vague “you’re all caught up” + founder-only meta | Sample-alert honesty + check-back guidance |
| 18 | Confidence unexplained on board | Badge without meaning | One-line progressive education under entitlement note |
| 19 | League switcher when only one league | Dead end | “Only one league saved. Import another…” |
| 20 | Trade Hub purpose / nav blurbs | “Primary trade discovery workspace” | “Find realistic trades… ranked by fit and fairness” |
| 21 | My Team “Controls and diagnostics” kicker | Dev diagnostics vibe | **Manual controls & detail** (prior polish retained / reinforced) |
| 22 | Premium inventory used “Intelligence” / “workflow” | Feature inventory felt technical | Overview / league updates / trading posture wording |
| 23 | Return Explorer “shared trade engine” | Engine = backend | League rosters / tendencies / needs |
| 24 | Dashboard urgent caption “another workflow” | Process language | “Handle the urgent roster issue below first” |
| 25 | Repeated engineering defaults in narratives | “active lens” fallbacks | “current strategy focus” fallbacks |

## Confusing wording (inventory)

| Before (customer-facing) | After |
| --- | --- |
| Value delta | Value change |
| Active lens / Team Lens / team lens | Strategy focus / Team Focus |
| Premium unlock | Unlock with Premium |
| All Destinations | Where to go |
| GM (orb) | Menu |
| Full Next Moves | More next moves |
| Expanded League Pulse | Full League Pulse |
| Finish loading a league | Import your Sleeper league |
| Search limits | Fewer matching partners… |
| clears the engine | weaker backups / less likely to close |
| Trust approved / approved ideas | trade ideas / fairness checks |
| league context (account save) | this league / remember username and leagues |
| Lowest-utility | Clearest / lowest-impact |
| workflow (orientation / quick actions) | how to use / decision area |
| Roster utility (waiver note) | helps right away |

Internal module names (`trust_engine`, `workflow_continuity`, diagnostics expanders gated for developers) remain developer-only and were not customer-exposed.

## Hidden features / discoverability

| Feature | First-user findability | Change |
| --- | --- | --- |
| Import a league | Present but empty states said “finish loading” | Import-forward empty notes |
| Trade Hub | Reachable from Menu / Quick Actions; purpose opaque | Purpose + empty/loading education |
| Dashboard | Orientation modal improved | GM steps without Trust/workflow jargon |
| Premium | Locks existed; CTA/inventory jargon | Clearer lock titles + CTA |
| Feedback | Already branded entry (prior work) | Unchanged behavior |
| Notifications | Sample-only easily misread as live | Explicit sample + empty guidance |
| Player Quick View | Reachable from cards | Narrative fallbacks cleaned |
| League switching | Easy with 2+ leagues; dead with one | Explicit import prompt |

## Missed opportunities → progressive education

| Moment | One-sentence teach (no popup) |
| --- | --- |
| Trade board with ideas | “Confidence estimates how likely this move improves your roster. Value change shows whether the package favors your side.” |
| League Intelligence (Dashboard) | “League-wide signals that may change your next move — scarcity, posture, and market pressure.” |
| Strategy selector help | Auto follows evaluated direction; changing focus re-ranks without skipping fairness |
| Orientation | How to use FantasyGM Lab — Dashboard → My Team → Trade Hub → Waivers |

## Empty / loading state audit

| State | Expectation for a new user | Status after this PR |
| --- | --- | --- |
| No league | What happened / what to do / what next | Import Sleeper league notes on Trade Hub, My Team, Waivers, Analyzer |
| No trade ideas | Fairness empty + try focus / player search | Fixed |
| No waivers / no notifications | Check-back guidance | Notifications improved; waiver empty paths rely on existing panels |
| No Premium | Lock explains value without hard sell | Unlock CTA + inventory wording |
| Startup loading | Phase copy already GM-facing (prior #138) | Unchanged architecture; presentation retained |

## Premium audit (Free user)

Free users now see:

- **What unlocks:** More next moves, Full League Pulse, full trade board, waiver/roster depth, league updates
- **Why a lock:** Short feature-titled lock + **Unlock with Premium**
- **No hard sell:** No checkout/subscribe language on locks (existing contract retained)

## Emotional experience / executive simplicity

Reduced: engine/diagnostics/utility/workflow/lens jargon; repeated Trust-as-product language on entitlement captions; abstract navigation titles. Kept: single primary move emphasis, quiet captions, no new tutorial popups, no card inflation.

## UX improvements shipped (summary)

1. Value change label on trade cards  
2. Strategy focus / Team Focus language  
3. Unlock with Premium CTA  
4. Where to go destinations sheet  
5. Menu label + destination help  
6. More next moves / Full League Pulse locks + Premium inventory  
7. Import-forward empty/onboarding notes  
8. Fairness-first Trade Hub empty states  
9. Trade Hub entitlement captions in GM language  
10. Trade board confidence / value progressive education  
11. League Intelligence progressive caption + clearer headers  
12. Account save / notification / waiver / cut language cleanup  
13. Orientation and Quick Actions copy  
14. Secondary/thin-market path copy  
15. Nav purpose strings for Trade Hub / Waivers / Analyzer  

## Before / after screenshots

Captured from deterministic harnesses after copy changes (CI also runs Chromium mobile UI validation):

- Trade card label: **Value delta → Value change** (`scripts/ui_validation_harness.py` trade surface)
- Destinations sheet: **All Destinations → Where to go** (navigation surface)
- Dashboard Free locks: **More next moves** / **Full League Pulse** (`scripts/dashboard_visual_harness.py`)
- Menu control: **Menu** with destination help (`modules/brand_identity.py`)

Artifact paths (agent run): `/opt/cursor/artifacts/first-user-audit/` when browser capture is available; otherwise CI `ui-mobile-screenshots-*` from `.github/workflows/ci.yml`.

## Remaining usability concerns

1. **Trust** as a product word still appears in some deep explanation surfaces — educate further only where users open detail, without renaming the system.
2. **League Intelligence** as a destination name is still abstract until the caption is read.
3. **Experimental** routes still require Menu literacy; first-time users may never find Trade Analyzer / Live Draft (acceptable for Founder Beta).
4. Streamlit chrome / native select density (FQA-001) remains a platform constraint.
5. Live notifications are still sample-backed in Founder Beta — copy is honest, but expectations will rise once delivery is live.
6. Premium value is clearer; conversion copy could still add one outcome-focused sentence on the Premium page later (no hard sell).

## Rollback boundary

Revert the merge commit of this PR on `main`. Presentation/copy and harness expectations only — no schema, entitlement, or recommendation-logic rollback required.

## Validation

- `python -m compileall` on touched packages  
- Focused + full `pytest`  
- Performance budget scripts used by CI  
- Chromium / mobile UI validation harness markers  
- CI green before merge  
