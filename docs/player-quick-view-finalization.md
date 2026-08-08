# Player Quick View finalization

Baseline: `main` after My Team roster workspace (#194).
Scope: information architecture, automatic news hydration, and presentation only.
Football truth, valuations, rankings, recommendation generation, Trust, injuries,
trade/waiver logic, auth, entitlements, Stripe, Supabase, and Sleeper semantics
are unchanged.

## Before — section inventory

| Section | Placement | Disclosure |
| --- | --- | --- |
| Identity / portrait / team / position / health pills | Always visible | — |
| Recommendation / Player Context | Always visible | — |
| Share Recommendation [Experimental] | Always visible (when flag on) | — |
| Current Value (ranks, value, PPG, health, trend) | Always visible | — |
| Ranking methodology | Collapsed | Expander |
| Current Season compact summary | Always visible | — |
| Career Resume (compact) | Always visible | — |
| Full career resume / timeline | Behind button | `View full career resume` |
| Complete season stats | Collapsed + Load | Expander → Load |
| Recent News | Collapsed + Load | Expander → Load |
| Advanced Details (executive, roster read, dense metrics, college, diagnostics) | Collapsed + Load | Expander → Load |
| Quick Actions (Trade Hub, Untouchable, GM Targets, feedback) | Always visible | Full-width stack |

**Disclosure count (default experience):** 4 expanders + 1 career Load button + up to 3 deferred Load buttons ≈ **7 disclosure/Load controls**.

**Required clicks to see routine content:**

| Content | Before |
| --- | ---: |
| Recommendation | 0 |
| Current season summary | 0 |
| Recent news | 2 (open expander + Load) |
| Career summary (compact) | 0 |
| Full career timeline | 1 |
| Complete season tables | 2 |
| Advanced / methodology | 2 |

## Final hierarchy

1. **Player** — identity, portrait (muted surface), team/position/age, health
2. **Recommendation / Player Context** — action, reason, confidence/context (canonical narrative only; no synthetic Shop/Hold for neutral PQV)
3. **Rank / value / health** — compact `OVR #N · POS #N · Format` strip + Value & Health snapshot
4. **Current Snapshot | Recent News** — two columns on desktop; stacked on mobile
5. **Career Context** — compact prestige résumé (highest-value facts)
6. **More details** — one intentional disclosure (toggle, not expander+Load):
   methodology captions, complete season tables, full résumé + timeline,
   executive summary, roster read, dense metrics, college, diagnostics
7. **Actions** — primary Trade Hub; secondary Untouchable / GM Targets; utility Share + Feedback collapsed

### Disclosure contract

> Collapse complexity, not routine information.

Appropriate disclosure: complete season stats, full career timeline, methodology,
executive/technical evidence.

Inappropriate disclosure: recommendation, canonical rank, health, current snapshot,
recent news, core identity.

**Disclosure count after:** **1** primary deep disclosure (`More details`), plus optional
utility expanders (Share / Feedback) and optional `More news (N)` when curated
headlines exceed three. Default dossier reading path has **no Load buttons**.

**Required clicks after:**

| Content | After |
| --- | ---: |
| Recommendation | 0 |
| Current season snapshot | 0 |
| Recent news | 0 |
| Career summary | 0 |
| Deep detail | 1 (`More details`) |

## Recent News — before / after

| Aspect | Before | After |
| --- | --- | --- |
| Access | Expander → Load recent news | Auto after first-useful |
| Presentation | Single compacted `time \| source \| summary` note + Read source | Source · freshness / headline / snippet / Read article → |
| Count | Effectively 1 shown | Up to 3 default; overflow in `More news` |
| URL | Hidden behind link button (summary still source-heavy) | Never primary visible copy |
| Failure | Gate / empty caption | Quiet: “Recent news is temporarily unavailable.” |

### News data flow

```
PQV open
  → identity / recommendation / rank strip / Value & Health
  → mark pqv_first_useful
  → Current Snapshot (in-memory stats)
  → Recent News auto:
       1. player presentation cache (TTL = NEWS_CACHE_TTL_SECONDS, 20m)
       2. session news pool
       3. disk news_cache.json (no network)
       4. cold only: st.fragment skip-first tick, then live fetch_news()
  → Career Context (row-backed compact résumé)
  → More details only if toggled
```

### Framework limitation (Streamlit)

Streamlit cannot paint mid-script. Calling live RSS in the same parent render as
identity would delay browser paint of first-useful content. Therefore:

- Warm session/disk news paints immediately after first-useful work.
- Cold network hydration uses `@st.fragment(run_every="0.6s")` with a skip-first
  tick so the parent can finish, then one network hydrate + `st.rerun()` to stop
  the timer.
- If `st.fragment` is unavailable, the sync fallback still auto-fetches (no Load
  button) and is documented as the degraded path.

### Provider / cache behavior

| Path | Provider calls |
| --- | --- |
| Warm reopen within TTL | 0 (presentation cache hit) |
| Session or disk pool present | 0 live RSS; filter/curate only |
| Cold first open | 1 `fetch_news` after first paint (fragment) |
| Failure | Cached as `status=error` for TTL; quiet UI; PQV remains usable |

Source labels are normalized from feed URLs (`ESPN`, `CBS Sports`, `RotoWire`, …).
Unknown hosts fall back to a clean domain label — never a invented brand.

Timestamps use provider `published_ts` when present; compact relative labels
(`35m`, `2h`, `Yesterday`) for PQV only. No manufactured times.

## Current Snapshot / Career Context

- **Current Snapshot** renames the compact season executive summary and remains
  position-aware from existing `PlayerQuickViewStats` (games, PPG, fantasy, key
  production, light usage). No new derived scores.
- **Career Context** is the compact résumé (top achievements). Full timeline and
  expanded résumé live under More details and run only when that toggle is open
  (Streamlit expander bodies always execute; a button toggle avoids that trap).

## Action hierarchy

| Tier | Controls |
| --- | --- |
| Primary | Open in Trade Hub |
| Secondary | Untouchable, GM Targets (experimental / entitlement unchanged) |
| Utility | Share (experimental), Feedback — collapsed |

## Mobile / desktop

- **320–430:** stacked Snapshot → News → Career → More; muted portrait surface;
  no raw URL walls; fewer full-width utility buttons.
- **1024–1920:** `st.columns(2)` for Snapshot | News under the decision header;
  deep material still one More details control.

## First-useful performance

Preserved from #157:

Required before first-useful: portrait, name, team/position, canonical OVR /
positional rank, scoring format, value, health, canonical recommendation/context.

Must not block first-useful: live news network, complete career scan, timeline,
advanced methodology / executive snapshot.

Milestones: `pqv_open_received` → `pqv_first_useful` → `pqv_news_start` /
`pqv_news_complete` → `pqv_secondary_ready` (More details open).

## Remaining PQV debt

- True async news without a short fragment delay still needs a non-Streamlit
  delivery channel.
- Dense technical rows inside More details can still echo recommendation labels.
- Share / Feedback remain Streamlit expanders (utility chrome, not dossier IA).
- Portrait contrast depends on shared headshot tokens; PQV now forces muted
  avatar background inside the dialog.
