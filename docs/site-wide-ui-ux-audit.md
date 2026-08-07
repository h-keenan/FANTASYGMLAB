# Site-Wide UI/UX Consistency & Founder Beta Experience Audit (PR #167)

Presentation, copy, layout, interaction, and accessibility only.
**No football logic**, valuations, rankings, recommendation generation/scoring/ordering,
Trust, waiver/trade logic, auth, entitlements, Stripe, Supabase schema, Sleeper
semantics, lifecycle semantics, or business rules changed.

| Field | Value |
| --- | --- |
| Baseline | `b358b62e9b8b9006570d93b95b3468fbcc1eb8b2` (main after PR #166) |
| Harness | `scripts/validate_mobile_ui.py` + `scripts/ui_validation_harness.py` |
| Contract doc | this file |
| Scope | Fix P0/P1 (+ low-risk P2); document remaining debt |

---

## Success criterion

A new user can move through FantasyGM Lab on mobile or desktop without confusing
hierarchy, inconsistent terminology, dead interactions, giant unexplained spacing,
mismatched components, duplicate patterns, unclear actions, or framework leftovers
on audited primary routes.

---

## Screenshot matrix

CI / local Chromium captures via `python scripts/validate_mobile_ui.py`:

| Surface | Widths |
| --- | --- |
| dashboard, league, trade, my-team, waivers, navigation, live-draft, player-dossier | **320, 390, 430, 768, 1024, 1280, 1440, 1600, 1920** |
| Alerts dropdown open | same matrix |

Artifacts: `artifacts/ui-mobile/{surface}-{width}x844.png`, `alerts-inbox-open-{width}x844.png`.

Existing asserts (preserved / extended): horizontal overflow, ≥44px tap targets,
executive shell count, Alerts popover (not dialog), GM sheet scroll, trade avatar
size, **Immediate Action above Your Next Move**, **Alerts title (not Inbox)**.

---

## Top 25 UX issues found

| # | Issue | Severity | Status |
| ---: | --- | --- | --- |
| 1 | Today's Game Plan and Your Next Move competed as equal primary sections | P1 | **Fixed** — Next Move demoted when Game Plan present |
| 2 | Immediate Action buried below Intelligence / Next Move | P1 | **Fixed** — promoted above Next Move |
| 3 | Alerts chrome vs “Inbox” panel title inconsistency | P1 | **Fixed** — panel title **Alerts** |
| 4 | Waivers used raw `st.metric` (framework leak) | P1 | **Fixed** — executive metric tiles |
| 5 | Trade Analyzer used raw `st.metric` | P1 | **Fixed** — executive metric tiles |
| 6 | Responsive matrix missing 1280/1600/1920 for core surfaces | P1 | **Fixed** — harness widths extended |
| 7 | League Intelligence still abstract for first-time users | P2 | Deferred — keep name; caption already explains |
| 8 | FQA-001 native league switcher cohesion | P2 | Deferred (known FQA) |
| 9 | 320px dialog density (FQA-002) | P2 | Deferred |
| 10 | Notification Center sample/demo content in Founder Beta | P2 | Deferred — intentional until live activity |
| 11 | Players / My Team deferred `st.dataframe` disclosures | P2 | Keep — progressive disclosure, not primary chrome |
| 12 | Heavy `st.info` on empty/gate paths | P2 | Partial — empty-state primitive preferred going forward |
| 13 | Desktop long one-column stacks at 1920 | P2 | Deferred — no stretch-mobile redesign |
| 14 | GM Orb still reads slightly floating on some desktop widths | P2 | Deferred — preserve #144/#150 contracts |
| 15 | Value Change jargon on Trade Hub | P2 | Keep label; ordering semantics preserved (#126) |
| 16 | Decision Memory / What Changed overlap education | P2 | Contract clear; copy already distinct |
| 17 | Premium lock density on Free Dashboard | P2 | Preserve #161 activation |
| 18 | Experimental badge visual weight | P2 | Acceptable — labeled, not unlabeled |
| 19 | Loading copy “Loading league…” generic | P2 | Deferred |
| 20 | Support email / contact empty on Privacy | P2 | Marketing backlog |
| 21 | Portrait dark-on-dark edge cases | P2 | Deferred — canonical portrait retained |
| 22 | Icon-only controls without text on some sheets | P2 | Deferred |
| 23 | Duplicate legal footer + sidebar legal links | P2 | Deferred |
| 24 | Guest Premium billing “not configured” copy dense | P2 | Ops-gated; leave for launch ops |
| 25 | Chromium wall times ≫ server (harness overhead) | — | Not UX; noted for perf interpretation |

**P0 functional blockers found this pass:** none (Alerts remain clickable; no unusable overlays observed on fixture paths).

---

## Issues fixed vs deferred

### Fixed (this PR)

1. Dashboard hierarchy: Immediate Action before Your Next Move; Next Move secondary when Game Plan renders; clarifying caption.
2. Alerts panel title aligned to command-bar **Alerts** (remove customer “Inbox” noun in panel).
3. Waivers + Trade Analyzer metrics → `render_executive_metric_tiles` (existing executive chrome).
4. Mobile validator width matrix expanded; Alerts title + dashboard order asserts.

### Deferred

- League Intelligence rename decision
- FQA-001/002/004–006 polish
- Broad `st.info` → empty-state migration
- 1920 multi-column layout redesign
- Full WCAG certification claim

---

## Terminology map

| Preferred | Deprecated / colliding | Where | Recommendation |
| --- | --- | --- | --- |
| **Alerts** | Inbox (panel title) | Notification center | **Use Alerts** (done) |
| **Today's Game Plan** | — | Dashboard | Keep as primary “what now?” |
| **Your Next Move** | Competing primary with Game Plan | Dashboard | Keep noun; demote weight when Game Plan present (done) |
| **Immediate Action** | — | Dashboard urgency | Keep; place above Next Move (done) |
| **What Changed** | — | Transition history | Keep |
| **Decision Memory** | — | Premium experimental | Keep + Experimental label |
| **League Intelligence** | abstract | Dashboard + destination | Keep name; retain explanatory caption |
| **League Overview** | Rankings internal key | Nav | Keep customer label |
| **Value change** | Value delta | Trade Hub | Keep; do not imply sort key |
| **Player Quick View** | dossier slang internally | PQV | Keep customer name |
| **Trade Review** | — | Trade detail | Keep |
| **GM Targets** | — | Experimental | Keep + Experimental |

---

## Typography hierarchy contract

Reuse Founder Beta tokens (`docs/founder-beta-ui-hierarchy.md`):

| Level | Token | Role |
| --- | --- | --- |
| 1 | `--type-page-eyebrow-size` | Page eyebrow / Founder Beta |
| 2 | `--type-page-title` | Page title |
| 3 | `--type-body-explanation` | Page description |
| 4–5 | section eyebrow / `--type-section-title` | Section headers via `ui_primitives` weights |
| 6 | `--type-card-title` | Card titles |
| 7 | `--type-primary-metric` | Primary metrics |
| 8 | `--type-supporting-metadata` | Metadata |
| 9–10 | body / badge | Explanation + status |

Only eyebrows, section labels, and compact statuses use forced uppercase.
No new type system introduced.

---

## Spacing contract

Use `--space-2xs` … `--space-4xl` only. No one-off margin hacks in this PR.
Dashboard section rhythm remains token-backed in `dashboard_workflow_styles.py`.

---

## Card system

Customer-facing families stay specialized (recommendation, player, trade, waiver,
roster, league, history, target, notification, premium/lock, metrics).
Waivers/Trade Analyzer summary metrics now use executive table row cards instead
of Streamlit `st.metric`.

---

## CTA hierarchy

| Class | Pattern |
| --- | --- |
| Primary | Entitled recommendation / Game Plan CTAs |
| Secondary | Open Trade Hub / Waivers / workflow links |
| Tertiary | Expanders / progressive disclosure |
| Upgrade | Unlock with Premium |
| Navigation | Command bar + GM destinations |
| Disclosure | Deferred PQV / League Pulse |

No new primary-looking button clusters added.

---

## Overlay behavior

Preserve #144 / #150 / #153:

- Alerts = anchored popover, not dialog
- Z-order: nav → sheet → popover → modal
- GM hidden while Alerts open
- ≥44px targets

---

## Empty / loading / error rules

| State | Rule |
| --- | --- |
| Empty | Prefer `ui_primitives.empty_state_panel_html` — why empty, is it OK, next action |
| Loading | Scoped startup / switch acknowledgements; avoid global blocking loaders |
| Error | No stack traces; recoverable captions; Founder Ops may keep framework UI |

---

## Accessibility findings

| Check | Result |
| --- | --- |
| Tap targets ≥44px | Enforced in Chromium harness |
| Focus / keyboard | Native Streamlit + link cards retain native focus |
| Alerts region label | `aria-label='Alerts'` |
| Contrast | Tokenized surfaces; not a full WCAG audit claim |
| Icon-only gaps | Documented P2 |

---

## Legacy Streamlit findings

| Location | Before | After |
| --- | --- | --- |
| Waivers metrics | `st.metric` ×3 | Executive metric tiles |
| Trade Analyzer metrics | `st.metric` ×2 | Executive metric tiles |
| Players / My Team tables | `st.dataframe` in expanders | Keep (deferred disclosure) |
| Founder Ops | Framework UI allowed | Unchanged |

---

## Mobile / desktop interaction findings

| Width band | Finding |
| --- | --- |
| 320–430 | Shell height + Alerts geometry contracts retained; Immediate Action order fixed |
| 768–1024 | Command cells + Alerts width band retained |
| 1280–1920 | Now in automated matrix; no stretch-mobile card redesign |

---

## Performance / protobuf guard (PR #166)

No broad new global CSS. Metric tiles reuse existing executive table styles.
Scoped Game Plan CSS unchanged.

| Measure | Baseline (#166) | This PR | Budget |
| --- | ---: | ---: | ---: |
| Cold protobuf | 512141 | 512141 | ≤520000 |
| Warm protobuf | 469370 | 469370 | ≤520000 |
| Warm server ms | ~69–76 | 76.0 | ≤750 |
| Cold server ms | — | 1477.3 | ≤2500 |

`scripts/check_founder_beta_performance_budget.py`: **PASS**. No protobuf regression.

---

## `app.py` impact

- Waivers summary metrics → `executive_table_ui.render_executive_metric_tiles`
- Trade Analyzer send/receive metrics → same helper
- No football / ranking / entitlement logic edits

---

## Remaining UI debt

1. League Intelligence naming research
2. FQA polish list (switcher, 320 dialogs, harness history)
3. Broader `st.info` → empty-state migration
4. Desktop multi-column densification at ≥1600 without redesign
5. Authenticated visual regression with live leagues
6. Full accessibility audit pass

---

## Rollback boundary

Revert the PR #167 merge commit. Restores Inbox panel title, prior Dashboard section
order/weights, and `st.metric` on Waivers/Trade Analyzer. No schema or football rollback.
