# DynastyGM MVP Deployment

## Start command

```text
streamlit run app.py
```

Let the deployment platform provide its own port. The application does not require
port `3000`; that port is used only by the local Windows launcher and smoke tests.

## Python dependencies

- Use Python 3.11 or newer. Python 3.13 is the recommended deployment target.
- Runtime packages are declared in `requirements.txt`.
- Test-only packages are declared in `requirements-dev.txt`.
- Install both files only in development or CI.

## Environment variables

No environment variable is required for the current MVP.

- `DYNASTYGM_BUILD` is optional and labels locally stored feedback reports.
- `DYNASTYGM_DEBUG_UI` is optional. Leave it unset in production. Values such as
  `1`, `true`, `yes`, or `on` enable internal decision-debug sections.

## Runtime requirements

The deployment environment must:

- allow outbound HTTPS requests to Sleeper, FantasyCalc, player-image CDNs, and
  configured news feeds;
- permit the process to write to the local `data/` directory;
- start from `app.py` with the repository root as the working directory.

The MVP creates player databases and API caches on demand. A cold process may take
longer while those files are rebuilt.

## Files that must not be deployed from a developer machine

The following mutable files can contain usernames, league identifiers, preferences,
feedback, cached news, or downloaded player data and are excluded by `.gitignore`:

- `data/accounts.json`
- `data/profile.json`
- `data/feedback_reports.jsonl`
- `data/weekly_rank_snapshots.json`
- `data/news_cache.json`
- `data/roster_news_cache.json`
- `data/players.db`
- `data/sleeper_players.json`
- `data/sleeper_player_stats_*.json`
- `data/fantasycalc_values.csv`
- local Streamlit smoke-test output, logs, virtual environments, and test caches

If deployment artifacts are uploaded directly instead of built from version
control, exclude these files manually.

## Current MVP storage limitation

Accounts, preferences, feedback, snapshots, and caches use local files. On
multi-instance or ephemeral hosting, writes may not persist or synchronize between
instances. This is acceptable only if that limitation matches the MVP deployment
plan. Durable multi-user storage requires a separate persistence project.

## Pre-launch checks

1. Confirm the deployment artifact contains no developer `data/` files.
2. Confirm `DYNASTYGM_DEBUG_UI` is unset.
3. Start the app from a clean process and verify onboarding is shown.
4. Enter a test Sleeper username and explicitly choose a league.
5. Verify Dashboard, My Team, Trade Hub, Waivers, Draft Center, and legal pages.
6. Submit a test feedback report and confirm the deployment filesystem behavior is
   understood.
