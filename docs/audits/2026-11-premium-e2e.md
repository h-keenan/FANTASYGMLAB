# Premium / Pro end-to-end audit (2026-11-17)

Scope: web-next, mobile (Expo), the billing Edge Functions and the FastAPI backend. Stripe TEST mode
fixtures only; no live keys, no real customer data, no dashboard changes. PR #1579 (Zach's billing PR)
was not touched.

## 1. Money-path map

| Step | Web | iOS / Android | Server |
|---|---|---|---|
| Subscribe | `/premium` -> Edge `create-checkout-session` (Stripe Embedded Checkout, `client_reference_id` + `supabase_user_id` metadata) | `PaywallScreen` -> RevenueCat `purchasePackage` (App Store / Play) | Stripe or RevenueCat webhook writes `profiles.entitlement` |
| Grant | `stripe-webhook`: `checkout.session.completed`, `customer.subscription.created/updated`, `invoice.payment_succeeded` -> `premium` (`front_office` by price id) | `revenuecat-webhook`: any verified event triggers a fresh RevenueCat "active entitlements" read; entitlement is never inferred from the body | Both write one column, `profiles.entitlement`, each guarded by its own durable ordering columns |
| Renewal | `invoice.payment_succeeded` / `subscription.updated` (active) keep `premium` | `RENEWAL` event -> re-read | idempotent by `billing_webhook_events(provider, event_id)` |
| Cancel | Billing portal (`billing-portal-session`); `cancel_at_period_end` keeps Pro until `customer.subscription.deleted` -> `free` | Store settings (Apple/Google); `CANCELLATION` keeps access, `EXPIRATION` -> `free` | |
| Payment failure | `invoice.payment_failed` -> `free` immediately (no grace); a later successful retry (`invoice.payment_succeeded`) restores `premium` | `BILLING_ISSUE` -> re-read of RevenueCat (store grace period is RevenueCat's call) | See finding G1 |
| Restore | n/a | `PaywallScreen.onRestore` -> `restorePurchases()`; RevenueCat re-attributes, webhook re-syncs | |
| Delete account | Self-service is disabled (docs/account-deletion.md): "contact support"; support cancels Stripe first | Same | Gap G2 |
| Entitlement read | `GET /v1/me` -> `entitlement` (`free`/`premium`) + `profile_status` | same endpoint | `_fetch_profile_fields` is the single reader (15s single-flight cache, never caches a failed read) |

### Entitlement resolution (single source)

```
Stripe webhook ─┐
                ├─> profiles.entitlement ─> _fetch_profile_fields ─> (+ live referral comp) ─> wire "free" | "premium"
RevenueCat ─────┘                                  │
                                                   ├─> server gates: premium.is_at_least(entitlement, PRO)  (is_premium on every endpoint)
                                                   ├─> /v1/me -> web-next lib/plan.ts  planOf()
                                                   └─> /v1/me -> mobile lib/plan.ts    planOf()   (+ RevenueCat SDK only as a "do not show Free markers" hint)
```

Premium carries over web <-> app because both providers write the same `profiles.entitlement` row and every
client reads it from `/v1/me`. Test-enforced by `tests/test_entitlement_matrix.py`, `web-next/src/lib/plan.test.ts`,
`mobile/src/lib/plan.test.ts` (each also source-scans for hand-rolled `entitlement === "premium"` checks).

## 2. Entitlement matrix (what is tested)

| Feature gate | Free | Pro / Front Office | Unreadable profile | Test |
|---|---|---|---|---|
| Plan label, Billing section, Pro tab markers (web + app) | Free + Upgrade | Pro + Manage Billing | "Unavailable", no upsell, no markers | plan.test.ts (web, mobile) |
| Premium page | plans shown | Manage Billing | retry error (no second checkout offered) | `premium/page.tsx` |
| Server gates (Manager Tendencies, Playoff Odds, Draft Center, College Scouting, Cross-league exposure, What-if) | upsell / `is_premium:false` | data | closed, never Free verdict | test_entitlement_matrix.py |
| Fantasy Sim | 1 free season in 1 saved game, then paywall; `max_games` 1 | up to 3 games, no season limit | `plan_unverified` retry (never paywall) | plan.test.ts `simNewGameBlock`; tests/test_sim_plan_verification.py |
| Free-limit notes (trade ideas, leagues, watchlist) | note + Upgrade | none | none | plan.test.ts `freeLimitNote` |
| Referral comp (3 referrals = 30 days) | n/a | Pro while live | stays Free on failed read | test_entitlement_matrix.py |
| Stored-value normalization | `free`, `""`, `banana` | `premium`, `pro`, `front_office`, `Front Office` | | test_entitlement_matrix.py |

Product direction recorded: self-hosted real leagues are free; advanced metrics and advice are Pro. The
gates above are the existing server `is_premium` gates; no gate was moved in this audit.

### Webhook tests (Stripe test-mode fixtures, no network)

`supabase/functions/_shared/billing_lifecycle_test.ts` (new) runs the real webhook code against an
in-memory profile row that evaluates the exact PostgREST ordering filters the functions send:

- late `active` update after a newer cancellation stays Free
- events delivered newest-first end on the newest state
- `payment_failed` revokes, later success restores, replayed failure is a no-op (idempotent)
- stale `payment_failed` after a newer success cannot revoke
- `cancel_at_period_end` keeps Pro until `deleted`
- cross-provider carry-over (see F1)
- checkout double-subscribe guard (see F2)

Pre-existing coverage in `stripe_events_test.ts` / `handlers_test.ts` (signature, mode mismatch, price allowlist,
trial transitions, idempotency, failed update not recorded) is unchanged.

## 3. Findings

Fixed in this PR:

- **F1 (money / carry-over): a lapsed App Store subscription could strip Pro bought on the web.** Both
  providers write one `entitlement` column; RevenueCat's "no active store entitlement" verdict (`EXPIRATION`,
  `BILLING_ISSUE`) overwrote `premium` with `free` even when the Stripe subscription was live. RevenueCat
  downgrades are now conditional on `stripe_subscription_status` not being `active`/`trialing`.
