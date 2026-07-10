# Local Configuration

Use one local-only folder for every value you manually fill in:

```powershell
Copy-Item config\secrets.example.toml local_secrets\secrets.toml
```

Then edit:

```text
local_secrets/secrets.toml
```

Rules:

- Never upload `local_secrets/secrets.toml`.
- The local app reads it automatically.
- Render production values go into Render Environment Variables, not GitHub.
- Existing `.streamlit/secrets.toml` support remains as a compatibility fallback.

Runtime configuration is loaded in this order:

1. Environment variables, used by Render and CI.
2. Streamlit secrets, for compatibility with existing `.streamlit/secrets.toml` setups.
3. `local_secrets/secrets.toml`, for local Windows development.
4. Safe missing-config behavior.

## Values To Fill In

| Local key | Render env var | Scope | Where to get it |
| --- | --- | --- | --- |
| `APP_BASE_URL` | `APP_BASE_URL` | Web app | Use `https://fantasygmlab.com` in production, `http://localhost:8501` locally if preferred. |
| `DYNASTYGM_BUILD` | `DYNASTYGM_BUILD` | Web app optional | Any release/build label Harry wants shown in feedback context. |
| `SUPABASE_URL` | `SUPABASE_URL` | Web app | Supabase project settings -> API -> Project URL. |
| `SUPABASE_ANON_KEY` | `SUPABASE_ANON_KEY` | Web app | Supabase project settings -> API -> anon public key. |
| `STRIPE_SECRET_KEY` | `STRIPE_SECRET_KEY` | Web app, test mode only | Stripe Developers -> API keys -> test secret key. Must start with `sk_test_`. |
| `STRIPE_PRICE_MONTHLY` | `STRIPE_PRICE_MONTHLY` | Web app | Stripe test product monthly recurring price id. |
| `STRIPE_PRICE_ANNUAL` | `STRIPE_PRICE_ANNUAL` | Web app | Stripe test product annual recurring price id. |
| `STRIPE_CUSTOMER_PORTAL_RETURN_URL` | `STRIPE_CUSTOMER_PORTAL_RETURN_URL` | Web app | Premium page URL, usually `https://fantasygmlab.com/?page=premium`. |
| `STRIPE_CHECKOUT_SUCCESS_URL` | `STRIPE_CHECKOUT_SUCCESS_URL` | Web app | Premium page success return URL. |
| `STRIPE_CHECKOUT_CANCEL_URL` | `STRIPE_CHECKOUT_CANCEL_URL` | Web app | Premium page cancel return URL. |
| `STRIPE_WEBHOOK_SECRET` | `STRIPE_WEBHOOK_SECRET` | Backend-only | Stripe CLI or webhook endpoint signing secret. Keep out of browser-visible UI. |
| `SUPABASE_SERVICE_ROLE_KEY` | `SUPABASE_SERVICE_ROLE_KEY` | Backend-only | Supabase project settings -> API -> service role key. Keep out of the Streamlit web app unless a reviewed server-only webhook path requires it. |
| `DYNASTYGM_PREMIUM_OVERRIDE` | `DYNASTYGM_PREMIUM_OVERRIDE` | Local/dev only | Set `true` only to simulate Premium locally. |
| `DYNASTYGM_DEBUG_AUTH` | `DYNASTYGM_DEBUG_AUTH` | Local/dev only | Set `true` only for temporary auth diagnostics. |
| `DYNASTYGM_DEBUG_PERF` | `DYNASTYGM_DEBUG_PERF` | Local/dev only | Set `true` only for temporary performance diagnostics. |
| `DYNASTYGM_SHOW_EXPERIMENTAL` | `DYNASTYGM_SHOW_EXPERIMENTAL` | Web app optional | Set `true` only when beta testers should see experimental destinations. |
| `DYNASTYGM_SHOW_DEV_DESTINATIONS` | `DYNASTYGM_SHOW_DEV_DESTINATIONS` | Local/dev only | Set `true` only for developer-only routes. |

Backend-only values belong in the Stripe webhook backend or Supabase Edge Function if that is where the webhook is hosted. Do not show them in Streamlit diagnostics, HTML, browser code, screenshots, logs, or support output.
