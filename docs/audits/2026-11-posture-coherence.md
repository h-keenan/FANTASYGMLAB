# Posture coherence retune (DYNASTYGM_POSTURE_COHERENCE_V1, default OFF)

Owner-approved 2026-11-19 under the standing rule: three divergences that the shared posture model (#2199) preserved
on purpose are coupled to the shared tables behind one flag.

| # | Change (flag ON) | Source of truth |
|---|---|---|
| 2 | Injury weights are never below the starter weight: rebuild 0.15 -> 0.20, tank 0.05 -> 0.20 | `max(injury base, STARTER_STRENGTH_WEIGHTS)` |
| 3 | Multi-team finder pick want for tank 2.0 -> 2.667 (rebuild stays 2.0) | rebuild want x `PICK_SALE_FIT_TERM[tank] / [rebuild]` (16/12) |
| 5 | Pick-sale priority per pick for fringe 6 -> 4 (contender 6, retool 1) | linear in `ORIENTATION` between retool and contender |

Backtest (scripts/trade_advice_backtest.py -> trade_advice_outcomes.py, 2023 train, 2024-25 test, 14,433 identical
trades, 5 postures x 4 leagues x 5 dates, 300 draws each): zero trades changed score, band or verdict; per-posture AUC
for lineup points and points over replacement identical to four decimals. Reason: the production grade path
(trade lineup model) never reads the injury weights, they only price per-asset injury cost for the consolidation term
and the lineup-model-failed fallback. The harness does not exercise the finder or the pick-sale terms, so divergences
3 and 5 are not measured by it. Fixture Hub/Finder/GM Plan idea counts are identical ON vs OFF (Hub 48 per posture).

Decision: ship OFF. Flipping the default requires re-pointing the flag-OFF goldens in
tests/test_posture_model_golden.py, which is a deliberate owner step.
