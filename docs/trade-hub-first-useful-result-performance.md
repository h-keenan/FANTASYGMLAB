# Trade Hub First-Useful-Result Performance (PR #154)

Engineering optimization only — no football logic, valuation math, ranking math,
recommendation scoring/ordering, Trust thresholds, entitlement rules, auth,
Stripe, Supabase schema, Sleeper semantics, lifecycle material-change meaning,
or workflow continuity semantics changed.

**Baseline main:** `50f95b32b3667e3b442a9bd0dcd55c932c79c2df` (after PR #153)
**Harnesses:** `scripts/measure_trade_hub_first_useful.py`,
`scripts/profile_trade_hub.py`, `scripts/check_founder_beta_performance_budget.py`,
`DYNASTYGM_RUNTIME_TRACE=1` AppTest.

Measurement environment: local Windows process, synthetic fixtures / logged-out
AppTest. Authenticated Sleeper/Supabase network paths are inventoried but not
exercised with real credentials.

---

## Recommendation #1 correctness contract

**Case that applies: complete candidate evaluation is required before #1.**

PR #126 / `order_trade_hub_visible_ideas` + Trust + entitlement determine the
presentation #1. `_trade_surface_sort_key` is relative across the approved set.
Therefore this PR **does not** invent provisional early-result semantics.

Progressive UX is limited to:

1. Trade Hub chrome + strategy controls first
2. Concise board-working caption while the complete minimum board is built
3. Canonical Recommendation #1 (and currently visible cards)
4. Remaining board via existing “Show more”
5. Deferred return-path search / detail / dossiers

If architecture later proves a monotone upper bound for #1, that would be a
separate football-safe algorithm PR with golden rewrites. Not done here.

---

## Before / after critical-path diagram

### Before (post-#152)

```text
nav → full shared league context (incl. intelligence)
    → strategy selector
    → apply_strategy_age_curve (copy every visit)
    → owned-pool DataFrame copy (eager)
    → st.cache_data hashed DF lookup / build_trade_ideas
    → Trust enforce
    → tendency enrich (all ideas)
    → entitlement + presentation order
    → render visible cards (default 1)
    → secondary search tools
```

### After

```text
nav (trade_hub_nav_received)
  → shared context WITHOUT intelligence (Trust/roster/maturity retained)
  → strategy selector (chrome first)
  → strategy-frame session memo (hit on unchanged lens)
  → presentation-board session memo
        miss: generate (st.cache_data) → Trust → enrich → order → store
        hit:  reuse approved ordered inventory (fail closed on provenance miss)
  → entitlement summary + Recommendation #1 render
  → Show more / deferred return search (pool copy only when opened)
  → route complete
```

---

## Timing table by pipeline stage

### Synthetic board generation (12-team Superflex primary)

From `scripts/profile_trade_hub.py` (before optimization, n=20 cold):

| Stage / metric | Median | p95 |
| --- | ---: | ---: |
| Cold full `run_trade_hub` | **1011.9 ms** | 1127.5 ms |
| Warm raw-cache Trust+present | **7.2 ms** | 8.0 ms |
| `_build_team_shape` (12 calls, profile) | ~1353 ms cum | — |
| Package scoring (memoized) | 670 ms cum | — |
| DataFrame `copy()` observations | 220 | — |

Dominant cold cost remains football generation inside `build_trade_ideas`
(required for final #1). Pick-context once-per-roster reuse was already on main.

### Presentation-board session memo (`scripts/measure_trade_hub_first_useful.py`, n=8)

| Scenario | Median | p95 |
| --- | ---: | ---: |
| Cold generation + present | 857.9 ms | 904.1 ms |
| **Warm presentation-cache hit** | **0.46 ms** | 0.47 ms |
| Strategy-change miss (memo only) | 0.89 ms | 0.92 ms |

Warm identical-context Trade Hub revisits no longer re-hash large DataFrames or
re-run Trust/order when provenance matches.

### Logged-out production AppTest (protobuf / shell)

| Measure | Before (#152/#153) | After (#154) |
| --- | ---: | ---: |
| Cold server `total_page_ms` | ~508 ms | ~2183 ms* |
| Warm server `total_page_ms` | ~35–70 ms | ~71 ms |
| Cold protobuf bytes | 509,809 → ~512KB (#153) | **512,152** |
| Warm protobuf bytes | ~467–469KB | **469,381** |

\*Cold AppTest wall varies on this workstation (OneDrive / import); CI budget
≤2500 ms still passes. Protobuf ceiling **not raised** (max 520,000).

---

## Cache hit / miss behavior

| Cache | Hit behavior | Miss / invalidate |
| --- | --- | --- |
| Prepared valued+ranked frame (#152) | Reused | Lens/settings/fingerprint change; logout; league switch |
| Shared league context (Trade Hub flags) | Session memo without intelligence | Flag/signature change; hygiene clear |
| Strategy age-curve frame | Isolated DF copy | Strategy / frame signature change |
| **Presentation board (new)** | Deep-copied ordered inventory | Lifecycle dims, strategy, entitlement, untouchables/roles, frame signature, settings |
| `st.cache_data` raw ideas | Process TTL 5m | Arg hash / TTL (Trust still outside) |

Fail closed: signature mismatch rebuilds; empty/malformed memos are dropped.
Entitlement is part of the key — Free never receives a Premium inventory hit.

---

## Duplicate-work inventory

| Work | Before | After |
| --- | --- | --- |
| League intelligence on Trade Hub | Eager via full shared context | **Skipped** (`include_intelligence=False`) |
| Strategy age-curve DF | Rebuilt every Trade Hub visit | Session memo |
| Owned-player pool `.copy()` | Eager before board | Deferred until return-search open |
| Valued+ranked frame | Already memoized (#152) | Unchanged reuse |
| Trust after raw cache | Every visit | Skipped on presentation-board hit |
| Presentation order / annotate | Every visit | Skipped on presentation-board hit |
| Manager tendency enrich | Every visit (all ideas) | On board miss only (still before #1 paint) |

---

## Deferred-work inventory

| Work | Deferred? | Why safe |
| --- | --- | --- |
| League intelligence frame | Yes (Trade Hub) | Not used for board correctness |
| Return-path explorer + pool copy | Yes (gate) | Secondary tool |
| Cards beyond `visible_count` | Yes (Show more) | Membership already fixed |
| Detail modal / dossier | Yes (existing) | Interaction-gated |
| Player-centric search (no focus) | After board | Existing order retained |
| Provisional #1 before full board | **No** | Ordering contract forbids it |

---

## Cache / invalidation matrix

| Dimension | Presentation board | Strategy frame | Prepared frame |
| --- | --- | --- | --- |
| account_scope / logout | clear | clear | clear |
| league / roster switch | clear | clear | clear |
| scoring_format | miss | — | miss |
| valuation_lens / score_field | miss | miss | miss |
| strategy / archetype | miss | miss | — |
| entitlement Free↔Premium | miss | — | — |
| roster_state_version | miss | — | — |
| provider_data_version / settings | miss | — | miss |
| untouchables / roles | miss | — | — |
| PQV / Alerts / GM open | hit | hit | hit |
| Show more visible_count | hit | hit | hit |

---

## Rerun inventory

No explicit `st.rerun()` sites were removed solely for benchmarks.

| Interaction | Explicit reruns |
| --- | --- |
| Initial Trade Hub navigation | 0 (destination `on_click` commit) |
| Strategy dropdown | Widget rerun only |
| Review Package / Trade Review back | Existing workflow; board memo hits when context unchanged |
| PQV open/close on Trade Hub | Widget/dialog; board memo hit |
| Alerts/GM open/close | Session flags; board memo hit |
| Show more | `on_click=increment_session_counter` (no explicit rerun) |

AST explicit rerun budget remains ≤42 (`check_founder_beta_performance_budget.py`).

---

## Provider / network contribution

Logged-out fixture: **0** Sleeper / **0** Supabase / **0** RSS on Trade Hub path.
Cold board cost in the synthetic harness is **CPU generation**, not provider
latency. Authenticated first visit still pays Sleeper roster/league reads via
existing `lru_cache` / `@st.cache_data` boundaries; those are unchanged.

---

## DataFrame copy / count reduction

| Path | Before | After |
| --- | ---: | ---: |
| Eager owned-pool copy on every board paint | 1 | **0** (deferred) |
| Strategy age-curve rebuild on warm revisit | 1 | **0** (memo hit) |
| Generator-internal copies (cold miss) | 220 (profile) | unchanged (football path untouched) |

---

## Correctness equivalence

- Golden Trade Hub fixtures unchanged (`tests/test_trade_hub_profiling.py`).
- Cache hit/miss fingerprints identical in
  `scripts/measure_trade_hub_first_useful.py` (`stable: true`).
- Free visible_count 2 vs Premium 10 on the primary fixture; distinct fingerprints.
- No edits to `modules/trade_ideas.py`, `trust_engine.py`, `trust_enforcement.py`,
  or `rankings.py`.

---

## Chromium / responsive

Width matrix **320 / 390 / 430 / 768 / 1024 / 1440** retained via
`scripts/validate_mobile_ui.py` and
`tests/test_trade_hub_progressive_loading.py`.

Progressive loading adds **no** global CSS and **no** fake recommendation
skeletons. Strategy controls render before board generation. Trade summary
visual harness remains the synthetic card surface for layout checks.

---

## Remaining bottlenecks

| Rank | Bottleneck | Evidence | Next decision |
| ---: | --- | ---: | --- |
| 1 | Cold `build_trade_ideas` / `_build_team_shape` | ~0.85–1.1 s median synthetic | Algorithmic reuse only with golden proof; not early #1 |
| 2 | DataFrame hashing into `st.cache_data` on presentation miss | Warm miss still pays hash | Lightweight raw-board session memo keyed without DF (future) |
| 3 | Authenticated provider cold path | Not measured with live creds | Separate auth telemetry PR |
| 4 | Local AppTest / import variance | Cold 2–50 s outliers observed | Infrastructure noise |

---

## Files changed

| File | Role |
| --- | --- |
| `modules/trade_hub_first_useful.py` | Stage timers, presentation/strategy memos, equivalence helpers |
| `modules/prepared_player_frame.py` | Clear Trade Hub memos on hygiene |
| `modules/session_integrity.py` | Account-bound clear of Trade Hub memos |
| `modules/runtime_trace.py` | Trade Hub milestones |
| `app.py` | Trade Hub orchestration only (reduced context, memos, milestones) |
| `scripts/measure_trade_hub_first_useful.py` | Repeatable harness |
| `tests/test_trade_hub_first_useful_result.py` | Provenance / equivalence |
| `tests/test_trade_hub_progressive_loading.py` | Progressive UX contracts |
| `tests/test_founder_beta_architecture_sprint.py` | Reduced-context count |
| `docs/trade-hub-first-useful-result-performance.md` | This report |

`app.py` impact: Trade Hub route orchestration + one import. No football modules.

---

## Rollback boundary

Revert the merge commit on `main`. Session memos and reduced intelligence on
Trade Hub are the only behavioral orchestration changes; football outputs match
pre-optimization for identical fixtures.
