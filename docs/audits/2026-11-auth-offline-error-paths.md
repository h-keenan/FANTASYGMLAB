# Auth sessions and offline / slow network: error-path audit (2026-11-19)

Scope: error handling and recovery UX only, from the auth provider (Supabase GoTrue) and the API through web (`web-next/`) and the app (`mobile/`). Judged from code paths; no live Supabase or Sleeper calls. Built on the league-import audit (`2026-11-league-import-error-paths.md`) and the bad-day audit (`2026-11-bad-day-and-words.md`), reusing the typed error shape (`code`/`reason`/`retryable`/`Retry-After`), the shared `ErrorState`, offline banner and `SlowLoadNote`.

Out of scope by instruction: where or how tokens are stored, the session model or lifetime, the refresh mechanism, Supabase auth config, a cookie-session redesign. Anything that needs those is under "Recommendations needing session-model changes".

## Top findings

1. **An auth-provider outage signed every user out.** `require_user` turned any failure of the GoTrue `/user` lookup (unreachable, timeout, 429, 5xx, an HTML body) into `401`. Clients map 401 to "Your session ended" with a button that calls `signOut()`. A Supabase blip therefore asked healthy users to sign in again, and an HTML 200 from GoTrue raised an unhandled 500.
2. **Offline with an expired access token read as "session ended".** On a failed refresh because the device is offline, auth-js returns `{session: null, error: AuthRetryableFetchError}` and keeps the stored session. Both clients ignored the error and threw `401 Not signed in.`, so launching offline after the token's hour was up showed "Your session ended" and the "Sign in again" button signed the user out for real.
3. **Web dropped every specific server message.** The API writes `{ok:false, error, code?, reason?}`; web read only `detail`, so provider messages and `reason` codes never reached the UI. The app read `error` but showed the bare `Request failed.` of a 500.
4. **A 2xx that was not JSON (proxy or error page) returned `null` as data.** Screens then crashed on property reads and showed a technical-looking error.
5. **A forced sign-out was silent.** Remote revocation, deletion or another tab's sign-out set `session = null`; about 25 web pages `router.replace("/")` and the app swaps to the login stack, with no word why and no way back to the page. (Unsaved input still goes; see "Not fixed".)
6. **403 had no copy.** A bare `Request failed with status 403.` under "Try again". Plan changes (Pro to Free) are mostly answered as `200 reason: premium_required` and handled by the upsell cards, so 403 is rare (`Not authorized.` on founder routes).

## Mode x layer table

Legend: "before" is the behaviour before this change. Fix names the change (flag in brackets).

