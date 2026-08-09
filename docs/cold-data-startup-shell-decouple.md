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

## Why fast vs cold

- Fast: auth settle + cache hits across players / prepared / shell summary.
- Cold: expired sleeper JSON TTL + cold valuation/rank build + cold league summary — previously all before dismiss.

## Remaining bottleneck

Post-dismiss cold valuation + league summary can still take tens of seconds before Dashboard recommendations appear. The user is already inside the app with navigation. Next measured owner after this PR: **prepared valued/ranked frame cold miss** (then shell summary enrichment).

## Verdict direction

KEEP STREAMLIT — COLD START PATH FIXED for global loading, with remaining post-dismiss football hydration owned by prepared-frame cold miss.
