# League Leaderboards Modernization + Repository Cleanup

Presentation modernization and conservative hygiene after the long UI migration.

**Rollback boundary:** Revert this PR. No football logic, rankings math, valuations, Trust, auth, entitlements, Stripe, Supabase, or Sleeper semantics changed.

---

## Leaderboard modernization summary

### Surfaces updated

| Surface | Change |
| --- | --- |
| Power Rankings board | Executive ranked rows via `ranked_leaderboard_row_html` |
| Franchise Value board | Same ranked-row renderer (shared function) |
| Draft capital ranking board | Migrated to the same ranked-row helper |
| League Intelligence cards | Flat `dg-ui-card` articles; current-team accent |
| Team score details | Fixed accidental per-cell re-render loop; denser cards |
| CI harness `surface=league` | Now renders power board + intel cards (not only team-rank tiles) |

### Hierarchy contract

Each ranked row now reads:

1. **Rank**
2. **Team** (logo + name + owner)
3. **Primary metric** (score for the active board)
4. **Interpretation** (strategy · archetype)
5. **Secondary** (supporting ranks / health) — lower visual weight

### Current-team emphasis

One canonical treatment: `dg-ranked-row--current` / accent left rail (same idea as modal leaderboard highlights). Applied on Power/Franchise boards and intel cards when `current_roster_id` matches.

### Old UI removed

- Glowing / gradient `power-row` and `intel-card` chrome
- Purple→cyan `::after` accents on power rows
- Fill-track bars that competed with the primary metric
- Giant padded board boxes without a content max-width
- Legacy `app-top-league-*` header CSS (module already unused)

---

## Dead-code audit

### Files deleted

| File | Why dead | Evidence | Replacement |
| --- | --- | --- | --- |
| `modules/app_header.py` | Unused league-identity HTML | No production imports; shell tests assert absence | `application_shell.executive_workspace_shell_html` |
| `modules/executive_visual_finalization_styles.py` | Alias-only re-export | Zero importers | `executive_design_unify_styles` |
| `modules/executive_info_compression_styles.py` | Alias-only; explicitly not in `APP_CSS` | Only its own test imported it | `RECOMMENDATION_TRUST_CSS` |

### Functions / classes removed

| Symbol | Why | Replacement |
| --- | --- | --- |
| `explanation_panel_html` | Zero callers | `executive_trade_detail_html` |
| `informational_callout_html` / `render_informational_callout` | Product code unused | badges / empty states / content cards |
| `player_prestige_badge_html` | Test-only duplicate | `player_status_pill_html` + `status_badge_html` |
| `career_profile_html` | Never rendered in production dossier path | `career_resume_html` / `career_timeline_html` |

### Helpers consolidated

| Before | After |
| --- | --- |
| Ad-hoc `power-row` markup in League Overview + Draft Center | Shared `league_workspace_ui.ranked_leaderboard_row_html` |

### CSS selectors removed / flattened

- Removed orphan `.app-top-league-header` / avatar / copy / kicker / title / meta / actions-label rules
- Flattened `.power-board`, `.power-row`, `.intel-card` to executive surfaces (no glow/shadow/gradient boards)
- Hidden obsolete `.power-track` / `.power-fill` (no longer emitted)

### Session keys

No session keys removed. Harness-only `visual_onboarding_dismissed` left untouched (manual harness). `#145` state-integrity paths unchanged.

### Feature flags

| Class | Action |
| --- | --- |
| Active / experimental (`DYNASTYGM_EXPERIMENTAL_*`, billing, etc.) | **Retained** |
| Dead flags | **None found** — no removals |

### Scripts / harnesses

| Script | Status |
| --- | --- |
| `scripts/ui_validation_harness.py` | Retained; league surface expanded |
| `scripts/dashboard_visual_harness.py` | Retained; switched to executive shell |
| `scripts/capture_marketing_screenshots.py` / launch capture | Both retained (different outputs) |
| Historical audit docs | Retained |

---

## Hygiene counts (approx.)

| Metric | Before | After |
| --- | --- | --- |
| Python modules under `modules/` | 142 | 139 |
| Style-ish modules | 27 | 25 |
| Dead files removed | — | 3 |
| Dead helpers removed | — | 5 symbols |
| Shared ranked-row helper | 0 | 1 |

Exact line delta is reported in the PR diff.

---

## Performance

Measured via `scripts/check_founder_beta_performance_budget.py`:

| Metric | Before (#175) | After |
| --- | --- | --- |
| Cold protobuf | 519,704 | **517,384** |
| Warm protobuf | 475,309 | **472,989** |
| Warm server ms | ~75 | **~66** |

APP_CSS char length dropped ~2.3k (orphan header + flatter leaderboard + dead callout CSS).

---

## Remaining intentional legacy / debt

- `summary-tile` / `analysis-card` / `concept-chip` transitional classes still used widely (normalized by unify CSS, not structurally migrated).
- `team-rank-card` / team identity header chrome still transitional.
- Executive table disclosure still uses `st.dataframe` behind expanders (by design).
- `CareerProfile` dataclass remains as a future-safe model even though its HTML helper was removed.
- Stacked CSS layers in `APP_CSS` still overlap; further compression is a follow-up, not this PR.
- Dedicated standings board shipped in a follow-up (see `docs/league-standings-board-contract.md`).

---

## Regeneration / validation

```bash
python -m compileall -q app.py modules scripts tests
python -m pytest -q
python scripts/check_founder_beta_performance_budget.py
git diff --check
```

Browser: harness `surface=league` plus mobile validation suite.
