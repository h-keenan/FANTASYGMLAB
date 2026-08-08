# League-switch state integrity & Waiver Priority Adds relevance

| Field | Value |
| --- | --- |
| Baseline | `8c49e03` (main after #205) |
| Scope | P0 Streamlit widget-state crash on league switch; P1 Priority Adds roster relevance |
| Explicit non-changes | Valuations, rankings, Trade Hub, Trust, My Team evaluation, entitlements |

## P0 — StreamlitAPIException root cause

**Exception:** `st.session_state.league_format_override cannot be modified after the widget with key league_format_override is instantiated.`

**Lifecycle (broken):**

1. Script run starts
2. **Sidebar** instantiates `st.selectbox(..., key="league_format_override")` (and sibling override keys)
3. Header Switch League custom component returns a click later in the same run
4. `_switch_to_saved_league` → `set_selected_league` → `_clear_league_switch_transient_state` → `_reset_league_settings_overrides`
5. `_reset_league_settings_overrides` assigned `st.session_state[key] = "Auto"` for widget-owned keys → **StreamlitAPIException**

**Widget-backed keys (all of `LEAGUE_SETTINGS_OVERRIDE_KEYS`):**

`league_format_override`, `league_scoring_override`, `league_qb_override`, `league_te_premium_override`, `league_rb_count_override`, `league_wr_count_override`, `league_te_count_override`, `league_starters_override`, `league_flex_override`, `league_bench_override`, `league_taxi_override`, `league_ir_override`, `league_size_override`

## Repaired state lifecycle

1. League selection callback still clears PQV / Trade Review / narrative / inbox / Decision Memory session / GM Targets session / prepared league memos / role_map / etc.
2. `_reset_league_settings_overrides` **only** sets `_pending_league_settings_override_reset = True` (no widget-key writes)
3. `st.rerun()` / next script run
4. **Before** sidebar override widgets: `_apply_pending_league_settings_override_reset()` writes Auto defaults
5. Widgets instantiate with Auto values

No `try/except StreamlitAPIException`. No post-instantiation key deletion.

## P1 — Waiver Priority Adds

### Pipeline before

`featured_free_agents` sorted by `[injury_replacement_fit, score_field]` then `.head(6)`.

`needed_positions` from `TeamNeedsAssessment` / `get_needed_positions(..., include_fallback=False)` only labeled copy — did not reorder Priority Adds.

Dashboard `select_top_waiver_opportunity` already soft-filtered non-need QB/TE.

### Screenshot QB dominance root cause

Score-ordered board + Superflex/dynasty QB inflation + **no Priority Adds need ranking** + kickers not suppressed on the board → multiple QBs/TE/K could occupy Priority Adds even when those rooms were not true needs.

### Contracts after

| Surface | Meaning |
| --- | --- |
| **Waiver Snapshot** | Best Available by position — broad wire scan |
| **Priority Adds** | `rank_priority_add_candidates` — need fit / injury first, then exceptional value opportunity; soft position diversity (cap ~2); 1QB demotes ordinary covered QBs; K only if required and missing |
| **Stash** | Premium secondary (age/opportunity) — unchanged membership rules |

**Ordering changed:** yes — Priority Adds now uses roster-aware ranking in `modules/waivers_ui.rank_priority_add_candidates` (canonical waiver layer). Dynasty/value score remains the underlying value signal; need/injury/value-opportunity/diversity shape the board. Snapshot remains score-by-position.

**Rank labels:** FA-relative chips read `Wire QB #1` (not ambiguous `#1 QB`). Canonical OVR/POS chips unchanged when present.

**Dashboard consistency:** `select_top_waiver_opportunity` now consumes the same ranking helper (max_items=1).

## Remaining limitations

- Historical multi-year waiver trends not modeled
- Soft diversity is decision-utility oriented, not a rigid one-per-position quota
- Exceptional non-need “value opportunity” uses top-wire / high-quantile score — not a new opaque model
- Chromium may still be limited for custom-component league cards; regression covers widget-key mutation guard + apply lifecycle
