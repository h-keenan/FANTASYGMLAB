# Pre-launch onboarding: email verification + welcome IA

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-08-12 |
| Rollback SHA | `ecdb5a6329f5e52912aa12506146d2154080d713` (#276) |

## Email verification contract

| Stage | Meaning |
| --- | --- |
| Auth user created | GoTrue user row exists |
| Email confirmed | `email_confirmed_at` set |
| Session exists | access + refresh tokens |
| Authenticated for app | session + confirmed email |
| Profile bootstrap | `upsert_profile` after usable auth |
| Entitlement | profile row default `free` after bootstrap |

`user_created` ≠ authenticated. Unconfirmed sessions are refused by `apply_auth_payload` / restore.

## Welcome section map

| Before | Classification | After |
| --- | --- | --- |
| Global app-hero (hidden on landing CSS) | KEEP | unchanged |
| Marketing hero | KEEP | shorter value + support + trust line |
| 3 equal hero CTAs | MERGE | Import primary + See how it works; pricing tertiary |
| What it does (cold) | DEFER | only after secondary CTA |
| Next step duplicate | DELETE | removed |
| Account card as primary | MOVE | Optional account; guest primary among account choices |
| Feature / Founder / Trust detail | DEFER | behind See how it works |
| Free vs Premium | DEFER | behind pricing control |
| Import panel | KEEP | “Import your Sleeper league” |
| Live executive shell on guest | KEEP gated (#275) | unchanged |

## Founder control-plane

1. Confirm email **ON** (dashboard) — production immediate-session behavior implies it was off.
2. Custom SMTP **required** before public launch.
3. Site URL / redirect allowlist already correct — do not change unless broken.
