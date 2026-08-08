# Experimental Feature Inventory and ROI Audit

**Repository baseline:** `h-keenan/FANTASYGMLAB`, `main` at `1bd73973c6e0ce48991bc269415b13dfb89d8fe3`

**Audit date:** 2026-08-02

**Scope:** static repository evidence only; no feature was enabled, registered, completed, removed, or rewired.

<!-- experimental-routes: players, player_detail, teams, weekly_report, trade_analyzer, live_draft, news, archetypes, manager_tendencies -->

## Executive decision

The repository contains **20 unfinished or restricted capabilities**: 11 are meaningful product implementations, five are partial product foundations, and four are development/roadmap capabilities rather than shippable features. The highest return is not a new valuation lens or platform integration. It is completing the **read-only Live Draft assistant**: it has substantial deterministic logic and tests, solves a time-sensitive workflow, and can remain safely read-only.

The next-best opportunities are Draft Center consolidation, the hidden Weekly Report, and exposing the already-built Player Explorer after focused validation. ESPN, notifications, historical analytics, and achievement credentials are constrained by data or operations rather than UI effort. The legacy Player Detail route should be retired in favor of canonical Player Quick View; no implementation is recommended in this audit.

### Count summary

| Measure | Count | Definition |
|---|---:|---|
| Total capabilities inventoried | 20 | Distinct user-facing concepts or development capabilities with repository evidence |
| Currently user-visible | 7 | Reachable in normal Founder Beta flows, including partial/placeholder presentation |
| Feature-flagged | 11 | Nine experimental routes plus UI diagnostics and runtime diagnostics |
| Dormant | 6 | No normal production entry point or only a roadmap/placeholder surface |
| Meaningful automated tests | 14 | Dedicated tests or substantial contract coverage, not incidental imports |
| Depend on unavailable/unreliable data | 7 | External feed, history, credentials, ESPN private access, or incomplete production fields |

Counts overlap: a capability can be visible and incomplete, or dormant and tested.

## Evidence and estimation method

The navigation registry is authoritative for route exposure. `modules/ui_architecture.py` defines nine `EXPERIMENTAL` destinations; `_destination_visible()` exposes them only when `DYNASTYGM_SHOW_EXPERIMENTAL` is true. `render.yaml` keeps that flag false. Route bodies in `app.py` prove whether a hidden destination is actually wired. Imports, adapters, persistence boundaries, and dedicated tests establish readiness.

“Implementation percentage” is a repository-readiness estimate, not elapsed engineering effort. Each estimate uses five gates: domain/data path (25%), usable UI (20%), route/workflow integration (15%), meaningful tests (20%), and mobile/operational readiness (20%). Partial gates receive partial credit; the evidence is stated per feature. Estimates intentionally use five-point increments and should not be read as precision forecasts.

### Priority rubric

All raw dimensions are scored 1–5. For benefits, 5 is best. For **maintenance cost** and **technical risk**, 5 means costly/risky. For **time to ship**, 5 means fastest. The transparent weighted score is:

`20% user value + 15% differentiation + 12% readiness + 10% revenue + 15% retention + 10% data reliability + 5% mobile suitability + 8% time to ship + 3% inverse maintenance cost + 2% inverse technical risk`.

This produces a 0–100 priority score. It is a decision aid, not a market forecast. Revenue and retention scores are product hypotheses because the repository contains no conversion analytics.

Abbreviations below: **UV** user value, **DIFF** differentiation, **READY** implementation readiness, **REV** revenue potential, **RET** retention potential, **MAINT** maintenance cost, **RISK** technical risk, **DATA** data reliability, **MOB** mobile suitability, **SHIP** time to ship.

## Complete inventory and scores

