# Founder Beta performance audit (PR #152)

Route latency & warm-rerun performance audit. Engineering optimization only —
no football logic, valuation math, ranking math, recommendation scoring/ordering,
Trust, lifecycle semantics, auth, entitlements, Stripe, Supabase schema, or
Sleeper semantics changed.

**Baseline:** `a80ffe7035740029ed45138b47e58d6202e3a5c2` (main after PR #151)
**Harnesses reused:** `scripts/check_founder_beta_performance_budget.py`,
`scripts/audit_founder_beta_performance.py`, `scripts/measure_navigation_reruns.py`,
`scripts/measure_handoff_reruns.py`, `DYNASTYGM_RUNTIME_TRACE=1` AppTest traces.

Measurement environment: logged-out production AppTest on CI-equivalent hardware.
Authenticated Sleeper/Supabase network paths were inventoried but not exercised
with real credentials — those remain documented gaps.

---

## 1. Before / after timing matrix

Logged-out production AppTest (1 cold + 10 warm Dashboard reruns):

| Measure | Before median | After median | Before p95 | After p95 |
| --- | ---: | ---: | ---: | ---: |
| Cold server `total_page_ms` | 515.2 | 508.2 | — | — |
| Warm Dashboard server `total_page_ms` | **190.6** | **35.0** | 226.0 | 37.6 |
| Cold protobuf bytes | 509,809 | 509,809 | — | — |
| Warm protobuf bytes | 467,038 | 467,038 | — | — |
| Warm `league_data_complete` milestone | 179.8 | 25.2 | — | — |
| Warm dataframe copies | 7 | 2 | — | — |
| Warm `injury_parsing` counter | 988 | 988 (unchanged; LRU still skips work) | — | — |
| Warm prepared-frame hits | 0 | 1 | — | — |
| Warm shell-chrome hits | 0 | 1 | — | — |

Navigation (`scripts/measure_navigation_reruns.py`, dashboard→my_team, n=10):

| Measure | After median | After p95 |
| --- | ---: | ---: |
| Explicit rerun events / action | **0** | 0 |
| Server ms | 38.0 | 63.6 |
| Protobuf bytes | 470,560 | 470,752 |

Handoff (`scripts/measure_handoff_reruns.py`, n=10):

| Mode | Explicit reruns (median) |
| --- | ---: |
| Fixed `on_click` commit | **0** |
| Legacy queue + `st.rerun()` | 1 |

### Suggested Founder Beta targets vs measured evidence

| Target (awake Render) | Suggested | Measured (logged-out AppTest) | Verdict |
| --- | ---: | ---: | --- |
| First usable shell (server) | ≤1.0s | Cold ~508 ms | Met in fixture |
| Warm Dashboard rerun | ≤300 ms | **~35 ms** | Met |
| Simple route transition | ≤250 ms | Nav server median ~38 ms | Met (server); AppTest wall ~590 ms includes harness overhead |
| Notification Center open | ≤200 ms | Compose-only on warm path (no inventory rebuild) | Met architecturally |
| GM/Menu open | ≤150 ms | Sheet open is session-flag + widgets | Met architecturally |
| PQV decision-critical | ≤500 ms | Critical path before deferred news | Fixture-limited |
| Trade Hub first useful | ≤750 ms | Cache hit path; cold board still provider-bound | Partial — needs auth evidence |
| League switch first useful | ≤1.0s | Correctness-preserving invalidate + rebuild | Partial — needs auth evidence |

Wall-clock CI thresholds remain intentionally wide. Prefer call counts / memo hits.

---

## 2. Call graph (warm common path)

```
begin_rerun
  ensure_players / normalize_player_ids          # public cache hit
  auth / profile / entitlement bridges          # logged-out: local only
  resolve_active_league_context
  sidebar widgets
  prepared valued+ranked frame                  # HIT after first build
  prepared shell chrome (strategy + rank row)   # HIT within 5-min bucket
  route restore + lifecycle fingerprint sync
  topbar / Notification Center compose          # session snapshot only
  route body (Dashboard / Trade Hub / …)
    get_shared_league_context(*)                # session memo within TTL bucket
  PQV modal (if open) — news deferred behind gate
finish_rerun
```

---

## 3. Route computation ownership

| Route | Expensive work owned here | Must not run |
| --- | --- | --- |
| Dashboard | Briefing compose, What Changed, `publish_activity_inventory`, full shared context | Trade Review detail, Live Draft board |
| Trade Hub | `cached_trade_ideas` + Trust enforce + visible cards | Dashboard briefing publish |
| Waivers | FA filter/rank from roster map | Live Draft state |
| PQV | Identity / rank / recommendation / value / health first | News until deferred gate; full career resume until expand |
| Notification Center | `list_*` from session snapshot | Recommendation inventory regeneration |
| News / Players / Trade Analyzer | Reduced shared context (`include_intelligence/trust/maturity=False`) | Full league intelligence |
| GM Menu / Alerts | Session flags + compose | Rebuilding valued frame (memo hit) |

---

## 4. Provider-call before / after (logged-out fixture)

| Boundary | Cold before | Warm before | Cold after | Warm after |
| --- | ---: | ---: | ---: | ---: |
| Sleeper | 0 | 0 | 0 | 0 |
| Supabase | 0 | 0 | 0 | 0 |
| RSS news (PQV closed) | 0 | 0 | 0 | 0 |

Warm route navigation no longer rebuilds valuation/ranks when inputs are unchanged,
so authenticated warm navigation should not re-issue identical valuation-derived
downstream work. Existing Sleeper `lru_cache` / `@st.cache_data` TTLs unchanged.

---

## 5. Rerun inventory

| Source | Count / behavior |
| --- | --- |
| Explicit `st.rerun()` (AST) | 36 (budget ≤42) |
| Nav destination `on_click` | 0 explicit reruns |
| Handoff Quick Actions | 0 explicit reruns |
| Auth restore / league auto-resume | Retained (required) |
| League switch | Clears prepared memos + lifecycle (correctness) |

Rerun-count before/after for primary navigation: **1 legacy → 0** (already fixed in prior PRs; reconfirmed).

---

## 6. Cache inventory

| Cache | Inputs | TTL / scope | Invalidation | Notes |
| --- | --- | --- | --- | --- |
| `@st.cache_data` league stack | league id + settings + DF hash | 5 min | args / TTL | Unchanged |
| Public players | source fingerprint | process | fingerprint / refresh | Unchanged |
| Sleeper `lru_cache` | endpoint args | process | process restart | Unchanged |
| `_injury_level_cached` | status pair | process LRU 4096 | process | Unchanged |
| **Prepared valued+ranked frame** | fingerprint + lens + settings + format + archetype + season + rows | session | signature miss; account clear; league switch; rank-context change | New |
| **Prepared shell chrome** | frame sig + league + roster + settings + 5-min bucket | session | same + TTL bucket | New |
| **Prepared shared league context** | shell sig + include_* flags | session | same + TTL bucket | New |
| Deferred section gates | section id | session | reset / league switch prefixes | PQV news gate added |
| Activity inbox snapshot | context fingerprint | session | lifecycle / league switch | Unchanged (PR #149 authoritative) |

No TTLs lengthened. No stale-data risk beyond existing 5-minute league caches.

---

## 7. Protobuf contributors

| Contributor | Approx warm bytes | Action |
| --- | ---: | --- |
| Global `APP_CSS` HTML | ~426 KB | Cannot emit-once under Streamlit redraw (prior measurement) |
| Founder / dashboard CSS fragments | ~6–13 KB | Left unchanged |
| Cold total | 509,809 / 510,000 ceiling | **Not raised** |

Protobuf before/after: **unchanged**. Cold headroom remains ~191 bytes.

---

## 8. Cold wake vs app latency

| Layer | What it is | Code can fix? |
| --- | --- | --- |
| A. Render cold wake | Sleeping free/hobby instance spin-up | **No** — infrastructure |
| B. Python/Streamlit import | Process import + Streamlit bootstrap | Partial (already optimized) |
| C. First usable shell | Auth bridge + public players + chrome | Yes — measured ~0.5s logged-out |
| D. Route hydration | Route-specific builders | Yes — memo + route scoping |

If Founder Beta still runs on sleeping Render infrastructure, users pay **A** on top of **B–D**. Code changes cannot eliminate sleep latency.

---

## 9. Fixes made

1. **Session memo for valued + canonical-ranked player frame** (`modules/prepared_player_frame.py`) — eliminates repeated `apply_valuation_lens` + `attach_canonical_ranks` on warm reruns when inputs are unchanged.
2. **Session memo for shell chrome** (strategy label + power/franchise row) within a 5-minute bucket matching existing `@st.cache_data` TTL — avoids repeated DataFrame hashing of `cached_team_direction_summary` / shell context on every rerun.
3. **Session memo for shared league context** keyed by signature + include flags — warm Trade Hub / Dashboard / My Team revisits reuse prepared context.
4. **Invalidation** wired into account-bound cleanup and league-switch transient clear; rank-context changes clear the frame memo.
5. **PQV Recent News** behind `render_deferred_section_gate` so news provider work is not paid to open decision-critical PQV content.
6. Tests: `tests/test_route_latency_rerun_audit.py`.

---

## 10. Remaining bottlenecks

| Bottleneck | Class |
| --- | --- |
| ~426 KB CSS protobuf every rerun | Streamlit framework |
| Authenticated Trade Hub board on cache miss | Provider / computation (unchanged math) |
| League switch full invalidate + rebuild | Correctness (intentional) |
| Render sleep wake | Infrastructure |
| AppTest wall ≫ server ms | Harness / Streamlit overhead |
| Sidebar widget tree on every run | Streamlit framework |

### Recommended next infrastructure move

Once code optimization is exhausted: keep Founder Beta on an **always-on** Render instance (or minimum instance count ≥1) so users never pay sleep wake. Separately, investigate CSS delivery outside ForwardMsg if Streamlit gains a supported path — do not fake emit-once.

---

## 11. Reproduction

```bash
DYNASTYGM_RUNTIME_TRACE=1 python3 scripts/check_founder_beta_performance_budget.py
DYNASTYGM_RUNTIME_TRACE=1 python3 scripts/measure_navigation_reruns.py
DYNASTYGM_RUNTIME_TRACE=1 python3 scripts/measure_handoff_reruns.py --samples 10
python3 -m pytest tests/test_route_latency_rerun_audit.py -q
```
