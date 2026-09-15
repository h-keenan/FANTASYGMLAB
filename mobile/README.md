# FantasyGM Lab — mobile app

Expo (React Native) + TypeScript client for iOS and Android. Talks to the same
Supabase project as the web app (`app.py`) for accounts/entitlement, and to
[`services/mobile_api_service.py`](../services/mobile_api_service.py) for
league/roster data. No fantasy-analytics logic lives here — this app is a
thin client over the existing Python engine.

## Setup

```sh
cd mobile
npm install
cp .env.example .env   # fill in real values, see below
npm start
```

Then press `i` (iOS simulator), `a` (Android emulator), or scan the QR code
with Expo Go on a physical device.

## Environment variables

See `.env.example`. All required vars are prefixed `EXPO_PUBLIC_` (Expo's
convention for values safe to bundle into the client — same rule as the web
app's anon key: never put a service-role or secret key here).

- `EXPO_PUBLIC_SUPABASE_URL` / `EXPO_PUBLIC_SUPABASE_ANON_KEY` — same Supabase
  project as the web app.
- `EXPO_PUBLIC_API_BASE_URL` — points at `services/mobile_api_service.py`.
  Locally, run that service with `uvicorn services.mobile_api_service:app
  --reload --port 8000` from the repo root and use `http://localhost:8000`
  (`http://<lan-ip>:8000` if testing on a physical device, since `localhost`
  on-device means the device itself).
- `EXPO_PUBLIC_REVENUECAT_IOS_SDK_KEY` / `EXPO_PUBLIC_REVENUECAT_ANDROID_SDK_KEY`
  — RevenueCat public SDK keys (`appl_...` / `goog_...`), not the secret key.

## Structure

```
mobile/
  App.tsx                  entry: providers + navigation
  src/
    lib/
      env.ts               required env var loading
      supabase.ts          Supabase client (session-persisted via AsyncStorage)
      api.ts                mobile_api_service.py client
      revenuecat.ts         RevenueCat SDK setup + entitlement checks
    context/
      AuthContext.tsx       Supabase session state, sign in/up/out
    navigation/
      RootNavigator.tsx     auth-gated stack navigation
    screens/
      LoginScreen.tsx
      HomeScreen.tsx         entitlement + saved leagues (reads Supabase
                              saved_leagues directly, same RLS as the web app)
      LeagueDetailScreen.tsx  teams for one league (tap a team for its roster)
      TeamRosterScreen.tsx    one team's players (name, position, status)
```

## What's not built yet

- Player *values*/rankings — `/v1/players` returns Sleeper's own fields only
  (name, position, team, status, injury). No valuation/ranking engine is
  wired up yet; that needs its own endpoint wrapping `modules/rankings.py`.
- Rankings, Trade Hub, Waivers, News — not started. These need real backend
  endpoints wrapping the existing `modules/` engines; nothing here invents
  placeholder football data ahead of that.
- RevenueCat paywall UI — the SDK is configured and entitlement can be read
  (`hasPremiumEntitlement()` in `revenuecat.ts`), but there's no purchase
  screen yet.
- A real build. Fastlane config exists (`fastlane/Fastfile`, `Appfile`,
  `Matchfile` — see below) and parses correctly, but no lane has actually
  been run yet, so nothing has produced an installable build so far.

## Native builds (Fastlane)

`ios/` and `android/` are never committed — every build regenerates them
fresh via `expo prebuild` (Expo's "Continuous Native Generation"), which the
Fastlane lanes below do automatically. This keeps native project state from
drifting out of sync with `app.json`.

```sh
cd mobile
PATH="/opt/homebrew/opt/ruby@3.4/bin:$PATH" bundle install   # first time only
cp fastlane/.env.example fastlane/.env   # fill in real values
PATH="/opt/homebrew/opt/ruby@3.4/bin:$PATH" bundle exec fastlane ios beta
PATH="/opt/homebrew/opt/ruby@3.4/bin:$PATH" bundle exec fastlane android beta
```

(The system Ruby on macOS is too old for current Fastlane — use a modern
Ruby, e.g. `brew install ruby@3.4`.)

- **iOS**: `match` (git-based cert/profile storage, see `Matchfile`) syncs
  signing, then `build_app` + `upload_to_testflight`. Needs Xcode ≥ 26.4
  (Expo SDK 57's minimum) — check `xcodebuild -version` before running this
  locally.
- **Android**: Gradle release bundle + `upload_to_play_store` (`internal`
  track). Needs the app already created in Play Console and the service
  account granted access there (Play Console → Setup → API access) — that
  grant is a manual step Google doesn't expose via any API.
- Confirm `FGL_IOS_WORKSPACE`/`FGL_IOS_SCHEME` in `fastlane/.env` after the
  *first* `expo prebuild` run — see the comment in `Fastfile`.
