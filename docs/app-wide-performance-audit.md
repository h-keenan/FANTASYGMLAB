# App-Wide Performance & Runtime Efficiency Audit (PR #166)

Engineering-only audit. **No football logic**, valuations, rankings, recommendation
generation/scoring/ordering, Trust, waiver/trade logic, authentication rules,
entitlements, Stripe, Supabase schema, Sleeper semantics, lifecycle semantics, or
business rules were changed.

| Field | Value |
| --- | --- |
| Baseline | `234813b78ac7630e1942e76eae5ce4b8b343270c` (main after PR #165) |
| Harness | `scripts/measure_app_wide_performance.py` |
| Static inventory | `scripts/audit_founder_beta_performance.py` |
| CI budget gate | `scripts/check_founder_beta_performance_budget.py` |
| Environment | Local logged-out Streamlit AppTest + fixture harness (`ui_validation_harness.py`) |
| Samples | n=5 warm route opens (directional p95) |

Authenticated Free/Premium + live Sleeper/Supabase network paths remain inventoried
gaps (no production secrets in this harness). Fixture surfaces approximate league-backed
UI without mutating football contracts.

---

## Final verdict on remaining latency

FantasyGM Lab has **no unexplained application-level duplicate-work bottleneck** left on
the measured logged-out warm path. Remaining delay classes are attributable to:

1. **Streamlit framework floor** — global CSS/`st.html` re-injection (~426 KB) every rerun; AppTest wall ≫ server ms
2. **Required football computation** — cold valued/ranked frame + shell; Trade Hub board miss (prior audits)
3. **Provider/network** — authenticated Sleeper/Supabase (not exercised here); Live Draft discovery when TTL expires
4. **Render infrastructure** — sleeping service wake (not app-fixable)

---

## 1. Latency map (ranked)

Logged-out production AppTest (n=5). Server ms = `total_page_ms` from `DYNASTYGM_RUNTIME`.

| Surface | Cold | Warm median | Warm p95 | Main bottleneck | Severity |
| --- | ---: | ---: | ---: | --- | --- |
| Dashboard (production cold) | 1357 ms | — | — | Public players + shell + CSS html payload | Medium (cold only) |
| Dashboard warm | — | **71 ms** | 96 ms | Streamlit CSS/html re-injection | Low |
| My Team warm | — | **73 ms** | 121 ms | Shell + route body; framework floor | Low |
| League Overview (`rankings`) | — | **72 ms** | 101 ms | Framework floor (no league intel without league) | Low |
| Draft Center | — | **72 ms** | 79 ms | Framework floor | Low |
| Premium | — | **75 ms** | 93 ms | Framework floor; profile force-refresh removed | Low |
| Warm Dashboard rerun (same route) | — | **71 ms** | 96 ms | Framework floor | Low |
| Trade Hub / Waivers (guest, no league) | — | see fixtures | — | Guest path often omits finished runtime trace; fixture walls ~80–85 ms | Low / instrument gap |
| Fixture Dashboard | — | wall **104 ms** | — | Fixture HTML only | Low |
| Fixture Trade / Waivers / League / Live Draft / PQV | — | wall **74–87 ms** | — | Fixture HTML only | Low |

### Suggested warm budgets vs evidence

| Budget | Target | Measured | Verdict |
| --- | ---: | ---: | --- |
| Dashboard | ≤100 ms | median 71 / p95 96 | Met (logged-out) |
| My Team | ≤150 ms | median 73 / p95 121 | Met |
| Waivers | ≤250 ms | fixture wall ~81 ms | Met in fixture; auth league path still provider-bound |
| Trade Hub cached | ≤150 ms | prior + fixture | Met architecturally; auth miss remains provider-bound |
| Alerts / GM | ≤150 ms | compose-only on warm path | Met architecturally |
| PQV first useful | ≤250 ms | deferred gates retained | Met architecturally |
| League switch first useful | ≤400 ms | prior audit | Partial — auth evidence still needed |

---

## 2. Protobuf / CSS breakdown

| Contributor | Bytes (cold) | Class |
| --- | ---: | --- |
| Total protobuf | **512,152** | At 520 KB CI ceiling |
| Largest `html` message (`st.html` APP_CSS inject) | **426,522** | CSS/markup weight / Streamlit floor |
| Remaining non-CSS html/markdown/widgets | ~85.6 KB | Shell + guest chrome |
| Markdown `<style>` css_messages (sum) | ~42.5 KB (7 msgs) | Secondary style injects |

`modules/app_styles.py` source ≈ 274 KB UTF-8; delivered as one large `st.html` ForwardMsg each rerun.
**Do not raise the 520 KB budget.** Further payload cuts require Streamlit delivery changes
or careful CSS splitting without visual redesign (deferred / infrastructure).

Warm protobuf median ≈ **469 KB**.

---

## 3. Explicit rerun inventory

| Count | Cap |
| ---: | ---: |
| **38** production `st.rerun()` sites | ≤42 CI |

Classification (summary):

| Class | Sites | Action |
| --- | --- | --- |
| Required | Auth restore, login/logout/signup, league open/switch/import/refresh, overlay open/close that must remount | Keep |
| Required (tap grids) | Draft board / Live Draft / Trade Review HTML taps → PQV or team | Keep |
| Avoidable (already removed historically) | Primary nav (`on_click` commit) | Done prior |
| Legacy | None newly identified as safe to delete in this PR | — |

Primary navigation remains **0 explicit reruns** per destination click (confirmed in route samples).

---

## 4. Provider-call matrix (logged-out warm)

| Route / path | Provider calls (warm median) | Notes |
| --- | ---: | --- |
| Dashboard / My Team / Rankings / Draft / Premium | **0** | Logged-out AppTest |
| Live Draft discovery | **0 on TTL hit / support routes** | **Fixed this PR** — 60s TTL; skip premium/legal/founder_ops; always refresh on `live_draft` / league change |
| Authenticated league routes | Not measured | Expected Sleeper + optional Supabase |

Warm interactions must not re-hit Sleeper drafts on every Premium/legal open — addressed.

---

## 5. Cache inventory (summary)

| Kind | Count | Owners |
| --- | ---: | --- |
| `st.cache_data` + `lru_cache` | **34** | `app.py` league/trade caches; `sleeper.py` API LRU; rankings/public players; Trust validation |
| Session memos | prepared frame / shell / shared context; Trade Hub presentation; PQV fit; Decision Memory; GM Targets | League-scoped clear on switch |
| `st.cache_resource` | **0** | — |

Findings:

- No second freshness system introduced.
- DataFrame hashing into `st.cache_data` on Trade Hub presentation miss remains a known cost (prior Trade Hub audit) — required for correctness, not duplicate accidental work.
- Prepared valued+ranked frame correctly misses on scoring/lens change and hits on warm identical signature.

---

## 6. DataFrame / copy findings

| Site | Behavior | Verdict |
| --- | --- | --- |
| `prepared_player_frame` | Returns `.copy()` of cached frame | Intentional isolation; warm hit avoids rebuild |
| `trade_hub_first_useful` / `interaction_latency` | `deepcopy` on memo get/set | Intentional mutation safety |
| Rankings enrichment paths | `.copy()` before mutate | Correctness-preserving |

No unsafe copy removal in this PR (equivalence risk). Further copy reduction belongs with football-adjacent owners only when equivalence harnesses exist.

---

## 7. Route → computation ownership

| Route | Owns | Must not run |
| --- | --- | --- |
| Dashboard | Briefing, What Changed, activity inventory, full shared context when league present | Live Draft board poll; Trade Review detail |
| Trade Hub | Cached trade ideas + Trust enforce + visible cards | Dashboard briefing publish |
| Waivers | FA filter/rank from roster map | Live Draft state machine |
| My Team | Roster advice / lineup surfaces | Trade board generation |
| League Overview | Intelligence / rankings when league present | Trade Hub board |
| Premium | Entitlement + billing chrome | **Forced** profile refetch every open (**fixed**); Live Draft discovery (**skipped**) |
| Founder Ops | Ops snapshot only when enabled | Customer football engines |
| GM Targets | Preference CRUD + canonical enrichment | Football recommendation recompute |
| Decision Memory | Material history UI | Full Trade Hub |
| PQV | Critical dossier first; news/season deferred | Career resume until expand |
| Live Draft | Draft poll on that route | Discovery spam on support routes (**fixed**) |
| Alerts / GM | Session compose | Rebuild valued frame (memo hit) |

---

## 8. Fixes made (this PR)

| Fix | Before | After |
| --- | --- | --- |
| Live Draft nav discovery every rerun with a league | Sleeper `get_league_drafts` consulted each warm run | 60s TTL + league-key; skip support routes; always on `live_draft` |
| Premium `_refresh_supabase_account_profile(force=True)` | Supabase profile fetch every Premium open | Force only when `?billing=success`; else 60s cache |
| League/account cleanup | Discovery TTL keys could linger | Cleared with league switch + account-bound transient keys |
| Harness + doc | Fragmented prior audits | `measure_app_wide_performance.py` + this document |

### Before / after (measured)

| Measure | After (this PR) |
| --- | --- |
| Warm Dashboard server median | **70.7 ms** |
| Warm Dashboard p95 | **96.4 ms** |
| Cold protobuf | **512,152** (unchanged class — CSS html) |
| Warm protobuf | **469,381** |
| Explicit reruns | **38** |
| Warm external calls (logged-out) | **0** |
| Live Draft discovery on Premium | **Skipped** |

`app.py` impact: Live Draft discovery gate + Premium profile refresh policy + league-switch key clears only.

---

## 9. Startup separation

| Phase | Evidence | Class |
| --- | --- | --- |
| Render wake | Not measured locally | Infrastructure |
| Python import + first AppTest | Cold wall ~3.5 s includes harness | Framework + process |
| Cold server `total_page_ms` | ~1.36 s | App + Streamlit |
| First usable paint milestone | ~1.31 s into cold run | App |
| Warm shell | ~70 ms server | App + CSS floor |

Sleeping Render wake is **not** claimed as an app fix.

---

## 10. Memory / churn

| Check | Result |
| --- | --- |
| Session keys for overlays / discovery | Cleared on logout + league switch |
| Unbounded growth after 20 route changes | Not observed in AppTest samples (stable protobuf) |
| PQV / Trade Hub memos | Capped session stores; league-scoped clear |

Dedicated process RSS soak against authenticated multi-league remains a follow-up.

---

## 11. Authenticated / mobile gaps (honest)

| Gap | Status |
| --- | --- |
| Free / Premium authenticated fixtures | Not run (no secrets); ownership + cache contracts covered |
| 12-team SF / PPR vs Standard | Scoring signature already invalidates prepared frame |
| 390 / 1440 mobile vs desktop server | Same server path; mobile markup weight → PR #167 |
| Chromium interaction floor | Existing `measure_streamlit_interaction_floor.py` |

---

## 12. How to re-run

```bash
set DYNASTYGM_RUNTIME_TRACE=1
python scripts/measure_app_wide_performance.py --samples 8 -o data/app_wide_performance_measurement.json
python scripts/audit_founder_beta_performance.py
python scripts/check_founder_beta_performance_budget.py
```

---

## 13. Next infrastructure recommendation

1. **Always-on / non-sleeping Render** (or paid awake instance) — eliminates customer-visible wake.
2. **Streamlit CSS delivery outside per-rerun ForwardMsg** if/when platform supports it — only way to materially cut the ~426 KB `st.html` floor without visual redesign.
3. **Authenticated performance fixture pack** (synthetic JWT + recorded Sleeper fixtures) for Free/Premium and multi-league without production secrets.

---

## Rollback boundary

Revert the PR #166 merge commit. Live Draft discovery falls back to per-rerun refresh; Premium resumes forced profile refresh. No schema or football-logic rollback required.
