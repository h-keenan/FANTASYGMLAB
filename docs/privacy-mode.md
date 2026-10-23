# Privacy mode

Display-only masking so screenshots can be taken from a real account. Real NFL
player names, positions, NFL teams and headshots are never masked.

## Where the toggle lives

- Web: Founder Analytics page (`/founder-analytics`), same `founder_ops` gating as
  that page. Flipping it reloads the page so every screen refetches.
- Mobile: More > Developer > "Privacy mode" (the pre-existing Showcase mode,
  now extended). Visible only to `app_metadata.founder_ops` accounts or the
  legacy email allowlist in `mobile/src/lib/showcaseMode.ts`.
- A small "Privacy mode on" pill is shown on every page/screen while on; tap
  to turn off.
- Persistence: localStorage `fd_privacy_mode` (web), AsyncStorage
  `fgl:showcase-mode` (mobile).

## How it works (central)

- Web: `web-next/src/lib/privacy.ts`. `performRequest` in `lib/api.ts` masks
  every JSON response; outgoing JSON bodies are un-masked (masked label ->
  real value) so a label is never saved to the server.
- Mobile: `mobile/src/lib/privacyMask.ts` (copy of the web engine) driven by
  `showcaseMode.ts`; `authorizedRequest` in `lib/api.ts` masks/un-masks.
- Labels: `Manager N` (owner/display names), `manager_N` (usernames, handles),
  `Team A/B/..` (team names), `Sample League` / `Sample Dynasty League` /
  `Sample League N` (league names). Stable per real value (web persists only
  hashed counters in sessionStorage, mobile in memory). Masking is idempotent.
- Avatars (`avatar_url`, `avatar_id`, `team_avatar_url`,
  `partner_team_avatar_url`) become null, so `TeamAvatar` shows initials from
  the generic label.
- Email fields become `hidden@example.com`.
- Free text: names seen in a response are scrubbed from other string values
  (alert/news/recap copy). Heuristic: a one-word name touching another
  capitalized word is skipped so "Chris Olave" is not mangled.
- Web `?name=` league-name URL param: all pages read it through
  `lib/useSearchParams.ts`, which returns the masked label. Header league
  switcher and `LandingAuthIsland` mask the `saved_leagues` rows they read
  straight from Supabase.
- Web share cards (`/share-card/*`): the client sends `X-Privacy-Mode: 1`; the
  routes mask upstream data with a per-request masker (and key the PNG cache on
  it). Mobile share previews render from already-masked data.

## Masked response fields

`team_name`, `owner_team_name`, `current_team_name`, `original_team_name`,
`partner_team_name`, `primary_team`, `secondary_team`, `fantasy_team`,
`original_team`, `source_team_name` (mobile), `owner_name`, `display_name`,
`current_manager_name`, `manager` (string), `username`, `sleeper_username`,
`owner_handle`, `owner_username`, `league_name`, `last_league_name` (mobile),
`partners[]`, `league_names[]`, `email`, `user_email`, avatar fields above, and
`name` only on objects with `league_id` (league) or `roster_id`/`owner_*`
(team) and no `player_id`/`position`.

## Known gaps

- The browser tab title is static ("FantasyDesk") so nothing to mask; the
  real `?name=` is still in the address bar (display of the URL bar itself is
  not masked).
- Names not under a known key and not previously seen in any response are not
  masked (e.g. a new API field, or names inside maps keyed by roster id).
- Free-text scrub only knows names already seen this session; a sentence
  loaded before the name appears elsewhere may keep it until a reload.
- Share-card PNG labels come from a separate server-side masker, so the
  numbering (Team A/B..) may not match what the app shows for the same team.
- Mobile: native push notification text and the OS share sheet contents are
  not masked; Apple/Google sign-in screens and Stripe/RevenueCat sheets show
  real account data.
- Real names typed by the user into forms (search boxes, ESPN/Sleeper import
  username field) are shown as typed.
- Founder Analytics itself shows aggregate product data, not league members.
