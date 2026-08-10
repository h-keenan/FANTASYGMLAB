# Experimental Feature Reincorporation + Graduation (#232)

Baseline: main after #231 (`002e4db8fb80311c4eb2e03741763ba9330c3b3b`).

## Philosophy

Graduate only what earns permanent surface area. Prefer embedding into existing
CORE surfaces over expanding navigation. Finish high-upside experiments before
launch when they clear the product bar.

Registry source of truth: `modules/experimental_graduation.py`.

## Final decision matrix

| Feature | Before (#226) | Final | Surface | Free / Premium | Launch default |
| --- | --- | --- | --- | --- | --- |
| Decision Memory | KEEP EXPERIMENTAL (off) | FINISH → GRADUATED | Dashboard What Changed + Premium history | Free session; Premium durable | ON (`=0` kills) |
| GM Targets | KEEP EXPERIMENTAL (off) | FINISH → GRADUATED | CONDITIONAL route + PQV Add/Remove | Free ≤3; Premium ≤50 | ON (`=0` kills) |
| Share Recommendation | KEEP EXPERIMENTAL (off) | FINISH → GRADUATED Free | Trade Hub / Waivers / PQV | Free | ON (`=0` kills) |
| Player Explorer | KEEP EXPERIMENTAL | GRADUATE NOW | Players CORE | Free | visible CORE |
| Trade Analyzer | KEEP EXPERIMENTAL | DEFER/HIDE | ARCHIVED | — | hidden |
| Weekly Report | KEEP EXPERIMENTAL | DEFER/HIDE | ARCHIVED | — | hidden |
| Teams route | KEEP EXPERIMENTAL | MERGE | League Overview owns Teams | Free | nav archived |
| Manager Tendencies | KEEP EXPERIMENTAL | MERGE | Trade Hub + League Overview | Free | nav archived |
| ESPN | KEEP EXPERIMENTAL | KEEP EXPERIMENTAL | Import (limited) | Free limited | limited |
| Live Draft | GRADUATED (#226) | ALREADY GRADUATED | CONDITIONAL | Free (Sleeper) | active draft only |

## Kill switches (graduated defaults ON)

| Flag | Default | Disable |
| --- | --- | --- |
| `DYNASTYGM_EXPERIMENTAL_DECISION_MEMORY` | ON | `0` / `false` / `off` |
| `DYNASTYGM_EXPERIMENTAL_GM_TARGETS` | ON | `0` / `false` / `off` |
| `DYNASTYGM_EXPERIMENTAL_SHARE_CARDS` | ON | `0` / `false` / `off` |
| `DYNASTYGM_SHOW_EXPERIMENTAL` | OFF | remains off on managed hosts |

## Ops requirements

1. Apply `docs/supabase_decision_memory.sql` for Premium durable Memory.
2. Apply `docs/supabase_gm_targets.sql` for Free/Premium Targets persistence.
3. Missing tables: fail soft — core app remains usable.

## Performance

- Player Explorer CSS lazy-injected on `players` route only (removed from cold `APP_CSS`).
- Graduated features remain off cold Dashboard provider path when unused.
- Process-cache single-flight (#231) unchanged.
- Game Plan fingerprints must not include preference/share state.

## Rollback boundary

Revert this PR / reset main to `002e4db8fb80311c4eb2e03741763ba9330c3b3b` and set graduated kill switches to `0` if Ops needs an emergency off.