| # | Capability | Completion evidence | UI / data / tests | Classification | UV | DIFF | READY | REV | RET | MAINT | RISK | DATA | MOB | SHIP | Priority |
|---:|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | Live Draft read-only assistant | 75%: full state, boards, recommendations, route and tests; production validation remains | Hidden experimental route; Sleeper draft APIs; strong dedicated tests | Ship for Founder Beta | 5 | 5 | 4 | 4 | 5 | 3 | 3 | 4 | 4 | 4 | 89.0 |
| 2 | Draft Center / rookie workspace | 85%: visible route, posture, picks, partner cards, assistant; fragmented modes remain | Visible; Sleeper plus local player/pick models; strong tests | Ship for Founder Beta | 5 | 4 | 5 | 4 | 5 | 3 | 2 | 4 | 4 | 4 | 88.8 |
| 3 | Startup Draft Center | 90%: conditional route, live/manual draft context, grading and completed review | Visible only for startup leagues; Sleeper; strong tests | Ship for Founder Beta | 4 | 4 | 5 | 4 | 4 | 3 | 2 | 4 | 4 | 4 | 81.8 |
| 4 | Player Explorer route | 90%: shared explorer, search, picks, filters, Quick View, detailed table | Hidden experimental route; stable local/league data; broad UI tests | Ship for Founder Beta | 5 | 3 | 5 | 3 | 4 | 2 | 1 | 5 | 5 | 5 | 86.4 |
| 5 | Weekly League Report | 70%: complete renderer and route, but narrow current-week evidence and hidden exposure | Hidden route; cached league summary; dedicated UI tests | Finish immediately after Founder Beta | 4 | 4 | 4 | 3 | 5 | 3 | 2 | 3 | 4 | 4 | 78.4 |
| 6 | Trade Analyzer | 80%: exact-package builder, ownership checks, picks, fit evaluation and profile links | Hidden route; existing league/trade data; broad indirect coverage | Validate with users before building | 4 | 3 | 4 | 4 | 3 | 4 | 3 | 4 | 3 | 3 | 69.8 |
| 7 | Teams workspace | 75%: route delegates to mature League Overview team sections; separate purpose remains unclear | Hidden route; shared league context; workspace tests | Validate with users before building | 3 | 2 | 4 | 2 | 3 | 3 | 2 | 4 | 4 | 4 | 62.4 |
| 8 | Manager Tendencies | 65%: classifier, evidence thresholds, table/detail UI and Trade Hub enrichment exist | Hidden route; requires sufficient transaction history; tests cover maturity/UI | Keep experimental | 4 | 5 | 3 | 4 | 4 | 4 | 4 | 2 | 3 | 2 | 70.4 |
| 9 | League Intelligence extensions | 70%: production feed, league ownership context, disclosures and action labels exist; alerting/history do not | Core feed visible; RSS/Sleeper data varies; strong tests | Finish immediately after Founder Beta | 5 | 5 | 4 | 4 | 5 | 4 | 3 | 3 | 4 | 3 | 84.8 |
| 10 | Roster News legacy route | 75%: RSS fetch/cache, roster matching and League Intelligence rendering exist | Hidden route; external RSS reliability; strong intelligence tests | Archive or remove | 3 | 2 | 4 | 2 | 3 | 4 | 3 | 2 | 4 | 4 | 57.4 |
| 11 | ESPN experimental import | 45%: adapter, mapping diagnostics, session review UI; downstream pages deliberately gated | Visible at import; private cookies/external library; dedicated adapter/UI tests | Keep experimental | 4 | 4 | 2 | 4 | 4 | 5 | 5 | 2 | 3 | 1 | 62.4 |
| 12 | Experimental valuation archetypes | 60%: protocol, frozen models, CLI and isolated Contender transformation; intentionally no registry/UI | Offline only; deterministic fixtures; extensive tests | Keep experimental | 4 | 5 | 3 | 4 | 4 | 5 | 5 | 3 | 4 | 1 | 70.8 |
| 13 | Archetypes comparison route | 55%: current league archetype presentation exists, but only Balanced may affect production | Hidden route; current league metrics; workspace/archetype tests | Archive or remove | 2 | 2 | 3 | 2 | 2 | 3 | 3 | 4 | 4 | 4 | 52.6 |
| 14 | AI-style Player Explainer | 70%: deterministic narrative helper and controls exist; no model/API is used | Inside hidden Players route; existing valuation fields; limited direct tests | Validate with users before building | 3 | 3 | 4 | 3 | 3 | 2 | 2 | 4 | 4 | 4 | 68.0 |
| 15 | Career credentials / achievement badges | 25%: frozen presentation model and safe renderer, but only an empty placeholder has real data | Placeholder visible in Quick View; no credential source; renderer tests | Validate with users before building | 3 | 4 | 2 | 3 | 3 | 3 | 4 | 1 | 4 | 2 | 55.6 |
| 16 | Notifications and news alerts | 10%: premium roadmap copy and feed primitives only; no subscription, delivery, durable events or worker | Mentioned to users as future; no service/data contract; no feature tests | Validate with users before building | 4 | 4 | 1 | 4 | 5 | 5 | 5 | 2 | 4 | 1 | 64.0 |
| 17 | Historical league/player intelligence | 30%: maturity gates and historical-only safety exist, but durable snapshots and adequate history do not | Partial withheld labels; missing source depth; maturity/safety tests | Foundational work only, not user-facing | 5 | 5 | 2 | 4 | 5 | 5 | 5 | 1 | 3 | 1 | 70.4 |
| 18 | Legacy Player Detail route | 65%: functional route but duplicates canonical Player Quick View dossier and navigation contract | Hidden route; existing player data; Quick View has stronger tests | Archive or remove | 2 | 1 | 3 | 1 | 1 | 4 | 2 | 5 | 3 | 5 | 47.0 |
| 19 | Prospect watchlist | 55%: My Team renderer and 2027 labels exist; it is a static positional shortlist rather than a persisted watchlist | Visible under advanced roster detail; local prospect fields; UI tests | Validate with users before building | 3 | 3 | 3 | 3 | 3 | 3 | 3 | 2 | 4 | 3 | 59.0 |
| 20 | Developer/runtime diagnostics | 90%: auth/UI/performance/runtime flags, sanitized traces, scripts and tests exist | Env-gated; production-safe when off; extensive tests | Foundational work only, not user-facing | 2 | 2 | 5 | 1 | 2 | 2 | 2 | 5 | 2 | 5 | 58.0 |

