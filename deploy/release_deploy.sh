#!/usr/bin/env bash
# Forced-command target for the scoped `fgl-releaser` SSH key (see
# docs/SELF_HOSTED_MIGRATION.md section 5.6). Not meant to be run with
# arguments or edited by the account that triggers it over SSH — that
# account only ever gets to invoke this exact script, nothing else.
#
# Re-deploys the current `main` branch: fetch, fast-forward (never discards
# local commits — fails loudly on divergence instead), rebuild containers,
# restart, print status.
set -euo pipefail

cd /opt/fantasygmlab

echo "== fetching origin/main =="
git fetch origin main

echo "== fast-forwarding local main =="
git merge --ff-only origin/main

echo "== rebuilding containers =="
# Exported (not written to .env) so each build bakes in exactly what this
# run is deploying — a leftover value in .env would silently go stale the
# next time someone builds by hand outside this script. Must be exported
# before `docker compose build`, not after: docker-compose.yml passes both
# through as Dockerfile `build.args`, baked into the image's ENV, so the
# build identity survives any later container restart that doesn't go
# through this script (e.g. the systemd unit's `docker compose up -d` on
# every host boot) instead of resetting to "local" the moment anything
# restarts the stack without re-exporting these. See
# services/mobile_api_service.py's /health docstring and
# modules/build_identity.py for why this exists (Render set
# RENDER_GIT_COMMIT automatically; this box has to do it itself).
export DYNASTYGM_BUILD="$(git rev-parse --short HEAD)"
# Same reasoning, for the companion staleness question "how long ago was
# this deployed" rather than "what commit is this" — see
# modules/build_identity.py and /health's docstring. UTC, strict
# ISO-8601, matching modules/build_identity.py's _DEPLOYED_AT regex
# exactly (it rejects anything else rather than mangling it).
export DYNASTYGM_DEPLOYED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
docker compose build

echo "== restarting stack =="
docker compose up -d

echo "== status =="
docker compose ps --format 'table {{.Name}}\t{{.Status}}'
