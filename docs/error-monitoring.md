# Error monitoring and app resilience

All Sentry wiring is optional and env-gated: with no DSN nothing is imported or sent.

| Surface | Env var | Where set | Notes |
|---|---|---|---|
| API (`services/mobile_api_service.py`) | `SENTRY_DSN` (+ `SENTRY_ENVIRONMENT`, `SENTRY_TRACES_SAMPLE_RATE`) | the `.env` read by `docker-compose.yml` (`env_file`) on the prod box | `sentry-sdk` is already in `requirements.txt`. Confirm it is set in prod: startup logs "Sentry error reporting initialized." |
| Web (`web-next`) | `NEXT_PUBLIC_SENTRY_DSN` | web build env (inlined at build) | `@sentry/browser`, init in `src/instrumentation-client.ts`, reports from `app/error.tsx` and `app/global-error.tsx`. No tracing/replay/PII. Server-side/SSR errors are NOT covered. |
| Mobile | `EXPO_PUBLIC_SENTRY_DSN` | EAS/fastlane build env | `@sentry/react-native` (Expo SDK 54 compatible `~7.2`). No DSN => errors only logged on-device through `src/lib/errorReporter.ts`. |

Native Sentry requires a new mobile build (do not ship one without an explicit go). Source-map /
debug-symbol upload is intentionally NOT configured (it needs `SENTRY_AUTH_TOKEN`; without it
stack traces are minified). To enable later: add the `@sentry/react-native` config plugin to
`mobile/app.json` with org/project and provide `SENTRY_AUTH_TOKEN` in the build environment.

## Mobile resilience
- Root `AppErrorBoundary` (`mobile/src/components/AppErrorBoundary.tsx`): friendly recovery screen, "Try again" remounts the tree.
- Minimum-version gate: `GET /v1/app-config` (public) returns `min_app_version.{ios,android}` and `store_urls`.
  Set `MIN_APP_VERSION_IOS` / `MIN_APP_VERSION_ANDROID` (e.g. `1.2.0`) in the API env to force an update;
  set `APP_STORE_URL_IOS` once the iOS app is live (Android defaults to the Play listing). Unset = no gate;
  network failure = app runs (fail open). The gate only works for builds that include this code.