Scores were recomputed with `python scripts/audit_experimental_features.py`; the script also proves that every currently registered experimental route is represented.

## Feature dossiers

### 1. Live Draft read-only assistant

- **Problem / user:** dynasty managers need an on-clock view of available players, positional runs, team needs, recent picks, and their next selection. The target is a Sleeper manager drafting live.
- **Evidence / entry points:** `modules/live_draft.py` builds deterministic draft state, available pools, rankings, team boards and recommendations; `modules/live_draft_ui.py` renders the route wired at `app.py`’s `live_draft` branch. It is excluded from the normal GM Orb by the experimental flag.
- **Data / tests:** reads Sleeper drafts and picks with an eight-second request timeout, then combines cached player and roster data. `tests/test_live_draft.py` and `tests/test_live_draft_rankings.py` cover discovery, state, ranks, ordering and failure preservation.
- **Blockers / implications:** validate real active, paused, completed, rookie and startup rooms; define refresh cadence and degraded-state behavior. It needs authenticated league context but no new entitlement. It is mobile-oriented but browser evidence for an active draft is still needed.
- **Risk / maintenance / impact:** Sleeper API drift and draft-state polling are the main costs. Read-only behavior contains security risk. This is differentiated from static rankings because context changes pick by pick. Expected frequency is seasonal and intense; conversion/retention impact is plausibly high during draft windows; the on-clock board is a credible wow moment.
- **Effort:** Founder Beta 1–2 weeks; production 3–5 weeks including live-room operational validation and monitoring.

### 2. Draft Center / rookie workspace

- **Problem / user:** managers need current pick posture, owned capital, likely partners, remaining prospects and decision support in one draft workspace.
- **Evidence / entry points:** `modules/draft_center_ui.py` contains the visible `draft_summary` surface, posture, decision cards, partner cards, draft assistant and ownership tables; `modules/draft_assistant.py` handles draft selection, manual marks, pick grading and remaining pools.
- **Data / tests:** Sleeper league drafts/picks plus normalized player values. Dedicated draft-center and assistant tests are extensive.
- **Blockers / implications:** two overlapping concepts—rookie Draft Center and live assistant—need one lifecycle and clearer handoff. Authentication and league context already exist; no entitlement change is necessary. Mobile components exist but dense fallback tables remain.
- **Risk / maintenance / impact:** medium Sleeper lifecycle maintenance. Expected use is high in rookie-draft season and intermittent year-round for capital planning. It can retain serious dynasty users; the partner/posture view is a moderate wow moment.
- **Effort:** Founder Beta 1 week consolidation; production 2–4 weeks for complete draft-state validation.

