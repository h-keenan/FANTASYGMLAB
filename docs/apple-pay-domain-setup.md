# Apple Pay / Google Pay on embedded Checkout: domain setup

Embedded Checkout runs on our own domains, so Apple Pay is offered only when
each domain is registered with Stripe as a payment method domain and serves
Stripe's Apple association file. Google Pay needs no file; it appears in
Chrome/Android once a card is saved in Google Pay, and also depends on the
payment method being enabled (step 3).

## Code (already shipped)

- `web-next/public/.well-known/apple-developer-merchantid-domain-association`
  is Stripe's public association file (same for every Stripe account). It is
  served by web-next at `/.well-known/apple-developer-merchantid-domain-association`
  on every domain Caddy proxies to web-next (app.fantasygmlab.com,
  fantasydesk.app, and the others). No auth gating applies to it.
- If Stripe ever rotates the file, re-download it from
  https://stripe.com/files/apple-pay/apple-developer-merchantid-domain-association
  and replace the checked-in copy.

## Manual steps (Stripe Dashboard, live mode)

1. After this PR is deployed, confirm in a browser that
   `https://app.fantasygmlab.com/.well-known/apple-developer-merchantid-domain-association`
   returns a long hex string (not a 404 or the app).
2. Dashboard > Settings > Payments > Payment method domains > Add a domain.
   Add each domain users check out on: `app.fantasygmlab.com`,
   `fantasydesk.app` (and `www.` / `fantasygmlab.com` only if checkout is
   ever opened there). Stripe verifies the file automatically; each domain
   should show Apple Pay as "Active".
3. Dashboard > Settings > Payments > Payment methods: confirm Apple Pay and
   Google Pay are turned on for the live account/default configuration.
4. Test on a real iPhone (Safari, with a card in Wallet): open checkout and
   confirm the Apple Pay button appears. It never shows in desktop Chrome or
   an iOS in-app browser that blocks Apple Pay.

Do the same in test mode if you want to verify against test keys.
