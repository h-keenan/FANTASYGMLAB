# Executive Information Compression & Progressive Disclosure

## Scope

Presentation-only information architecture. Baseline `d41bda6` (post PR #126).

No changes to football logic, valuations, rankings, recommendation generation,
recommendation ordering, Trust calculations, authentication, entitlements,
Stripe, Sleeper, Supabase schema, caching semantics, or business rules.

## Disclosure structure

### Trade Review Detail

1. Package matchup (send / receive) — decision boundary
2. **Executive verdict** (visual weight: verdict) — value delta + confidence
3. One **Reason** and one **Risk** (primary)
4. Expected outcome when distinct from verdict (support)
5. Supporting evidence / Supporting metrics in `<details>` (advanced)

Health risk appears only in the Risk row (no duplicate `st.warning`).

### Player Quick View (canonical for all surfaces)

1. Player identity hero
2. Recommendation (verdict weight) + one concise rationale
3. Current Value — dynasty value, ranks, PPG, health, trend
4. Current Season executive summary (games / PPG / fantasy / production / usage)
5. Career Resume — highest-value achievements only
6. Career Timeline — behind explicit expand; achievements not restated
7. View complete season stats — collapsed expander (full verified tables)
8. Recent News — collapsed
9. Advanced Details — executive metadata, roster read, technical metrics, college

Consumers (Waivers, Trade Hub dossier, My Team, Live Draft, Player Explorer)
all open or embed `render_player_quick_view_content`.

### Comparative dialogs

1. Active value / rank summary
2. League leaderboard first
3. Short interpretation
4. Methodology collapsed (`<details>`)

## Visual weight contract

| Level | Class | Use |
| --- | --- | --- |
| Verdict / action | `dg-info-weight-verdict` | Recommendation, trade verdict |
| Primary evidence | `dg-info-weight-primary` | Reason, Risk |
| Supporting context | `dg-info-weight-support` | Soft outcomes, secondary copy |
| Advanced / raw | `dg-info-weight-advanced` / `<details>` | Metrics, evidence, methodology |

Borders mark interaction or decision boundaries; spacing/typography group the rest.

Weight-level CSS ships inside `RECOMMENDATION_TRUST_CSS` (not a separate
cascade layer) to stay within the Founder Beta cold protobuf budget.

## Duplicated content removed

- Equal-weight Reason / Evidence / Risk / Expected / Metrics rows
- Duplicate health `st.warning` after Risk row
- Always-visible executive metadata grid competing with the decision
- Dense Current Season tables competing with Career Resume
- Timeline restating resume achievement labels by default
- Collapsed Career Resume “Current season” badge spam
- Methodology panel before / equal to the leaderboard

## Remaining density issues

- Full-page `render_player_detail_content` still exists for the dedicated
  player_detail route (outside Quick View); Quick View is the shared dossier.
- Free entitlement truncation still limits visible trade packages (membership).
- Some Advanced Details technical rows can still restate recommendation labels
  when expanded — intentional for power users, collapsed by default.

## Rollback

Revert the merge commit on `main` (boundary: `d41bda6`).
