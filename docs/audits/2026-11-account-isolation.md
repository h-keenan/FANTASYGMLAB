# Account isolation audit, 2026-11

Follow-up to `2026-11-client-data-races.md` (C: keys not user-keyed). Scenario: user A signs out and user B signs in on the same browser or phone. B must never see A's leagues, games, trades, watchlists, notes, cached API responses or Pro state.

Scope: web (`web-next/src`) and app (`mobile/src`) client persistence only. Not touched: Supabase auth storage and the session model, billing, server data.

## Mechanism (one per platform)

| Piece | Web | App | Shared twin |
|---|---|---|---|
| Scoped key | `userGet/userSet/userRemove` in `lib/userStorage.ts` | `userStorage.get/set/remove` in `lib/userStorage.ts` (core: `userStorageCore.ts`) | `lib/accountScope.ts` `userScopedKey` -> `u:<userId>:<baseKey>` |
| Migration | first session after upgrade moves old plain keys into that user's scope (read once, write scoped, delete plain; an existing scoped value wins) | same, async | `migrateLegacyKeysSync/Async`, `LEGACY_SCOPED_BASES` |
| Purge | `purgeAccountStorage()`: local + session storage keys, `clearRequestCache()`, registered in-memory caches | `purgeAccountStorage()` plus the existing `clearAuthenticatedQueryCache()` (React Query memory + persisted blob) | `isAccountPurgeKey`, `planPurge`, `lib/accountCaches.ts` |
| Triggers | user -> nobody, user A -> user B, reload into a different user than the browser last held (`fgl:last-storage-user` marker) | sign-out, delete-account, `didAuthenticatedUserChange` (existing marker `fgl:auth-scope-user-id`) | |
| Guard | `scripts/check_storage_keys.mjs` (CI step in the lib-twins job) | same script | |
| Kill switch | `ACCOUNT_ISOLATION_ENABLED` in `accountScope.ts`: `false` = plain keys, no migration, no purge | same constant | |

Rules: per-user state is scoped; keys that cannot carry a user (inline script reads, hand-offs written before sign-in) stay plain and are purged on user change; pure device preferences stay global and are listed in `DEVICE_LEVEL_KEYS` with a reason.

Who owns the migrated plain keys: whoever signs in first after the upgrade. Old versions never cleared them on sign-out, so this is the device's existing user in practice. If a different user is the first to sign in, the plain keys are purged, not adopted.

Trade-off: scoped soft state (seen/dismissed flags, last league, recents) is removed on sign-out, so the same user signing back in starts those afresh. Progress flags that are already user-keyed (Start here, onboarding steps, last visit, pending alert reads) are kept so nobody repeats onboarding or loses an unsent read.

## Inventory

Columns: holds user/league data, keyed by user (after this change), cleared on sign-out (after this change). Class: S scoped, P unscoped but purged, K already user-keyed and kept, D device-level.

### Web (localStorage unless noted)

| Key | Holds | Keyed | Cleared | Class |
|---|---|---|---|---|
| `fgl:sim-notif-read:<game>` | read cursor per game | yes (`u:`) | yes | S |
| `fgl:sim-rookie-notice:<game>` | dismissal per game | yes | yes | S |
| `sim.realism.banner.<game>...` | dismissal per game | yes | yes | S |
| `fgl:compare-recent:<league>` | recent opponent player ids per league | yes | yes | S |
| `fd:guess-the-player-dismissed-pick-id`, `...name-match...` | dismissed pick | yes | yes | S |
| `fd:trade-outcome-prompt-dismissed` (session) | prompt dismissed | yes | yes | S |
| `fgl.detectedLens.v1` | lens per league id (read by the inline early-fetch script, so cannot carry a user) | no | yes | P |
| `fd_protected_route_return_path`, `fd_auth_return_path` | path (may name a league) written before sign-in | no | yes | P |
| `fd_pending_bridge_trade_v1` | trade handed from public analyzer to sign-in | no | yes | P |
| `fd:portfolio:v1:<user>:<lens>` | Portfolio snapshot (leagues) | user in key | yes (existing + purge) | P |
| `fd:start-here:v1:<user>`, `fgl:onboarding:<step>:<user>`, `fd:last-visit:v1:<user>:<league>` | progress flags, timestamps | user in key | no (kept) | K |
| `fgl:alert-reads-pending:v1` | unsent mark-read queue, scope `user:league` inside | user inside | no (kept so unsent reads survive) | K |
| `fgl:theme-mode`, `fgl:ui-density`, `fgl:college-football-interest-web` | appearance | no | no | D |
| `fgl:sim-to-prefs`, `fd.sim.celebrations`, `fgl:nav`, `fgl:sim-open:<id>`, `fd-help-seen:orb-menu` | UI layout and hints | no | no | D |
| `fgl:age-gate-passed` | legal gate of the person at the device | no | no | D |
| `fd_privacy_mode`, `fd_privacy_labels` (session) | masking choice, hashed labels | no | no | D |
| `fd_analytics_*` anon id, session, `LAST_PAGE_VIEW` (session) | anonymous ids | no | no | D |
| `fd_attribution_v1`, `fd_pending_ref` | first touch and referral, captured before sign-in | no | no (consumed state clears it) | D |
| `sb-*-auth-token` | Supabase auth | n/a | not touched | off limits |
| `fgl:last-storage-user` | which user the scoped state belongs to | n/a | no (read on next sign-in) | D |

