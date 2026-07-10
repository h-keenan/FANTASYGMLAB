# Render Deployment

FantasyGM Lab runs on Render as two Python web services: the Streamlit app and a backend-only Stripe webhook service. Python is pinned to `3.12.10` with `.python-version` and `render.yaml` because Streamlit Community Cloud attempted Python 3.14.6 and crashed after startup.

## Create The Render Service

1. In Render, connect the private GitHub repository `h-keenan/FANTASYGMLAB`.
2. Create a Blueprint from `render.yaml`, or create a Python web service manually with the same settings.
3. Confirm the Streamlit service:
   - Build command: `pip install -r requirements.txt`
   - Start command: `streamlit run app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true`
   - Health check path: `/`
   - Auto-deploy from `main`: enabled.
4. Confirm the Stripe webhook service:
   - Name: `fantasygm-lab-stripe-webhook`
   - Build command: `pip install -r requirements.txt`
   - Start command: `uvicorn services.stripe_webhook_service:app --host 0.0.0.0 --port $PORT`
   - Health check path: `/health`
   - Auto-deploy from `main`: enabled.

## Environment Variables

Add these to the Streamlit web service:

- `APP_BASE_URL=https://fantasygmlab.com`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `STRIPE_SECRET_KEY` test key only until live billing review
- `STRIPE_PRICE_MONTHLY`
- `STRIPE_PRICE_ANNUAL`
- `STRIPE_CUSTOMER_PORTAL_RETURN_URL`
- `STRIPE_CHECKOUT_SUCCESS_URL`
- `STRIPE_CHECKOUT_CANCEL_URL`
- `DYNASTYGM_BUILD` optional
- `DYNASTYGM_SHOW_EXPERIMENTAL` optional

Do not add `SUPABASE_SERVICE_ROLE_KEY` to the Streamlit web service unless a reviewed server-only webhook path is hosted there. The preferred production webhook path is Supabase Edge Function or a separate backend.

Add these to the Stripe webhook backend service:

- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `STRIPE_SECRET_KEY` test key only until live billing review
- `STRIPE_WEBHOOK_SECRET`

The webhook URL format is:

```text
https://<render-webhook-service-host>/stripe/webhook
```

The health URL is:

```text
https://<render-webhook-service-host>/health
```

## Deploy And Verify

1. Deploy the service.
2. Open Render logs and verify there is no startup traceback.
3. Open the Render URL and confirm the app loads.
4. Visit:
   - Dashboard
   - My Team
   - Trade Hub
   - Waivers
   - Premium
5. Run signup, confirmation email, login, logout, and saved-league restore.
6. Test Stripe test checkout only if Stripe test config is present.
7. Test webhook entitlement updates from the webhook backend, not from browser code.
8. Test customer portal and cancellation before live billing is considered.

## Custom Domain

1. Add `fantasygmlab.com` to the Render service.
2. Add `www.fantasygmlab.com` if Render supports both root and www for the service.
3. Copy Render DNS records into the domain registrar.
4. Wait for verification.
5. Confirm HTTPS is active.
6. Open `https://fantasygmlab.com`.

## Supabase Updates

In Supabase Auth settings:

1. Set Site URL to `https://fantasygmlab.com`.
2. Add redirect URLs:
   - `https://fantasygmlab.com`
   - `https://www.fantasygmlab.com`
   - local development URL if needed, such as `http://localhost:8501`
3. Send a confirmation email to a test account and verify the link returns to the deployed app.

## Stripe Updates

In Stripe test mode:

1. Set business/support URLs to `https://fantasygmlab.com` when appropriate.
2. Create monthly and annual test prices.
3. Put the test price ids in Render environment variables.
4. Set checkout success/cancel URLs to the Premium page on `https://fantasygmlab.com`.
5. Configure the Customer Portal return URL.
6. Add a webhook endpoint using the Render backend URL:
   `https://<render-webhook-service-host>/stripe/webhook`
7. Subscribe the endpoint to:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
8. Copy the endpoint signing secret to the backend service `STRIPE_WEBHOOK_SECRET`.
9. Verify checkout, webhook, portal, cancellation, and entitlement state.

Live billing remains blocked until a separate live-billing review is complete.

## Rollback

Render rollback options:

1. Redeploy a previous Render deploy from the Render dashboard.
2. Revert the bad Git commit and push to `main`.
3. Temporarily disable auto-deploy while investigating.

If auth or billing configuration caused the issue, rollback environment variable changes from Render's environment settings rather than editing source code.
