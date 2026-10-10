# Yahoo Fantasy Sports integration spike — human runbook

## Why this document exists

coridian_ approved a short technical spike, per the recommendation of an
earlier scoping audit: register a Yahoo Developer app, get OAuth2 working
end-to-end for one real test league on the web app only, and pull raw
league/roster/scoring/transaction JSON to confirm Yahoo's actual data shape
and current rate-limit behavior firsthand.

**This agent could not do that.** The sandboxed environment this was
written in has no real Yahoo account, no Yahoo Developer credentials, and
no live internet access to complete app registration or a real OAuth
consent flow. Fabricating what a live response "would look like" would be
dishonest and worthless for a spike whose entire point is to find out what
Yahoo *actually* returns. So instead this agent built:

1. This runbook — the exact steps, URLs, and parameters a human needs to
   actually run the spike, sourced from Yahoo's current published
   documentation (link list below).
2. `modules/platforms/yahoo_oauth.py` — a real OAuth2 client implementing
   Yahoo's documented Authorization Code flow, built to Yahoo's published
   contract but **never run against Yahoo's live servers**.
3. `modules/platforms/yahoo.py` — a stub `YahooPlatformAdapter` implementing
   the shared `modules/platforms/base.py` Protocol, with data-fetching
   methods built against Yahoo's documented/reported response shapes, also
   **never run against live data**.
4. Unit tests (`tests/test_yahoo_oauth.py`, `tests/test_yahoo_platform_adapter.py`)
   that exercise the above against mocked/fixture data only.

None of this proves Yahoo's integration works. It's scaffolding so a human
with real Yahoo access can finish the spike quickly instead of starting from
zero.

## Primary sources used for this runbook

Yahoo has a documented history of changing this API without much notice —
re-check these before trusting anything below:

- App registration: <https://developer.yahoo.com/apps/create/>
- OAuth2 Authorization Code flow (endpoints, params, token response shape):
  <https://developer.yahoo.com/oauth2/guide/flows_authcode/>
- Fantasy Sports API overview / resource model:
  <https://developer.yahoo.com/fantasysports/guide/> (currently 308-redirects
  to <https://sports.yahoo.com/developer/> — Yahoo appears to be
  consolidating developer docs; if the old guide URL is gone entirely by the
  time you read this, that consolidation is itself useful intel to note)
- Getting-started / app-creation walkthrough:
  <https://sports.yahoo.com/developer/docs/>
- Community-maintained resource reference (not official, but detailed and
  widely cited): <https://yahoofantasysportsapidocs.readthedocs.io/guide/>
- Yahoo Fantasy Sports API Terms of Use (usage/volume language):
  <https://legal.yahoo.com/us/en/yahoo/terms/product-atos/fantasysportsapi/index.html>

## Step 1 — Register a Yahoo Developer app

1. Sign in with the Yahoo account that owns (or is a member of) the test
   league, then go to <https://developer.yahoo.com/apps/create/>.
2. Fill in:
   - **Application Name** — required, any descriptive name (e.g.
     "DynastyGM Lab — Yahoo spike").
   - **Application Type** — select **Installed Application** (not Web
     Application) unless Yahoo's current form has since relabeled this;
     installed-app type is what the authorization-code flow below assumes.
   - **Redirect URI(s)** — required. For a local web-app spike, use
     something you control and can intercept, e.g.
     `http://localhost:8501/yahoo/callback` if testing against the local
     Streamlit dev server, or a one-off redirect catcher
     (`https://httpbin.org/get` is sometimes used for grabbing the `code`
     manually, but prefer a URI you actually control once this moves past
     a one-off manual test).
   - **API Permissions** — check **Fantasy Sports**. Leave **Read** selected
     (do not request Read/Write — this spike only needs read access, and
     requesting write access to a real league's roster/transactions is an
     unnecessary and unapproved scope expansion).
3. Submit. Yahoo will show a **Client ID (Consumer Key)** and **Client
   Secret (Consumer Secret)**. Copy both immediately and store them like any
   other secret (this repo's convention: `local_secrets/` locally, never
   committed — see `local_secrets/secrets.toml` for the existing pattern).

## Step 2 — Set local environment variables

`modules/platforms/yahoo_oauth.py` reads these via
`modules.app_config.config_value`, so any of plain env vars, Streamlit
`secrets.toml`, or `local_secrets/secrets.toml` work:

```
YAHOO_CLIENT_ID=<Consumer Key from step 1>
YAHOO_CLIENT_SECRET=<Consumer Secret from step 1>
YAHOO_REDIRECT_URI=<the exact Redirect URI registered in step 1>
```

Do not commit these. Do not add them to `.env.example` or
`render.yaml` yet — this is a local spike, not a deployed feature.

## Step 3 — Build the authorization URL and get a `code`

```python
from modules.platforms.yahoo_oauth import build_authorization_url

print(build_authorization_url(state="spike-test-1"))
```

This prints a URL to `https://api.login.yahoo.com/oauth2/request_auth?...`.
Open it in a browser while signed into the Yahoo account for the test
league. Yahoo will show its consent screen (confirm it mentions Fantasy
Sports / your app name). After approving, Yahoo redirects to your
`redirect_uri` with `?code=...&state=...` appended. Copy the `code` value
immediately — Yahoo's authorization codes are documented as short-lived
(typically single-use, expiring quickly), so exchange it right away.

Equivalent raw request, if you want to see exactly what's happening without
Python:

```
GET https://api.login.yahoo.com/oauth2/request_auth
    ?client_id=<consumer key>
    &redirect_uri=<redirect uri>
    &response_type=code
    &state=spike-test-1
```

