# Comprehensive Product UX Audit

## Scope and evidence

This audit evaluates commit `7a36db8d79366fc82d0f028485188b8b317ab34c`
as a first-time dynasty manager, experienced manager, returning Premium user,
mobile user, and desktop user. Evidence comes from production render paths, the
page registry, shared components, CSS, state handling, UI tests, and the
repository's prior controlled runtime and visual investigations.

No customer account, customer league, or organic session was used. A controlled
credentialed browser was unavailable, so exact viewport geometry, screen-reader
output, browser history, and click counts are validation gaps rather than claimed
findings. No production UI change is included in this audit.

## Executive summary

DynastyGM has a strong decision-support concept: connect a league, understand the
franchise, then move into roster, trade, waiver, league, or draft workflows. Shared
page shells, cards, status chips, stable startup, single-rerun navigation,
canonical entitlement handling, and category-aware Team Needs language provide a
sound foundation.

The main problem is prioritization, not missing functionality. New users face two
setup surfaces, many destinations, advanced vocabulary, and little orientation to
the relationship among values, Trust, recommendations, and Premium. Experienced
users receive useful depth, but frequently move among cards, expanders, tables, and
page-specific interaction patterns. Mobile safeguards are extensive, yet optional
DataFrames and long card stacks still create likely scroll and scanning friction.

No source-verifiable Critical dead end was found. The highest-impact next phase is
a small post-import orientation pattern explaining the product's recommended
workflow. It should be validated with controlled users before implementation.

## Strengths

- Page purpose is normally explicit through a shared title, subtitle, and chips.
- Startup holds one accessible shell until the application is ready.
- Desktop and mobile navigation share a registry and callback contract.
- Core destinations cover a coherent manager workflow.
- Recommendations include reasons, confidence, empty states, and Trust filtering.
- Team Needs separates deficiencies, upgrades, future risks, and injury pressure.
- Premium branches are canonical and have behavior-level regression coverage.
- Mobile CSS preserves zoom, focus, control sizing, and overlay clearance.
- Experimental destinations are explicitly separated from the core beta.
- Error states generally avoid false certainty and retain a next step.

## System-wide weaknesses

- First-use setup is duplicated between the main launch flow and desktop sidebar.
- The broad navigation inventory is not taught as a task sequence.
- Trust is operationally important but weakly explained at first encounter.
- Density varies: compact cards coexist with tables, many expanders, and long stacks.
- Rendering assembly in `app.py` permits subtle hierarchy and wording differences.
- The large, override-heavy visual system increases consistency risk.
- Status meaning relies on domain vocabulary and color despite accompanying text.
- Settings are distributed across sidebar, header, account, import, and Premium.

## Primary-page audit

| Page | Purpose / primary action | Strength | Main UX risk |
|---|---|---|---|
| Dashboard | Daily command center; choose the next action | Strong executive hierarchy and accurate need/Premium states | Several blocks compete for “next”; ranks, Trust, and strategy are not taught inline |
| My Team | Operate the selected roster | Clear identity, pressure, advice, lineup, and decisions | Long vertical workflow; parallel advice categories can feel equally urgent |
| Trade Hub | Discover team-wide and player-specific trades | Strong cards and strategy/fairness/confidence context | Generated, Trust-approved, primary, secondary, and gated ideas create high conceptual load |
| Players / Rankings | Scan the player market and open detail | Compact scan first, full table retained | “Players” and “Rankings” vocabulary overlap; dense controls are harder on small screens |
| Player Detail | Understand value, fit, trade outlook, and news | Coherent narrative and category-aware fit | Missing data can create many fallback blocks; Back depends on route context |
| League Overview | Compare power, value, teams, and picks | Rich intelligence and correct relative-weakness language | Tabs, tables, rank types, and drill-ins create density |
| Waivers | Find priority adds and FAAB guidance | Need-aware context and mobile cards | Multiple boards cause scroll; no-agent and data-failure states need clearer separation |
| Premium | Explain plan and founder-beta billing | Current plan and current/future features are explicit | Feature inventory outweighs outcome framing; developer/test copy is prominent |
| Settings / account | Import, refresh, configure, and manage account | Advanced controls exist and auto-detection is explained | No single destination; twelve league overrides form a dense sidebar workflow |
| Experimental | Validate future workflows | Live Draft clearly says Read Only and Experimental | Large, uneven inventory can clutter discovery and expectations |

### Experimental-page findings