### 3. Startup Draft Center

- **Problem / user:** a new-league manager needs useful guidance before rosters exist.
- **Evidence / entry points:** the visible conditional `startup_draft_center` route calls `render_startup_draft_center`; startup detection, manual/live drafted state and completed-round review are implemented and tested.
- **Data / tests:** Sleeper draft metadata/picks and player rankings; strong `test_draft_assistant.py` and Startup Coordinator coverage.
- **Blockers / implications:** edge cases around missing draft IDs, stale draft states and transition into normal roster mode. Existing auth/entitlement behavior is sufficient. Mobile readiness is good but real startup-room browser evidence is limited.
- **Risk / maintenance / impact:** seasonal, lower frequency than core pages but strategically strong onboarding for new leagues. It differentiates DynastyGM before roster construction and can create a wow moment.
- **Effort:** Founder Beta under 1 week validation; production 2–3 weeks.

### 4. Player Explorer route

- **Problem / user:** managers need fast cross-player and pick discovery with filters and canonical dossier access.
- **Evidence / entry points:** the hidden `players` route calls `player_asset_explorer_ui.render_player_asset_explorer`, supports picks and search, and defers a detailed table and deterministic explainer.
- **Data / tests:** local normalized player data plus league draft assets; strong explorer, Quick View, asset, mobile and navigation coverage.
- **Blockers / implications:** validate why it remains hidden and distinguish it from League Overview. Public use may expose a limited no-league mode; entitlement behavior must remain explicit. It is already mobile-designed.
- **Risk / maintenance / impact:** low incremental maintenance because canonical Football Asset and Quick View are reused. Expected frequency is high; it improves retention more than direct conversion. Visual player/pick discovery is a moderate wow moment.
- **Effort:** Founder Beta 2–4 days of product/browser validation; production 1–2 weeks.

### 5. Weekly League Report

- **Problem / user:** returning managers need a concise “what changed” briefing.
- **Evidence / entry points:** `modules/weekly_report_ui.py` renders highlights, rank movement, trends and transactions; the hidden `weekly_report` route constructs it from shared league context.
- **Data / tests:** current team summaries and maturity-gated evidence. `tests/test_weekly_report_ui.py` covers empty and populated rendering.
- **Blockers / implications:** without durable snapshots, “weekly” can overpromise historical movement. Authentication/league context is required; no new entitlement is implied. Mobile presentation is compact.
- **Risk / maintenance / impact:** data semantics, not UI, are the blocker. Expected weekly frequency and retention impact are high if genuine changes can be proven. A credible personalized briefing is a wow moment.
- **Effort:** Founder Beta 1–2 weeks with honest current-state language; production 4–8 weeks if durable comparisons are required.

### 6. Trade Analyzer

- **Problem / user:** users with a specific offer need exact package valuation and partner-fit review.
- **Evidence / entry points:** the hidden `trade_analyzer` route builds send/receive packages, enforces a single partner, supports picks, calculates fit, and links player profiles.
- **Data / tests:** existing valuation, ownership, picks and team context. Trade invariants have broad coverage, but the builder lacks a dedicated end-to-end test suite comparable with Trade Hub.
- **Blockers / implications:** validate demand and avoid confusing it with Trade Hub discovery. It requires authenticated league data; Premium positioning is a product decision, not a technical need. Mobile builder density needs focused validation.
- **Risk / maintenance / impact:** high interaction/state maintenance and potential perceived contradiction with recommended trades. Frequency is medium; revenue potential is plausible but unsupported by analytics. Exact package evaluation is useful, not uniquely wow-inducing.
- **Effort:** Founder Beta 2–3 weeks; production 4–6 weeks.

### 7. Teams workspace

- **Problem / user:** managers want opponent roster, direction, assets and trade-partner context.
- **Evidence / entry points:** hidden `teams` maps into the mature shared League Overview branch and forces the Teams section; `modules/league_workspace_ui.py` supplies team cards and manager context.
- **Data / tests:** shared league context, roster profiles and current ranks; workspace tests cover renderers.
- **Blockers / implications:** it substantially overlaps League Overview and My Team, so the missing work is information architecture rather than code. Standard auth and league scope apply. Mobile is supported by shared components.
- **Risk / maintenance / impact:** a separate route increases navigation and duplicate-presentation cost. Frequency is medium. Validate with users before treating it as a destination.
- **Effort:** Founder Beta 1–2 weeks; production 2–3 weeks if research supports separation.

