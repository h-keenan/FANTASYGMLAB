# Post-first-useful Game Plan fingerprint drift (#239)

## Incident

Production session `a85e97c9` proved #238 fixed the post-football player-refresh
stall. Dashboard reached:

`football_context_ready` → `dashboard_game_plan_entry` → package MISS →
`game_plan_first_useful` → `dashboard_football_ready`

Immediately afterward, the post-usable-auth / presentation remount changed Game
Plan fingerprint inputs:

| Component | First package | Remount |
| --- | --- | --- |
| package fingerprint | `d0d36a0b` | `820ed613` |
| team_strategy | `03e8f038` | `468ac786` |
| prepared frame | `ccc7b75c` | `ccc7b75c` (unchanged) |
| trade pick_score_multiplier | `82c8b606` | `0354ca44` |

Symptoms: `package_fingerprint_drift` → package MISS → trade rebuild (~4.4s) →
`duplicate_work` / `post_ready_rebuild` after Dashboard was already useful.

## Root cause

1. **Identity shell** seeded `active_team_strategy` from session default (`retool`)
   for the first package fingerprint.
2. **Valued shell enrichment** (after Game Plan) resolved real football strategy
   and wrote it into session state.
3. Identity and valued shells shared a **single** shell-chrome memo slot, so valued
   enrichment clobbered the identity signature.
4. Post-usable-auth remount rebuilt identity chrome (signature miss) reading the
   enriched session strategy → fingerprint drift → package MISS.

`pick_score_multiplier` in the **trade** fingerprint is strategy-adjusted, so
strategy drift also moved the trade key.

## Fix

1. Resolve and **lock** canonical `team_strategy` + base pick multiplier **before**
   the first package fingerprint (`modules/game_plan_truth_canon.py`).
2. Presentation enrichment cannot overwrite the lock; explicit My Team strategy
   changes replace it and invalidate once.
3. Shell chrome memos are **per-signature** so identity and valued do not clobber.
4. Fingerprints normalize pick multipliers to a stable 8-decimal string.
5. Diagnostics: `game_plan_truth_mutation` / `game_plan_truth_canon_ready` when
   `DYNASTYGM_STARTUP=1`.

## Acceptance

An unchanged returning-user Dashboard has exactly one Game Plan package build;
later auth/presentation reruns are package HITs with zero post-READY league /
trade / briefing / compose rebuilds.