| Mode | Backend | Web (before) | App (before) | Fix |
|---|---|---|---|---|
| Access token expires mid-session | Provider rejects: 401 | auth-js refreshes on `getSession()`; a 401 that still arrives shows "Your session ended" + Sign in again | Same; refresh driven by AppState | Already clean. 401 message now fixed by status, not by server text. Clock skew: see recommendations |
| Refresh fails, offline | n/a (request never sent) | `401 Not signed in.` -> "Session ended", button signs out | Same | Retryable session-lookup error reads as offline ("Could not reach the server...") with retry; session kept |
| Refresh fails, token rejected (revoked, reused refresh token) | n/a | auth-js signs out locally -> `SIGNED_OUT`, silent bounce to `/` | Silent swap to login stack | `sessionEnded` flag: sign-in form shows "Your session ended..."; web also remembers the page and returns there after sign-in (existing `protectedRouteReturn`) |
| 401 loop / request storm | Per request, GoTrue lookups are memoised 10 s per token and single-flight | Each failing request is one request; no retry loop in `api.ts`; no client refresh on 401 | Same | Verified, no loop. No retry-on-401 added (would touch refresh design; see recommendations) |
| Signed out on another device / session revoked | Revoked token: GoTrue 401 (after the 10 s memo) | Other tab: `SIGNED_OUT` via auth-js broadcast. Other device: next API call 401 -> session-ended card | Same | Forced sign-out note and return path (above); 401 body now carries `code: session_invalid` |
| User deleted mid-session | GoTrue 403 `user_not_found` -> 401 | Session-ended card | Same | `session_invalid` 401; test pins it |
| Pro -> Free mid-session | Gates answer `200 reason: premium_required`; never 403 | Upsell cards (`limitWall`, `PremiumUpsellCard`) | Same | Unchanged. Bare 403 now says "Your account cannot open this. If your plan just changed, refresh the page or sign in again." |
| Auth provider down / 429 | `401 Invalid or expired session.` | "Session ended" + sign out | Same | `503 {code: auth_unavailable, retryable: true}` + `Retry-After` (5 s, 30 s on 429); not cached, so recovery is immediate [`DYNASTYGM_AUTH_PROVIDER_TYPED_ERRORS_V1`]. Clients show the server sentence with Try again |
| App offline at launch | n/a | Offline banner; each screen errors after the failed fetch with the shared card + retry | Banner (request-inferred); React Query cache paints with StaleNote on Today | Unchanged; the offline-token case above no longer masquerades as sign-out |
| Offline mid-use | n/a | Banner, content stays, "Back online" | Same | Unchanged |
| Slow network / spinner with no timeout | n/a | 30 s abort in `performRequest`; `SlowLoadNote` at 8 s, retry at 15 s | Same (30 s, `SkeletonRegion`) | Verified. Gap: Supabase PostgREST reads and the Stripe `billingRequest` rely on the browser default (no client timeout); listed under "Not fixed" |
| Request in flight on navigation / stale response overwrite | n/a | Pages use a `cancelled` flag per effect (My Team and others sampled); caller `signal` is wired into `performRequest` | React Query cancels via `signal`; `useEffect` screens vary | Verified by sampling; not changed |
| Unsaved input on forced sign-out | n/a | Trade builder, notes and settings are component state: lost on the redirect | Same, the navigator swaps | Partly: the user is told why and (web) returned to the page. Draft preservation is not done (see "Not fixed") |
| Backend 5xx JSON | `{ok:false,error:"Request failed."}` | Generic status text | Bare `Request failed.` | `Request failed.` is generic: becomes "Our servers hit a snag..." on both |
| 5xx / 4xx HTML (proxy page) | n/a | Non-JSON caught; status-based sentence | Same | Verified, test added |
| 2xx HTML (proxy page) | n/a | `null` returned as data, screen crash | Same | `ApiError(502, "We got an unexpected reply...", "bad_response")` on both |
| Unhandled backend exception | JSON 500 | Generic | Generic | Verified JSON, not HTML; test added |
| GoTrue HTML or non-object 200 | Raised an unhandled `ValueError` -> 500 | Generic | Generic | Treated as transient 503 `auth_unavailable` |
| Clock skew | Server verifies with GoTrue (no local clock) | The stored-session fast path in `lib/supabase.ts` trusts `expires_at` against `Date.now()`; a clock behind by more than the token's remaining life sends an expired token, gets 401 | auth-js uses the device clock | Not fixed: the cure is a one-shot refresh on 401 or server-time sync (recommendations) |

## What changed

Backend
- `modules/auth_supabase.py`: `TransientAuthError(str)` (a `str` so every existing `(user, error)` caller and mock keeps working); `fetch_auth_user` marks unreachable, timeout, 429, 5xx and unreadable replies as transient.
- `services/mobile_api_service.py`: `require_user` raises `AuthProviderUnavailable` (503, `code auth_unavailable`, `Retry-After`) for transient errors and `SessionInvalid` (401, `code session_invalid`) for a rejected token; the `HTTPException` handler now passes through `code`, `reason`, `retryable` and headers.
- Tests: `tests/test_auth_error_paths.py` (GoTrue mocked): unreachable, timeout, 5xx, 429, HTML body, rejected token, deleted user, not cached, kill switch, JSON 500.