## Step 4 — Exchange the code for tokens

```python
from modules.platforms.yahoo_oauth import exchange_code_for_token

token = exchange_code_for_token(code="<code from step 3>")
print(token.access_token, token.refresh_token, token.expires_in)
```

Equivalent curl (Basic auth header is base64 of `client_id:client_secret`):

```bash
curl -X POST https://api.login.yahoo.com/oauth2/get_token \
  -u "<consumer key>:<consumer secret>" \
  -d grant_type=authorization_code \
  -d redirect_uri="<redirect uri>" \
  -d code="<code from step 3>"
```

Documented response shape (per the OAuth2 guide):

```json
{
  "access_token": "...",
  "token_type": "bearer",
  "expires_in": 3600,
  "refresh_token": "...",
  "xoauth_yahoo_guid": "..."
}
```

**Record exactly what Yahoo actually returns here** — field names, extra
fields, actual `expires_in` value — and compare it against the above. This
is one of the two things the product owner specifically asked this spike to
confirm firsthand.

## Step 5 — Make the first real API calls

Base URL: `https://fantasysports.yahooapis.com/fantasy/v2`. Every resource
supports `?format=json` to get JSON instead of the default XML.

**Get the authenticated user's leagues** (replace `nfl` with the current
season's game key if different — Yahoo versions NFL as a "game" per season):

```bash
curl "https://fantasysports.yahooapis.com/fantasy/v2/users;use_login=1/games;game_keys=nfl/leagues?format=json" \
  -H "Authorization: Bearer <access_token>"
```

Or with Python's `requests`:

```python
import requests
resp = requests.get(
    "https://fantasysports.yahooapis.com/fantasy/v2/users;use_login=1/games;game_keys=nfl/leagues",
    params={"format": "json"},
    headers={"Authorization": f"Bearer {token.access_token}"},
)
print(resp.status_code)
print(resp.json())
```

From the response, find the test league's `league_key` (format is
reported as `<game_id>.l.<league_id>`, e.g. `414.l.123456` — confirm the
actual format you get back).

**Get the league's settings/scoring:**

```bash
curl "https://fantasysports.yahooapis.com/fantasy/v2/league/<league_key>/settings?format=json" \
  -H "Authorization: Bearer <access_token>"
```

**Get the league's teams/rosters:**

```bash
curl "https://fantasysports.yahooapis.com/fantasy/v2/league/<league_key>/teams?format=json" \
  -H "Authorization: Bearer <access_token>"
```

then, per `team_key` found in that response:

```bash
curl "https://fantasysports.yahooapis.com/fantasy/v2/team/<team_key>/roster?format=json" \
  -H "Authorization: Bearer <access_token>"
```

**Get league transactions:**

```bash
curl "https://fantasysports.yahooapis.com/fantasy/v2/league/<league_key>/transactions?format=json" \
  -H "Authorization: Bearer <access_token>"
```

## Step 6 — What to actually capture and report back

This is the real deliverable of the spike. For each call above, save the
raw JSON response (redact nothing structural — only redact if it contains
another real person's PII you shouldn't retain) and note:

1. **Exact JSON shape.** Yahoo's API is XML-first; its JSON is a mechanical
   conversion of that XML and is widely reported (not confirmed by this
   agent) to represent collections as objects keyed by stringified indices
   plus a `"count"` field, rather than plain arrays — e.g.
   `{"0": {...}, "1": {...}, "count": 2}`. `modules/platforms/yahoo.py`
   defends against this shape, but **only real captured responses can
   confirm whether that's actually correct**, and the adapter's parsing
   almost certainly needs adjustment once you have them. Paste a few real
   responses (or attach as files) and that adapter should be corrected to
   match — ping engineering with the raw payloads.
2. **Rate-limit behavior.** Yahoo's Fantasy Sports API Terms of Use only
   say usage "should not exceed reasonable request volume" and that Yahoo
   may throttle or contact you if it does — no official numeric limit for
   this specific API was found in current published docs (a 20,000/hour
   figure that circulates online is for the separate, legacy YQL service,
   not confirmed to apply here). Make ~20-30 calls in a short burst against
   the test league and note: any `429`/`999` style status codes, any
   `Retry-After` or rate-limit headers, and roughly how many calls it took
   before (if ever) you saw throttling.
3. **Token lifetime in practice.** Confirm the real `expires_in` and that
   `refresh_access_token()` in `modules/platforms/yahoo_oauth.py` actually
   works against a real expired-but-refreshable token (wait out the
   `expires_in` window, or just call it once to confirm the refresh grant
   round-trips).
4. **Anything that doesn't match this runbook.** Especially: different
   field names, a different auth header format, a different error shape,
   or scopes/permissions behaving differently than described in Step 1.

## What's already built vs. what's still needed (quick reference)

| Piece | Status |
| --- | --- |
| OAuth2 authorization URL builder | Built, matches docs, **unexercised live** |
| OAuth2 token exchange / refresh | Built, matches docs, **unexercised live** |
| `YahooPlatformAdapter` (league/roster/users/transactions) | Built against documented/reported shapes, **unexercised live** |
| `YahooPlatformAdapter` (traded picks, draft listing, draft picks) | Explicitly stubbed as unimplemented — return `[]` with `last_error` set |
| Yahoo Developer app registration | **Human required** — Step 1 |
| Real OAuth consent flow against a real account | **Human required** — Steps 3-4 |
| Real API calls against one real test league | **Human required** — Step 5 |
| Confirming actual JSON shape / rate limits | **Human required** — Step 6 (this is the point of the spike) |
| Adjusting the adapter once real shapes are known | Follow-up engineering work after Step 6 |
