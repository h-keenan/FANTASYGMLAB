# Supabase Accounts Setup

DynastyGM accounts use Supabase Auth with the public anon key and Row Level Security. The Streamlit app does not use a service-role key. The separate Stripe webhook service uses a service-role key only to apply verified billing entitlement updates.

## 1. Configure secrets

Set these values in Render environment variables for production. For local development, prefer `local_secrets/secrets.toml` using `config/secrets.example.toml` as the template. Existing `.streamlit/secrets.toml` files still work as a compatibility fallback.

```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_ANON_KEY = "your-public-anon-key"
```

Use the **project URL** only (`https://<ref>.supabase.co`). Do not paste the dashboard REST endpoint (`…/rest/v1`) — the app appends `/auth/v1/...` and `/rest/v1/...` itself. A doubled `/rest/v1` path returns PostgREST `PGRST125`. Both legacy JWT anon keys and `sb_publishable_…` keys are accepted on `SUPABASE_ANON_KEY` (publishable keys go on the `apikey` header only).

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

## 4. Confirmation email (required for public launch)

DynastyGM does not send auth email directly. Supabase Auth sends confirmation mail.

### Founder dashboard checklist (required)

1. **Authentication → Providers → Email → Confirm email: ON**
   When this is off, signup returns an immediate session and the app cannot invent a confirmation flow.
2. **Email / password provider: enabled**
3. **URL Configuration** (already set for production; do not change unless broken):
   - Site URL: `https://app.fantasygmlab.com`
   - Redirect allowlist: `https://app.fantasygmlab.com`, `https://app.fantasygmlab.com/**`, and
     **`fantasygmlab://`** (the mobile app's deep link scheme, declared in `mobile/app.json`'s
     `expo.scheme`). Mobile signup (`mobile/src/context/AuthContext.tsx`) passes
     `emailRedirectTo: 'fantasygmlab://'` — if this scheme isn't on the allowlist, Supabase
     silently falls back to the Site URL, and a mobile user's confirmation email opens the web
     app instead of returning to the mobile app. **Verify this entry exists in the dashboard —
     it is easy to add during initial setup and never revisit.**
4. **Custom SMTP** for public launch: **required** for reliable delivery.
   Supabase built-in mail is rate-limited (~2 emails/hour on free tier) and is not enough for public users. Configure Authentication → SMTP Settings with a production mail provider before inviting the public.
5. Customize **Authentication → Email Templates** (Confirm signup) so the sender/subject is recognizable.

The app posts `email_redirect_to` on signup using `APP_BASE_URL` / production Site URL. After the user clicks the link, the auth storage bridge consumes hash tokens or `token_hash` query params, restores a durable session only when email is confirmed, then profile bootstrap can run.

If a user cannot find the confirmation email, DynastyGM shows a resend option that calls Supabase Auth's signup confirmation resend endpoint with the public anon key. Supabase still controls delivery, link validity, and rate limits.

Do **not** disable Confirm email to work around SMTP. Fix SMTP instead.

Suggested subject:

```text
Confirm your FantasyGM Lab account
```

Suggested body:

```text
Welcome to FantasyGM Lab.

Confirm your email to finish creating your account:
{{ .ConfirmationURL }}

If you did not request this, you can ignore this email.

FantasyGM Lab is an independent fantasy football tool. It is not affiliated with, endorsed by, or sponsored by Sleeper, ESPN, NFL, NFLPA, teams, players, or any fantasy platform.

Support: support@example.com
```

Replace `support@example.com` with your public support contact when ready.

## 5. Current MVP session behavior

Auth tokens are stored in browser `localStorage` for MVP login persistence. On startup, DynastyGM attempts to restore the stored Supabase session. If the access token is expired and a refresh token is available, the app calls Supabase Auth's refresh-token endpoint with the anon key and updates the stored session.

Logout clears Streamlit session state and removes the stored browser session. If browser storage is unavailable, the app degrades to session-only login and guest mode remains available.

This is not equivalent to secure HTTP-only cookie auth. It is an MVP Streamlit-compatible persistence layer. Do not store service-role keys or private credentials in the client.

## 6. Decision Memory (graduated — Ops migration required)

Graduated retention feature. Launch default **ON**. Disable with `DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY=0`.

- Free: session What Changed on Dashboard (no durable Supabase write).
- Premium: durable cross-session history when the migration is present.

1. Run `docs/supabase_decision_memory.sql` in the SQL Editor (after accounts schema).
2. Leave the kill switch unset (default ON) or set `=0` to disable.
3. Confirm RLS: authenticated users only see their own `decision_memory_events` / `decision_memory_baselines` rows.

Contract: `docs/experimental-decision-memory-contract.md`.
Until the migration is applied, the app fails safely (no crash, no durable writes).

## 7. GM Targets (graduated — Ops migration required)

Graduated acquisition watchlist. Launch default **ON**. Disable with `DYNASTYGM_EXPERIMENTAL_GM_TARGETS=0`.

- Free: up to 3 targets per league.
- Premium: up to 50 targets per league.

1. Run `docs/supabase_gm_targets.sql` in the SQL Editor (after accounts schema).
2. Leave the kill switch unset (default ON) or set `=0` to disable.
3. Confirm RLS: authenticated users only see their own `gm_targets` rows.
4. Cap enforced in app (Free 3 / Premium 50); no silent eviction.

Contract: `docs/experimental-gm-targets-contract.md`.
Until the migration is applied, the app fails safely (no crash, no durable writes).