In-memory (web): `requestCache` (key already includes the access token; now also cleared by the purge, previously only on writes), `managerTendencies` cache, `TradeOddsEffect` cache (Pro-gated response) and `liveFeedStore` were module Maps keyed by league only and survived a client-side sign-out. They now register with `lib/accountCaches.ts` and are reset by the purge. No IndexedDB and no persisted React Query on web.

### App (AsyncStorage)

| Key | Holds | Keyed | Cleared | Class |
|---|---|---|---|---|
| `fgl:last-league` | last league id and name | yes | yes | S |
| `fgl:dashboard-seen-recs:<league>`, `fgl:trade-hub-seen:<league>`, `fgl:recap-opened:<league>`, `fgl:compare-recent:<league>` | seen state, recents per league | yes | yes | S |
| `fgl:trial-lapsed-shown-expiration` | Pro trial lapse notice shown for an expiry date | yes | yes | S |
| `fgl:guess-the-player-*`, `fgl:sim-notif-read:<game>`, `fgl:sim-rookie-notice:<game>`, `sim.realism.banner.*` | dismissals, cursors | yes | yes | S |
| `fgl:react-query-cache` | persisted React Query blob (query keys rooted at `['user', id]`) | yes | yes (`clearAuthenticatedQueryCache`) | already handled |
| `fd:start-here:v1:<user>` | progress flag | user in key | no | K |
| `fgl:alert-reads-pending:v1` | unsent mark-read queue | user inside | no | K |
| `fgl:theme-mode`, `fgl:ui-density`, `fgl:experience-level`, `fgl:showcase-mode`, `fgl:effects-prefs:v1`, `fgl:orb-horizontal-fraction`, `fgl:player-list-view-mode:*`, `fgl:sim-to-prefs`, `fd.sim.celebrations`, `fgl:sim-open:*`, `fd-help-seen:orb-menu` | appearance and layout | no | no | D |
| `fgl:onboarding-complete`, `fgl:trial-offer-pending` | per-install first-run gates; device-level by product decision (the intro is about this install) | no | no | D |
| `fgl:college-football-prompt-answered`, `fgl:college-football-interest` | personal preference | scoped `u:<user>:` (app), existing keys adopted on first sign-in | scoped, kept across sign-out (`USER_SCOPED_KEEP_BASES`) | S |
| `fgl:age-gate-passed`, `fgl:push-prompt-dismissed-at` | gate and OS prompt, per device | no | no | D |
| `dynastygm_analytics_anon_id`, `dynastygm_analytics_queue_v1` | anonymous ids, events | no | no | D |
| `fgl:pending-referral-code` | referral code captured before sign-in, cleared when consumed | no | no | D |
| `fgl:auth-scope-user-id` | marker for the user change check | n/a | on sign-out | D |
| Supabase session (AsyncStorage/SecureStore adapter) | auth | n/a | not touched | off limits |

No MMKV and no IndexedDB in the app. In-memory (app): React Query is cleared on sign-out and user change (existing); `liveFeedStore` is now reset by the purge.

## Why attribution, referral, age gate, privacy mode stay global

They are written before any account exists, or describe the device or the person in front of it, and hold no league, game, trade or Pro data. Purging them on sign-out would break attribution of a later sign-up and would make the age gate and privacy masking reappear for the same person. Attribution and referral clear themselves once consumed.

## Other checks

- Web return path from #2218 (`fd_auth_return_path`, `fd_protected_route_return_path`): purged on user change, and the user-to-nobody purge runs before a forced sign-out stores its own return path, so the same user still returns and a different user does not.
- Web request cache: key includes the bearer token, so B could not read A's entry; it is now also cleared on sign-out and user change.
- App push token: sign-out and delete-account call `unregisterCurrentPushToken()` while the session is live, and `syncPushToken()` runs on the next session. Whether the backend moves a token from A to B when the same device registers under B is backend behaviour; not changed here, flagging for the backend owner.

## Not fixed (documented)

- App `OnboardingContext` stays device-level by product decision. `CollegeInterestContext` is now per user (done): reloads on user change, migrates the old keys, and its answer survives sign-out.
- Web `fgl:college-football-interest-web` is device-level for the same reason.
- Pending alert reads (`fgl:alert-reads-pending:v1`) carry A's alert keys on disk until A signs in again; they are inside a user:league scope and hold no names.
- Server-side: nothing deleted or changed.
