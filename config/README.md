# Local Configuration

Runtime configuration is loaded in this order:

1. Environment variables, used by Render and CI.
2. Streamlit secrets, for compatibility with existing `.streamlit/secrets.toml` setups.
3. `local_secrets/secrets.toml`, for local Windows development.
4. Safe missing-config behavior.

For local development:

1. Copy `config/secrets.example.toml` to `local_secrets/secrets.toml`.
2. Replace placeholder values locally.
3. Never commit `local_secrets/secrets.toml`.

`.streamlit/secrets.toml` still works as a compatibility fallback, but new local setup should use `local_secrets/secrets.toml` so Streamlit deployment secrets and local secrets are not mixed together.

Web app / Render service variables:

- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `STRIPE_SECRET_KEY` test key only
- `STRIPE_PRICE_MONTHLY`
- `STRIPE_PRICE_ANNUAL`
- `STRIPE_CUSTOMER_PORTAL_RETURN_URL`
- `STRIPE_CHECKOUT_SUCCESS_URL`
- `STRIPE_CHECKOUT_CANCEL_URL`
- `APP_BASE_URL`

Backend webhook-only variables:

- `SUPABASE_SERVICE_ROLE_KEY`
- `STRIPE_WEBHOOK_SECRET`

Do not put backend-only variables in browser-visible diagnostics, HTML, Streamlit component code, screenshots, logs, or public support output. If the Stripe webhook runs as a Supabase Edge Function or separate backend, those backend-only values belong there, not in the Streamlit web service.
