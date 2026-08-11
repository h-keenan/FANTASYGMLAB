# Automatic league settings → player value calibration audit

Branch: `cursor/league-context-valuation-audit-71e1`  
Builds on core valuation audit (#252 / `docs/valuation-calibration-audit.md`).

## VERDICT: **NEEDS MORE WORK**

Automatic detection from Sleeper payloads is proven for dynasty/redraft,
PPR buckets, superflex/2QB, TE premium, starters, team count, and reserve
depth. League multipliers move scores in the right direction with profile-aware
PPR/TE differentials when targets/receptions exist, and settings digests isolate
prepared frames across dissimilar leagues.

**Not TRUSTWORTHY yet** because:

1. PPR/Half/Standard still cannot fully model receiving-role economics without
   reliable usage (fallback uses `opportunity_score`).
2. Passing TD / first-down / yardage bonuses are detected but **unused**.
3. Keepers are mapped to dynasty horizon math (`_keeper_mode` flag only).
4. Redraft pick discounting stacks across pick-format + lens multipliers.
5. League adjustments overwrite `dynasty_score` / `value_score` /
   `rebuild_score` in place (intentional league-context values on the prepared
   frame — no separate `league_adjusted_score` column).

---

## 1. Pipeline map

```
Sleeper get_league(league_id)
        ↓
detect_league_value_settings_from_payload  ← canonical auto-detect
        ↓
resolve_league_value_settings (+ optional UI Auto overrides)
        ↓
league_value_settings_key (digest)
        ↓
apply_valuation_lens
  base score from rankings.apply_valuation_model
  rebuild value_score (current availability blend)
  redraft blend on dynasty_score when league_format=Redraft
  × _league_settings_multiplier (league-context)
        ↓
attach_canonical_ranks (score_field from active lens)
        ↓
prepared_player_frame (signature includes settings key)
        ↓
PQV / My Team / Trade Hub / Waivers / League Overview / Game Plan
```

| Concern | Canonical owner |
| --- | --- |
| Raw fetch | `modules/sleeper.get_league` |
| Normalize / detect | `app.detect_league_value_settings_from_payload` |
| UI overrides | `app.resolve_league_value_settings` |
| League multipliers | `app._league_settings_multiplier` |
| Lens application | `app.apply_valuation_lens` |
| Prepared frame | `modules/prepared_player_frame` |
| Pick format | `trade_ideas._pick_format_multiplier` + `draft_pick_score_multiplier` |
| Base football value | `modules/rankings.apply_valuation_model` (unchanged this pass) |

### Architecture layers (must stay distinct)

| Layer | Representation |
| --- | --- |
| Canonical football/base | `rankings` `score` before lens |
| League-adjusted value | lens outputs after `_league_settings_multiplier` |
| Team-strategy preference | `apply_strategy_age_curve` / pick strategy multipliers (Trade Hub copies) |

League adjustments **overwrite** the prepared-frame score columns (not a parallel
column). That is intentional: surfaces read one league-context value. Isolation
is via settings digest + lens in the prepared-frame signature.

---

## 2. Settings inventory

| Setting | Status | Notes |
| --- | --- | --- |
| Dynasty vs redraft (`settings.type`) | **Auto + applied** | 0→Redraft; 1→Dynasty+`_keeper_mode`; else Dynasty |
| Keeper | **Partial** | Detected as dynasty horizon; no separate keeper math |
| PPR / Half / Standard (`rec`) | **Auto + applied** | Buckets ≥0.95 / ≥0.45 / else; profile-scaled differentials |
| Points per reception by position | **Unsupported** | No per-position rec in Sleeper path |
| Superflex / 2QB / 1QB | **Auto + applied** | QB ×1.35 / ×1.55; also picks + lineup |
| TE premium | **Auto + applied** | Receiving-intensity scaled (~1.06–1.18) |
| Starter requirements | **Auto + applied** | Count deltas + starter_pressure |
| Roster / bench / taxi / IR | **Auto + applied** | Youth/stash boosts |
| Team count | **Auto + applied** | Pressure + 1QB deep-league QB bump |
| Flex counts | **Auto + applied** | Combined flex in multiplier; regular/WRRB in digest |
| Passing TD (4 vs 6) | **Detected, unused** | Stored in `_detected_scoring` |
| Yardage / FD bonuses | **Detected, unused** | Same |
| Unusual reception scoring | **Partial** | Forced into 3 buckets; ranks may mark custom unsupported |
| ESPN settings | **Ignored** | Detect is Sleeper-shaped |

### Detection honesty fix

Missing `rec` no longer rewrites `scoring_format` via a silent `rec=1.0`
default. Format stays default PPR with `_sources.scoring_format=default`.

---

## 3. Automatic detection fixtures

Harness: `tests/test_league_context_valuation_audit.py`

| Fixture | Asserted |
| --- | --- |
| Dynasty 1QB standard / half / PPR | format + scoring + 1QB |
| Dynasty SF half / PPR | Superflex + scoring + taxi/IR when present |
| Dynasty TE premium | `te_premium=True` from `bonus_rec_te` |
| Redraft 1QB standard / PPR / SF | Redraft + scoring + QB format |
| Keeper PPR | Dynasty + `_keeper_mode` |
| Missing `rec` | default PPR, source≠Sleeper |

---

## 4–10. Calibration results (controlled)

### Dynasty vs redraft
- Redraft lens (`Non-Dynasty`) favors current `value_score` path; aging productive
  WR can outrank young WR on current field while dynasty keeps horizon.
- `league_format=Redraft` blends `dynasty_score` toward current inside lens.

### PPR / Half / Standard
- Identity = PPR.
- Standard/Half scale with `_receiving_intensity_series` (targets/receptions when
  present; else opportunity_score).
- Measured direction: slot WR (140 targets) gains more Standard→PPR than
  early-down RB (12 targets).

### Superflex
- Elite/starting QBs gain ×1.35 (SF) / ×1.55 (2QB) on league-adjusted scores —
  applied in `apply_valuation_lens`, **not** Trade-Hub-only.
- QB/WR ratio rises; starter lift > backup lift.

### TE premium
- Target-earning TE lift > TD-dependent TE lift (intensity-scaled).

### Starters / flex / team count / bench
- More WR starters / flex → higher WR league value.
- 8→16 team raises pressure; 1QB deep leagues bump QB ratio.
- Deep bench+taxi boosts young stash more than aging vet.

### Scoring bonuses
| Field | Classification |
| --- | --- |
| `pass_td` | detected, unused |
| `bonus_rec_yd_100` / rush yard bonuses / FD | detected keys listed when present, unused |
| TE bonus keys | supported |

### Picks
- Dynasty pick components >> redraft (`_pick_format_multiplier` ×0.52).
- Lens `Non-Dynasty` / redraft further discounts via `draft_pick_score_multiplier`.
- Stacking is intentional directionally; magnitude remains debt.

---

## 11–13. Isolation & surfaces

| Check | Result |
| --- | --- |
| Settings key includes format/scoring/QB/TEP/starters/flex/reserves/`other_starter_count`/`_keeper_mode` | Pass |
| Dynasty SF PPR TEP digest ≠ redraft 1QB standard | Pass |
| Prepared-frame signature includes settings key + lens + scoring | Pass |
| Same league-adjusted frame consumed by PQV/My Team/Trade/Waivers/GP | Via prepared frame (no alternate league formula) |
| Strategy overlays | Still preference copies (valuation audit debt) |

League switch retains valued frame **only** when signature matches (identical
settings/lens). Dissimilar leagues miss and rebuild.

---

## 14–16. News & invariants

- `news_factor` remains 0; no headline→score mutation.
- Invariants locked: PPR ≥ Standard for high-target WR; SF > 1QB for elite QB;
  TE premium raises target TE; deeper WR demand raises WR value.

---

## Bugs discovered / fixed

| Bug | Fix |
| --- | --- |
| Missing `rec` treated as PPR via `_safe_float(..., 1.0)` rewrite | Only set scoring when `rec` present |
| TE premium / PPR identical for all profiles at a position | Receiving-intensity scaled differentials |
| `other_starter_count` omitted from settings digest | Included in `league_value_settings_key` |
| Keeper indistinguishable from dynasty | `_keeper_mode` flag on type==1 |
| Detection hard to fixture without network | `detect_league_value_settings_from_payload` |

---

## Cache / performance

- No new provider calls; still one `get_league` for detect.
- League transform remains inside prepared-frame builder (memoized by digest).
- Expected flat protobuf / reruns vs prior pass.

---

## Remaining league-context debt

1. True usage-share PPR model (route/target share when feed quality allows).
2. Apply or explicitly refuse `pass_td` / FD / yardage bonuses.
3. Dedicated keeper valuation (share counts, keep cost).
4. Separate `league_adjusted_score` column vs in-place overwrite (explainability).
5. Soften stacked redraft pick discounts to a single documented layer.
6. ESPN / non-Sleeper league settings path.
7. Per-position reception scoring.

### Top follow-ups
1. Wire optional pass-TD QB differential once product confirms 4pt vs 6pt stance.
2. Persist receiving-role features in base model residual (next football pass).
3. Keeper-specific horizon / pick rules.
4. Single pick-discount owner for redraft.
5. Explainability panel: base vs league multiplier components.

---

## Validation

- `pytest tests/test_league_context_valuation_audit.py` (+ player valuation)
- Full suite / compileall / diff-check / perf budget recorded in PR
