# Push token handoff (2026-11)

Follow-up to docs/audits/2026-11-account-isolation.md. Requirement: when user A signs out, or user B signs in on the
same device, the device's push token is detached from A on the server, so A's notifications never reach B.

## Trace

- **Token.** `mobile/src/lib/pushNotifications.ts` gets an Expo push token (`Notifications.getExpoPushTokenAsync`,
  EAS project id). Expo's managed push service wraps APNs (iOS) and FCM (Android); the app never handles raw APNs/FCM
  tokens. iOS and Android share this path (`platform` is sent as `ios` / `android`). Simulators skip it.
- **Register.** `syncPushToken({requestPermission:false})` runs on every session start and sign-in (AuthContext) and
  posts `/v1/push/register` (`services/mobile_api_service.py`) -> `modules/push_tokens.register_token`.
- **Storage.** `public.push_tokens` (docs/supabase_push_tokens.sql): `expo_push_token text PRIMARY KEY`, `user_id`
  FK, RLS `auth.uid() = user_id` for select/insert/update/delete. The primary key already gives one owner per token,
  so no new unique constraint or migration is needed.
- **Unregister.** `/v1/push/unregister` already existed; it deletes with `user_id=eq.<caller>` under the caller's JWT.
  A cannot delete B's token (0 rows; RLS plus the filter).
- **Senders.** `modules/push_triggers.fetch_push_recipients` (service role, all users) builds user -> tokens for the
  sweep; `/v1/push/test` reads the caller's own tokens under RLS. Expo `DeviceNotRegistered` tokens are deleted.
- **Web push.** None exists (no service worker, no PushManager, no subscription table in `web-next/`). Not applicable.

## Findings (before)

1. **Re-own was broken.** The doc comment promised that B registering the same token reassigns the row. It does not:
   registration ran under B's JWT, and an upsert whose conflicting row is owned by A fails the UPDATE policy (A's row
   is invisible to B). B's `/v1/push/register` returned `not_available` and the row stayed with A. Duplicates were
   impossible (primary key), but A kept the device.
2. So the only protection was A's sign-out unregister. It was awaited with no timeout, could silently do nothing
   (token held only in memory, so a cold start before the first sync skipped it), and was skipped entirely on forced
   sign-out (expired session) or when offline.
3. Net: **yes, A's notifications could reach B** on a shared device whenever A's unregister did not land.

## Fix

- Backend (`modules/push_tokens.py`): with the flag on, register upserts on the token primary key with the service
  role, `user_id` = the caller verified by `require_user`. One atomic statement moves the token to the caller. Falls
  back to the old JWT upsert if `SUPABASE_SERVICE_ROLE_KEY` is not configured on the API process. Unregister stays on
  the caller's JWT only (never service role), so it can only remove the caller's own token.
- Senders (`owned_recipients`, used by `fetch_push_recipients`): a token that ever shows under two users goes to the
  most recently updated owner only. Defense in depth; the primary key should make it a no-op.
- App: `lib/pushHandoffCore.ts` `unregisterThenDropSession`: unregister first, bounded by 2.5 s, never throws, then the
  session is dropped (sign-out and delete-account). `unregisterCurrentPushToken` reads the token from the OS when this
  process has not registered yet (no prompt). The #2224 user-change branch (`handleAuthenticatedUserId`) forgets the
  previous user's in-memory token; the session effects then re-register for the new user, which re-owns server-side.
- Flags: backend `DYNASTYGM_PUSH_TOKEN_HANDOFF_V1` (FLAG_REGISTRY, owner Zach, default on); app
  `PUSH_TOKEN_HANDOFF_ENABLED` in `pushHandoffCore.ts`. Off restores the previous behaviour exactly.
- No migration. No data is deleted beyond the single token row being moved from the old owner to the new one.

## Not fixed / needs ops

- Prod API needs `SUPABASE_SERVICE_ROLE_KEY` in its environment (already used by the push sweep and other modules).
  Without it the fix degrades to the old behaviour. No provider (APNs/FCM/Expo) configuration changes are needed.
- A forced sign-out (expired session) or offline sign-out cannot call unregister; the next sign-in on that device
  re-owns the token. Until then A may still receive pushes on that device. Closing this fully would need a
  server-side device-session signal, out of scope here.
- A sweep that loaded recipients just before a handoff can still send once to the old owner (seconds-wide race).
