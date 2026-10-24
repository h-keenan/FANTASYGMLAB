#!/usr/bin/env bash
# Run LOCALLY. Sends the live payment settings from ~/.config/fantasygmlab to
# the box's set_payment_env.sh over ssh. Values go over stdin only; nothing is
# echoed. Usage: deploy/push_payment_env.sh user@box [/path/to/repo/on/box]
set -euo pipefail
TARGET="${1:?usage: push_payment_env.sh user@box [remote_repo_dir]}"
REMOTE_DIR="${2:-/opt/fantasygmlab}"
CFG="$HOME/.config/fantasygmlab"
get() { ( set -a; . "$1"; set +a; printf '%s' "${!2:-}" ); }
S="$CFG/stripe.env"; R="$CFG/revenuecat.env"
{
  echo "STRIPE_BILLING_MODE=live"
  echo "STRIPE_SECRET_KEY=$(get "$S" STRIPE_SECRET_KEY)"
  # The live endpoint's secret, NOT the old Cloud Run test endpoint's.
  echo "STRIPE_WEBHOOK_SECRET=$(get "$S" STRIPE_WEBHOOK_SECRET_PRODUCTION)"
  [ -n "${REVENUECAT_WEBHOOK_AUTH_TOKEN:-}" ] && echo "REVENUECAT_WEBHOOK_AUTH_TOKEN=$REVENUECAT_WEBHOOK_AUTH_TOKEN"
  true
} | ssh "$TARGET" "cd '$REMOTE_DIR' && deploy/set_payment_env.sh"
