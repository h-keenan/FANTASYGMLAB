# Canonical Recommendation Narrative Audit

Presentation / context-integrity only. Football logic, valuations, rankings,
recommendation generation, ordering, Trust math, authentication, entitlements,
Stripe, Sleeper, Supabase schema, caching contracts, and business rules are
unchanged.

## Previous narrative sources

| Surface | Prior source | Drift risk |
|---|---|---|
| Dashboard Next Move / Top Trade | `trade_summary["rationale"]`, partner prefix copy | Could diverge from Trade Hub card “why” sentence |
| Trade Hub cards | `trade_problem_sentence(idea)` + tag/title | Authoritative for trades, but not shared |
| Trade Review / detail | Inline Reason / Evidence / Risk / Expected outcome assembly | Same idea, separate field assembly |
| Player Quick View | Independent Shop / Hold / Monitor / Trade Target heuristics from roster role + `source_note` | **Primary drift vector** vs Trade Hub |
| My Team Next Move / Top Trade / Waiver | Local immediate recommendation strings + opportunity notes | Parallel wording without shared identity |
| Waiver detail | `free_agent_reason_text` + `waiver_recommendation_label` | Local to waivers; not reused in PQV provenance |
| Notifications | Demo route-only titles/bodies | No recommendation payload (still true for demos) |

## Canonical model

`modules/canonical_recommendation_narrative.py` defines
`CanonicalRecommendationNarrative` with:

- `action`, `target_label`, `package_label`
- `reason`, `evidence`, `risk`, `expected_outcome`
- `confidence_label`, `confidence_wording`
- `market_signal`, `fit_signal`
- `recommendation_id` (deterministic; trade IDs match Trade Hub identity digest)
- `league_id`, `roster_id`, `valuation_lens`
- `source_surface`, `player_ids`
- `is_active_recommendation` (false = neutral player context)

Builders derive only from existing recommendation / Trust presentation fields:

- `build_trade_narrative`
- `build_waiver_narrative`
- `build_roster_decision_narrative`
- `build_neutral_player_narrative`

Surface shortening uses `shorten_narrative_text` / `consumer_fields` and must
preserve the same facts and conclusion.

## Consumer map

| Consumer | How it consumes the model |
|---|---|
| Dashboard Next Move / Top Trade / Waiver | Tiles attach `recommendation_narrative`; notes/actions shorten canonical fields |
| Trade Hub cards | Card “why” sentence = canonical `reason`; opens bind provenance |
| Trade Review / detail | Explanation panel from `narrative.explanation_fields()` |
| Player Quick View | Resolves bound narrative by league + player; else neutral context |
| My Team Next Move / Top Trade / Waiver | Same narrative objects as headline trade / top waiver |
| Waiver detail | Builds waiver narrative on open and binds for PQV |
| Notifications | `summary_from_recommendation_narrative` when a real narrative exists; demo items remain route-only |

## Provenance flow

```text
Recommendation object (trade idea / waiver row / roster decision)
  -> build_*_narrative(...)
  -> bind_narrative(session) on surface open / card open
  -> PQV resolve_narrative_for_player(player_id, league_id)
       |-- match -> active Recommendation presentation
       `-- miss  -> build_neutral_player_narrative (no synthetic Shop/Hold/Monitor)
```

League switch / PQV clear / notification route clear call `clear_narrative`.
Stale prior-league payloads fail `resolve_narrative_for_player` on league mismatch.

## Inconsistencies found

1. PQV invented Monitor / Trade Target / Shop actions from roster heuristics while
   Trade Hub described Acquire / package fit from the idea object.
2. Dashboard trade notes used franchise summary rationale rather than the same
   target-reason chain as Trade Hub cards.
3. Opening PQV without a recommendation still reused whatever `source_note` the
   route happened to carry, without distinguishing analysis from recommendation.
4. No deterministic recommendation identity was attached to PQV / Dashboard opens.

## Inconsistencies fixed

1. Trade / Dashboard / My Team / Trade Review / PQV share one trade narrative for
   the same idea identity.
2. PQV without matching provenance shows **Player Context** (neutral), not a
   synthesized recommendation action.
3. Session provenance is league-scoped and cleared on league switch / PQV close /
   notification routing.
4. Waiver opens bind a waiver narrative so PQV cannot rewrite Add/Stash/Watch.
5. Cached Trade Hub idea objects still rebuild the same narrative from fields;
   membership/order/Trust scores are not recomputed by the narrative layer.

## Retained builders

These remain as field extractors or shorteners that **feed** the canonical model
(they do not independently redefine recommendation meaning):

| Builder | Why retained |
|---|---|
| `trade_hub_ui.trade_target_reason` | Existing target/fit field chain |
| `trade_hub_ui.trade_partner_reason` | Existing partner/evidence field chain |
| `trade_hub_ui.trade_confidence_reason` | Existing confidence + health caveat |
| `player_cards.recommendation_reason_text` | Length-only shortening |
| `waivers_ui.free_agent_reason_text` | Existing waiver reason assembly |
| `waivers_ui.waiver_recommendation_label` | Existing waiver action label |

Independent PQV Shop/Hold/Monitor **recommendation** synthesis is no longer the
active recommendation story. Roster status chips may still describe roster role
separately from the recommendation panel.

## Remaining risks

1. **Notifications demos** still lack live recommendation payloads; summaries can
   use the canonical helper only when a real narrative is supplied.
2. **Non-trade roster decision cards** that do not attach
   `recommendation_narrative` still open PQV as neutral unless structured
   decision tiles include the narrative payload.
3. **Live Draft** recommendation reasons remain draft-board specific; they are
   outside the Trade Hub / Dashboard / PQV trade consistency contract unless a
   narrative is explicitly bound later.
4. Surface shortening can truncate mid-sentence at display limits; the underlying
   `recommendation_id` and full fields remain the source of truth.

## Validation

- `python3 -m compileall` on touched modules / `app.py`
- `pytest` (full suite)
- Founder Beta performance budget
- `git diff --check`
- Chromium widths 320–1440 for Dashboard, Trade Hub, Trade Review, PQV, My Team, Waivers
- CI Delivery Validation

## Rollback

Revert the merge commit that lands this branch. Boundary: prior `main` SHA
`c09bf3d58cdb34ec8158318d476d44979ee1944b` (post PR #131).
