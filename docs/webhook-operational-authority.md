# Current webhook operational authority

Authoritative deployment supplied by the founder: main commit `6d379dcd38f1a87f501dafa119dc58d0f0d6134a`.

- Customer service: `FANTASYGMLAB`, live on main, https://fantasygmlab.onrender.com; observed primary custom origin https://www.fantasygmlab.com.
- Existing webhook service: `fantasygmlab-stripe-webhook`, live on main, https://fantasygmlab-stripe-webhook.onrender.com.
- This records supplied deployment truth, not a fresh health/readiness verification.

## Probe configuration

Set the non-secret configuration input `DYNASTYGM_WEBHOOK_HEALTH_URL=https://fantasygmlab-stripe-webhook.onrender.com/health` in the environment running the probe. No default hostname is used. Missing configuration reports `not_configured`; malformed endpoints report `invalid_configuration`. HTTPS is required. Credentials, query strings and fragments are rejected. Never put a secret in this URL.

The configured URL wins. `/ready` is derived by replacing the final `/health` segment, preserving any configured reverse-proxy prefix. `/health` proves process liveness only. `/ready` checks billing readiness independently. A healthy process does not authorize checkout or live billing. Webhook probe reports omit target URLs, response bodies and exception text.

Founder Ops reports configured liveness. Public and P0 probes report readiness separately. The older domain-cutover/P0 scripts also contain legacy app/marketing topology gates; those are not authority to change the observed www customer origin or Supabase redirects.

## Blueprint mismatch: fail safe

`render.yaml` retains a historical, differently named webhook Blueprint entry. We cannot establish its association with the existing live Render service from source alone. Its name and service settings are deliberately unchanged; only warning comments are updated. Do not apply/sync, rename, recreate or deploy that entry until the founder verifies its Render service association. A guessed-host 404 never establishes that the current service is missing.

## Remaining production verification (no live billing enablement)

1. Fresh GET https://fantasygmlab-stripe-webhook.onrender.com/health.
2. Fresh GET https://fantasygmlab-stripe-webhook.onrender.com/ready; retain the distinction from liveness.
3. Verify safe `APP_BASE_URL` against the observed primary origin https://www.fantasygmlab.com. Verify, do not silently change it from old topology assumptions.
4. Verify Supabase Site URL and redirect allowlist against that approved origin.
5. Stripe Test Mode checkout -> signed webhook -> entitlement -> app refresh.
6. Test portal/cancel lifecycle, including entitlement refresh.

No secret values should be copied into reports. Do not enable live Stripe billing. This PR changes no service settings or entitlement semantics.
