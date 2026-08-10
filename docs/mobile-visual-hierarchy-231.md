# Mobile Visual Hierarchy + Perceived-Load QA (#231)

| Field | Value |
| --- | --- |
| Baseline | `89c80f3be6c588cdb9326c9d09a4f13023d6f4bc` (#230) |
| Scope | Visual polish + GM orb O/PE repair + bounded perceived-load harness |
| Not in scope | Brand redesign, football methodology, #230 instrumentation rewrite |

## Visual

- Quieter mobile header (no heavy identity card chrome)
- Utility rail separators lightened (nav, not spreadsheet cells)
- Surface levels L0/L1/L2 via existing tokens
- Game Plan Top Priority = L2 + accent rail; supporting denser
- CTA tiers: primary / secondary / tertiary (44px floor)
- Deep Analysis = compact 2-col tertiary nav (no giant primary stack)
- Expander canonical quiet closed / connected open
- Completed Draft: denser round labels; remaining pool single disclosure (no nested table expander)
- GM orb: removed legacy `height:0` / `width:auto`; hardened 44px + `text-indent` clip so **"Open GM menu" cannot paint as O/PE**

## Perceived load

```bash
python scripts/test_perceived_load.py --concurrency 1,3,5,10 --synthetic
```

Production probes require `DYNASTYGM_ALLOW_PRODUCTION_LOAD=1` and clamp to ≤2 sessions.

Throttle presets (`FAST` / `MID` / `SLOW`) are Chromium-style configured values — not claimed exact 4G/5G.

Process-cache same-signature builds use per-key single-flight (league / trade / prepared frame).

## Manual iPhone checklist

1. Header: title > league > League/Alerts/You
2. No bottom-left O/PE fragment
3. Circular GM orb with mark
4. Game Plan owns first useful viewport
5. Deep Analysis actions dense
6. Completed Draft rounds scannable
7. No horizontal overflow at 390
8. Alerts overlay scrolls cleanly

## Screenshot limitation

Streamlit iframe browser automation remains unreliable locally; deterministic CSS/AppTest contracts cover hierarchy. Founder iPhone Safari smoke still recommended.