### 8. Manager Tendencies

- **Problem / user:** trade initiators need evidence about counterpart preferences and activity.
- **Evidence / entry points:** app classifiers produce trading style, roster philosophy, asset behavior and activity; the hidden route renders table/detail views and Trade Hub already consumes summaries.
- **Data / tests:** league transaction history governed by `league_maturity` evidence thresholds. Maturity, workspace and Trade Hub tests exist.
- **Blockers / implications:** new or quiet leagues cannot support claims. No auth/entitlement change is required, but privacy-safe wording and provenance matter. Dense tables are not fully mobile-first.
- **Risk / maintenance / impact:** high differentiation and wow potential, but also high trust risk if labels appear causal or certain. Expected frequency is medium within trade workflows.
- **Effort:** Founder Beta 3–5 weeks of data-quality review; production 6–10 weeks with historical coverage.

### 9. League Intelligence extensions

- **Problem / user:** raw news should answer why an event matters to this league and what to do.
- **Evidence / entry points:** `modules/league_intelligence.py` and `league_intelligence_ui.py` provide chronological items, ownership relevance, presentation recommendations, disclosure and canonical player interaction. The production Dashboard/news experience already uses this foundation.
- **Data / tests:** RSS headlines, Sleeper roster updates and league ownership. Contract, UI, visual-harness and feed tests are strong.
- **Blockers / implications:** richer alerts, watchlists and longitudinal significance need durable events and more reliable sources. Existing auth/entitlement is sufficient for the feed; push delivery would introduce new privacy/operations obligations. Mobile readiness is high.
- **Risk / maintenance / impact:** external feed quality and editorial confidence are ongoing costs. Expected daily/weekly frequency and retention are high. League-specific “why it matters” is differentiated and can be a wow moment.
- **Effort:** Founder Beta 1–2 weeks for feed refinements; production extensions 4–8 weeks.

### 10. Roster News legacy route

- **Problem / user:** roster-specific headlines and Sleeper status changes.
- **Evidence / entry points:** `modules/news.py` fetches/caches RSS and player searches; `modules/my_news.py` filters, ranks and summarizes; hidden `news` renders the newer League Intelligence feed.
- **Data / tests:** unauthenticated RSS/Google News and Sleeper status, with disk cache; intelligence tests cover presentation more than provider reliability.
- **Blockers / implications:** it overlaps the Dashboard intelligence feed and creates a duplicate destination. External URL/content safety is handled, but provider stability and request volume remain concerns.
- **Risk / maintenance / impact:** medium maintenance with low standalone differentiation. Archive the route, not necessarily the reusable ingestion code.
- **Effort:** Founder Beta removal decision 1–2 days; a production standalone page is not recommended.

### 11. ESPN experimental import

- **Problem / user:** ESPN managers need roster import rather than switching platforms.
- **Evidence / entry points:** `modules/platforms/espn.py` maps leagues, teams and players; `modules/platform_import_ui.py` provides experimental public/private import and diagnostics. Trade Hub/Waivers explicitly fail closed in ESPN limited mode.
- **Data / tests:** ESPN API/library plus SWID and ESPN_S2 for private leagues; adapter/UI tests cover mapping and sanitization.
- **Blockers / implications:** private credentials, platform API volatility, incomplete transactions/free agents/drafts and no full downstream parity. Credentials must remain session-confined and never logged. Mobile import forms exist but the workflow is not production-ready.
- **Risk / maintenance / impact:** high acquisition reach but high security and adapter maintenance. It could improve conversion for ESPN users but lacks evidence. The import itself is not a wow moment; parity is.
- **Effort:** Founder Beta 4–6 weeks for controlled limited support; production 10–16 weeks plus ongoing maintenance.

### 12. Experimental valuation archetypes