Clients (web and app)
- `lib/badDayCopy.ts` (twin): `FORBIDDEN_MESSAGE`, `BAD_RESPONSE_MESSAGE`, `isRetryableSessionLookupError`, 401 always the session message, bare "Request failed." is generic, 403 copy.
- `lib/sessionEnded.ts` (new twin): `isForcedSignOut`, notice copy, marker storage helpers.
- `lib/api.ts` (both): retryable session-lookup failure -> offline error; `error`/`detail` and `code`/`reason` read; 2xx non-JSON -> `bad_response`.
- `AuthContext` (both): `sessionEnded` flag set only for a `SIGNED_OUT` the user did not request; web also stores the current path for return after sign-in and survives a reload. `SignInForm` (web) and `LoginScreen` (app) show the note.
- Tests: `apiAuthErrors.test.ts`, `AuthContext.sessionEnded.test.tsx` (web vitest); `sessionEnded.test.ts` (app node:test).

Pure error-state and copy fixes carry no client flag (the repo has no client flag mechanism). The backend behaviour change is behind a kill switch.

## Flag

| Flag | Default | Owner | Kill switch off means |
|---|---|---|---|
| `DYNASTYGM_AUTH_PROVIDER_TYPED_ERRORS_V1` | on | Zach | Legacy: every auth lookup failure is `401 Invalid or expired session.` |

## Recommendations needing session-model changes

Not done, by the boundary. For the cookie-session decision.

1. **One-shot refresh on 401.** On an API 401 the client could call `refreshSession()` once, retry the request once, and only then show "session ended". It would cure clock-skew 401s and tokens that expired between auto-refresh ticks (throttled background tabs). It changes the refresh mechanism's use, so it needs sign-off. It must be single-flight per session to avoid a storm (auth-js already serialises refresh behind a lock).
2. **Cookie session with a server-side refresh.** Lets the server answer "session ended" authoritatively, removes the dependency on a lazily loaded auth chunk, and removes the clock-skew class (server clock decides expiry). Needs a decision on cookie flags and CSRF.
3. **Server-time hint.** Return `Date` or a `server_time` field on `/v1/me` so the client can correct `expires_at` checks (fast path in `peekStoredSession`) without a cookie redesign.
4. **Immediate revocation.** The 10 s per-token memo in `fetch_auth_user_cached` bounds revocation latency; a shorter memo or a revocation list is a session-model choice.
5. **Draft persistence across sign-out.** If sessions become server-managed, trade builder, notes and settings drafts should be keyed by user and stored locally (not tokens) so a forced sign-out is recoverable. Storage location of drafts is a product decision.

## Not fixed

- **Unsaved input on a forced sign-out** (trade builder, notes, settings) is still lost; the user is now told why and the web returns them to the page. Preserving drafts needs a per-screen draft store (web and app); too broad for this pass and wants a product call on retention.
- **Client timeouts on PostgREST reads and billing: done** (follow-up PR). `lib/requestTimeouts.ts` (twin): `withReadTimeout` wraps the one Supabase fetch on each platform (`lib/supabase.ts`); GET/HEAD to `/rest/v1/` give up after 15 s and resolve a 408 `{message, code: client_timeout}`, so postgrest-js returns `error.message` = "This is taking too long..." and the existing ErrorState + retry shows it. Writes and auth calls are never timed out. Billing (`billingClient.ts`, web only; the app has no billing request client): plan list 15 s; checkout, portal and account deletion keep 30 s and on timeout say "we cannot say whether that went through. Refresh the page to check your plan". Kill switch: constant `REQUEST_TIMEOUTS_ENABLED` (no client flag mechanism exists); false restores the old behaviour. Not timed out: all PostgREST writes (`update`/`insert`/`delete`), the three billing writes above (30 s limit unchanged, copy only).
- **Stale-response overwrite** was sampled, not exhaustively audited across all screens (the app has many `useEffect` fetches).
- **App connectivity is still request-inferred** (no NetInfo module; adding it needs a native build).
- **No retry on 401** (see recommendation 1).