- **F2 (money): double billing.** Checkout never checked whether the account already paid, so a second tab,
  or a store subscriber visiting the web, could start a second subscription. `create-checkout-session` now
  returns 409 `already_subscribed`.
- **F3 (entitlement): referral comp was never honored by the API.** `modules.premium.effective_entitlement`
  models it, but web-next and the app read `/v1/me`, which only looked at `profiles.entitlement`, so a
  promised "3 referrals = free Pro month" never unlocked anything. The profile read now upgrades a Free read
  while `referral_program.comp_until` is live (fails closed, never touches a paid plan). Cost: one extra
  own-row read for Free users, inside the existing 15s cache.
- **F4 (the Sim-week-4 class of bug, on the clients): a failed profile read showed Free.** Web Account said
  "Free" + "Upgrade to Pro", and the Premium page offered checkout, to someone who might be Pro. Mobile More
  said "Free". Now all go through one `planOf()` (`pro | free | unknown`); `unknown` shows neutral copy.
  Mobile had three copy-pasted Pro-marker blocks (GmOrb, Features, `useShowProTags`) and four more
  `entitlement === 'premium'` literals; they all use `lib/plan.ts` now. The two `plan.ts` files are lib twins
  (registered MIRRORED).
- **F5 (mobile purchase UX): stale Free state after buying or restoring.** Cached screens (plan marker,
  dashboard/waivers limits, Sim gate) were fetched as Free and nothing invalidated them, so Pro looked locked
  for minutes. Purchase, restore and Done now invalidate the query cache.
- **F6 (mobile): `restorePurchases()` rejection left the button spinning forever** (no try/catch). Now shows
  a store-unreachable message.

Verified, no change needed:

- The prior Sim fix (PR #1995) holds: a failed read is never cached, retried once, and Sim answers
  `plan_unverified` instead of a paywall. All other server gates use `premium.is_at_least(...)`; no server
  surface keeps its own comparison (now test-enforced).
- Front Office is collapsed to wire value `premium` in `/v1/me`, so no client treats it as Free.
- Webhook signature, mode/livemode match, live price allowlist, idempotency and ordering guards are sound.

## 4. Gaps and owner decisions (not changed)

- **G1: no payment-failure grace.** `invoice.payment_failed` drops Pro on the first failed attempt although
  Stripe retries for days (and the sub is only `past_due`). Restored if a retry succeeds. Recommended: keep Pro
  while `past_due`, revoke on `unpaid`/`canceled`. Product decision; left as is.
- **G2: delete-account does not cancel billing.** Self-service deletion is off; support cancels manually.
  Store (Apple/Google) subscriptions can never be cancelled by us, only by the user in store settings.
  Re-enabling needs the `delete-account` Edge Function (commit `d681010f`) deployed.
- **G3: Stripe -> free is not guarded against an active store subscription** (the reverse of F1). Needs a
  RevenueCat API read inside `stripe-webhook`; rare (someone paying on both). Not done.
- **G4: Pro via referral comp or App Store has no Stripe customer**, so "Manage Billing" returns 404 "No
  billing account found". Copy could say where to manage it.
- **G5: most server gates still fail closed on a failed read** (only Sim reports `plan_unverified`). The read
  is retried and never cached, so it is rare, but a Pro user can briefly see an upsell on those endpoints.
- Mobile `ModuleTemplates` source-scan flags `NewsDigest.tsx` (pre-existing, unrelated).

## 5. Owner asks

- No migration required. (`stripe_subscription_status` is in `docs/supabase_stripe_billing.sql`; F1 needs
  that file applied, which the Stripe webhook already requires.)
- Deploy the Edge Functions (`stripe-webhook` unchanged; `revenuecat-webhook`, `create-checkout-session`
  changed) when merging.
- Decide G1 (grace policy) and whether to re-enable self-service delete (G2).
- Live-mode steps: none taken. A live smoke test of the 409 guard and the carry-over guard needs a real
  account and is left to the owner.
