# Experimental Decision Memory Contract (PR #160)

Premium + Experimental Founder Beta feature. Presentation and durable
persistence only. Does **not** change football logic, valuations, rankings,
recommendation generation/scoring/ordering, Trust, auth rules, entitlement
rules globally, Stripe, Sleeper semantics, or lifecycle material-change meaning.

**Baseline main:** `eddea45832c6a11222c3480972a2affba2b51647` (after PR #159)

**Kill switch:** `DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY` (default **ON**; set `=0` to disable)

---

## Product purpose

Answer for returning Premium founders:

> What changed since I was last here?

Decision Memory records **material canonical decision transitions** already
detected by #149/#151 — not a generic activity log.

---

## Architecture

```text
Dashboard tiles
  → publish_activity_inventory
      → hydrate durable baseline (Premium + experiment, session cold)
      → compare_inventory_signatures  (#149 authority)
      → record_inventory_transition   (#151 session events)
      → persist_after_transition      (events + baseline upsert)
  → What Changed (≤3)
      → View Decision Memory → (Premium dialog)
```

Lifecycle remains the sole authority for *whether* something changed.
Decision Memory only stores and recalls already-built `DecisionChangeEvent` rows.

---

## Current vs historical truth

| System | Role |
| --- | --- |
| Recommendations / Trust / rankings | **Current** football truth |
| Decision Memory | Historical record of observed material transitions |

Historical events never feed recommendation generation, scoring, ordering,
Trust, valuations, or rankings.

Deep links reopen **current** destinations only (`recommendation_narrative=None`).

---

## Schema

Migration: `docs/supabase_decision_memory.sql`

### `decision_memory_events`

Primary key `(user_id, event_id)` — idempotent multi-tab inserts.

Fields: `event_id`, `user_id`, `league_id`, `roster_id`, `recommendation_id`,
`event_type`, `transition`, `reason_code`, `category`, `target_label`,
`player_id`, `destination`, `previous_state` / `current_state` (bounded JSON),
priorities, `priority_band`, `confidence_band`, `scoring_format`,
`valuation_lens`, summary fields, `created_at`.

### `decision_memory_baselines`

Primary key `(user_id, league_id)`.

Stores material signatures + slim prior snapshots + top recommendation id for
cross-session compare. **Never pruned** by retention cleanup.

---

## RLS (fail closed)

Both tables: `ENABLE ROW LEVEL SECURITY`.

Policies (authenticated only):

- SELECT / INSERT / UPDATE / DELETE: `auth.uid() = user_id`

No anon policies. League id alone is never authorization.
Streamlit uses anon key + user JWT — **no service_role**.

---

## Event taxonomy

Consumes #151 mapping only:

| Transition | Customer headline examples |
| --- | --- |
| Priority changed | Top priority changed |
| New recommendation | New trade / waiver opportunity |
| Action / confidence | Recommendation changed / strengthened / softened |
| Resolved | Recommendation / waiver / roster need resolved |
| Scoring / valuation context | Strategy context changed (via why labels) |

Identical reruns, navigation, menu opens, and first baseline seed create **zero** events.

---

## Baseline semantics

1. First valid inventory for a league (session or durable) seeds baseline only.
2. No “new recommendation” spam when persistence is first enabled.
3. Later sessions hydrate durable baseline into lifecycle session keys before compare.
4. Preserves #151 `had_prior_inventory` gate.

---

## Dedupe / idempotency

1. Deterministic `event_id` = hash(league, recommendation_id, reason, next_state, signature)
2. Session merge skips duplicate ids
3. DB unique `(user_id, event_id)` + upsert `on_conflict`
4. Multi-tab concurrent inserts converge to one row

---

## Retention

- Keep ~**90 days** of events per league
- Cap ~**200** events per league
- Prune is best-effort after writes
- **Baselines are never deleted** by retention

---

## Free / Premium

| Audience | Behavior |
| --- | --- |
| Experiment off | No surface, no durable reads/writes |
| Free + experiment on | Session What Changed stays visible; restrained Decision Memory discovery teaser + Premium lock afterward; no durable history contents; no writes |
| Premium + experiment on | What Changed + Decision Memory dialog; durable sync |

---

## Inbox / What Changed / Decision Memory

| Surface | Job |
| --- | --- |
| Inbox | Current activity / action |
| What Changed | Recent transition summary (≤3) |
| Decision Memory | Durable historical transitions |

Do not publish every Decision Memory event as a notification.

---

## League / account isolation

- League-scoped reads/writes
- League switch clears in-memory Decision Memory cache (#156 preserved)
- Logout / account switch clears in-memory cache (#145); durable rows remain
- Prior-account events never flash during auth restoration

---

## Performance

Not on first-usable-shell critical path.

| Operation | Notes |
| --- | --- |
| Baseline hydrate | Before inventory compare; Premium only; fail-soft |
| Event insert | Small upsert; idempotent |
| History fetch | On Decision Memory open / Dashboard merge; cached in session |
| Football recomputation | None for viewing history |

Protobuf budget unchanged (CSS remains route-scoped).

---

## Ops activation

1. Run `docs/supabase_decision_memory.sql` in Supabase SQL Editor.
2. Set Render env `DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY=1`.
3. Confirm Premium test account can open Decision Memory.
4. Confirm Free sees discovery only.
5. Confirm kill switch `=0` hides surface and stops writes.

Until migration is applied, the app marks Decision Memory unavailable and continues without crashing.

---

## Privacy / deletion

| Topic | Behavior |
| --- | --- |
| Stored | Material transition summaries + slim structured snapshots; account-owned |
| Retention | ~90 days / 200 events; baselines until account deletion |
| Ownership | `user_id` → `auth.users` |
| Account deletion | `ON DELETE CASCADE` removes events + baselines with the auth user |
| App logout | Clears session cache only — does not wipe durable history |

If a product self-serve “delete my data” workflow is added later, it must DELETE from
both Decision Memory tables for `auth.uid()`. No such customer workflow exists yet —
document as follow-up.

---

## Known limitations

- Requires Ops migration + kill switch before customer value appears
- Cross-session compare depends on successful baseline hydrate (network/table)
- Retention prune is best-effort client-side, not a scheduled job
- No LLM explanations (by design)
- Desktop uses a bounded `st.dialog` (not a giant modal wall)

---

## Files

| Path | Role |
| --- | --- |
| `docs/supabase_decision_memory.sql` | Schema + RLS |
| `modules/decision_memory.py` | Persistence + entitlement gates |
| `modules/decision_change_history_ui.py` | What Changed + Decision Memory UI |
| `modules/notification_center.py` | Hydrate + persist hooks |
| `tests/test_decision_memory.py` | Contracts |
