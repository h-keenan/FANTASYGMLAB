# Canonical Player Ranking Contract

| Field | Value |
| --- | --- |
| Baseline | latest `main` at implementation |
| Scope | Consistency and data-presentation for player overall / position ranks |
| Explicit non-changes | Valuations, recommendation generation/ordering, Trust, trade logic, waiver logic, auth, entitlements, Stripe, Supabase schema, Sleeper semantics, business rules |

## Ranking sources

| Source | Role |
| --- | --- |
| Format-adjusted dynasty / value scores | **Canonical ordering key** after the existing valuation lens applies league scoring multipliers |
| Sleeper `search_rank` | Market input to valuations only — **not** shown as customer OVR after this contract |
| FantasyCalc values | Market blend into scores; single cached PPR fetch remains (not a per-format rank table) |
| Live Draft board order | Draft-local board rank (`overall_rank` on the draft board) — separate from league canonical OVR |
| Waiver FA group ranks | Waiver-local `position_rank` for waiver recommendation logic — canonical ranks kept in `canonical_*` |

## Methodology

Players in the eligible skill-position pool (QB / RB / WR / TE, active, not retired/inactive) are ordered by the **existing** format-adjusted score field already produced for the active league (`dynasty_score` / `value_score` / rebuild field as selected by the valuation lens).

- **Overall rank**: dense 1..N in that ordered pool
- **Position rank**: dense 1..N within each position
- **Provenance**: `format_adjusted_valuation_order`
- **No new ranking formula** is invented; no Trust / trade / waiver scoring changes

Half-PPR is supported because league settings already resolve reception scoring into `Half-PPR` and the valuation lens already applies Half-PPR multipliers.

## Scoring-format resolution

Resolved by `canonical_player_ranking.resolve_scoring_rank_context`:

1. Manual league scoring override (`PPR` / `Half-PPR` / `Standard`) when not `Auto`
2. Else league settings `scoring_format` from Sleeper detection (`rec` thresholds) or defaults
3. Aliases: `Non-PPR` / `std` → `Standard`

### Fallback behavior

| Case | Behavior |
| --- | --- |
| Supported format | Ranks attached; `rank_scoring_format` labeled |
| Unknown / custom scoring | **Unsupported** — ranks unavailable with explicit reason; **no silent fallback** to PPR |
| Missing score / ineligible player | `Rank unavailable` — never `0` |

Default customer-facing ranks always reflect the **active league** format. The existing League scoring overrides control remains the comparison switch (PPR vs Half-PPR vs Standard); switching override refreshes valuation multipliers and canonical ranks together.

## Consumer map

| Surface | Display |
| --- | --- |
| Player Quick View | Overall Rank / Position Rank / Format; methodology disclosure |
| Player Explorer | Compact `OVR #n · POS #m` (canonical, not Sleeper search_rank) |
| My Team | Compact ranks on Core Assets notes; PQV inherits attached ranks |
| Trade Hub | PQV / package open uses annotated player rows; trade ordering unchanged |
| Trade Review | Same annotated player context |
| Waivers | Canonical compact chip when available; FA-relative `position_rank` retained for waiver logic |
| Dashboard | Shared `df_players` ranks; team power ranks remain team-level |
| League Intelligence | Team boards unchanged; player opens use canonical ranks |
| Live Draft | Board order kept for draft UX; league canonical OVR/POS shown beside board ranks |
| Search / recommendation cards | Annotated frame ranks when player rows carry `canonical_*` |

Compact: `OVR #12 · WR #4`
Detail: Overall `#12`, Position `WR4`, Format `PPR`

## Cache / invalidation

- Ranks are derived in-memory after valuation each run — not a separate persisted rank DB
- Session key `_canonical_rank_context_key` tracks `score_field + league settings + format`
- On context change, `invalidate_rank_columns` clears rank-related session keys so stale boards cannot linger across league / scoring switches
- Free and Premium use the **same** `attach_canonical_ranks` helper (identical underlying ranks)

## Unsupported cases

- Custom reception scoring outside PPR / Half-PPR / Standard
- Kickers / DST / non-skill positions
- Retired / inactive players
- Players without a verified score field

## Remaining risks

1. Live Draft still shows **board order** prominently (draft-local); canonical ranks are adjacent — users must not confuse board `#` with league OVR
2. Waiver FA-relative ranks remain for logic; display prefers canonical when present
3. FantasyCalc cache is still a single PPR market file; format differences come from valuation multipliers, not separate FantasyCalc rank feeds
4. Comparative PPR vs Standard examples require scoring override or the comparison helper on a **base** (pre-lens) frame — do not re-lens an already-adjusted board

## Consistency hardening (post-#141)

| Gap | Fix |
| --- | --- |
| Explorer fell back to Sleeper `search_rank` as OVR | Removed — missing canonical ranks stay unavailable |
| `lookup_player_rank` defaulted missing format to PPR | No silent PPR label; empty format when unset |
| Live Draft board `#0` | `format_local_board_rank` never prints `0` |
| Detail Position Rank `#4 WR` | Canonical detail uses `WR4` |

Rank chips are plain-text formatters (`format_compact_rank` / `format_detail_ranks`) with **no per-control alignment CSS** — surfaces consume shared text, not surface-specific rank chrome.

## Rollback

Revert the merge commit introducing `modules/canonical_player_ranking.py` and its surface wiring.
