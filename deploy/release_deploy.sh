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
docker compose build

echo "== restarting stack =="
docker compose up -d

echo "== status =="
docker compose ps --format 'table {{.Name}}\t{{.Status}}'
