#!/usr/bin/env bash
# Run ON the production box. Reads KEY=VALUE lines on stdin, writes ONLY the
# allowlisted payment keys into the compose .env, recreates the two webhook
# services so env_file is re-read, then waits for /ready. Never prints values.
#
#   printf 'STRIPE_WEBHOOK_SECRET=...\n' | deploy/set_payment_env.sh
#
# Env: ENV_FILE (default: <repo>/.env), COMPOSE (default: docker compose),
#      DRY_RUN=1 (write the file, skip docker).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-$ROOT/.env}"
COMPOSE="${COMPOSE:-docker compose}"
ALLOWED=(
  STRIPE_BILLING_MODE STRIPE_SECRET_KEY STRIPE_WEBHOOK_SECRET
  STRIPE_PRICE_PRO_MONTHLY STRIPE_PRICE_PRO_ANNUAL STRIPE_PRICE_MONTHLY STRIPE_PRICE_ANNUAL
  STRIPE_PRICE_FRONT_OFFICE_ANNUAL
  REVENUECAT_BILLING_MODE REVENUECAT_SECRET_KEY REVENUECAT_PROJECT_ID REVENUECAT_WEBHOOK_AUTH_TOKEN
)

[ -f "$ENV_FILE" ] || { echo "no env file at $ENV_FILE" >&2; exit 1; }
tmp="$(mktemp "$ENV_FILE.XXXXXX")"
trap 'rm -f "$tmp"' EXIT
cp -p "$ENV_FILE" "$tmp"
cp -p "$ENV_FILE" "$ENV_FILE.bak.$(date +%Y%m%d%H%M%S)"

while IFS= read -r line || [ -n "$line" ]; do
  [ -z "$line" ] && continue
  key="${line%%=*}"; val="${line#*=}"
  ok=0; for a in "${ALLOWED[@]}"; do [ "$a" = "$key" ] && ok=1; done
  [ "$ok" = 1 ] || { echo "refusing key not on allowlist: $key" >&2; exit 2; }
  [ -n "$val" ] || { echo "empty value for $key" >&2; exit 2; }
  grep -v -E "^${key}=" "$tmp" > "$tmp.n" || true
  printf '%s=%s\n' "$key" "$val" >> "$tmp.n"
  mv "$tmp.n" "$tmp"
  echo "set $key (${#val} chars)"
done
chmod 600 "$tmp"; mv "$tmp" "$ENV_FILE"; trap - EXIT

if [ "${DRY_RUN:-0}" = 1 ]; then echo "dry run: skipped restart"; exit 0; fi
cd "$ROOT"
$COMPOSE up -d --force-recreate --no-deps stripe-webhook revenuecat-webhook
for svc in stripe-webhook revenuecat-webhook; do
  code=000
  for _ in $(seq 1 20); do
    code="$($COMPOSE exec -T "$svc" curl -s -o /dev/null -w '%{http_code}' http://localhost:8080/ready || true)"
    [ "$code" = 200 ] && break; sleep 3
  done
  echo "$svc /ready -> $code"
done
