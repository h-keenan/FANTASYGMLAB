# League platform import status

Checked 2026-10-22. Imported leagues are saved as `{platform}:{league_id}:{season}` in
`saved_leagues.league_id` and load into one Sleeper-shaped snapshot
(`modules/external_league_common.py`, routed by `modules/external_leagues.py`).
Pages open to every imported league: Dashboard, Matchup, My Team, Trade Analyzer,
Players, League Rankings. Waivers, Trade Hub, Alerts, GM Plan, Drafts and
Recaps need Sleeper-only data and answer "Not available for X leagues yet."

## Dashboard and Matchup for imported leagues (checked 2026-10-23)

Week, pairing and lineups come from `modules/external_matchups.py` (30s cache, single
flight per key, platform throttles unchanged), mapped through the snapshot's `id_map`
(the same crosswalk as the roster import). Starters that do not map are listed
(`unmapped_players`) and left out; win odds are then withheld (`unmapped_starters`).
An imported season other than the current NFL season has no "this week" (`no_current_week`).

| | Fleaflicker | MFL | ESPN (public) |
| --- | --- | --- | --- |
| Source | `FetchLeagueScoreboard` (1 call) + `FetchRoster` per displayed team (2) | `TYPE=liveScoring` (1 call) | none extra: the one `espn_api` load |
| Opponent, current week | yes | yes | yes |
| Record, power / franchise rank, snapshot tiles | yes | yes | yes |
| Starters with slot names | yes | starters yes, slot names no | yes |
| Bench | yes | roster minus starters | roster minus starters |
| Live points per player / team | yes | yes | team score only once final |
| Platform projected points | sent (league scoring), not used | not offered | not read |
| Win probability | FantasyDesk projections (generic scoring), only if every starter maps | same | same |
| Dashboard lineup check | yes (needs fully mapped starters) | yes | yes |

Dashboard omits, with a visible notice: waiver and trade rows/tiles (an imported snapshot
cannot tell a free agent from an unmapped player, and Trade Hub needs Sleeper pick
ownership). Not done: Fleaflicker/ESPN live per-player points are not used for ESPN; MFL
`projectedScores` and Fleaflicker projected points are not fed into the odds.

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
  keeper/dynasty flag, draft picks, transactions. Weekly matchup data is read lazily for
  Dashboard/Matchup (see above): `FetchLeagueScoreboard` and `FetchRoster`, at most 3 calls
  per page load, 0.5s apart, cached 30s.
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
- Not imported: scoring values, keeper settings, draft picks. Dashboard/Matchup read
  `TYPE=liveScoring` lazily (1 call, 30s cache, same 1.1s spacing).
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
