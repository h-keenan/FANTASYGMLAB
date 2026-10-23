> **Historical / partly obsolete (2026-10):** this document describes the retired Streamlit web app (`app.py`, `streamlit run`, `/_stcore/health`, `st.session_state`), which has been removed. The production web app is `web-next/` (Next.js) on the FastAPI services. See [`streamlit-removal-2026-10.md`](streamlit-removal-2026-10.md). Streamlit-specific details below are no longer current.

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
| ~~`fantasygm-lab` (Streamlit)~~ | ~~`web`~~ | Removed 2026-10 -- see `docs/streamlit-removal-2026-10.md` (APP_DOMAIN now proxies to `web-next`) |
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

## 5.5. Keeping the box in sync with `main`

As of `fantasygmlab-autopull.timer` (section 5.7), this box auto-deploys
on a ~2-minute poll of `main`, the same way Render used to auto-deploy on
push — but that's a server-side systemd timer, not anything in this
repo's `.github/workflows/`, so there's nothing here to verify it's
installed/enabled short of checking the box directly (`systemctl status
fantasygmlab-autopull.timer`). Manual redeploy (below) remains the
fallback whenever autopull is down.

Before that timer existed, nothing touched this server automatically —
`.github/workflows/` only ran CI (`ci.yml`) and auto-merge
(`auto-merge.yml`). (A Render-specific `keep-alive.yml` ping used to live
here too; it was retired once the app fully cut over to this self-hosted
box, since the Render free/sleeping-tier cold-start problem it worked
around doesn't apply to a `restart: unless-stopped` Docker stack.) Absent
a working autopull timer, the stack runs whatever was on disk the last
time someone ran section 3's `docker compose build && docker compose up
-d` here, and it will keep serving that exact build indefinitely,
through any number of later merges to `main`, until a human repeats
those steps (or autopull starts working again).

Concretely: if this box was stood up once and left alone with no working
auto-deploy, it can silently drift arbitrarily far behind `main` —
including missing later brand-asset, styling, or welcome-screen changes
that look completely normal in the repo and in CI, but were never
actually deployed here. If the live site ever looks wrong in a way the
current `main` branch's code doesn't explain, check this first, before
assuming it's a code bug:

```bash
cd /opt/fantasygmlab
git fetch origin
git log --oneline HEAD..origin/main   # anything listed here is NOT live yet
git pull
export DYNASTYGM_BUILD="$(git rev-parse --short HEAD)"  # must come BEFORE `docker compose build` — see below
export DYNASTYGM_DEPLOYED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"  # must come BEFORE `docker compose build` — see below
docker compose build
docker compose up -d
docker compose ps --format 'table {{.Name}}\t{{.Status}}'
```

**Checking what's actually live, without guessing**: `curl
https://api.fantasygmlab.com/health` returns `{"status": "ok", "build":
"<short sha>", "deployed_at": "<UTC ISO-8601 timestamp>"}`. Compare
`build` to `git log origin/main -1 --format=%h` — if they match,
production is current; if not, something above didn't run (or didn't run
with `DYNASTYGM_BUILD` set before the `build` step — and if autopull is
the thing that's supposed to have run, confirm it actually exports
`DYNASTYGM_BUILD`/`DYNASTYGM_DEPLOYED_AT` the same way
`deploy/release_deploy.sh` does, per section 5.7's note, before
concluding it isn't deploying at all). Compare `deployed_at`
to `git log origin/main -1 --format=%cI` to see how long production has
been behind whatever is newest on `main` — a non-trivial gap between the
two, even when `build` still matches, is the signal that the autopull
timer (section 5.7) has stopped firing or stalled and is worth checking
on the box directly. Render used to answer the
first question automatically via its own `RENDER_GIT_COMMIT`; this box
has no equivalent unless these two are exported before whatever runs
`docker compose build` — `deploy/release_deploy.sh` (section 5.6) already
does both for you; a manual deploy only reflects the real
commit/timestamp if you also export them, **before building**, as shown
above.

Both are baked into the image at *build* time (Dockerfile `ARG`/`ENV`,
wired through docker-compose.yml's `build.args`), not passed as a runtime
`environment:` var — on purpose: the systemd unit (section 5.3) runs
`docker compose up -d` on every host boot/crash-restart with no shell env
set at all, and a runtime-only var would silently reset to
"local"/empty on every one of those restarts even though nothing was
actually redeployed. Baking it into the image means it only changes on
the next real `docker compose build`, i.e. the next real deploy — see
services/mobile_api_service.py's `/health` docstring and
modules/build_identity.py.

## 5.6. Scoped deploy access for a second operator

The `deploy` user from section 1.1 is a full sudo-capable admin account —
don't hand its key to anyone you wouldn't trust with root on this box. To
let a second person (e.g. a co-founder or product owner who isn't an infra
admin) run section 5.5's redeploy themselves without that level of access,
create a separate, narrowly-scoped account whose SSH key can only ever
trigger `deploy/release_deploy.sh` — never an interactive shell, never an
arbitrary command.

```bash
# Run as the existing `deploy` admin user (or root).

