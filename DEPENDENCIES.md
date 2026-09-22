# Third-Party Dependencies

Every third-party SDK/service this codebase actually calls at runtime — cross-checked against real imports and call sites, not just what's listed in a lockfile. Update this file whenever a new third-party integration is added, and whenever the privacy policy (`mobile/src/data/legalContent.json`) is updated, cross-check it against this list.

| Service | Data Received | Purpose | Where used |
|---|---|---|---|
| Supabase (Auth + Postgres + Storage) | Email, password hash, OAuth tokens, auth session tokens, app data (saved leagues, GM stance/targets, device push tokens, user settings) | Primary backend datastore + authentication | `mobile/src/lib/supabase.ts:9`, `modules/auth_supabase.py` |
| Sleeper API (`api.sleeper.app`) | League ID, roster IDs, usernames (outbound query params only — public read-only API, no account PII sent) | Source of truth for league/roster/player/matchup data | `modules/sleeper.py:12`, `modules/sleeper_leagues.py:7` |
| nflverse (`github.com/nflverse/nfldata`) | Nothing (anonymous GET of a public static CSV) | Real NFL schedule/game results/spread data (schedule tab, defense-strength feature) | `modules/nfl_schedule.py:27` |
| ESPN Fantasy API (`espn-api` package) | League ID, ESPN `swid`/`espn_s2` cookies for private leagues | Alternate fantasy-platform data source alongside Sleeper | `modules/platforms/espn.py` |
| RevenueCat | Supabase user ID, purchase/receipt data, device platform | Subscription/entitlement management (mobile premium tier, wraps StoreKit/Play Billing) | `mobile/src/lib/revenuecat.ts` |
| Stripe | Email, payment method, subscription/invoice data, webhook events | Web-app billing (separate from RevenueCat/mobile IAP) | `modules/stripe_billing.py`, `modules/stripe_webhook.py`, `services/stripe_webhook_service.py` |
| Apple (Sign in with Apple) | Apple user identifier, name/email (first sign-in only), identity token | Mobile auth option | `mobile/src/lib/appleAuth.ts`, `mobile/src/screens/LoginScreen.tsx` |
| Google Sign-In | Google account email, name, OAuth token | Mobile auth option | `mobile/src/lib/useGoogleSignIn.ts` |
| Expo Push Service (`exp.host`) | Expo push token, notification payload (title/body/league context) | Delivers push notifications to devices | `modules/push_tokens.py:21`, `mobile/src/lib/pushNotifications.ts` |
| Apple App Store Connect API / TestFlight | Build binaries, dSYMs, app metadata | CI/release distribution — not runtime user data | `mobile/fastlane/Fastfile` |

## Explicitly not present

Confirmed absent by direct code audit (worth recording so a future addition gets flagged instead of assumed-fine by omission):

- No crash reporting / error tracking SDK (no Sentry, Bugsnag, Crashlytics)
- No session-replay or keystroke-capture tool (Hotjar, FullStory, LogRocket, PostHog, Microsoft Clarity, Smartlook, Mouseflow)
- No analytics SDK (Firebase Analytics, Mixpanel, Amplitude, Segment, AppsFlyer)
- No third-party chat widget (Intercom, Drift, Crisp)
- No ad SDK actually wired up (`mobile/src/lib/ads.ts` is fully stubbed; AdMob only exists as unused config constants in `mobile/src/lib/env.ts`)
- No transactional/marketing email service beyond Supabase's own built-in auth emails (no SendGrid, Resend, SES, Mailgun, Postmark)
- No external font/script/style CDN (Google Fonts, cdnjs, jsdelivr, unpkg) — fonts are bundled locally via `@expo-google-fonts/inter`
- No AI API (OpenAI, Anthropic, or otherwise) anywhere in the backend
