# App Store privacy labels (guideline 5.1.2(i))

## Context

Apple rejected the app under guideline 5.1.2(i) (privacy: App Privacy answers
and the data the app actually collects must agree, and any tracking must be
disclosed). This PR (a) audits real collection, (b) adds the full answer set as
`mobile/fastlane/app_privacy_details.json`, (c) fixes
`mobile/ios/FantasyGMLab/PrivacyInfo.xcprivacy` where it under-reported, and
(d) adds fastlane lanes so a human can upload the draft.

No tracking: no ad SDKs, no IDFA/ATT, no cross-app data sharing (grep of
`mobile/src`, `mobile/App.tsx`, `mobile/package.json`, `mobile/app.json`).
`NSPrivacyTracking` stays `false`.

## Data types

All "tracking = no". Paths relative to repo root.

| Data type (Apple) | Linked to identity | Purposes | Justification |
|---|---|---|---|
| Email Address | Yes | App Functionality | Supabase email/password `mobile/src/context/AuthContext.tsx:207` (sign in), `:216` (sign up); Sign in with Apple requests EMAIL scope `mobile/src/lib/appleAuth.ts:29-32` |
| Name | Yes | App Functionality | Apple FULL_NAME scope `mobile/src/lib/appleAuth.ts:30`; user `display_name` on shared trades `mobile/src/lib/api.ts:4857` |
| User ID | Yes | App Functionality | Supabase user id; also sent to RevenueCat `mobile/src/lib/revenuecat.ts:77` (`Purchases.logIn`); Sleeper username + league ids saved via `mobile/src/lib/api.ts:4561-4571` (`saveLeague`, `sleeper_username`) |
| Device ID | Yes | App Functionality | Expo push token `mobile/src/lib/pushNotifications.ts:49`, registered with platform + timezone `:111` -> `mobile/src/lib/api.ts:4656` |
| Purchase History | Yes | App Functionality | RevenueCat SDK `mobile/src/lib/revenuecat.ts:57` (`Purchases.configure`); entitlement/subscription state. Web purchases use Stripe (billing state kept server-side, `docs/supabase_stripe_billing.sql`); the app never collects card data |
| Other User Content | Yes | App Functionality, Product Personalization | Scouting grades/notes `mobile/src/lib/api.ts:4614-4625`; shared community trades `:4851-4858`; saved leagues `:4561` |
| Product Interaction | Yes | App Functionality, Analytics | Push-open events `mobile/src/lib/pushNotifications.ts:198` -> `mobile/src/lib/api.ts:4688`; decision log / trade-outcome answers `mobile/src/lib/api.ts:4862+`; verdict feedback `:4794` |
| Crash Data | No | App Functionality | Sentry, conditional: `mobile/src/lib/errorReporter.ts:16` reads `EXPO_PUBLIC_SENTRY_DSN`; `mobile/src/lib/errorReporterCore.ts:29-41` inits Sentry only if a DSN exists, with `sendDefaultPii: false`, `tracesSampleRate: 0`, no `setUser`. Without a DSN errors only go to the console. Declared because the SDK ships and the DSN is a build-time env (`mobile/.env.example:46`) |

Not collected (verified absent): location, contacts, photos, health, audio,
browsing/search history, advertising data, ATT. Checkout on web is Stripe-hosted.

## Manifest cross-check (`PrivacyInfo.xcprivacy`)

Before: Email, Name, User ID, Purchase History, Device ID (all linked, not
tracking, App Functionality), tracking false.

MISMATCHES found and fixed in this PR (manifest under-reported vs. code):

1. Other User Content (scouting notes, shared trades) missing, now added.
2. Product Interaction (notification opens, decision log) missing, now added.
3. Crash Data (Sentry SDK is bundled) missing, now added (not linked).

Required-reason API entries were left unchanged. Note: `@sentry/react-native`
and `react-native-purchases` ship their own privacy manifests which Xcode
merges into the app report; the app-level manifest must still be a superset of
what we send.

## Account deletion

Self-service deletion is currently disabled; the app directs users to
`support@fantasydesk.app` (`mobile/src/screens/MoreScreen.tsx:396-402`,
`mobile/src/context/AuthContext.tsx:79`), per `docs/account-deletion.md`.
CAVEAT: guideline 5.1.1(v) requires in-app account deletion for apps with
account creation. Apple may flag this separately. Restoring it per
`docs/account-deletion.md` (re-apply `d681010f`, deploy `delete-account`) is
recommended before or with resubmission. Not changed here (out of scope).

## What Zach runs (human, 2FA; do NOT run in CI)

This action uses an Apple ID web session, not the ASC API key.

```sh
cd mobile
export FASTLANE_USER="<apple id email>"     # prompted if unset
export APPLE_TEAM_ID="<team id>"            # optional; prompted to select a team if unset
bundle exec fastlane privacy_labels
```

Prompts: Apple ID password (or `FASTLANE_PASSWORD`), the 2FA code, and team
selection if `APPLE_TEAM_ID` is unset. Bundle id defaults to
`com.fantasygmlab.app` (`FGL_BUNDLE_ID` overrides). `privacy_labels` saves a
DRAFT (`skip_publish: true`). `privacy_labels_publish` is the same with
`skip_publish: false` and publishes immediately; prefer the draft and review.

## After the command

1. App Store Connect -> the app -> App Privacy: review the draft against the
   table above, then Publish.
2. Submit the build again for review.
3. Reply in App Review (suggested text below).

## Suggested App Review reply

> Thank you for the feedback. We reviewed our App Privacy answers against the
> data the app actually collects and updated them. FantasyDesk collects email,
> name (Sign in with Apple), user ID, push token (device ID), purchase history
> (via RevenueCat/App Store), user content (scouting notes, shared trades) and
> product interaction, all linked to the account and used only for app
> functionality, personalization and analytics. Crash data is collected not
> linked to identity. We do not track users and do not use any advertising SDK
> or the advertising identifier. Our privacy manifest has been updated to match.
> Account deletion is available by request via support@fantasydesk.app.