- Startup Draft Center and Draft Center are core but need clearer lifecycle framing.
- Live Draft's Read Only / Experimental disclosure is a strong trust pattern.
- Trade Analyzer clearly follows discovery as an exact-package evaluator.
- Players, Teams, Weekly Report, News, Archetypes, Manager Tendencies, and Player
  Detail should remain subordinate to the primary journey while experimental.

## First-time journey

1. The hero communicates a Sleeper league analyzer for roster value, league leverage,
   trade paths, and decision support.
2. League import is available in the main launch flow and repeated in the sidebar.
3. After selection, the shell exposes league, team, account, plan, strategy, and
   rankings.
4. Dashboard supplies decisions, but no single unit explains the sequence: inspect
   team state, choose a recommendation, validate its rationale, act externally.

Source-based comprehension assessment:

- What DynastyGM does: quick to understand.
- What to click: moderate; the main flow is named fastest, but sidebar setup competes.
- Where the league is: clear after import in the identity header.
- How Trade Hub works: understandable after exploration, not before.
- Why Trust exists: low discoverability despite cautious result language.
- Why Premium exists: coverage is explicit; user outcome is less prominent.

## Returning-user journey

- Saved league, route, profile, and entitlement restore under one startup shell.
- Ordinary navigation is one rerun and query-route state is preserved.
- The identity header communicates league, team, platform, account, and plan.
- “Switch League / Refresh / Import / Premium” combines four intents.
- Power users can adjust value and league settings in context.
- Multiple-league click counts require a controlled browser to measure accurately.

## Visual consistency

The product has reusable page shells, section headers, team identity cards, summary
tiles, intelligence cards, player cards, trade cards, and draft cards. Consistency
is strongest within each family. It weakens between native Streamlit status blocks,
custom HTML cards, DataFrames, and page-specific expanders. Typography and spacing
are centrally styled, but the CSS investigation recorded 1,284 unique selector
tokens and substantial later overrides, making drift likely. Colors and chips have
text labels, but the semantic palette is not documented as a single contract.

## Mobile findings

Confirmed safeguards:

- Six core destinations use a dedicated mobile shell and destination sheet.
- Focus-visible rules, 16px form controls, bottom clearance, and overlap protection
  are tested.
- Player, waiver, trade, and draft cards have compact mobile variants.
- Reduced-motion preferences are respected.

Risks needing viewport validation:

- Optional DataFrames can require horizontal exploration.
- Trade Hub and My Team can produce high scroll distance.
- Dense chips and long team names may wrap at 320px.
- New overlays could regress floating-control clearance.
- Mobile account/import/settings paths need parity testing with desktop.

## Accessibility findings

Strengths:

- Startup uses `role=status`, `aria-live`, `aria-busy`, and a progress bar.
- Clickable player/team cards receive focus and accessible labels.
- Decorative icons are hidden; legal navigation is labeled.
- Focus-visible and mobile text/control floors are tested.
- Semantic colors normally include text.

Gaps:

- Custom card grids are mostly `div`-based; headings and landmarks vary.
- JavaScript card activation needs screen-reader and Enter/Space verification.
- Generic native labels such as View, Back, and Remove rely on nearby visual context.
- DataFrame keyboard and screen-reader behavior is unverified.
- Contrast is not measured across every status and muted-text combination.
- Focus restoration after dialogs and sheets needs browser validation.
- Reflow at 200% zoom and 320 CSS pixels remains unverified.

## Premium findings

- Canonical entitlements prevent upgrade prompts for Premium users on protected paths.
- Free Trade Hub upgrades appear only when approved ideas are actually hidden.
- The Premium page separates included-now from possible-future features.
- Value framing is feature-led rather than outcome-led.
- Test billing and local override copy are acceptable in founder beta but should move
  out of the primary narrative before public paid launch.
- Experimental features should not become the main paid promise without explicit
  stability expectations.

## Information architecture

- Home, Roster, League, Transactions, Draft, Intelligence, and Support are sound.
- Internal `rankings` means League Overview while Players presents player rankings.
- My Team owns daily decisions while Teams owns comparison; current copy supports it.
- Trade Hub (discovery) and Trade Analyzer (specific package) form a clear sequence.
- Settings are an action cluster, reducing nav clutter but fragmenting ownership.
- News and injuries appropriately support decisions rather than owning core flow.

## Perceived responsiveness

Stable startup and single-rerun navigation reduce visible uncertainty. Named spinners
communicate league analysis. The larger perception risk is ambiguous waiting or
empty output: users may not know whether scarcity, Trust, entitlement, or service
failure caused it. Operation-specific feedback should be reserved for measured
long operations; ubiquitous skeletons would add motion without evidence.

## Bug inventory

