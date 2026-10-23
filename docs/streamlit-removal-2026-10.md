# Streamlit removal (2026-10)

The original Streamlit web app (`app.py` plus the `*_ui.py` render modules) is
deprecated and has been deleted. Production is the FastAPI services
(`services/mobile_api_service.py`, `services/stripe_webhook_service.py`,
`services/revenuecat_webhook_service.py`), the Next.js web app (`web-next/`)
and the Expo app (`mobile/`). Nothing in those imports `streamlit`.

## How "Streamlit-only" was proven

An AST import graph (static imports, lazy imports inside functions, and
`"modules.x"` string references) was built from the real production entry
points: the three FastAPI services, `services/fantasy_content.py`, and every
script used by a workflow, the Dockerfile, a cron job or a content export
(`prepare_public_player_cache`, `refresh_and_commit_players_db`,
`refresh_players_db_subprocess`, `run_player_rating_snapshot`,
`run_push_trigger_sweep`, `run_trade_outcome_result_sweep`,
`sync_injury_status`, `projection_scoreboard`, `build_static_landing_assets`,
`classify_pr_changes`, `benchmark_public_player_cache`,
`export_legal_content`, `export_methodology_content`). A module was deleted
only if it is outside that closure. The closure was re-run after every step
until no module in it imported `streamlit`. Final check: every module,
service and script imports with `streamlit` blocked (`sys.modules["streamlit"] = None`)
and in a venv that does not have streamlit installed.

## What was removed

- `app.py` (23.7k lines), `.streamlit/config.toml`, `run_dynastygm_3030.bat`.
- 146 files in `modules/`: all Streamlit render modules (`*_ui.py`, `premium_page`
  checkout, `account_ui`, `guest_conversion`, `marketing_landing`,
  `html_rendering`, `page_shell`, `workspace_ui`, ...), the ~45 `*_styles.py`
  CSS-injection modules, and helper modules whose only importer was `app.py`
  or another deleted module (`application_shell`, `navigation_state`,
  `render_ownership`, `route_render_ownership`, `deferred_rendering`,
  `workflow_continuity`, `archetype_*`, `valuation_archetype*`, `founder_labs`,
  `founder_ops`, `league_intelligence`, `webhook_probe_config`, ...).
- 81 files in `scripts/`: the Streamlit AppTest/Playwright visual harnesses
  (`*_visual_harness.py`, `ui_validation_harness.py`, `validate_*`,
  `capture_*`), Streamlit latency/rerun measurement scripts, and Render/Streamlit
  launch gates (`deployment_check.py`, `verify_production_domain_cutover.py`,
  `verify_p0_launch_blockers.py`, `founder_beta_ops_public_probe.py`,
  `probe_founder_beta_launch.py`, `audit_unused_modules.py`,
  `check_founder_beta_performance_budget.py`, `benchmark_deferred_payload.py`).
- 143 test files that only exercised the above (AppTest, CSS/source-string and
  render-HTML tests), plus about 300 individual test functions removed from
  files that also test live logic (tests that read `app.py`, deleted modules,
  or UI-only helpers). `tests/fixtures/archetype_experiments/` went with the
  deleted archetype code.
- 24 Streamlit-only engineering docs (rerun/render stability, CSS delivery,
  Streamlit latency investigations, ...). Other docs that still describe
  Streamlit now carry a "Historical / partly obsolete" banner instead of being
  rewritten.
- `streamlit` from `requirements.txt`, `playwright` from
  `requirements-dev.txt`, the `mobile-ui` CI job (Streamlit fixture + Playwright),
  and the CI steps that ran deleted scripts.
- Deploy config: the `web` (Streamlit) service in `docker-compose.yml`, the
  `fantasygm-lab` service in `render.yaml`, the `web:8080` upstream in
  `Caddyfile`, and the `NEXT_PUBLIC_STREAMLIT_BASE_URL` build arg / env var.
- web-next: `streamlitLink.ts` (renamed to `destinationLabels.ts`, labels
  only). The Game Plan / Watchlist fallback link now goes to the league
  Dashboard instead of a Streamlit `?page=` URL, and the "Open classic Draft
  Center" link (Streamlit-only) was removed from the Draft Center page.

## What was kept, and why

Live code imported by the production services lived in Streamlit-flavoured
files. Behaviour is unchanged; only the Streamlit parts were dropped.

