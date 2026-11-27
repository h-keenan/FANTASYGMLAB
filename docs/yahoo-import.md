# Yahoo Fantasy league import

Status: built and tested against fixtures. **Not yet exercised against live Yahoo** (the build
environment has no Yahoo account or internet access to it). The owner checklist below is the
first real test. Replaces the "not built for import" note in `docs/platform-import-status.md`.

## Flow

1. Connect league -> More ways to connect -> **Yahoo** -> **Connect Yahoo** (web and app).
2. `POST /v1/yahoo/oauth/start {return_to: "web"|"app"}` (signed-in user) returns Yahoo's
   authorize URL (`https://api.login.yahoo.com/oauth2/request_auth`, `response_type=code`) with a
   signed, 10 minute `state` naming the user and where to return.
3. User signs in at Yahoo and approves Fantasy Sports read access.
4. Yahoo redirects to `GET https://api.fantasygmlab.com/v1/yahoo/oauth/callback` (the exact
   redirect URI registered on the Yahoo app; override only with `YAHOO_REDIRECT_URI`). The signed
   state is the identity (there is no FantasyDesk session on that request). The API exchanges the
   code (Basic auth, `/oauth2/get_token`), stores the encrypted tokens, then 302s to
   `{APP_BASE_URL}/connect-league?yahoo=connected` (web) or `fantasygmlab://yahoo?status=connected`
   (app, via `WebBrowser.openAuthSessionAsync`). Failures return `status=error&reason=...`
   (`denied`, `bad_state`, `exchange_failed`, `storage_failed`, `not_configured`).
5. `GET /v1/yahoo/leagues` lists the user's NFL leagues for the current game key
   (`game/nfl` -> `users;use_login=1/games;game_keys={key}/leagues`).
6. `POST /v1/yahoo/leagues/preview {league_key}` loads the league (settings, standings, one roster
   call per team, scoreboard), maps players, and returns teams + match rate + feature list. It
   refuses (`mapping_too_low`) below the shared 60% match-rate threshold, like ESPN.
7. The user picks their team and the app saves through the existing `POST /v1/leagues/save` with
   league id `yahoo:{yahoo league_key}:{season}` (e.g. `yahoo:461.l.12345:2026`).

Other routes: `GET /v1/yahoo/status` (`available`, `connected`; never a token),
`POST /v1/yahoo/refresh` (force a refresh to prove the connection), `POST /v1/yahoo/disconnect`.

## Tokens

* Access token: 1 hour. Refreshed on demand (60s skew) by `modules/yahoo_connect.get_access_token`.
  Yahoo may rotate the refresh token; the new one is stored. A 400/401 on refresh means
  `reconnect_needed` (UI asks the user to tap Connect Yahoo again).
* Stored Fernet-encrypted in `public.yahoo_credentials` (`docs/supabase_yahoo_credentials.sql`).
  Key: `YAHOO_CREDENTIAL_KEY`, else the existing `ESPN_CREDENTIAL_KEY`. Never returned to a client,
  never logged; Sentry scrubbing also redacts `code=` / `state=` URL params.
* The callback runs without a user session, so it writes with `SUPABASE_SERVICE_ROLE_KEY`
  (already used by ESPN credentials). Without it the save fails closed (`storage_failed`).
* Until the SQL is applied, Connect Yahoo ends with "We couldn't save your Yahoo connection"; no
  other feature is affected.

## Data privacy

Yahoo leagues are always private to the signed-in user. Snapshots are cached per (league, user)
for 5 minutes and served only to the user whose token loaded them; background jobs without a bound
login see nothing. The league-keyed week cache is bypassed for Yahoo.

## What is supported

Same as ESPN/Fleaflicker/MFL: My Team, Trade Analyzer (players only), Players, League Rankings,
Dashboard and Matchup (current-week pairings, scores and lineups from the same load). Imported:
teams, managers, record, points, rosters, lineup slots (IR as reserve), roster positions, and
scoring for pass/rush/rec yards and TDs, receptions, INT, fumbles lost (other stat ids are left to
FantasyDesk defaults, never guessed). Player ids map through DynastyProcess' `yahoo_id` column,
then unambiguous name + position + team; D/ST maps by NFL team; everything else is listed as
unmapped and left off.

**Not available for Yahoo leagues yet** (honest refusals, HTTP 409, same message on web and app):
Waivers, Trade Hub / Trade Finder, Alerts, GM Plan, Draft Center / Live Draft, League Recaps,
Portfolio, draft-pick ownership, transactions. Current season only; prior-season leagues are not
listed. Punters/unlisted positions are ignored.

## Cost and limits

About 2 calls to list leagues, and per import/refresh of a snapshot: settings + standings +
scoreboard + one roster call per team (about 15 for a 12 team league), spaced 0.25s, cached 5
minutes. Yahoo's rate limit is undocumented (it answers 999/429; surfaced as "limiting requests").

## Owner test checklist (needs a real Yahoo account in an NFL league)

Prereqs on the API host: `YAHOO_CLIENT_ID`, `YAHOO_CLIENT_SECRET` (set), `ESPN_CREDENTIAL_KEY` or
`YAHOO_CREDENTIAL_KEY` set, `SUPABASE_SERVICE_ROLE_KEY` set, and `docs/supabase_yahoo_credentials.sql`
run in the Supabase SQL editor (idempotent).

1. `GET /v1/yahoo/status` as a signed-in user shows `available: true`.
2. Web: Add a league -> More ways to connect -> Yahoo -> **Connect Yahoo**. Sign in at Yahoo and
   approve. You land on /connect-league with your leagues listed.
3. App: same path; the Yahoo sign-in opens in a sheet and closes itself, leagues listed.
4. Pick a league -> preview shows teams, match %, "Works for / Not available" lists -> pick your
   team -> Add this league. Dashboard opens; Matchup shows this week's opponent and lineups.
5. Wait over an hour, reopen the league (token refresh path). Reopen after Disconnect Yahoo:
   expect "Connect Yahoo" again.
6. Report anything off: wrong team count, missing players (unmapped list), wrong scoring (`rec`),
   a 999/429 from Yahoo. Real JSON differences go in `tests/fixtures/yahoo/`.

If Yahoo rejects the authorize/token call, check that the registered redirect URI is exactly
`https://api.fantasygmlab.com/v1/yahoo/oauth/callback` and the app type is Confidential client.

## Code map

`modules/yahoo_connect.py` (state, callback, refresh), `modules/yahoo_credentials.py` (encrypted
store), `modules/yahoo_leagues.py` (listing, parsing, snapshot), `modules/platforms/yahoo_oauth.py`
(OAuth HTTP client), routes in `services/mobile_api_service.py`, UI in
`web-next/src/components/YahooConnectStep.tsx` and `mobile/src/components/YahooConnectStep.tsx`.
`modules/platforms/yahoo.py` is the older spike adapter; the import does not use it.
