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
      LeagueDetailScreen.tsx  teams/rosters for one league
```

## What's not built yet

- Player-level data (names, positions, values) — needs a `/v1/players`
  endpoint added to the backend; current screens only show roster player
  *counts*, not fabricated player details.
- Rankings, Trade Hub, Waivers, News — not started. These need real backend
  endpoints wrapping the existing `modules/` engines; nothing here invents
  placeholder football data ahead of that.
- RevenueCat paywall UI — the SDK is configured and entitlement can be read
  (`hasPremiumEntitlement()` in `revenuecat.ts`), but there's no purchase
  screen yet.
- Native builds / code signing — this is the Expo-managed JS layer only.
  `expo prebuild` (to generate `ios/`/`android/`) and Fastlane (build, sign,
  submit to TestFlight/Play) are a separate, later step.
