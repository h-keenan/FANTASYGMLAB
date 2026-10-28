# Incident runbook

Companion to `docs/box-runbook.md` (deploys) and `docs/billing-on-supabase.md`
(billing). This file covers what to do when something is wrong, who finds out,
and how to recover. No secrets here. Owners: **box/Cloudflare/Supabase
dashboard actions are human (Zach)**; code and docs are agent work.

## How we find out today

| Signal | Where it shows up | Latency |
| --- | --- | --- |
| `Ops Health Check` workflow (`.github/workflows/ops-health-check.yml`) | Opens/updates the GitHub issue "Ops health check is failing"; optional webhook ping if the `OPS_ALERT_WEBHOOK_URL` secret is set | 20 min nominal, often hours late (GitHub throttles schedules) |
| `Players DB Refresh` failure | GitHub issue "Players DB refresh is failing" | per 6 h run |
| Other scheduled workflows (news, push sweep, injury sync, snapshots, outcome sweep) | Only the freshness checks in the ops health check | see above |
| Backend exceptions | Sentry, only if `SENTRY_DSN` is set on the box; the web app and mobile app have no error tracker | n/a |
| Users | Discord channel, `feedback_reports` table (triage it: `status = 'new'`) | n/a |

There is no pager. Add an external uptime monitor (UptimeRobot, Better Stack or
Healthchecks) on `https://api.fantasygmlab.com/health`, `https://app.fantasygmlab.com/`
and `https://app.fantasygmlab.com/trade-analyzer` with SMS/push to a phone. That is the
only thing that wakes someone up.

Run the same checks by hand any time:

```
python scripts/ops_health_check.py          # public checks; add SUPABASE_* / GITHUB_TOKEN env for the rest
```

## Triage by symptom

| Symptom | First look | Likely fix |
| --- | --- | --- |
| Site down, `/health` fails | Cloudflare tunnel status, `docker compose ps` on the box | `docker compose up -d`; check `docker compose config` (broken override) |
| `/health` OK but `build` is old | `fgl-release status` | Approve or roll back the blocked release (`box-runbook.md`) |
| Slow pages during a traffic spike | `docker stats`, mobile-api CPU | Capacity is about 50 concurrent *cold* users (`docs/load-test-2026-10.md`); pre-warm, shed load, raise workers |
| Sleeper data empty/old | Sleeper 429s in mobile-api logs | `SLEEPER_CALLS_PER_MINUTE` budget (`modules/sleeper_budget.py`); wait it out |
| News or injury data stale | Ops check `news_fresh`, `workflow_*` | Re-run the workflow with `workflow_dispatch`; see "Scheduled jobs" |
| Push notifications late | Ops check `workflow_push_trigger_sweep` | Same; GitHub schedule delay is the usual cause |
| Paid user sees free tier | `billing_webhook_events`, then the `profiles` row | Replay the Stripe event from the Stripe dashboard; never edit `entitlement` by hand without a note |
| Sign-up/reset emails missing | Supabase Auth logs and SMTP settings | Confirm custom SMTP is configured (built-in sender is rate limited) |

## Scheduled jobs (GitHub Actions)

Nominal cron versus what we observed on 2026-10-27: news `*/15` ran about every
4 to 6 hours, push sweep `*/30` about every 5 hours. Anything that needs real
timeliness (lineup-lock pushes, injury alerts, deadline pushes) should move to a
systemd timer or cron on the box that runs the same `scripts/run_*.py` entrypoints
(box change, needs review). Until then treat GitHub schedules as best effort.

Re-run one by hand: GitHub, Actions, pick the workflow, "Run workflow".

## Backups and restore

* **Supabase (accounts, billing state, feedback, news, analytics)**: the only
  durable store of record. Confirm in the Supabase dashboard which backup tier
  the project has (daily backups need Pro; point-in-time recovery is a paid
  add-on). Do a restore drill into a scratch project once and write the result
  here. Until that is done, assume there is no tested restore.
* **`data/players.db` and the JSON caches**: versioned in git (refreshed by the
  scheduled commits). Restore by `git revert` of the bad data commit or
  `git checkout <good-sha> -- data/`. Never run `rankings.load_players` against the
  real file while testing.
* **Box volumes**: only Caddy's certificate state (`caddy_data`) is stateful.
  Redis is intentionally disposable (rate limits, single-flight caches, and the
  Free-tier counters in `modules/free_tier_ledger.py`; a Redis restart resets
  those counters).
* **Box itself**: rebuild from the repo plus `.env` and `docker-compose.override.yml`
  (kept off-repo). Store an encrypted copy of both outside the box.

## Rollback

* Code: `sudo /usr/local/sbin/fgl-release rollback` (cannot undo SQL migrations).
* A bad data commit: revert it on `main`; the box picks it up like any merge.
* Billing: `docs/billing-on-supabase.md` has the Edge Function rollback recipe.

## Secret rotation checklist

Rotate immediately if a key appears in a log, screenshot, chat, commit or issue.
Update every place in the same sitting.

| Secret | Rotate in | Update in |
| --- | --- | --- |
| Supabase service role key | Supabase, Project settings, API | Box `.env`, GitHub secret `SUPABASE_SERVICE_ROLE_KEY`, Edge Function secrets |
| Supabase anon key | Same (public, but rotates sessions) | Box web build args, mobile build env |
| Stripe secret + webhook signing secret | Stripe dashboard, Developers | Supabase Edge Function secrets (`stripe-webhook`, `create-checkout-session`, `billing-portal-session`) |
| RevenueCat webhook auth / API keys | RevenueCat project settings | Edge Function secrets, app builds |
| GitHub Actions secrets | Repo settings, Secrets | n/a |
| `OPS_ALERT_WEBHOOK_URL` | Discord/Slack integration | GitHub secret |

After rotating Stripe, send a test event and confirm a `billing_webhook_events` row.

## Data requests

* Delete: in-app, More, Account, Delete account (`public.delete_user()` RPC,
  `docs/supabase_delete_account.sql`). It deletes the Supabase user and cascades app
  tables. It does **not** cancel a Stripe subscription: cancel it in Stripe first.
* Export: `GET /v1/me/export` (in-app, More, Account).
* Contact: `support@fantasydesk.app` must have a working mailbox (MX records) before
  the address is shown to users. Verify with `dig MX fantasydesk.app`.

## After an incident

Write three lines in the Discord channel (what broke, how long, what changes), and
add the failure to the triage table above if it was new.