| New / pruned module | Came from | Used by |
| --- | --- | --- |
| `modules/premium_benefits.py` | `premium_page.py` (Premium benefit copy) | `/v1/me`, paywall |
| `modules/draft_center_cards.py` | `draft_center_ui.py` | Draft Center endpoint |
| `modules/trade_hub_presentation.py` | `trade_hub_ui.py` (ordering, confidence, injury context) | Trade Hub, dashboard, league glance |
| `modules/waivers_logic.py` | `waivers_ui.py` (pool, ranking, labels) | Waivers endpoints, dashboard |
| `modules/league_display.py` | `league_workspace_ui.py` (score formatting helpers) | API, dashboard |
| `player_quick_view.py`, `player_cards.py`, `notification_center.py`, `startup_coordinator.py`, `dashboard_workflow.py`, `premium_conversion.py`, `dashboard_loading_state.py`, `legal_pages.py`, `methodology_page.py` | pruned in place to the non-render parts | API / auth / mobile content exports |

`legal_pages.py` and `methodology_page.py` stay because
`scripts/export_legal_content.py` and `scripts/export_methodology_content.py`
generate the mobile app's bundled legal and methodology JSON.

Replacing the Streamlit APIs that live code used:

- `rankings._cached_public_players`: `@st.cache_data(max_entries=4)` became a
  small in-process keyed cache (`rankings._process_cache_data`) with the same
  contract (bounded, per-caller deep copy, `.clear()`).
- `st.secrets` fallbacks (`gm_targets`, `team_stance`, `referrals`,
  `notification_center`): removed; configuration comes from environment
  variables / `local_secrets`, which is what production already used.
- `performance._session_state()` and `sleeper._note_provider_timing`: the
  session store was `st.session_state`; they now no-op (callers already
  handled "no session"). `runtime_trace`'s Streamlit message hooks removed.
- `pyarrow` is now listed explicitly in `requirements.txt`. It used to arrive
  only as a transitive dependency of streamlit, and pandas 3 switches string
  storage depending on whether it is installed.

## Deploy-related files changed

`docker-compose.yml`, `Caddyfile`, `render.yaml`, `Dockerfile` (comments only),
`.dockerignore` (comment only), `.env.example`, `requirements.txt`,
`requirements-dev.txt`, `.github/workflows/ci.yml`, `web-next/Dockerfile`,
`web-next/.env.example`, `DEPLOYMENT.md`, `config/README.md`,
`docs/SELF_HOSTED_MIGRATION.md` (table row / log command).
`deploy/release_deploy.sh`, `deploy/systemd/fantasygmlab.service` and the other
workflows are unchanged (`docker compose up -d --remove-orphans` removes the old
`web` container on the next deploy).

## Before merging (server-side items this repo cannot show)

- `deploy/autopull.sh` and `/usr/local/bin/fantasygmlab-sync-caddy` live on the
  box, not in this repo. If either health-checks or routes to the `web`
  service by name, update it first or autopull will roll the deploy back.
  `Caddyfile` now sends `{$APP_DOMAIN}` to `web-next:8080`.
- A `docker-compose.override.yml` on the server that references `web` would
  now define a service with no image.

## Leftover references (intentionally not rewritten)

- Docs: `runtime-environment-contract.md`, `production-launch-configuration.md`,
  `RENDER_DEPLOYMENT.md`, `STRIPE_TEST_MODE_SETUP.md`,
  `stripe-webhook-service-contract.md`, `SUPABASE_SETUP.md` and ~40 audit docs
  still say things like "must be absent on Streamlit". Read "Streamlit web app"
  as "the web/API service": `SUPABASE_SERVICE_ROLE_KEY` and `STRIPE_WEBHOOK_SECRET`
  still belong only on the webhook services. The `docs/supabase_*.sql` file
  comments also mention Streamlit.
- `modules/app_config.py` still carries `MANAGED_WEB_*` names and
  `enforce_managed_web_config` from the Streamlit era; nothing calls the
  enforcement any more, the helpers are still used for config lookup.
- Diagnostic key names such as `streamlit_cache_data`, `streamlit_hit` and
  `streamlit_cache_data_absent` (`rankings`, `trade_ideas`, `runtime_trace`) are
  kept so existing log consumers and tests do not change.
- `.gitignore` keeps `.streamlit/secrets.toml`, `.tmp_streamlit_*`,
  `streamlit_*.log`; `tests/test_repository_root_hygiene.py` pins them.
- Many module comments say "Streamlit" for historical context.

## Validation

See the PR description for the test comparison against `origin/main`.
