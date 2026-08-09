# App-wide dead-code / repository hygiene

| Field | Value |
| --- | --- |
| Baseline | `3c4f59d3e0c7f4daa6d9114fa759f9a49f134c55` (post-#192) |
| Scope | Proven-dead deletion + inventory documentation |
| Explicit non-changes | Football logic, valuations, rankings math, recommendation generation/order, Trust, auth, Stripe, Supabase, Sleeper, lifecycle, branding artwork |

## Audit method

1. Import/reference scan across `app.py`, `modules/`, `scripts/`, `tests/` (`scripts/audit_unused_modules.py`).
2. Selector/emitter cross-check for transitional and orphan CSS families.
3. Session-key sample via writers/readers (no bulk key deletion without integrity proof).
4. Feature-flag inventory from `modules/app_config.py` + env readers.
5. Route registry comparison: live `PLATFORM_DESTINATIONS` vs orphan planning metadata.
6. Script/harness duplicate review (retain dual-purpose tools).
7. Classification: **A** proven dead · **B** superseded but referenced · **C** compatibility shim · **D** active · **E** uncertain/dynamic.

Prior hygiene already removed `app_header.py`, `executive_visual_finalization_styles.py`, `executive_info_compression_styles.py`, and several orphan helpers (`docs/league-leaderboards-and-repo-cleanup.md`, `docs/transitional-ui-css-consolidation.md`).

## Import / reference map (summary)

| Bucket | Count / notes |
| --- | --- |
| Top-level `modules/*.py` before | 140 |
| After Class A module deletes | 138 |
| Unused-module scan hits before deletion | `age_model`, `news_factor` only |
| Live nav owner | `PLATFORM_DESTINATIONS` + `current_platform_destinations` |
| Orphan IA metadata removed | `CURRENT_PAGE_REGISTRY`, `current_primary_tabs`, `FUTURE_NAV_GROUPS`, section/migration planning tuples |

## Candidates considered

### Removed (Class A)

| Item | Why unused | Replacement | Proof |
| --- | --- | --- | --- |
| `modules/age_model.py` | Never imported; `age_penalty()` never called | `rankings.py` computes `age_penalty` column from age curve | Import scan + symbol grep |
| `modules/news_factor.py` | Never imported; `apply_news_factor()` never called | `rankings.py` zero-fills `news_factor` | Import scan + runtime architecture audit already noted stub |
| `CURRENT_PAGE_REGISTRY` + `current_primary_tabs` | Zero external callers; superseded by platform destinations | `PLATFORM_DESTINATIONS` | Grep across repo |
| `FutureNavGroup` / `SectionDefinition` / `DuplicateSectionAudit` / `MigrationPhase` + planning tuples | Defined only; never imported by app/tests/scripts | Historical docs | Grep across repo |
| Unused `app.py` imports of mobile destination helpers | Import-only in `app.py` | Tests import helpers directly from `ui_architecture` | AST usage count = 1 |

### Retained (with reason)

| Item | Class | Why retain |
| --- | --- | --- |
| Transitional `summary-tile` / `analysis-card` / `advice-card` / `prospect-card` / `home-command-card` | C | Live emitters in `workspace_ui` / `my_team_ui`; dual-class with `dg-ui-card` intentional |
| `concept-band` / `concept-chip` | Removed (#223) | Migrated to summary-tile |
| `dg-intel-*` / `dg-intelligence-*` | D | Canonical League Insights / News feed markup |
| Stacked CSS override modules + unify `::after` kill | C/D | Late unify depends on mid-layer; visual harness required before collapsing accents |
| Orphan-looking `.app-*` / `.dg-glass-panel` CSS | E | Asserted by visual identity tests even without markup emitters; not proven safe |
| `platforms/base.py` Protocol | E | Structural contract for adapters |
| `context_integrity` / archetype validation modules | B | Audit/experiment tooling |
| `stripe_webhook` | D | Separate service surface |
| All surveyed feature flags | D | Live readers |
| Dual marketing/screenshot/perf scripts | D | Different outputs or roles |
| Session keys incl. harness-only `visual_onboarding_dismissed` | C/D | Preserve #145/#149/#156 integrity; no write-only production key proven |
| Brand archives / Command Plate history | D | Intentional archive |
| `CareerProfile` model without HTML helper | C | Documented intentional |

## CSS ownership map

| Module | Owns |
| --- | --- |
| `app_styles.py` | Base APP_CSS body, ranked boards, transitional cards, shared chrome |
| `executive_command_header_styles.py` | Command bar geometry (injected separately) |
| `application_shell_styles.py` | Executive shell grid / identity |
| `executive_design_unify_styles.py` | Late neutralize accents / unify |
| `league_intelligence_styles.py` | News feed `.dg-intelligence-*` |
| `marketing_landing_styles.py` | Landing only (not in APP_CSS) |
| Others | Surface-scoped (dashboard, waivers, PQV, overlays, brand, primitives…) |

**Override chains eliminated this PR:** none (would require visual proof). Documented for follow-up: base colorful `::after` → mid-layer monochrome → unify `content:none` on transitional cards.

**Selectors removed this PR:** none (CSS bytes essentially flat; comment text only).

## Session-key inventory (summary)

No keys removed. Writers/readers for account, league, destination, scroll, news cache, and experimental surfaces remain active. Harness-only keys retained.

## Feature-flag inventory (summary)

| Flag family | Status |
| --- | --- |
| Experimental show + Decision Memory / GM Targets / Share Cards | Active |
| Launch analytics / Founder Ops / debug / perf / webhook | Active |
| Dead flags removed | **None** |

## Route inventory

| Registry | Status |
| --- | --- |
| `PLATFORM_DESTINATIONS` | Live |
| `CURRENT_PAGE_REGISTRY` / obsolete keys (`home_dashboard`, `free_agents`, `trade_ideas`, …) | Removed (planning-only; no handlers deleted) |
| Live route handlers | Unchanged |

## Script inventory

| Script | Status |
| --- | --- |
| CI harnesses / budget / mobile validation | Retain |
| Dual marketing/screenshot tools | Retain (different outputs) |
| `scripts/audit_unused_modules.py` | Added — reproducibility for unused-module scan |
| Obsolete scripts deleted | **None** |

## Asset inventory

No brand/marketing assets deleted. Archives remain intentional.

## app.py ownership notes

- Removed unused mobile destination imports only.
- No orchestration rewrite.
- Presentation wrappers left in place.

## Before / after metrics

| Metric | Before | After |
| --- | ---: | ---: |
| `modules/*.py` | 140 | 138 |
| Style modules (`*styles*.py`) | 25 | 25 |
| Files deleted | — | 2 (`age_model.py`, `news_factor.py`) |
| Planning symbols removed from `ui_architecture.py` | — | registries + 4 dataclasses + `current_primary_tabs` |
| Unused imports removed | — | 2 |
| Session keys removed | — | 0 |
| Feature flags removed | — | 0 |
| Routes/handlers removed | — | 0 (registry metadata only) |
| Scripts removed | — | 0 |
| APP_CSS bytes | ~424,469 | **424,482** (comment text only; no structural CSS cut) |
| Cold protobuf | ~519,054 | **519,067** |
| Warm protobuf | ~474,771 | **474,784** |
| Warm server ms | ~85–95 | **~76** (local) |

Performance ceiling remains 520,000 protobuf bytes. No provider calls or football recomputation. Delta is noise-level from comment edits, not CSS growth.

## Remaining intentional debt

1. Transitional card classes still dual-styled; collapse only with visual harness.
2. Neutralized `::after` accent chains still occupy CSS weight.
3. `.app-*` primitive CSS retained for test/contract coupling despite weak emitters.
4. Large `app.py` wiring surface remains (out of scope for rewrite).
5. Internal `league_intelligence*` names / nav group **INTELLIGENCE** remain for compatibility.
6. `platforms/base.py` unused Protocol retained as adapter contract.
