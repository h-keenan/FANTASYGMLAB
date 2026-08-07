# Supabase Accounts Setup

DynastyGM accounts use Supabase Auth with the public anon key and Row Level Security. The Streamlit app does not use a service-role key. The separate Stripe webhook service uses a service-role key only to apply verified billing entitlement updates.

## 1. Configure secrets

Set these values in Render environment variables for production. For local development, prefer `local_secrets/secrets.toml` using `config/secrets.example.toml` as the template. Existing `.streamlit/secrets.toml` files still work as a compatibility fallback.

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-public-anon-key"
```

If either value is missing, FantasyGM Lab hides account login and continues in guest mode.

## 2. Create account tables

Run `docs/supabase_accounts.sql` in:

Supabase Dashboard -> SQL Editor

The schema uses these public tables:

- `profiles`
- `saved_leagues`
- `user_settings`

All three tables use `user_id uuid references auth.users(id)` and Row Level Security policies so authenticated users can only read and write their own rows.

## 3. Premium entitlement grants

Premium is currently controlled by `public.profiles.entitlement`. The allowed values are:

- `free`
- `premium`

For an existing Supabase project, run `docs/supabase_profile_entitlement.sql` once in the SQL Editor. The full `docs/supabase_accounts.sql` schema already includes this column for new projects.

Manual grant example:

```sql
update public.profiles
set entitlement = 'premium'
where user_id = '<auth-user-id>';
```

Manual removal example:

```sql
update public.profiles
set entitlement = 'free'
where user_id = '<auth-user-id>';
```

Do not expose this as a normal user preference. Standard app settings should not write or overwrite `entitlement`.

Before Founder Beta launch, also run these additive SQL scripts:

1. `docs/supabase_stripe_billing.sql` — Stripe customer/subscription columns
2. `docs/supabase_entitlement_security_hardening.sql` — block client entitlement self-grant; allow webhook `service_role` updates
3. `docs/supabase_feedback.sql` — durable Founder Beta feedback table

Founders review feedback in Supabase Dashboard → Table Editor → `feedback_reports`.

## 4. Confirmation email template

DynastyGM does not send auth email directly. Customize Supabase confirmation email in:

Supabase Dashboard -> Authentication -> Email Templates

If a user cannot find the confirmation email, DynastyGM shows a resend option that calls Supabase Auth's signup confirmation resend endpoint with the public anon key. Supabase still controls delivery, link validity, and rate limits.

Before founder beta, also verify:

- Supabase Dashboard -> Authentication -> URL Configuration -> Site URL is your production DynastyGM URL.
- Any local/test URLs you use are listed under Redirect URLs.
- Confirmation links open the deployed app domain you expect.
- The email template sender/name is recognizable enough that testers will not miss it.

Suggested subject:

```text
Confirm your DynastyGM account
```

Suggested body:

```text
Welcome to DynastyGM.

Confirm your email to finish creating your account:
{{ .ConfirmationURL }}

If you did not request this, you can ignore this email.

DynastyGM is an independent fantasy football tool. It is not affiliated with, endorsed by, or sponsored by Sleeper, ESPN, NFL, NFLPA, teams, players, or any fantasy platform.

Support: support@example.com
```

Replace `support@example.com` with your public support contact when ready.

## 5. Current MVP session behavior

Auth tokens are stored in browser `localStorage` for MVP login persistence. On startup, DynastyGM attempts to restore the stored Supabase session. If the access token is expired and a refresh token is available, the app calls Supabase Auth's refresh-token endpoint with the anon key and updates the stored session.

Logout clears Streamlit session state and removes the stored browser session. If browser storage is unavailable, the app degrades to session-only login and guest mode remains available.

This is not equivalent to secure HTTP-only cookie auth. It is an MVP Streamlit-compatible persistence layer. Do not store service-role keys or private credentials in the client.

## 6. Experimental Decision Memory (optional)

Premium Founder Beta feature. Disabled until Ops enables the kill switch.

1. Run `docs/supabase_decision_memory.sql` in the SQL Editor (after accounts schema).
2. Set `DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY=1` on the Render service.
3. Confirm RLS: authenticated users only see their own `decision_memory_events` / `decision_memory_baselines` rows.

Contract: `docs/experimental-decision-memory-contract.md`.
Until the migration is applied, the app fails safely (no crash, no durable writes).
