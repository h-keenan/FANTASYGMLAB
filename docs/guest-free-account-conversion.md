# Guest / Unsigned → Free Account Conversion (#224)

Baseline: main after #223 (`f7e061f`).

## Guest journey before

1. Marketing / app URL → account vs guest choice → Sleeper username → league cards → Dashboard.
2. Guest ran as Free entitlement with limited depth (Game Plan yes; truncated Next Moves / Trade / Waivers).
3. After import there was **no free-account continuity CTA** — only Premium locks and launch-time account UI.
4. You popover labeled **Guest** with Premium + Feedback only (no Sign in).
5. Guest → account auth **wiped** username/league; saved account default (if any) resumed — no intentional guest-league handoff.

## Guest journey after

Same first-value path (username → league → Game Plan) without a signup wall.
After first useful Game Plan, a restrained **Save your front office** module appears.
You / GM menu offer Create free account / Sign in that open an in-app auth dialog.
Auth handoff captures guest league/route before wipe and restores when safe.

## First useful guest moment

**Today's Game Plan** on Dashboard (existing `game_plan_first_useful` / `first_game_plan_seen`).
Signup prompt renders **below** Game Plan, never above Top Priority.

## Guest-access surface matrix

| Surface | Class |
| --- | --- |
| Dashboard / Game Plan | LIMITED (full Game Plan; truncated Next Moves; Pulse Premium) |
| My Team | LIMITED (core open; Deep Analysis / advanced Premium) |
| League Overview | FULL GUEST |
| Trade Hub | LIMITED (preview ideas Free) |
| Waivers | LIMITED (Priority Adds Free) |
| PQV | FULL GUEST core |
| News / Alerts | FULL GUEST (filtered) |
| GM menu | FULL GUEST for core routes |
| Deep Analysis | PREMIUM |
| Decision Memory durable | ACCOUNT + PREMIUM + experiment |
| GM Targets durable | ACCOUNT + PREMIUM + experiment |
| Premium checkout | ACCOUNT REQUIRED |

## Free account benefits (canonical — actually true)

- Remember Sleeper username and saved leagues
- Resume default league next visit
- Keep league selection ready without re-importing
- Carry account preferences across sessions once signed in

**Not promised:** Decision Memory, GM Targets, Share, deeper Premium boards.

## Canonical signup copy

**Title:** Save your front office  
**Body:** Create a free account to keep this league and your personalized setup ready next time. No payment required.  
**Guest label:** Browsing as guest

## Prompts

| Surface | Placement | Dismissal |
| --- | --- | --- |
| Dashboard | After Game Plan | Session `Not now` |
| My Team | After workspace, before Deep Analysis | Session |
| Trade Hub | After visible trade board, before Premium lock | Session |
| Waivers | After Priority Adds, before Premium lock | Session |
| PQV | After untouchable / GM Targets controls | Session |
| Header You | Create / Sign in buttons (not a banner) | N/A |
| GM menu | Quiet “Save this setup” | Opens dialog |

One soft module per surface; dismiss remembered for the session/view. No auto modals / timers.

## Auth handoff

Preserved fields: platform, username, selected_league_id/name, my_roster_id, route, optional player_id, prompt_surface.  
Stored in `_guest_auth_resume` (survives `apply_auth_payload` wipe).

**Signup / sign-in with no account default:** restore guest league + route; `save_current_context` when possible.  
**Sign-in with existing default saved league:** account truth wins; guest league not forced.  
**Post-signup destination:** `_pending_platform_route` from resume (same page when safe).  
**Logout:** clears guest auth dialog/resume/dismiss keys with auth session.

## Analytics (no PII)

`guest_username_submitted`, `guest_league_selected`, `guest_first_useful`, `guest_signup_prompt_seen`, `guest_signup_started`, `guest_signup_completed`, `guest_signin_started`, `guest_signin_completed`  
Props may include `prompt_surface` / `route` / `league_id` / `account_state`. Username and email remain blocked.

## Funnel

Landing → guest username → guest league → first useful → signup prompt → signup start → signup complete → return to context.

## Out of scope

Premium redesign, experimental graduation, forced signup wall, football logic changes.
