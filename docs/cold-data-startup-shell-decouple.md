# Cold-data startup + shell/football decoupling (#215)

## Problem

After #214 collapsed auth reruns, production showed two realities:

| Path | `loading_dismissed` |
| --- | ---: |
| Warm returning auth | ~1.727 s |
| Cold reusable-data path | ~50.567 s |

The catastrophic gaps after `league_restored`:

| Window | ~Duration | Owner |
| --- | ---: | --- |
| league → players | ~6.63 s | `ensure_players` → `build_players_table(refresh=True)` when `sleeper_players.json` TTL (>1h) expired |
| players → prepared | ~20.40 s | cold `apply_valuation_lens` + `attach_canonical_ranks` (session memo miss) |
| prepared → shell | ~17.76 s | `cached_league_shell_context` → `cached_league_summary` scoring every roster on full valued frame + draft/context |

Warm path was fast because process `@st.cache_data` / session memos / Sleeper `@lru_cache` were already hot.

## Architectural change

Separate:

- **shell_ready** — auth + entitlement + league identity + roster identity + navigation
- **football_context_ready** — persisted players + valued/ranked frame + optional valued chrome enrichment

Global loading dismisses at **shell_ready**.

Football work runs **after** `loading_dismissed`.

## Before / after loading prerequisites

**Before:** auth → league → players (possibly network rebuild) → prepared valuation → draft context → league summary shell → nav → dismiss

**After:** auth → league → identity shell (roster profile only) → nav → **dismiss** → persist-first players → prepared valuation → draft context → valued chrome enrichment → routes

## Player cache architecture

**Before:** stale `sleeper_players.json` forced `build_players_table(refresh=True)` on the loader.

**After:** `ensure_players_for_startup` loads SQLite first; marks `_players_network_refresh_pending` for deferred refresh; network rebuild only when disk is empty.

## Shell context architecture

**Before:** `_build_shell_chrome_bundle` always called `get_shell_league_context` → full summary.

**After:** `_build_identity_shell_chrome_bundle` for first-useful (profile only). Valued bundle runs post-dismiss.

### `shell_display` ownership (post-#215)

| Name | Source | When |
| --- | --- | --- |
| Identity shell | `my_roster_id` + `get_roster_profile(league, roster)` | Before players / prepared / league summary |
| Valued `shell_display` | `get_shell_league_context()["league_detail_ranks"]` | After valued frame + shell league context |

`league_detail_ranks` comes from `add_league_detail_ranks(league_display_frame)` inside `cached_league_shell_context`. On cold/partial paths it may be:

- `pd.DataFrame()` (no columns)
- RangeIndex-only / empty schema
- partial columns without `roster_id`
- full valued rows with `roster_id`

`roster_id` is **not** guaranteed on the display frame for identity shell. It is only guaranteed after a successful valued shell context build that produced ranked team rows.

### Identity shell schema (A)

Guaranteed without a valued display frame:

- league identity (`selected_league_id`)
- roster identity (`my_roster_id` from membership / restore / selected league context)
- roster profile (when league + roster known)
- account / entitlement / navigation
- default strategy labels from session

Does **not** require: full league display frame, valued team rows, archetype, ranks, draft enrichment.

Provenance / memo prefix: `identity|…`

### Valued / enriched shell schema (B)

Optional fields when `league_detail_ranks` has `roster_id` and a matching row:

- power / franchise ranks and related team metrics
- strategy from team-vs-league metrics
- draft / direction context carried on the row

If the column is missing, the frame is empty, or no row matches: omit `shell_team_row` enrichment and keep identity-safe chrome. Do **not** synthesize `shell_display["roster_id"] = ""`.

Provenance / memo prefixes: `valued|…` (enriched) or `valued_pending` on the bundle when enrichment was skipped.

### roster_id KeyError regression (hotfix after #215)

**Root cause:** `_build_shell_chrome_bundle` assumed the pre-#215 full-schema frame and did:

```python
shell_row = shell_display[shell_display["roster_id"].astype(str) == str(my_roster_id)]
```

After cold-path decoupling, `shell_display` can lack `roster_id`, so pandas raises `KeyError: 'roster_id'`.

**Fix:** `modules/shell_chrome_schema.py` validates schema before indexing. Roster identity continues to come from `my_roster_id` / roster profile — never rediscovered only via DataFrame lookup. Late hydration replaces identity chrome with valued chrome under a distinct memo signature after prepared frame readiness.

### Late hydration contract

`identity` → `valued` must not:

- crash
- reuse League A ranks/names on League B (league switch clears shell memo)
- leak partial shell across logout/account switch (`clear_shell_chrome`)
- reintroduce full league summary onto the global loader
- force an extra auth restore

### Cache / provenance

Identity and valued builders use different signature prefixes so a partial identity bundle is never treated as the final valued bundle. League switch clears league-scoped shell memos via `clear_league_scoped_prepared_memos`.

## Why fast vs cold

- Fast: auth settle + cache hits across players / prepared / shell summary.
- Cold: expired sleeper JSON TTL + cold valuation/rank build + cold league summary — previously all before dismiss.

## Remaining bottleneck

Post-dismiss cold valuation + league summary can still take tens of seconds before Dashboard recommendations appear. The user is already inside the app with navigation. Next measured owner after this PR: **prepared valued/ranked frame cold miss** (then shell summary enrichment).

## Verdict direction

KEEP STREAMLIT — COLD START PATH FIXED for global loading, with remaining post-dismiss football hydration owned by prepared-frame cold miss.
