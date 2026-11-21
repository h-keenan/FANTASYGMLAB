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

Data coverage: every table with a `user_id` references `auth.users(id) on delete cascade`, except
`feedback_reports` (`on delete set null`, so message/email would survive) and
`billing_webhook_events` (`user_id` is plain text). The function deletes those two explicitly
before the auth user (best effort, logged on failure).

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

## 2026-11 privacy pass (anonymize what is kept, no path skips billing)

Run `docs/supabase_account_deletion_2026_11.sql` (owner), then redeploy `delete-account`. Optional edge secret:
`ANALYTICS_HASH_SALT` (same value as the API, so analytics rows hashed with the secret salt can be found).

- Kept, anonymized: Stripe customer (name, email, phone, address, user-id metadata cleared), `billing_webhook_events`
  (`user_id` blanked), `deleted_account_billing` (ids only, no name/email), analytics rows (account hash, anon and
  session ids cleared), anonymous feedback rows (account hash removed), referrer settings (deleted user's id replaced by
  a `deleted:` tombstone so the count and comp already earned stay).
- Deleted: everything cascading from `auth.users`, plus referral attribution pointing at the deleted user.
- No path skips billing: the edge function cancels first and aborts on failure; a `before delete` trigger on `profiles`
  snapshots billing ids into `deleted_account_billing` with `needs_stripe_cancel`, so any other deletion path (old RPC,
  dashboard) leaves a flagged row. The old `delete_user()` RPC is also revoked. Ops query:
  `select * from public.deleted_account_billing where needs_stripe_cancel and not stripe_cancel_confirmed;`
