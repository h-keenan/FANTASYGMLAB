# Auth + shell ownership RCA (P0)

| Field | Value |
| --- | --- |
| Date (UTC) | 2026-08-12 |
| Production | `https://app.fantasygmlab.com` |
| Rollback SHA | `97c934d1149a6c9878fa775fc9e5c291259bd96a` (#274) |

## A. Mid-page Dashboard header

### Classification: **B — guest marketing + live app shell sequentially**

Not intentional preview (D). Not double mount (A).

### Why

Latency fix painted marketing + account CTAs early, then the same `main()` run continued and unconditionally called `render_platform_topbar()` (SELECT / ALERTS / YOU).

### Call sites before → after

| Site | Before | After |
| --- | --- | --- |
| Early `render_marketing_landing` + `render_mobile_auth_entry` | yes | yes |
| `render_platform_topbar` on unsigned+no league | **yes (bug)** | **gated off** |
| Mobile nav / destination sheet on guest landing | yes | gated off |
| Guest league / authenticated workspace topbar | yes | yes (exactly one) |

### Live header DOM counts (ownership)

| Route | Expected live `.dg-executive-shell` / command rail |
| --- | ---: |
| Guest landing (unsigned, no league) | **0** |
| Guest league workspace | **1** |
| Authenticated workspace | **1** |

## B. CREATE FREE ACCOUNT

### Category: **G — environment/config mismatch** (provider unreachable)

Production `SUPABASE_URL` host:

`otsbideskqceaojfzgbt.supabase.co` → **NXDOMAIN** (DNS does not resolve).

Server-side `requests.post` cannot reach Auth → `"Could not reach Supabase Auth."` → UI previously swallowed into generic “Try again.”

| Question | Answer |
| --- | --- |
| Auth user created? | **No** (request never reached provider) |
| Profile/bootstrap failed? | N/A (no auth user) |
| Sanitized error | `provider_unreachable` / Could not reach Supabase Auth |
| Site/redirect URLs | Not implicated (DNS fails before Auth) |

### Code fixes (app-side)

- Structured `classify_auth_error` + actionable UX messages
- Diagnostics event `DYNASTYGM_AUTH` (no email/tokens)
- Client validation (email / min password) before network
- Submit in-flight guard + spinner

### Control-plane required for green signup

Restore a resolvable Supabase project URL + anon key on Render (`SUPABASE_URL` / `SUPABASE_ANON_KEY`). App cannot invent a live project.

## Session isolation (#274)

Preserved: unsigned unexplained leagues still stripped; `accounts.json` restore remains deleted.
