# Product coherence and runtime stability

## Runtime ownership

The Dashboard visibility probe is passive. It may write browser console evidence
and document attributes, but it must not emit a Streamlit component trigger after
useful content is visible. Before this correction, the probe emitted a stable
`visibility_ack` after five seconds of continuous visibility. That event forced a
full rerun during the exact window in which a phone user could begin scrolling.
Removing the event preserves diagnostics while removing one post-useful route
replacement. Dashboard Python computation and provider freshness are unchanged.

## Alert state

Persistent alert inventory and transient delivery have separate owners:

- `notification_center.publish_activity_inventory` owns the canonical,
  league-scoped history and explicitly marks hydration ready, including a valid
  empty result.
- command chrome renders `Initializing…` until that readiness marker matches the
  active league; it never translates missing inventory into `All caught up`.
- `render_pending_urgent_delivery` consumes one queued urgent roster event after
  the stable command header. Its material-signature state prevents rerun duplicates.

## FAAB authority

Sleeper is authoritative when both loaded values exist:

- league `settings.waiver_budget` (initial budget)
- active roster `settings.waiver_budget_used` (spent budget)

The difference is the league-scoped remaining balance. No provider request is
added: the resolver consumes payloads already loaded by the Waivers route. When
Sleeper does not provide both values, the authenticated user may save one
league-specific balance in the existing `user_settings.settings` JSON boundary.
Dollar guidance leads when remaining FAAB is known; percentages remain the
explicit fallback.

## Founder diagnostics authority

`DYNASTYGM_FOUNDER_OPS=1` remains the global kill switch, but is no longer enough
to expose navigation. The authenticated account must also carry a server-sourced
`founder_ops: true` capability in Supabase Auth `app_metadata`. Profile fields,
browser-editable `user_metadata`, query parameters, local storage, and session-only
flags do not grant access.

The existing Founder Ops surface remains the owner for analytics, performance,
cache/provider, Stripe/Supabase, and feedback evidence. Its Labs inventory reads
the existing experimental graduation registry and does not enable routes.

Registry findings:

- Runnable/graduated: Decision Memory, GM Targets, Share Recommendation, Player
  Explorer, Trade Analyzer, Live Draft.
- Experimental: ESPN limited import.
- Deferred/hidden: Weekly Report.
- Archived/merged into existing surfaces: Teams and Manager Tendencies routes.

## Player presentation

The canonical Football Asset remains the owner. `player_cards` already exposes
intentional `dense`, `compact`, and `standard` variants used by roster, explorer,
waiver, and trade workflows. This pass does not create a parallel player-summary
implementation.

## Deferred rendered findings

The following are polish observations, not runtime blockers, and were intentionally
not expanded into this PR:

- some desktop Dashboard supporting cards leave unused horizontal space;
- League Overview remains long on mobile because it presents four complete ordered
  boards before intelligence;
- some secondary captions are low contrast in synthetic fixture screenshots;
- Founder Ops uses practical Streamlit tables, appropriate for its restricted
  diagnostics audience but not a customer-facing pattern.