- **Problem / user:** managers may want a valuation philosophy matched to competitive window.
- **Evidence / entry points:** frozen experiment models, validation/comparison harnesses, CLI, fixtures and `contender_archetype_experiment.py` exist. Production registry intentionally contains only `balanced_dynasty`; no selector or profile persistence exists.
- **Data / tests:** synthetic deterministic fixtures and current valuation fields; extensive protocol and Contender tests.
- **Blockers / implications:** no real shadow/user evidence establishes better decisions. Production exposure would affect every value surface and entitlement expectations. Mobile UI is not the blocker; product validity is.
- **Risk / maintenance / impact:** high differentiation/revenue hypothesis and wow potential, but highest trust and coherence risk. Keep experimental until external evidence exists.
- **Effort:** Founder Beta exposure is not recommended; a production candidate needs 8–16+ weeks of shadow validation before an exposure PR.

### 13. Archetypes comparison route

- **Problem / user:** explain roster shape and active valuation philosophy.
- **Evidence / entry points:** hidden `archetypes` maps to a League Overview section; workspace presentation already shows descriptive roster archetypes and the only production valuation archetype.
- **Data / tests:** current roster metrics; workspace and registry tests.
- **Blockers / implications:** a full destination implies choice that does not exist. It overlaps metric explanations and the shell. Archive the standalone route while retaining concise contextual explanations.
- **Effort:** 1–2 days to make the future decision; no production build recommended now.

### 14. AI-style Player Explainer

- **Problem / user:** explain why DynastyGM values a player under current league and strategy context.
- **Evidence / entry points:** `modules/chat.py` is a deterministic templating/rules helper called from a deferred expander in the hidden Players route. Despite the module name, there is no model provider, key, network request or generative AI.
- **Data / tests:** existing value, tier, scarcity, opportunity, age, injury and news-factor fields. Escaping and general player UI are tested; explanation quality has limited dedicated coverage.
- **Blockers / implications:** the “AI” framing would be misleading; copy must expose deterministic evidence and Trust boundaries. No auth/entitlement or external service is required. Mobile fit is good as a disclosure.
- **Risk / maintenance / impact:** low technical risk, medium product value, modest differentiation. Expected frequency is medium; it can build trust but is not presently a strong wow moment.
- **Effort:** Founder Beta 1 week; production 2–3 weeks of explanation/edge-case review.

### 15. Career credentials / achievement badges

- **Problem / user:** a dossier should quickly communicate verified career distinction and season highlights.
- **Evidence / entry points:** `CareerProfile` is a frozen model and `career_profile_html()` safely renders achievements/highlights; the production dossier passes an empty profile and shows placeholder copy.
- **Data / tests:** no credential provider or normalized achievement dataset. Renderer/future-content tests exist.
- **Blockers / implications:** source licensing, player identity matching, recency/correction and completeness. No auth issue; data provenance and false accolade risk are material. Mobile component is ready but empty content is not value.
- **Risk / maintenance / impact:** attractive visual wow potential but poor current data reliability. Validate demand/source before building.
- **Effort:** Founder Beta 3–6 weeks after a verified source; production 8–12 weeks including ingestion and corrections.

### 16. Notifications and news alerts

- **Problem / user:** time-sensitive injuries, waivers and trades should reach managers without an open session.
- **Evidence / entry points:** Premium roadmap copy names alerts and intelligence primitives produce candidate events, but there is no notification model, subscription UI, worker, durable event ID, delivery provider or tests.
- **Data / tests:** depends on external news/Sleeper freshness. No end-to-end capability exists.
- **Blockers / implications:** opt-in/opt-out, rate limiting, quiet hours, duplicate suppression, delivery failure, privacy, provider cost and mobile destination links. Authentication and entitlement would require explicit design.
- **Risk / maintenance / impact:** potentially high retention and revenue, but high operational burden and false-urgency risk. This is high-risk/high-reward, not a quick win.
- **Effort:** Founder Beta prototype 4–8 weeks; production 10–16 weeks plus service operations.

### 17. Historical league/player intelligence

- **Problem / user:** managers need trends, change detection, transaction patterns and historical value context.
- **Evidence / entry points:** `league_maturity.py` gates claims until evidence exists, weekly/manager surfaces contain withheld states, and Trust supports historical-only display. The performance architecture doc explicitly identifies versioned historical snapshots as future data.
- **Data / tests:** no complete durable player-value/league-event snapshot store. Maturity and safety behavior are tested.
- **Blockers / implications:** source/version identity, backfill, corrections, storage growth, missing weeks and privacy retention policy. It is foundational and should not be marketed until completeness is measurable.
- **Risk / maintenance / impact:** very high strategic differentiation and retention potential, equally high data/operations cost. Historical trend credibility can be a major wow moment.
- **Effort:** Founder Beta foundation 6–10 weeks; production 12–24 weeks depending on backfill.

