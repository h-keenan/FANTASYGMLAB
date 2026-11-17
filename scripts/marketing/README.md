# Fantasy Sim social ads

`sim_social_ads.mjs` regenerates the Fantasy Sim ad creatives from the **current UI**. Nothing it produces is committed.

1. **Capture**: drives `web-next` at 390px (dark theme, reduced motion, 3x scale) against the Sim mock backend
   (`scripts/sim_layout_playwright/simmock.mjs`, fictional teams and players only) and screenshots six scenes:
   `draft`, `week`, `trade`, `player`, `team`, `recap`. The mock's default team name is swapped for a fictional franchise and
   the player Story timeline is filled in by the script (the mock has none).
2. **Compose** (`sim_social_ads_compose.mjs`): phone frame on a branded dark gradient, headline, and the FantasyDesk
   wordmark from `web-next/public/fantasydesk-wordmark.png`. Two sizes per scene: 1080x1080 (feed) and 1080x1920 (Stories/Reels/TikTok).

## Run

```sh
# 1. dev server with dummy env (same as the CI route-overflow job)
cd web-next && npm ci
NEXT_PUBLIC_SUPABASE_URL=https://dummy.supabase.co NEXT_PUBLIC_SUPABASE_ANON_KEY=x \
  NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npx next dev -p 3231 &

# 2. playwright-core (pinned in CI) and a Chromium headless shell in the Playwright cache
mkdir -p /tmp/pw && (cd /tmp/pw && npm init -y >/dev/null && npm i playwright-core@1.65.1 && npx playwright-core install chromium)

# 3. generate
PW_CORE=/tmp/pw/node_modules/playwright-core/index.mjs BASE=http://localhost:3231 OUT=/tmp/sim-ads \
  node scripts/marketing/sim_social_ads.mjs
```

Outputs `OUT/NN-<scene>-1080x1080.png` and `OUT/NN-<scene>-1080x1920.png`; raw phone screenshots land in `OUT/raw/`.

Options: `--only draft,trade` (a subset of scenes), `--compose-only` (re-render from existing `raw/`, e.g. after tweaking copy).
Env: `CHROME` overrides the browser path (otherwise the newest `chromium_headless_shell-*` in the Playwright cache).

Copy (headlines, sub lines) and the scene steps live in `SCENES` in `sim_social_ads.mjs`; layout and colours are in
`sim_social_ads_compose.mjs`. Always eyeball the PNGs: the scene steps depend on UI labels and will fail loudly (and save
`raw/<scene>-FAILED.png`) if the UI changes.
