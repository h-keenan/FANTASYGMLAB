# Repository root & generated artifact contract

| Field | Value |
| --- | --- |
| Baseline | `b919eed` (main after #207) |
| Scope | Filesystem hygiene: root clutter, ignores, artifact ownership |
| Non-changes | Football logic, UI, auth, entitlements, Stripe, Supabase |

## Root inventory — before

Tracked root contained ~194 Streamlit harness `.tmp_*` / `.out` / `.err` logs, plus:

| Entry | Classification |
| --- | --- |
| `app.py`, `modules/`, `services/`, `scripts/`, `tests/` | A canonical source |
| `.gitignore`, `.python-version`, `requirements*.txt`, `render.yaml` | B configuration |
| `AGENTS.md`, `DEPLOYMENT.md`, `docs/` | C documentation |
| `favicon.png`, `favicon.ico`, `assets/`, `data/players.db`, Sleeper/FantasyCalc seeds | D required runtime / fixture data |
| `.tmp_streamlit_*`, `.tmp_*` | F temporary (incorrectly tracked) |
| `debug_bug_check.py` | J obsolete one-off |
| `run_dynastygm_3030 - Copy.bat` | J accidental duplicate |
| `run_dynastygm_3030.bat` | G local developer launcher (kept) |
| `artifacts/**` (local) | E generated (mostly untracked; one golden JSON was mis-homed) |
| `.cursor/`, `.pytest_cache/`, `__pycache__/` | G/H local/cache |

## Root inventory — after

Intentional root files only:

```
.gitignore
.python-version
AGENTS.md
DEPLOYMENT.md
app.py
favicon.ico
favicon.png
render.yaml
requirements-dev.txt
requirements.txt
run_dynastygm_3030.bat
```

Plus directories: `.github/`, `assets/`, `config/`, `data/`, `docs/`, `modules/`, `scripts/`, `services/`, `tests/`, `artifacts/` (`.gitkeep` only).

## Deleted (from git tracking)

- All tracked `.tmp_*` / `.tmp_streamlit_*` `.out` / `.err` pairs (194 files)
- `debug_bug_check.py` (no product/CI reference)
- `run_dynastygm_3030 - Copy.bat` (duplicate launcher)

Working-tree copies of the tmp logs were removed locally.

## Moved

| From | To | Why |
| --- | --- | --- |
| `artifacts/archetype_experiments/contender_fixture_validation.json` | `tests/fixtures/archetype_experiments/` | Golden deterministic fixture, not ephemeral QA capture |

## Generated / temporary ownership

| Kind | Location | Policy |
| --- | --- | --- |
| CI / Playwright mobile shots | `artifacts/ui-mobile/` | Ignored; CI uploads as workflow artifacts |
| Brand/marketing capture logs | `artifacts/*.log` | Ignored |
| Brand comparison boards | `artifacts/brand-*` | Ignored |
| Measurement JSON | `artifacts/measurements/` | Ignored; `measure_app_wide_performance.py` defaults here |
| Share-card PNGs | OS temp `fantasygmlab_share_cards/` | Runtime temp + TTL cleanup (#171) |
| Public player snapshots | `data/*.public-player-snapshot.*` | Ignored derived cache |
| Launch analytics JSONL | `data/launch_analytics.jsonl` | Ignored host-local analytics |
| Feedback reports | `data/feedback_reports.*` | Ignored |

## Canonical data retained under `data/`

| File | Role |
| --- | --- |
| `players.db` | Canonical checked-in player fixture / SQLite source |
| `sleeper_players.json`, `sleeper_player_stats_2025.json` | Seed/provider snapshots |
| `fantasycalc_values.csv` | Valuation seed |
| `news_cache.json`, `roster_news_cache.json` | Seeded runtime news cache (may refresh locally) |
| `accounts.json`, `profile.json`, `weekly_rank_snapshots.json` | App fixture/config seeds |
| `.gitkeep` | Keeps empty-data edge cases safe |

Do **not** delete `players.db` as “just a .db”.

## `.gitignore` contract

Ignore: Python/cache/editor/OS junk, root tmp/streamlit logs, entire `artifacts/**` (except `.gitkeep`), analytics/feedback JSONL, public-player snapshot sidecars, local measurement dumps under `data/`.

Do not ignore: `assets/`, checked-in `data/` seeds, root favicons (Streamlit `page_icon` fallback).

## Script output paths

| Script | Output |
| --- | --- |
| `validate_mobile_ui.py` | `artifacts/ui-mobile` |
| `capture_*_screens*.py` | `artifacts/…` or `assets/marketing/…` |
| `generate_brand_*` / `compare_brand_*` | `assets/brand` or `artifacts/brand-*` |
| `measure_app_wide_performance.py` | default `artifacts/measurements/app_wide_performance.json` |
| Share cards | OS tempdir (not repo root) |

## Temp-file policy

- Prefer `tempfile` / OS temp / `artifacts/` — never silent cwd dumps.
- Historical root `.tmp_streamlit_*` must stay untracked (ignore + deleted from index).

## Remaining intentional clutter

- `run_dynastygm_3030.bat` — local Streamlit launcher convenience
- Root favicons — dual of `assets/brand/` for `page_icon` fallback
- Seeded `data/news_cache.json` may diverge locally after runs (restore before commit if dirty)
