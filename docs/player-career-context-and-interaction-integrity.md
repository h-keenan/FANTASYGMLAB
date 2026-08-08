# Player Career Context & Interaction Integrity

| Field | Value |
| --- | --- |
| Baseline | latest main after #201/#204 (`544748f…`) |
| Scope | P0 interaction/PQV crash repair + Career Context résumé finalization |
| Explicit non-changes | Current valuations, rankings, recommendation generation/scoring/ordering, Trust, Trade/waiver math |

## Production TypeError — root cause

`modules/player_history.load_cached_career_resume` is **keyword-only** for all parameters (`def load_cached_career_resume(*, player_id, …)`).

`app.py` `render_player_quick_view_content` called it with a **positional** first argument:

```python
load_cached_career_resume(player_id, current_row=..., position_lookup=...)
```

That raises:

`TypeError: load_cached_career_resume() takes 0 positional arguments but 1 positional argument (and 2 keyword-only arguments) were given`

Triggered on **More details** (and now also on the default Career Context cache path).

### Repaired API contract

```python
load_cached_career_resume(
    *,
    player_id: str,
    current_row: Mapping[str, Any],
    position_lookup: Mapping[str, str],
    cache_dir: str | Path = "data",
) -> CareerResume
```

All call sites use keywords. Career load is wrapped in fail-soft `try/except` so optional history never destroys PQV.

Regression tests:

- `test_load_cached_career_resume_rejects_positional_player_id`
- `test_app_pqv_career_loader_call_uses_keyword_only_player_id`

## Interaction integrity

### Decision History / Memory

| CTA | Before | After |
| --- | --- | --- |
| Open current context | `on_click=open_event` but dialog open flag stayed true → dialog remounted over destination | `_open_current` closes dialog flag **then** opens current context |
| Close / X (`on_dismiss`) | Already closed flag | Unchanged; Close uses `on_click=_close` |
| View decision history / View Decision Memory | Body-path `if st.button` | `on_click=_open_flag` |
| Button geometry | Full-width dominating each row | Constrained `.dg-decision-history-cta` (max-width 16rem; full width ≤430px for touch) |

Open Current Context still uses `recommendation_narrative=None` and `_open_home_command_route` (current destination truth only).

### Copy

When structured prior/current snapshots include a priority-rank shift without action/confidence change, summaries now say **Priority increased/decreased** with `#N → #M`. Generic “changed in a material way” remains only when no structured delta exists.

## Career data inventory

| Field | Source | Coverage | Reliability | Notes |
| --- | --- | --- | --- | --- |
| Season aggregates | `data/sleeper_player_stats_YYYY.json` | Currently **2025** on disk in this checkout | High when present | Loader globs all years; no network fetch |
| fantasy_points_ppr / ppg | same | Sparse for some IDs | High when present | **Scoring basis: verified PPR** — explicitly labeled |
| passing/rushing/receiving yards & TDs | same | Position-dependent | High when present | |
| receptions / targets | same | WR/TE/RB | High when present | |
| games_played / snap_share | same | Common | High | |
| position_finish | Derived from PPR rank among same position in that year file | Only for players in file | Deterministic | Not league-scoring-specific |
| years_exp / draft | Sleeper player directory metadata | Good | High | Used for experience / rookie state |
| Awards / championships | **None sourced** | — | Rejected | Never invent |

Rejected/unreliable for Career Context: invented “Prestige” score, league-specific historical finishes without expensive recompute, college as NFL milestones.

## Career Context contract

**Job:** What has this player’s verified fantasy career established?

Default résumé metrics (when available):

- Experience
- Best finish (`POS# · year`)
- Best season production line
- Consistency (Top-12 TE / Top-24 other)
- Recent arc (`POS# → …`) when ≥2 finished seasons

Milestones: compact factual shortlist (finish + production thresholds). No prestige badge.

Empty states:

- Rookie / years_exp ≤ 0 → “Rookie season — career résumé still being established.”
- Limited cache → “Limited NFL history available.” / early-career copy
- Never: “No verified achievement threshold has been reached…”

More details: expanded milestones grouped by season/family, scoring basis caption, full Career Timeline, executive snapshot (unchanged deferral).

### Milestone priority

1. Elite fantasy finish  
2. Major production season  
3. Repeated high-level finishes (via consistency metric)  
4. Career-high production labels  
5. Longevity/availability (17-game)  

### Position thresholds (documented)

- **QB:** 4k/5k pass yds, 30/40 pass TD, 500 rush yds; finishes ≤24  
- **RB:** 1k rush / 1.5k+ scrimmage, 10 rush TD, 60 receptions; finishes ≤24  
- **WR:** 1k rec yds, 100 receptions, 10 rec TD; finishes ≤24  
- **TE:** same receiving thresholds; finishes notable through **TE12** (top-6 standout band)

## Performance / protobuf

- Career cache load runs **after** `pqv_first_useful`
- Local disk only; fail soft  
- Accent CSS lives in `PLAYER_QUICK_VIEW_CSS` / Decision History scoped CSS — not global `APP_CSS`  
- Do not raise 520,000 cold protobuf ceiling  

## Remaining limitations

- On-disk season cache may only include the current year → arcs/consistency limited until more year files exist  
- Finishes are **PPR baseline**, not active-league scoring recreate  
- Chromium may still struggle with Streamlit dialog callback timing; product path is `on_click` + close-then-navigate  
