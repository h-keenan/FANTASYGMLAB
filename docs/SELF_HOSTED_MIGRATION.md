# Self-Hosted Migration (Ubuntu 24.04 LTS)

Status: **additive prep only**. Nothing in this document, or in the Docker
artifacts it references, changes the live Render deployment. Render keeps
running exactly as `render.yaml` describes it until a separate, deliberate
cutover decision is made later. This runbook exists so that decision can be
made from a tested, working alternative rather than from scratch under
outage pressure.

## Why

Render has been experiencing a prolonged outage. coridian_ (product owner)
decided to prepare a self-hosted Ubuntu Server 24.04 LTS box as an
alternative, so this runbook and its accompanying Docker artifacts
(`Dockerfile`, `docker-compose.yml`, `Caddyfile`, `.env.example`,
`deploy/systemd/fantasygmlab.service`) are new files only — `render.yaml`
is untouched and Render is not being torn down.

## What's being replicated

From `render.yaml`, the following four **real** (non-cron) services. Note:
`render.yaml`'s `fantasygm-lab-stripe-webhook` entry is a **historical**
Blueprint identity whose association with the actual live Render service
(dashboard name `fantasygmlab-stripe-webhook`) is unverified — see
`docs/webhook-operational-authority.md`. That doesn't change anything
here (this table just mirrors `render.yaml`'s own service names and start
commands), but don't treat `fantasygm-lab-stripe-webhook` as a confirmed
production hostname when wiring up the real Stripe webhook URL at cutover.

| Render service | Container (docker-compose) | Start command |
|---|---|---|
| `fantasygm-lab` (Streamlit) | `web` | `streamlit run app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true` |
| `fantasygm-lab-mobile-api` | `mobile-api` | `uvicorn services.mobile_api_service:app --host 0.0.0.0 --port $PORT` |
| `fantasygm-lab-stripe-webhook` | `stripe-webhook` | `uvicorn services.stripe_webhook_service:app --host 0.0.0.0 --port $PORT` |
| `fantasygm-lab-revenuecat-webhook` | `revenuecat-webhook` | `uvicorn services.revenuecat_webhook_service:app --host 0.0.0.0 --port $PORT` |

Plus the static marketing site (`fantasygm-lab-marketing`, static
`./static/landing`), served directly by Caddy's `file_server` — no Python
container needed for it.

### What's intentionally NOT replicated here

The 4 Render **cron** jobs — `fantasygm-lab-push-trigger-sweep`,
`fantasygm-lab-trade-outcome-result-sweep`,
`fantasygm-lab-players-db-refresh`, `fantasygm-lab-injury-status-sync` —
are **out of scope for this box**. They are being migrated to GitHub
Actions scheduled workflows in a separate, parallel PR. Do not containerize
them here and do not expect them to run on this server; if that parallel PR
hasn't landed yet when this box goes live, those sweeps simply won't run
until it does (same as if Render's crons were paused).

## 1. Fresh server setup

Starting point: a clean Ubuntu Server 24.04 LTS box with SSH access as a
sudo-capable user.

### 1.1 Create a non-root deploy user

Never run the stack as root.

```bash
sudo adduser deploy
sudo usermod -aG sudo deploy
# Copy your SSH key so you can log in as `deploy` directly:
sudo rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy
# From here on, SSH in as deploy@<server-ip> instead of root/your sudo user.
```

### 1.2 Install Docker Engine + Compose plugin

Use Docker's official apt repository (the Ubuntu-bundled `docker.io`
package lags behind and doesn't always ship the `docker compose` v2 plugin):

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Let the deploy user run docker without sudo:
sudo usermod -aG docker deploy
# Log out and back in (or `newgrp docker`) for the group change to apply.

docker --version
docker compose version
```

### 1.3 Firewall (ufw)

Only ports 80 and 443 should be reachable from the internet. SSH stays
open on whatever port you actually use (22 by default — change this if
you've moved SSH to a non-standard port).

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH      # or: sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status verbose
```

Do **not** open any other port. Every service (`web`, `mobile-api`,
`stripe-webhook`, `revenuecat-webhook`) is reachable only through Caddy on
the internal Docker network — see `docker-compose.yml`'s `internal`
network — and none of their container ports are published to the host.

## 2. Clone the repo and configure `.env`

```bash
sudo mkdir -p /opt/fantasygmlab
sudo chown deploy:deploy /opt/fantasygmlab
git clone https://github.com/h-keenan/FANTASYGMLAB.git /opt/fantasygmlab
cd /opt/fantasygmlab
cp .env.example .env
```

Now fill in every value in `.env`. Every variable name matches the
corresponding Render service's env var **exactly** (see `.env.example`'s
section comments for which Render service each group came from), so this
is a direct dashboard-to-file copy, not a guessing exercise:

