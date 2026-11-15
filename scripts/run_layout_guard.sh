#!/usr/bin/env bash
# CI-friendly layout guard (docs/ui-patterns.md, "Never ellipsize, never clip"): starts web-next on a free port with dummy
# env, runs the Fantasy Sim guard and the Desk guard (320 / 360 / 390 / 430px, normal + large text), stops the server and
# exits non-zero with every violation printed. Needs Playwright (PW_CORE=<path to playwright-core/index.mjs>; set
# BROWSER=chromium and CHROME=<executable> to use an installed Chrome). Quick local run: WIDTHS=320,390 LARGE=0 scripts/run_layout_guard.sh
set -u
cd "$(dirname "$0")/.."
PORT="${PORT:-3231}"
export BASE="http://localhost:${PORT}"
export OUT="${OUT:-/tmp/layout-guard}"
mkdir -p "$OUT"
(cd web-next && NEXT_PUBLIC_SUPABASE_URL=https://dummy.supabase.co NEXT_PUBLIC_SUPABASE_ANON_KEY=x NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 \
  npx next dev -p "$PORT" >"$OUT/server.log" 2>&1) &
SERVER=$!
trap 'kill "$SERVER" 2>/dev/null; pkill -P "$SERVER" 2>/dev/null' EXIT
for _ in $(seq 1 60); do curl -s -o /dev/null -m 60 "$BASE/gm-game" && break; sleep 2; done
status=0
OUT="$OUT/sim" node scripts/sim_layout_playwright/layout_guard.mjs || status=1
OUT="$OUT/desk" GUARD=1 node scripts/sim_layout_playwright/module_scan.mjs || status=1
if [ "${LARGE:-both}" != "0" ]; then OUT="$OUT/desk-large" GUARD=1 LARGE=1 node scripts/sim_layout_playwright/module_scan.mjs || status=1; fi
exit $status
