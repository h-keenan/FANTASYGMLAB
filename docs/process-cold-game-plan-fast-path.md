# Process-cold Game Plan fast path (PR #221)

## Production evidence

Warm sessions after #219/#220 reach Game Plan in ~3.4–3.9s.

Process-cold first session after deploy paid:

| Owner | Cold | Later sessions |
|---|---|---|
| `game_plan_shared_league_context` | ~3.2s | ~30ms |
| `game_plan_trade_inventory` | ~2.6s | ~300ms |
| trade→compose gap | ~1s | still present as assembly |

Root cause: `@st.cache_data` still **hashes large DataFrames** (`df_players`, `df_summary`) on every call. Session package memo (#219) cannot help a brand-new Streamlit session.

## Cache architecture

| Layer | Scope | Key | Contents |
|---|---|---|---|
| Prepared frame `_PROCESS_FRAME_STORE` | Process | public/settings signature | valued+ranked players |
| **Game Plan league process memo** | Process | prepared-frame + league + settings + flags | lightweight shared context |
| **Game Plan trade process memo** | Process | frame + league + roster + roles/strategy/untouchables | enriched headline inventory |
| Session Game Plan package | Session | full package fingerprint | briefing + tiles |
| Compose process memo | Process | tile fingerprints + lifecycle digest | `DailyGmBriefing` |

### Ownership split

- **PUBLIC / PROCESS-REUSABLE:** prepared valued frame (existing)
- **LEAGUE-REUSABLE:** lightweight Game Plan context (`include_intelligence=False`) — no account in key
- **USER/ROSTER-SPECIFIC:** trade headline + session package (roster/roles/entitlement in key)

## Compose ~1s audit

Instrument separately:

1. `game_plan_briefing_assembly` — tiles / waiver / injury / organize / snapshot **between** trade ready and compose
2. `game_plan_compose` — `compose_daily_gm_briefing` only, with `cache_status` + phase ms

Compose itself is presentation-only; large trade→composed gaps are usually assembly, not zone sorting.

## Diagnostics

- `startup_cache_event` rows always emit (no 500ms gate) for package / process league / process trade / compose
- Milestones accept `cache_status` + safe `detail`
- Auth handshake adds `clock_domains` (no auth behavior change)

## Invariants

- `loading_dismissed` still before players / prepared / Game Plan
- No fake prewarm / cron pings
- Full intelligence remains deferred to League Pulse
- Cold build ≡ warm/cache path recommendation identity
