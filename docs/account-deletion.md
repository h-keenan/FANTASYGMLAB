# Account deletion (Stripe cancel + Sign in with Apple revocation)

Self-service deletion goes through the `delete-account` Supabase Edge Function
(`supabase/functions/delete-account`), not the old `public.delete_user()` RPC
(`docs/supabase_delete_account.sql` is kept only as a rollback path; it does
NOT cancel billing).

Order (each step idempotent; a failure before step 3 leaves the account intact so the user can retry):

1. Cancel every live Stripe subscription for the user (customer + profile subscription id + a
   metadata search safety net). Any Stripe failure (other than "already gone") aborts with a
   502 and the user is NOT deleted, so nobody ends up deleted-but-billed. If Stripe is not
   configured but the user has Stripe ids, it fails closed (503).
2. Revoke the Sign in with Apple grant (best effort, only when configured and the client sent
   a fresh `apple_authorization_code`). Not confirmed => logged, deletion still proceeds so a
   user is never stuck unable to delete.
3. Delete `auth.users` (cascades app tables). The later `customer.subscription.deleted`
   webhook for the deleted user is acknowledged (profile FK violation is treated as no-op).

Not covered: App Store / Google Play subscriptions (RevenueCat) cannot be cancelled by the
server. The mobile confirm dialog tells the user to cancel in their store account.

## Deploy / config (needs Zach)

- Deploy: `supabase functions deploy delete-account` (JWT verification is on, see `supabase/config.toml`).
- Apple revocation secrets (Supabase function secrets): `APPLE_TEAM_ID`, `APPLE_KEY_ID`,
  `APPLE_PRIVATE_KEY` (contents of the Sign in with Apple `.p8` key, `\n` escapes accepted),
  `APPLE_CLIENT_ID` (the iOS bundle id `com.fantasygmlab.app`, the audience of native sign-in).
  Create the key in Apple Developer > Keys > Sign in with Apple. Until set, revocation is skipped.
- iOS sign-in re-prompts Apple at deletion time to get a fresh single-use authorization code
  (codes expire in minutes, so it cannot be stored from sign-in).
- Web has no Sign in with Apple, so a user who signed up with Apple on iOS and deletes from the
  web is deleted without revocation; they can remove the app from Settings > Apple ID > Sign in with Apple.
