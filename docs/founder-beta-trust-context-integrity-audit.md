# Founder Beta Trust & Context Integrity Audit

## Verdict

The audited production paths share one league identity, roster identity, valuation frame, and route-level league context per Streamlit rerun. No cross-surface football-value discrepancy was reproduced. One state-hygiene weakness was corrected: direct league selection now invalidates the prior `active_league_context` immediately, rather than relying on the next resolver call to overwrite it.

## Canonical flow

`resolve_active_league_context` → frozen `WorkspaceIdentity` → active Balanced Dynasty valuation frame → shared league context → route presentation.

Dashboard, My Team, Trade Hub, Waivers, League Overview, Live Draft, League Intelligence, and Player Explorer receive the same selected league and active valuation frame. Route helpers may request a reduced shared context, but those flags omit secondary intelligence; they do not rebuild player values.

## Integrity matrix

| Concern | Evidence | Result |
|---|---|---|
| Active league | One `WorkspaceIdentity` is created in `main`; route calls use its `selected_league_id`. | Pass |
| Roster context | `my_roster_id` comes from the same identity and keys Trade Hub, news, waiver, and player-fit state. | Pass |
| Player valuation | `apply_active_valuation` produces one `df_players` frame before route rendering. | Pass |
| Trade recommendations | Generation and Trust enforcement occur before entitlement presentation and grouping. | Pass |
| Free vs Premium | Access slicing occurs after analysis. Values, order, fit, and explanations are not recomputed by tier. | Pass |
| News | News is cached globally, then filtered with league roster/player ownership. News does not mutate valuation or recommendation inputs. | Pass by contract |
| Explanation alignment | Trade explanations consume the enriched idea rendered by the same card/detail path; player dossiers consume the same selected row and score field. | Pass |
| League cache isolation | Cached league builders accept league ID, score field, settings, and player inputs; session keys for news, Trade Hub, orientation, and deferred sections include league identity. | Pass |
| League transition | Selected-team and dossier state were cleared; `active_league_context` is now also invalidated at selection time. | Corrected |
| Entitlement transition | Entitlement is restored before workspace/page rendering and refreshed on Premium entry; Premium locks fail closed when effective entitlement is Premium. | Pass |

## News and outlook semantics

Current news is contextual evidence, not a valuation input. Therefore a headline update appears consistently wherever the shared news feed is rendered, but it does not silently change player value, rank, or recommendation. If news becomes a calculation input later, its source fingerprint must become part of the canonical analysis fingerprint and cache keys before release.

## Cache rules

- League-specific cache keys must include stable league identity.
- Roster-specific state must include stable roster identity.
- Valuation caches must include score field, settings, archetype/strategy context, and player-source identity.
- Entitlement and authentication state must never enter shared football-analysis caches.
- League switching must invalidate unscoped active context and retain only deliberately league-namespaced historical state.

## Automated contract

Run `python scripts/audit_context_integrity.py`. It fails nonzero if canonical workspace resolution, valuation-frame reuse, shared-context routing, post-Trust entitlement, league-scoped news, or league-transition invalidation is removed.

`modules/context_integrity.py` provides a frozen cross-surface fingerprint and entitlement-independent recommendation signature for future regression fixtures.

## Limitations

The audit proves repository wiring and deterministic fixtures. It does not claim that external Sleeper or news providers update atomically. Provider freshness remains bounded by existing cache TTLs and refresh behavior.