# 1. A plain, non-sudo account. It needs `docker` group membership to run
#    `docker compose` (note: docker-group membership is root-equivalent in
#    general — a user in that group can trivially escalate by mounting the
#    host filesystem into a container. That's acceptable *only* because
#    this account will never get a shell — see step 3).
sudo adduser --disabled-password --gecos "" fgl-releaser
sudo usermod -aG docker fgl-releaser

# 2. Read access to the repo so the script can git fetch/merge and docker
#    compose can read the Dockerfile/compose file. Repo stays owned by
#    `deploy`; fgl-releaser gets read+traverse only, via ACL (install the
#    `acl` package first if `setfacl` isn't already present).
sudo apt-get install -y acl
sudo setfacl -R -m u:fgl-releaser:rX /opt/fantasygmlab
sudo setfacl -R -d -m u:fgl-releaser:rX /opt/fantasygmlab

# 3. Lock the account to one forced command over SSH: no shell, no port
#    forwarding (so this key can't be used to tunnel to anything else on
#    the box or network), no pty. Paste the real public key from whoever
#    will use this in place of <PASTE_PUBLIC_KEY_HERE>.
sudo -u fgl-releaser mkdir -p /home/fgl-releaser/.ssh
sudo -u fgl-releaser chmod 700 /home/fgl-releaser/.ssh
echo 'command="/opt/fantasygmlab/deploy/release_deploy.sh",no-port-forwarding,no-X11-forwarding,no-agent-forwarding,no-pty <PASTE_PUBLIC_KEY_HERE>' \
  | sudo -u fgl-releaser tee /home/fgl-releaser/.ssh/authorized_keys