### 18. Legacy Player Detail route

- **Problem / user:** full player detail outside modal context.
- **Evidence / entry points:** hidden `player_detail` calls `render_player_detail_page`, while every migrated production asset opens the canonical Player Quick View dossier with preserved return context.
- **Data / tests:** both use existing player/league data; the dossier has extensive dedicated coverage and canonical modal behavior.
- **Blockers / implications:** duplicate entry/state/rendering paths create drift and maintenance. No unique user need was found. Archive/remove only in a separate behavior-reviewed PR.
- **Effort:** 2–4 days to prove no remaining consumer and remove safely; no completion effort recommended.

### 19. Prospect watchlist

- **Problem / user:** managers need to remember prospects aligned with roster needs.
- **Evidence / entry points:** `my_team_ui.render_prospect_watchlist()` renders a need-filtered 2027 shortlist in advanced My Team content, but it is not user-editable or persisted.
- **Data / tests:** current prospect rows/source labels; focused My Team rendering tests. Prospect completeness and future class stability are not established.
- **Blockers / implications:** decide whether “watchlist” means a saved user preference or an automatically generated list. Persistence would affect profiles but should not require a new schema without review. Mobile cards exist.
- **Risk / maintenance / impact:** medium seasonal value and moderate retention. Validate before adding persistence.
- **Effort:** Founder Beta 2–3 weeks; production 4–6 weeks with data and persistence contracts.

### 20. Developer/runtime diagnostics

- **Problem / user:** operators need safe auth, UI, performance, eligibility and end-to-end timing evidence.
- **Evidence / entry points:** `DYNASTYGM_DEBUG_AUTH`, `DYNASTYGM_DEBUG_PERF`, `DYNASTYGM_DEBUG_UI`, `DYNASTYGM_RUNTIME_TRACE`, dev reload and dev-destination flags gate diagnostics; trace summarizers/profilers and privacy-focused tests exist.
- **Data / tests:** sanitized local/server timings and structural diagnostics; extensive performance/runtime tests.
- **Blockers / implications:** never make this a customer feature, never log identifiers/secrets, and keep all flags off by default. It has low mobile relevance and no conversion value, but high engineering leverage.
- **Effort:** ongoing foundational maintenance; no user-facing production milestone.

## Ranked top ten

Priority scores provide the initial order; product dependencies refine the recommendation.

1. **Live Draft assistant (89.0)** — best discrete next implementation and strongest differentiated workflow.
2. **Draft Center (88.8)** — nearly complete, visible, and high-value; consolidate its lifecycle.
3. **Player Explorer (86.4)** — closest quick ship, but less differentiated than Live Draft.
4. **League Intelligence extensions (84.8)** — high-frequency retention surface; provider quality constrains expansion.
5. **Startup Draft Center (81.8)** — already strong; finish validation rather than add scope.
6. **Weekly League Report (78.4)** — valuable recurring briefing once time semantics are honest.
7. **Experimental valuation archetypes (70.8)** — valuable research, not production-ready.
8. **Manager Tendencies (70.4)** — highly differentiated, gated by real history and trust.
9. **Historical intelligence foundation (70.4)** — unlocks multiple products but is not a Founder Beta feature.
10. **Trade Analyzer (69.8)** — meaningful but should pass demand testing before another trade surface ships.

Player Explorer outranks Live Draft numerically on speed/reliability, but Live Draft is the recommended next implementation because it has a narrow read-only boundary, stronger strategic differentiation, and a time-sensitive end-to-end workflow worth validating now.

## Quick wins

- Validate and expose Player Explorer without changing its football logic.
- Consolidate Draft Center labels and lifecycle handoffs between rookie, startup and live contexts.
- Reframe the deterministic Player Explainer as an evidence explanation, not AI.
- Keep League Intelligence feed improvements inside the existing destination rather than exposing the legacy News route.
- Decide and document retirement of the redundant Archetypes and legacy Player Detail routes.

## High-risk / high-reward

