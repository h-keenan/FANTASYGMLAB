# Account deletion (TEMPORARILY self-service disabled)

The `delete-account` Supabase Edge Function (cancel Stripe, revoke Sign in with Apple, then
delete) is reverted from `main` for now (supabase/ matches `76f4b4fc`). The bare
`public.delete_user()` RPC (`docs/supabase_delete_account.sql`) deletes the user WITHOUT
cancelling Stripe, so the clients no longer call it either.

Current behavior: web Account and mobile More show "contact support" (mailto
`support@fantasydesk.app`, topic `delete_account`). Support deletes the user manually, cancelling
any Stripe subscription first (see `docs/incident-runbook.md`, Data requests).

To restore self-service: re-apply commit `d681010f` (PR #1721) and deploy
`supabase functions deploy delete-account`.