sudo -u fgl-releaser chmod 600 /home/fgl-releaser/.ssh/authorized_keys
```

From then on, that person runs the equivalent of section 5.5's redeploy
with:

```bash
ssh fgl-releaser@<server-ip>
```

No arguments are accepted or needed — whatever command they type (or none
at all) is ignored; the `command=` entry always runs
`deploy/release_deploy.sh` instead. They cannot get a shell, cannot read
or write anything outside what that script does, and cannot use the
connection to reach any other service on the box.

To revoke access later, delete or comment out their line in
`/home/fgl-releaser/.ssh/authorized_keys` (as `deploy` or root) — no
restart needed, it takes effect on the next connection attempt.

## 5.7. Auto-deploy: `fantasygmlab-autopull.timer` (server-side)

Production's real, authoritative auto-deploy mechanism runs **on the
box itself**, not in GitHub Actions: a systemd timer,
`fantasygmlab-autopull.timer`, polls `origin/main` roughly every 2
minutes and, when it finds the checkout behind, runs
`deploy/autopull.sh`. That script:

- fetches `origin/main` and fast-forwards the local checkout to it
  (never discards local commits — fails loudly on divergence, same
  contract as `deploy/release_deploy.sh`);
- regenerates the Cloudflare-Tunnel-adapted runtime Caddy config via
  `/usr/local/bin/fantasygmlab-sync-caddy` (production's real
  `Caddyfile` is generated, not a direct copy of this repo's — see the
  compose-override note below);
- rebuilds and recreates the stack using **both** `docker-compose.yml`
  and a server-local `docker-compose.override.yml`;
- health-checks every service (`redis`, `web`, `mobile-api`,
  `stripe-webhook`, `revenuecat-webhook`, `caddy`) plus the local
  web/API health endpoints;
- on success, records the deployed SHA as last-known-good; on failure,
  **automatically rolls back** to that SHA and blocks the bad one from
  being retried every cycle (manual override: `sudo
  fantasygmlab-rollback`).

The following are production-local implementation details that live on
the box, not in this repo, and should stay that way — do not try to
replace them with something GitHub-Actions-hosted:

- `/opt/fantasygmlab/docker-compose.override.yml`
- `/opt/fantasygmlab/.runtime/Caddyfile` (generated — the real,
  Cloudflare-Tunnel-adapted Caddy config Caddy actually loads; binds
  Caddy to `127.0.0.1:80` only, with its healthcheck pointed at
  `127.0.0.1:2019`)
- `/usr/local/bin/fantasygmlab-sync-caddy`
- `/usr/local/sbin/fantasygmlab-rollback`
- `/var/lib/fantasygmlab/*` (last-known-good SHA / blocked-bad-SHA
  state)

**Note on `/health`'s `build`/`deployed_at` fields** (see
`services/mobile_api_service.py`'s `/health` docstring and
`modules/build_identity.py`): those are populated by
`DYNASTYGM_BUILD`/`DYNASTYGM_DEPLOYED_AT`, which `deploy/release_deploy.sh`
exports before building. Whether `deploy/autopull.sh` does the same is a
property of that script, which lives on the box and isn't tracked in
this repo — don't assume `/health` reflects autopull's deploy state
until that's confirmed; it may need the same two `export` lines added if
it doesn't already have them, or `/health` will keep showing "local"
even on a box autopull is correctly keeping current.

### GitHub Actions is a manual emergency fallback only, not the deploy path

`.github/workflows/auto-deploy.yml` ("Manual Emergency Deploy") used to
be the real continuous-deployment mechanism, triggered automatically on
every green CI run against `main`. It's been downgraded to
`workflow_dispatch` (manual trigger only) now that the server-side
autopull timer above is authoritative — two automatic deployers racing
the same box's one checkout is exactly the failure mode autopull exists
to be the single answer to.

It still SSHes in as the `fgl-releaser` scoped account from section 5.6
and runs `ssh fgl-releaser@<host>` with no command, same as a human
running section 5.6's manual redeploy. **Its required secrets
(`FGL_RELEASER_SSH_KEY`, `FGL_RELEASER_HOST`, `FGL_RELEASER_KNOWN_HOSTS`)
are intentionally not provisioned** — they're only needed if someone
deliberately decides to use this fallback path (e.g. autopull itself is
down and a deploy is needed urgently without direct SSH access). Running
it goes through `deploy/release_deploy.sh`, which is legacy/manual-only
now too (see its own header comment) and does **not** include autopull's
Caddy sync, compose-override layering, or automatic rollback — treat a
run through this workflow as a stopgap, not equivalent to a real
autopull cycle.

If a deploy is needed urgently and autopull is down, section 5.5's
manual `ssh fgl-releaser@<server-ip>` (or the full manual block above
it) remains the most direct fallback — the GitHub Actions path above is
one more layer behind that, not a replacement for operator access.

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
docker compose logs -f mobile-api      # just the API
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

## 9. `web-next` test-subdomain preview (additive, not a cutover)

**Status: additive prep only**, same spirit as this whole document. This
section documents a new, separate `web-next` container (the Next.js
frontend, `web-next/`) reachable at its own brand-new test subdomain —
`{$WEB_NEXT_DOMAIN}` (default `next.fantasygmlab.com`, see `.env.example`).
It does **not** change what `{$APP_DOMAIN}` (production, Streamlit)
serves. Making web-next the thing `APP_DOMAIN` actually points to is a
separate, deliberate, later decision — not part of this change, and not
something this section's manual steps accomplish.

Why this exists: `web-next/` is already fully built and tested (21
revisions merged, CI green) but has never been reachable anywhere except a
contributor's own `npm run dev` — this gives it a real, public,
TLS-covered URL to smoke-test against the real production `mobile-api`,
without touching anything already live.

### What changed in this repo

- `web-next/Dockerfile` — new, Node 22 multi-stage build (deps → builder →
  prod-deps → runtime), mirroring the root `Dockerfile`'s builder/runtime
  split. See its own header comment for the full reasoning, especially the
  **NEXT_PUBLIC_* build-time vs. runtime** distinction below.
- `docker-compose.yml` — new `web-next` service, built from
  `web-next/Dockerfile` with `context: .` (repo root, so the Dockerfile can
  `COPY web-next/...`), `mem_limit: 1g` / `cpus: 1.0` (see the service's
  own comment for sizing reasoning), healthcheck on `/`, and `caddy` now
  also waits on `web-next`'s healthcheck before proxying (added to
  `caddy`'s `depends_on`).
- `Caddyfile` — new `{$WEB_NEXT_DOMAIN} { reverse_proxy web-next:8080 }`
  block. The existing `{$APP_DOMAIN}` block is untouched.
- `.env.example` — new `WEB_NEXT_DOMAIN` (domain section) and a new
  `web-next (Next.js frontend)` section with the four `NEXT_PUBLIC_*`
  placeholders.

### IMPORTANT: `NEXT_PUBLIC_*` is build-time, not runtime

Unlike every other service in this stack, `web-next`'s four
`NEXT_PUBLIC_*` variables are **not** read by the running container at
all — Next.js statically inlines `process.env.NEXT_PUBLIC_*` into the
client JS bundle during `next build` (see `web-next/src/lib/env.ts`).
`docker-compose.yml` wires them in as Dockerfile **build args**
(`build.args`, interpolated by Compose from `.env` — the same mechanism
already used for `DYNASTYGM_BUILD`/`DYNASTYGM_DEPLOYED_AT` on the `web`/
`mobile-api` services), not as `environment:`/`env_file:` runtime values.
**Changing one of these four values requires `docker compose build
web-next` (or a full rebuild), not just a container restart or an `.env`
edit** — a plain `docker compose up -d` after only editing `.env` will
keep serving the old baked-in value.

`NEXT_PUBLIC_API_BASE_URL` specifically must be the real public
`https://api.fantasygmlab.com` (i.e. `MOBILE_API_DOMAIN`'s value), **not**
an internal Docker hostname like `http://mobile-api:8080`: every page in
`web-next` is a client component (`"use client"`) that calls the API from
a `useEffect` in the end user's own browser (`src/lib/api.ts`'s
`authorizedRequest`), never from inside this container — confirmed by
reading every `src/app/**/page.tsx`, all of which are `"use client"` and
call `api.*` after mount. An internal service name would not resolve from
a browser outside the Docker network even if it were set. This is also
why `web-next` has no `depends_on: mobile-api` in `docker-compose.yml`:
there is no runtime dependency between the two containers, only a
build-time value baked into the bundle.

### Known gap: the real production Caddyfile is generated, not this file

Section 5.7 above is the important caveat here: production's actual,
authoritative Caddy config is regenerated server-side by
`/usr/local/bin/fantasygmlab-sync-caddy` (Cloudflare-Tunnel-adapted;
written to `/opt/fantasygmlab/.runtime/Caddyfile`), **not** a direct copy
of this repo's checked-in `Caddyfile`. Whether that generator picks up a
brand-new route block like this one automatically, or needs its own
update (a change to a script that lives on the box, not in this repo), is
unverified from here — flagged explicitly in the manual steps below.

### Manual steps required (human with SSH access to the box)

None of the following can be done from this repo/PR — no secrets, DNS
credentials, or box access are available here:

1. **Fill in the four real `NEXT_PUBLIC_*` values** (and `WEB_NEXT_DOMAIN`
   if the default `next.fantasygmlab.com` isn't wanted) in the box's real
   `/opt/fantasygmlab/.env`, copying `.env.example`'s new section.
2. **Confirm Cloudflare DNS** has an A/CNAME record for `WEB_NEXT_DOMAIN`
   (e.g. `next.fantasygmlab.com`) pointed at this box, the same way
   `APP_DOMAIN`/`MOBILE_API_DOMAIN`/etc. already are — this repo/PR has no
   Cloudflare credentials and makes no DNS change.
3. **Confirm whether `fantasygmlab-sync-caddy` needs its own update** to
   emit a route for `WEB_NEXT_DOMAIN` — read that script on the box before
   assuming this PR's `Caddyfile` change alone is sufficient; it may need
   a matching edit there too (see "Known gap" above).
4. **Rebuild the image with the new build args actually populated**:
   `docker compose build web-next` (a plain `docker compose up -d` without
   a preceding build will not pick up real `NEXT_PUBLIC_*` values the
   first time this service exists).
5. **Bring the service up and verify health**: `docker compose up -d` /
   `docker compose ps --format 'table {{.Name}}\t{{.Status}}'` — confirm
   `web-next` and `caddy` both report healthy.
6. **Confirm autopull actually applies this**: either wait for
   `fantasygmlab-autopull.timer`'s next ~2-minute cycle after this PR
   merges to `main` (`systemctl status fantasygmlab-autopull.timer` to
   confirm it's active), or manually run section 5.5's redeploy steps —
   either way, step 1-3 above (the real `.env` values, DNS, and the
   sync-caddy question) must already be done, or the new container/route
   will come up with placeholder/empty build args and no way to actually
   resolve.
7. **Verify from outside**: `curl -I https://next.fantasygmlab.com/` (or
   whatever `WEB_NEXT_DOMAIN` was set to) once DNS has propagated —
   expect a valid cert and a 200 from the Next.js app's landing page.