- **Historical intelligence:** largest long-term data moat; highest storage, provenance and backfill burden.
- **Manager Tendencies:** compelling negotiation context; unacceptable if evidence is sparse or labels imply certainty.
- **Experimental archetypes:** potentially monetizable differentiation; can damage trust across every numerical surface.
- **ESPN support:** large addressable workflow hypothesis; private-cookie handling and adapter parity create permanent cost.
- **Notifications:** recurring engagement potential; requires reliable events, delivery infrastructure and privacy controls.

## Archive candidates

1. **Legacy Player Detail route** — canonical Player Quick View supersedes it.
2. **Standalone Archetypes route** — only one production valuation archetype exists; explanatory context already has a home.
3. **Standalone roster News route** — League Intelligence is the stronger product contract and already consumes the same feed.
4. **Obsolete current-page registry** — removed in the app-wide hygiene pass after confirming zero tooling consumers (`PLATFORM_DESTINATIONS` is the live registry). See `docs/app-wide-dead-code-repository-hygiene.md`.

“Archive” means prove consumers and remove in a separate PR. This audit deletes nothing.

## Dependency map

```text
Normalized public players ─┬─> Player Explorer ──> Player Quick View
                           ├─> Draft Center ─────┬─> Startup Draft Center
                           │                    └─> Live Draft + Sleeper draft state
                           ├─> Career credentials (blocked: verified credential source)
                           └─> Historical player intelligence (blocked: versioned snapshots)

Sleeper league context ────┬─> Teams / Trade Analyzer
                           ├─> Manager Tendencies (blocked: sufficient transaction history)
                           ├─> Weekly Report (blocked: durable comparison windows)
                           └─> League Intelligence ──> Notifications
                                                    (blocked: durable events + delivery)

Balanced valuation engine ──> isolated archetype protocol ──> Contender experiment
                              (separate explicit approval required for any exposure)

ESPN adapter + credentials ──> mapping review ──> parity contracts
                              (blocked: transactions, waivers, drafts, operational support)
```

## Three-phase roadmap

### Phase 1 — Founder Beta: finish safe, observable workflows

1. Complete production validation of the read-only Live Draft assistant.
2. Consolidate Draft Center/startup/live handoffs without changing calculations.
3. Validate and expose Player Explorer.
4. Retain League Intelligence in its current destination; retire duplicate route decisions.

Exit criteria: mobile browser evidence, degraded-state tests, no write paths, explicit data freshness, and supportable operational telemetry.

### Phase 2 — Immediately after Founder Beta: recurring intelligence

1. Establish versioned, privacy-reviewed league/player snapshots.
2. Make Weekly Report comparisons time-correct.
3. Validate Manager Tendencies only in leagues that pass evidence thresholds.
4. User-test Trade Analyzer and prospect watchlist before persistence or entitlement decisions.

Exit criteria: measured history completeness, provenance, correction policy, and user evidence that separate destinations reduce decision time.

### Phase 3 — Validate before investment

1. Run archetype shadow studies; do not expose a selector without a separate approval PR.
2. Decide ESPN support only after support-cost and credential-risk review.
3. Evaluate notification delivery only after durable events are reliable.
4. Source career credentials only with verified licensing/provenance.

Exit criteria: product evidence, operational owner, privacy review, rollback, and support budget.

## One recommended next implementation

**Finish and production-validate the read-only Live Draft assistant.**

Keep it Sleeper-only and read-only. The next PR should not add rankings logic; it should validate active-draft states, refresh/failure behavior, mobile on-clock usability, data freshness, and safe fallback across rookie and startup rooms. This yields a distinctive Founder Beta workflow from substantial existing code without risking writes, valuations, entitlements, or a new external provider.

## Limitations

- No product analytics, interviews, competitor dataset or pricing study exists in the repository. Revenue, conversion, retention and differentiation scores are explicitly hypotheses.
- Static analysis proves wiring and tests, not live ESPN/Sleeper reliability or active-draft UX.
- Completion estimates measure repository readiness, not calendar certainty.
- “Unavailable/unreliable data” means the current repository cannot establish production-grade completeness; it does not claim that no provider exists.

## Behavior-preservation statement

No production behavior was changed. This audit did not expose experimental navigation, register an archetype, alter authentication or entitlements, modify feature flags, change data sources, or implement/remove any product capability.
