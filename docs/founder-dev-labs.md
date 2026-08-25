# Founder Labs / trusted dormant-module review

Trusted founder/developer access to dormant, archived, or experimental **registry
surfaces**. This is not a customer subscription and does not enable experimental
mode for everyone.

## Authorization contract

Both are required:

1. Production kill switch **`DYNASTYGM_DEV_REVIEW=1`** (default **OFF**).
2. Live signed-in session (`session_is_signed_in`: user id + unexpired access token).
3. Server-issued Supabase Auth **`app_metadata.founder_ops`** or **`app_metadata.dev_review`**:

`founder_ops` reuses the existing Founder Ops claim. `dev_review` is the dedicated
Labs claim if you do not want the ops dashboard.

**Not authorities:** `user_metadata`, `account_profile`, email, query params,
localStorage, `DYNASTYGM_SHOW_EXPERIMENTAL`, `DYNASTYGM_ALLOW_PROD_DEBUG`,
`DYNASTYGM_SHOW_DEV_DESTINATIONS`.

The env flag alone never grants access. The metadata flag alone never grants
access if the kill switch is off. Expired tokens and logout deny access.

## How `SHOW_EXPERIMENTAL` differs

| Flag | What it does | Production |
| --- | --- | --- |
| `DYNASTYGM_SHOW_EXPERIMENTAL` | Adds remaining experimental/conditional destinations to **customer** nav | Forced **off** on managed hosts unless `DYNASTYGM_ALLOW_PROD_DEBUG` |
| `DYNASTYGM_ALLOW_PROD_DEBUG` | Unlocks customer-unsafe debug/overrides on Render | Must stay unset on customer Render |
| `DYNASTYGM_DEV_REVIEW` | Kill switch for Founder Labs only | Optional, founder-controlled |
| `DYNASTYGM_SHOW_DEV_DESTINATIONS` | `DEV_ONLY` nav (none registered today) | Forced off on managed hosts without allow-debug |

Labs does **not** set `show_experimental`.

## Supabase grant (Admin / server only)

Do **not** store this on `account_profile`. Users cannot set `app_metadata`
through the client `user.update()` API (that writes `user_metadata`).

In Supabase Dashboard: **Authentication → Users → user → App metadata** JSON:

```json
{
  "founder_ops": true,
  "dev_review": true
}
```

Or Auth Admin API (service role, never in the Streamlit app):

```http
PUT /auth/v1/admin/users/{user_id}
{ "app_metadata": { "founder_ops": true, "dev_review": true } }
```

**Revoke:** set the keys to `false` or remove them.

**Propagation:** `app_metadata` is in the JWT. Sign out and sign in, or wait for
token refresh so `auth_user.app_metadata` updates. Stale sessions keep the old
claim until refresh.

## Render

On `FANTASYGMLAB` only, for a controlled window: `DYNASTYGM_DEV_REVIEW=1`.
Unset when review is done. Do not set `DYNASTYGM_SHOW_EXPERIMENTAL`.

## Entitlement

Labs is not Premium. Opening a review route uses the existing handler, which
still honors Premium where that handler already does (e.g. GM Targets caps,
Decision Memory history). Labs only bypasses **nav visibility** for listed
reviewable routes.

## Analytics

A future Founder Analytics section should live on this Labs page, reading
`modules/launch_analytics.py` the same way Founder Ops does. This pass adds no
events and no vendor.