### Explicitly out of scope here

- The actual `{$APP_DOMAIN}` cutover — making web-next the thing
  production's real domain points to instead of Streamlit's `web` — is a
  separate, deliberate, later decision. Nothing in this section performs
  or prepares for that cutover beyond proving web-next can run
  successfully on this box.
- No Render changes (this box's deploy is independent of `render.yaml`,
  which remains legacy/historical per this repo's current state).
- No DNS or secret changes were made by this PR — see the manual steps
  above.

## Appendix: file inventory

| File | Purpose |
|---|---|
| `Dockerfile` | Multi-stage build (builder installs deps into a venv; runtime stage is a slim Python image + app code). One shared image for all four real services — see the Dockerfile's own header comment for the reasoning. |
| `.dockerignore` | Keeps the build context to only what the Python services need (excludes `mobile/`, `tests/`, `docs/`, dev/editor state, secrets). |
| `docker-compose.yml` | Orchestrates `web`, `mobile-api`, `redis`, `stripe-webhook`, `revenuecat-webhook`, `web-next` (additive test-subdomain preview — section 9), and `caddy`; healthchecks on each app service's existing `/health`/`/_stcore/health`/`/` endpoint (and `redis-cli ping` for `redis`); `mobile-api` depends on `redis` reporting healthy before it starts, and `caddy` waits on all five app services' healthchecks (`depends_on: condition: service_healthy`) before proxying; `restart: unless-stopped` everywhere; secrets only via `.env`; sets `DYNASTYGM_SELF_HOSTED=1` on every Python app service (see section 3). |
| `Caddyfile` | Reverse proxy + automatic HTTPS routing per placeholder subdomain (including `web-next`'s additive `{$WEB_NEXT_DOMAIN}` test subdomain — section 9), plus static `file_server` for the marketing site. Also handles response compression (`encode zstd gzip` on `web`/`mobile-api`/`web-next`/the marketing site, skipped on the two webhook endpoints) and `Cache-Control` headers on the marketing site's static assets (images/fonts get `max-age=86400`, CSS/JS get `max-age=3600`, both `must-revalidate` since those files aren't content-hashed; HTML/`robots.txt`/`sitemap.xml` get no explicit cache header). |
| `.env.example` | Every required secret/variable name, matching `render.yaml`'s names exactly, with a comment on which Render service/dashboard it comes from. Copy to `.env` (gitignored) and fill in real values. |
| `deploy/systemd/fantasygmlab.service` | systemd unit so the stack starts on boot and stops cleanly on `systemctl stop`. |
| `deploy/release_deploy.sh` | Forced-command redeploy script for the scoped second-operator SSH key — see section 5.6. Legacy/manual-only: `fantasygmlab-autopull.timer` (section 5.7) is the real auto-deploy path now. |
| `web-next/Dockerfile` | Separate Node 22 multi-stage build for the Next.js frontend (deps → builder → prod-deps → runtime) — see section 9. |
| `docs/SELF_HOSTED_MIGRATION.md` | This runbook. |
