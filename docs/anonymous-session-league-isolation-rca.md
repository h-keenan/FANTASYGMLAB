# Anonymous session account-league isolation (P0)

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-08-12 |
| Production host | `https://app.fantasygmlab.com` |
| Rollback SHA | `f6433c71c3872eae629a59a34c2763062413d7ff` (pre-branch `main`) |

## Verdict target

`SESSION ISOLATION CLEAN` after deploy + production matrix.

## Root cause

**State owner:** process/disk-global `data/accounts.json` `"current"` singleton, read by `resolve_active_league_context()` when `_identity_established` + `_league_selection_established` were set.

That path could restore another account’s `league_id` / username into a Streamlit session that was not authenticated and did not explicitly import a guest league. Header `league_name` is driven by `selected_league_id` (`has_league`), so this was **underlying football-context leakage**, not presentation-only chrome.

Amplifiers (not inventors of selection): process `@st.cache_data` / `_PROCESS_*` football memos keyed by league_id once a wrong selection existed.

## Auth boundary before → after

| | Before | After |
| --- | --- | --- |
| Unsigned + unexplained `selected_league_id` | Could survive / be restored from `accounts.json` | **Stripped** by `enforce_anonymous_account_league_boundary` |
| `accounts.json` restore in `resolve_active_league_context` | Active | **Removed** |
| Guest league allowed when | Any session state | Only `GUEST_LEAGUE_ORIGIN_EXPLICIT` in **this** session |
| Auth resume | Supabase auto-resume | Unchanged; marks `auth_resume` origin |
| Unsigned writes to `accounts.json` | Yes via `_persist_active_account_context` | **Skipped** |

## Cache / memo keys

| Store | Key fields | Session-safe? |
| --- | --- | --- |
| `selected_league_*` | `st.session_state` | Yes (per Streamlit session) |
| `GUEST_LEAGUE_ORIGIN_KEY` | session | Yes; cleared on logout |
| `data/accounts.json` current | **unkeyed singleton** | No longer a restore source |
| prepared frame / Game Plan process | football signature (league/settings) | Shared warm cache only after authorized request |
| shell chrome maps | session map by league/roster signature | Session-scoped |

## Incognito storage (production probe)

Fresh private context on `app.`:
- localStorage auth keys: **NONE**
- cookies: Streamlit XSRF + analytics only
- header: **No league selected**
- account: guest

## Logout

`clear_auth_session` + `ACCOUNT_BOUND_TRANSIENT_KEYS` clear league, roster, origin, identity sentinels. Boundary re-check leaves guest empty.

## Tests

`tests/test_anonymous_account_league_isolation.py` — named around anonymous account-league isolation, cross-user, logout, guest-to-guest, concurrency 1/3/5/10, diagnostics hygiene.