| Severity | Finding |
|---|---|
| Critical | None source-verifiable |
| High | None source-verifiable |
| Medium | Competing main/sidebar setup actions |
| Medium | Fragmented settings/account/import/refresh ownership |
| Medium | Low first-use Trust discoverability |
| Medium | Mobile-critical optional DataFrames |
| Medium | Long My Team and Trade Hub stacks (browser validation needed) |
| Low | Players/Rankings/League Overview terminology overlap |
| Low | Empty states lack one scarcity/gating/failure taxonomy |
| Low | Developer billing language appears in product-facing Premium content |

## Top 25 improvements

| # | Improvement | Impact | Effort | Risk |
|---:|---|---|---|---|
| 1 | Add one post-import orientation panel explaining Dashboard → decision surface → external action | High | S | Low |
| 2 | Standardize “why this result / why none” for Trust, scarcity, gating, and failure | High | M | Low |
| 3 | Test first use with novice dynasty managers; measure time to first useful action | High | M | Low |
| 4 | Consolidate settings discoverability behind one named entry point | High | M | Medium |
| 5 | Replace task-critical mobile DataFrames with existing compact cards | High | M | Medium |
| 6 | Define one dominant primary action per page | High | M | Low |
| 7 | Add concise Trade Hub funnel education | High | S | Low |
| 8 | Validate core pages at 320, 390, 768, and 1440px | High | M | Low |
| 9 | Screen-reader and keyboard test cards, sheets, dialogs, and tables | High | M | Low |
| 10 | Progressively disclose secondary My Team sections | Medium | M | Medium |
| 11 | Clarify Players versus League Overview terminology | Medium | S | Low |
| 12 | Standardize no-data, no-match, no-valid-result, gated, and service-error states | Medium | M | Low |
| 13 | Make Premium copy outcome-led without changing entitlement | Medium | S | Low |
| 14 | Move founder/developer billing diagnostics out of primary Premium narrative | Medium | S | Low |
| 15 | Audit touch targets and wrapping for chips and mobile sheets | Medium | S | Low |
| 16 | Standardize verbs: Open, View details, Add, Remove | Medium | S | Low |
| 17 | Restore focus consistently after quick views, sheets, and dialogs | Medium | M | Medium |
| 18 | Define heading levels and landmarks in shared components | Medium | M | Low |
| 19 | Add contrast tests for muted, warning, success, Premium, and disabled states | Medium | S | Low |
| 20 | Explain Startup Draft Center versus Draft Center at transition | Medium | S | Low |
| 21 | Preserve filter context between Players and Player Detail | Medium | M | Medium |
| 22 | Add result counts to long boards only where counts are already known | Low | S | Low |
| 23 | Consolidate CSS overrides after visual baselines exist | Low | L | Medium |
| 24 | Confirm non-obvious saved-state changes | Low | S | Low |
| 25 | Plain-language review of route subtitles | Low | S | Low |

## Top 10 cosmetic issues

1. “Fantasy GM” and “DynastyGM” branding is mixed.
2. Page subtitles vary substantially in length.
3. Status-chip wrapping can produce uneven header heights.
4. Card families use slightly different kicker/title/body rhythm.
5. Later CSS overrides make visual drift likely.
6. Optional tables depart from the card-first mobile language.
7. Repeated “available yet” fallbacks sound generic.
8. Test-mode warnings compete with Premium value.
9. Generic Back, View, and Remove labels vary in specificity.
10. Dense metadata can compete with the primary card title.

## Recommended implementation order

1. Validate first use, then add the post-import orientation pattern.
2. Standardize result-state explanations, starting with Trade Hub and Waivers.
3. Complete controlled responsive and accessibility testing.
4. Migrate only task-critical mobile tables to existing cards.
5. Clarify settings entry and Players/League Overview naming.
6. Refine Premium outcome copy after product policy is final.
7. Consolidate visual tokens only after screenshot baselines exist.

## Implementation decision

No UX change was implemented. The audit found no small correction with enough
browser evidence to justify consuming the one-change allowance. This avoids turning
unverified risks into product behavior. The proposed first implementation is the
post-import orientation panel, after controlled first-use validation.

`app.py` net change: zero lines. Production-code net change: zero lines.

## Remaining evidence gaps

- Controlled Free and Premium browser walkthroughs.
- Desktop, tablet, small-phone, and large-phone geometry.
- Browser back/forward and refresh observations beyond route tests.
- Screen-reader output and focus order.
- Measured contrast across all states.
- Active-draft and service-failure UX in a controlled environment.

These gaps define the evidence collection needed before implementing the roadmap.