1. Open the Render dashboard.
2. For each of `fantasygm-lab`, `fantasygm-lab-stripe-webhook`,
   `fantasygm-lab-mobile-api`, and `fantasygm-lab-revenuecat-webhook` →
   **Environment** tab, copy each `sync: false` secret's current value.
3. Paste it into `.env` under the matching variable name.
4. Fill in the `CADDY_ACME_EMAIL` and the `*_DOMAIN` placeholders (see
   DNS section below — these can be filled in immediately even before DNS
   is switched, since Caddy only requests a certificate for a domain the
   first time it actually receives a request for it).

`.env` is already gitignored (`.gitignore`'s `.env`/`.env.*`/`!.env.example`
rules) — never commit the filled-in file, and never paste real secret
values into a commit message, PR description, or this repo in any form.

## 3. Bring the stack up

```bash
cd /opt/fantasygmlab
docker compose build
docker compose up -d
docker compose ps
```

Verify every container reports healthy:

```bash
docker compose ps --format 'table {{.Name}}\t{{.Status}}'
```

At this point DNS still points at Render, so nothing public-facing has
changed yet. Verify the new stack directly against the server's IP before
touching DNS (see "Pre-cutover verification" below).

`docker-compose.yml` sets `DYNASTYGM_SELF_HOSTED=1` on every app service
automatically — this is **not** something to add to `.env`. It is the
marker `modules/app_config.py`'s `is_managed_cloud_host()` needs to treat
this box the same way it already treats Render (platform-injected
`RENDER`/`RENDER_SERVICE_ID`/`RENDER_EXTERNAL_URL`): fail closed on missing
Supabase config instead of silently running as if this were a contributor's
local checkout, and keep customer-unsafe debug/premium-override switches
locked. If `docker compose ps` or the app's own behavior ever suggests this
box is being treated as "local" (e.g. the Founder Ops environment label
reads anything other than `self_hosted`), check that this var actually
reached the container (`docker compose exec web env | grep DYNASTYGM_SELF_HOSTED`)
before debugging anything else.

### 3.1 Install the systemd unit (start on boot)

```bash
sudo cp deploy/systemd/fantasygmlab.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now fantasygmlab.service
sudo systemctl status fantasygmlab.service
```

This ensures the whole stack comes back up automatically after a reboot or
host crash — Docker Compose's own `restart: unless-stopped` policy (set on
every service) handles an individual container crashing while the box
stays up, but only systemd (or Docker's own `--live-restore`/boot-start of
the daemon) brings the stack back after the *machine* restarts. Self-hosted
means there's no platform auto-restarting a crashed box for you, so both
layers matter.

## 4. Pre-cutover verification (before touching DNS)

**Do not flip DNS blind.** Verify the new server works first by hitting it
directly via its IP, overriding only your own machine's name resolution —
this proves the stack is healthy from the outside world's perspective
(real TLS cert request included) without affecting any real user yet.

Caddy only issues a Let's Encrypt certificate for a domain once it
receives a request for that exact hostname with the right `Host` header —
so to test this pre-cutover, temporarily point your own machine's
`/etc/hosts` at the server:

```
<new-server-ip>  app.fantasygmlab.com
<new-server-ip>  fantasygmlab.com
<new-server-ip>  www.fantasygmlab.com
<new-server-ip>  api.fantasygmlab.com
<new-server-ip>  stripe-webhook.fantasygmlab.com
<new-server-ip>  revenuecat-webhook.fantasygmlab.com
```

This only affects name resolution on your own machine, not the live DNS
record anyone else resolves — it's a safe way to dry-run the real hostname
+ TLS path before the actual cutover. With that in place:

