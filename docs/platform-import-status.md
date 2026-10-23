# League platform import status

Checked 2026-10-22. Imported leagues are saved as `{platform}:{league_id}:{season}` in
`saved_leagues.league_id` and load into one Sleeper-shaped snapshot
(`modules/external_league_common.py`, routed by `modules/external_leagues.py`).
Pages open to every imported league: My Team, Trade Analyzer, Players, League
Rankings. Dashboard, Matchup, Waivers, Trade Hub, Alerts, GM Plan, Drafts and
Recaps need Sleeper-only data and answer "Not available for X leagues yet."

| Platform | Status | Credentials | Module |
| --- | --- | --- | --- |
| Sleeper | live | username only | `modules/sleeper.py` |
| ESPN (public) | live | none | `modules/espn_leagues.py` |
| Fleaflicker | built, public leagues | none | `modules/fleaflicker_leagues.py` |
| MyFantasyLeague | built, public leagues | none | `modules/mfl_leagues.py` |
| ESPN (private) | not built | needs user cookies | see below |
| Yahoo | not built for import | needs OAuth client id/secret | see below |

## Fleaflicker

- API: `GET https://www.fleaflicker.com/api/{Endpoint}` (docs: https://www.fleaflicker.com/api-docs).
  Used: `FetchLeagueRosters`, `FetchLeagueStandings`, `FetchLeagueRules`
  (`sport=NFL&league_id=..&season=..`). Verified live against a public league.
- Auth, rate limits, terms: the docs state none (contact info@fleaflicker.com). We make 3 calls
  per import, space calls 0.5s, send an identifying User-Agent, cache 5 minutes, never retry.
- Not imported: scoring values (left empty so FantasyDesk defaults apply, never assumed PPR),
  lineup slots per player, keeper/dynasty flag, draft picks, transactions, matchups.
  `FetchLeagueScoreboard` exists and could feed Matchup later.
- Player ids map through DynastyProcess' `fleaflicker_id` column, then unambiguous
  name + position + team. Everything else is listed as unmapped.

## MyFantasyLeague

- API: `GET https://api.myfantasyleague.com/{season}/export?TYPE=..&L=..&JSON=1`
  (docs: https://api.myfantasyleague.com/2025/api_info). Used: `league`, `rosters`,
  `leagueStandings`, and the global `players` list (cached 12h).
- Rate limits: per IP for unregistered clients, HTTP 429 when throttled, ~1 request/second
  advised, no retries. We space calls 1.1s, make 4 per import, cache 5 minutes.
- Terms (summary): free use; no harvesting league/user data, no overloading, no browser-side
  cross-domain JavaScript calls; registered clients must send their registered User-Agent.
- Private leagues need a user `APIKEY`. Not accepted: there is no encrypted secret store for
  user credentials. Such a league answers `private_league`. Needed from the owner to go further:
  a secret store design, and optionally registering FantasyDesk as an MFL client (higher limits,
  fixed User-Agent).
- Not imported: scoring values, keeper settings, draft picks, matchups.
- Player ids map through DynastyProcess' `mfl_id` column, then name + position + team.

## ESPN private leagues

Reading a private league needs the user's `espn_s2` and `SWID` cookies on every request.
That is a live ESPN session credential, so it would have to be stored server side; ESPN does
not offer an OAuth or API-key alternative and the cookies are not an official integration
surface. Blocked on: a decision to hold session cookies (encrypted per-user secret store,
rotation/expiry UX) and acceptance of ESPN terms risk. Public ESPN leagues work today.

## Yahoo

Yahoo Fantasy needs OAuth 2.0. Required from the owner: register an app at
https://developer.yahoo.com/apps/, then provide the client id and client secret (and approve
the redirect URI). The adapter and OAuth scaffolding in `modules/platforms/yahoo.py` and
`yahoo_oauth.py` already exist but are not wired into the API import flow; user refresh
tokens would also need an encrypted token store. Not implemented here.