- Visit `https://app.fantasygmlab.com` in a browser — confirm a valid
  cert was issued and the Streamlit app loads (Dashboard, My Team, Trade
  Hub, Waivers, Premium — same smoke checklist as
  `docs/RENDER_DEPLOYMENT.md`'s "Deploy And Verify" section).
- `curl https://api.fantasygmlab.com/health` → `{"status": "ok", ...}`
- `curl https://stripe-webhook.fantasygmlab.com/health`
- `curl https://revenuecat-webhook.fantasygmlab.com/health`
- Visit `https://fantasygmlab.com` — confirm the static marketing page
  loads.
- Run through signup/login/saved-league restore and (if Stripe test
  config is present) a test checkout, same as the existing Render
  pre-launch checklist.

Remove the `/etc/hosts` entries once verification is done (or leave them —
they only affect your own machine).

## 5. DNS cutover

This is the actual moment of cutover — the point where real user traffic
starts reaching the new server instead of Render. Only do this after
section 4 passes cleanly.

In your DNS provider, change:

| Host | Record type | Old target | New target |
|---|---|---|---|
| `app.fantasygmlab.com` | A (or CNAME) | Render-provided target | New server's public IP |
| `fantasygmlab.com` | A | Render-provided target | New server's public IP |
| `www.fantasygmlab.com` | CNAME/A | Render-provided target | New server's public IP |
| `api.fantasygmlab.com` | A | *(new — not previously a custom domain)* | New server's public IP |
| `stripe-webhook.fantasygmlab.com` | A | *(new)* | New server's public IP |
| `revenuecat-webhook.fantasygmlab.com` | A | *(new)* | New server's public IP |

Notes:

- `api.fantasygmlab.com` and the two webhook subdomains are **new**
  custom domains — today those services are reached via Render's own
  `*.onrender.com` hosts (see `render.yaml` and
  `docs/webhook-operational-authority.md`). Decide at cutover time whether
  external integrations (Stripe's webhook endpoint URL, RevenueCat's
  webhook URL, the mobile app's configured API base URL) get repointed to
  these new hostnames, or whether you'd rather keep those specific
  `*.onrender.com` hostnames resolving elsewhere — that's a product/ops
  decision outside this runbook's scope, called out here so it isn't
  missed.
- DNS propagation isn't instant. Expect stragglers for up to the TTL
  duration on the old records; don't decommission anything on the Render
  side (there is nothing to decommission per this task's scope anyway —
  Render keeps running) until traffic has clearly moved.
- After cutover, update the Stripe webhook endpoint URL and RevenueCat
  webhook URL in their respective dashboards if you repointed those
  subdomains, and re-verify a real signed webhook reaches the new host.

## 5.5. Keeping the box in sync with `main` (no auto-deploy here)

Render auto-deploys on every push to `main` — that behavior does **not**
exist on this box. Nothing in this repo (no GitHub Actions workflow, no
webhook, no cron) rebuilds or restarts this stack when `main` changes;
`.github/workflows/` only runs CI (`ci.yml`), a keep-alive ping
(`keep-alive.yml`), and auto-merge (`auto-merge.yml`) — none of them touch
this server. The stack runs whatever was on disk the last time someone ran
section 3's `docker compose build && docker compose up -d` here, and it
will keep serving that exact build indefinitely, through any number of
later merges to `main`, until a human repeats those steps.

Concretely: if this box was stood up once and left alone, it can silently
drift arbitrarily far behind `main` — including missing later brand-asset,
styling, or welcome-screen changes that look completely normal in the repo
and in CI, but were never actually deployed here. If the live site ever
looks wrong in a way the current `main` branch's code doesn't explain,
check this first, before assuming it's a code bug:

```bash
cd /opt/fantasygmlab
git fetch origin
git log --oneline HEAD..origin/main   # anything listed here is NOT live yet
git pull
docker compose build
docker compose up -d
docker compose ps --format 'table {{.Name}}\t{{.Status}}'
```

Standing up real continuous deployment for this box (e.g. a scheduled or
webhook-triggered GitHub Actions job that SSHes in and runs the block
above) is a reasonable follow-up, but is intentionally out of scope here —
it needs a deploy credential/secret decision this runbook isn't positioned
to make unilaterally.

## 6. Rollback plan

Because Render is **not** being decommissioned as part of this migration,
rollback is simply: **revert the DNS changes from section 5 back to their
previous Render targets.** That's the entire safety net — Render keeps
running the whole time, so there's no redeploy, no data restore, and no
rebuild involved in rolling back. If something is wrong with the new
server after cutover:

1. Revert each DNS record in the table above back to its original
   Render target.
2. Wait out DNS propagation (same TTL caveat as above).
3. Investigate the new server at leisure, with zero customer-facing time
   pressure, since Render is already serving traffic again.

This is also why section 4's pre-cutover verification matters: catching a
problem there costs nothing (DNS was never touched), while catching the
same problem after cutover costs a DNS round-trip.

## 7. Cron jobs: now on GitHub Actions, not this box

The 4 cron jobs that exist in `render.yaml` today —

- `fantasygm-lab-push-trigger-sweep` (`*/30 * * * *`)
- `fantasygm-lab-trade-outcome-result-sweep` (`0 13 * * *`)
- `fantasygm-lab-players-db-refresh` (`0 */6 * * *`)
- `fantasygm-lab-injury-status-sync` (`*/30 * * * *`)

are being migrated to GitHub Actions scheduled workflows in a **separate,
parallel PR** — not part of this migration's scope. This server does not
run any of them; there is no cron container, no host crontab entry, and no
systemd timer for them in this stack on purpose. Once that parallel PR
lands, GitHub Actions runs them on its own schedule regardless of which
host serves live web traffic, so they're decoupled from this cutover
either way (they already push results to Supabase or to `main` via a
scoped PAT — they don't need to run on the same box as the web services).

## 7.5. Resource isolation, Redis, and worker count (read before changing any of this)

Two things are genuinely different here vs. Render, both purely because
this box colocates every service instead of giving each one its own
isolated instance — plus a third, newer piece (Redis) that the other two
now depend on:

**Per-container memory/CPU limits.** `docker-compose.yml` sets an explicit
`mem_limit`/`cpus` on every service, sized for a 16GB RAM / 6-core /
12-thread box (per the latest hardware spec for this migration — confirm
this is still the actual box before relying on the exact numbers below; an
older "4-core/8-thread" figure was used for the original single-worker
sizing and is now stale):
`web`: 4GB RAM / 2 CPUs; `mobile-api`: 7GB RAM / 4 CPUs (see below for why
this grew); `redis`: 256MB / 0.25 CPUs; `stripe-webhook`/
`revenuecat-webhook`: 512MB / 0.5 CPUs each; `caddy`: 256MB / 0.5 CPUs —
leaving real headroom (~3.5GB RAM, ~4.25 logical threads) for the host and
Docker itself. On Render, one service leaking memory or pegging CPU
couldn't affect the others; on this box, without a limit, it could — these
limits are the guardrail that replaces that isolation. If you resize the
box, resize these proportionally rather than removing them.

**`mobile-api` now runs multiple workers, backed by Redis.** It used to be
single-worker on purpose: `services/mobile_api_service.py` kept an
in-memory rate limiter and three `@lru_cache` + `threading.Lock`
single-flight caches (`modules.trade_hub_engine`, `modules.league_rankings`
x2, `modules.playoff_simulator`), all scoped to one process's memory.
Multiple worker processes would each get their own independent copy of all
of that: the rate limiter's effective per-client limit would silently
become `limit * worker_count` instead of `limit` (a correctness
regression, not just a perf question), and the single-flight caches would
stop actually sharing work across workers (the exact problem they exist to
avoid, just moved up one level).

That state now lives in Redis instead (see the new `redis` service and
`modules/redis_cache.py`), which is what makes `--workers` safe:
`mobile-api`'s command now reads
`--workers $$MOBILE_API_WORKERS` (env var, default 4 — see
`docker-compose.yml`'s own comment on the `mobile-api` service for the
box-spec/sizing reasoning), and `depends_on: redis: condition:
service_healthy` means **Redis must come up healthy before mobile-api
starts** — Compose enforces this ordering automatically on `docker compose
up`, but it's worth knowing about if you ever start services individually
(`docker compose up mobile-api` with `redis` not already running will wait
on it, not skip the dependency).

One piece of per-process state did **not** move to Redis, and isn't in
scope here: the warmed `rankings.load_players` player table
(`_warm_players_cache_at_startup`). Each `mobile-api` worker still loads
and holds its own copy of that in memory — this is why `mobile-api`'s
`mem_limit` grew substantially (not just to cover Redis-related changes)
when `--workers` went from 1 to 4.

**Redis itself** (`redis:7-alpine`, `--maxmemory 200mb --maxmemory-policy
allkeys-lru`) is a simple, disposable state store here, not a database: no
persistence volume is configured on purpose, since every single thing
cached in it (rate-limit counters, the three ~30s-TTL single-flight cache
entries) is safe to lose on a restart — every reader of it already
degrades gracefully (fails open / recomputes) if a key it expects isn't
there, by the same design that makes it safe if Redis is unreachable
entirely (see `modules/redis_cache.py`'s module docstring). If you ever
point `REDIS_URL` at a Redis instance shared with something else, keep
that "disposable, no data of record" assumption true for whatever else
shares it, or give this stack its own instance/database index instead.

## 8. Logging and monitoring on the self-hosted box

Render aggregates logs per-service in its dashboard; a self-hosted box
needs an explicit equivalent so logs are both inspectable live and don't
silently fill the disk over time.

### Live/ad-hoc logs

```bash
docker compose logs -f                 # all services, follow
docker compose logs -f web             # just the Streamlit app
docker compose logs --since 1h caddy   # last hour, Caddy only
```

### Log rotation

By default, Docker's `json-file` logging driver has **no size cap** —
left alone, a busy container's logs can eventually fill the disk. Cap and
rotate logs at the daemon level so this applies to every container
automatically, including ones added later:

```bash
sudo tee /etc/docker/daemon.json > /dev/null <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "5"
  }
}
EOF
sudo systemctl restart docker
```

This keeps at most 5 rotated 10 MB log files per container (50 MB cap per
container) — restart the stack (`docker compose up -d` again, or just
`systemctl restart fantasygmlab`) after changing this, since existing
containers must be recreated to pick up a new logging config.

### Basic uptime monitoring

Nothing elaborate is required for a first pass — a free external uptime
checker (e.g. a UptimeRobot/Healthchecks.io-style HTTP monitor) pointed at
`https://app.fantasygmlab.com/_stcore/health` and each FastAPI service's
`/health` endpoint gives the same "is it actually up" signal Render's own
health checks provided, without needing to build anything custom. This is
a reasonable follow-up once the box is live, not a blocker for the
migration prep itself.

## Appendix: file inventory

| File | Purpose |
|---|---|
| `Dockerfile` | Multi-stage build (builder installs deps into a venv; runtime stage is a slim Python image + app code). One shared image for all four real services — see the Dockerfile's own header comment for the reasoning. |
| `.dockerignore` | Keeps the build context to only what the Python services need (excludes `mobile/`, `tests/`, `docs/`, dev/editor state, secrets). |
| `docker-compose.yml` | Orchestrates `web`, `mobile-api`, `redis`, `stripe-webhook`, `revenuecat-webhook`, and `caddy`; healthchecks on each app service's existing `/health`/`/_stcore/health` endpoint (and `redis-cli ping` for `redis`); `mobile-api` depends on `redis` reporting healthy before it starts, and `caddy` waits on all four app services' healthchecks (`depends_on: condition: service_healthy`) before proxying; `restart: unless-stopped` everywhere; secrets only via `.env`; sets `DYNASTYGM_SELF_HOSTED=1` on every app service (see section 3). |
| `Caddyfile` | Reverse proxy + automatic HTTPS routing per placeholder subdomain, plus static `file_server` for the marketing site. Also handles response compression (`encode zstd gzip` on `web`/`mobile-api`/the marketing site, skipped on the two webhook endpoints) and `Cache-Control` headers on the marketing site's static assets (images/fonts get `max-age=86400`, CSS/JS get `max-age=3600`, both `must-revalidate` since those files aren't content-hashed; HTML/`robots.txt`/`sitemap.xml` get no explicit cache header). |
| `.env.example` | Every required secret/variable name, matching `render.yaml`'s names exactly, with a comment on which Render service/dashboard it comes from. Copy to `.env` (gitignored) and fill in real values. |
| `deploy/systemd/fantasygmlab.service` | systemd unit so the stack starts on boot and stops cleanly on `systemctl stop`. |
| `docs/SELF_HOSTED_MIGRATION.md` | This runbook. |
