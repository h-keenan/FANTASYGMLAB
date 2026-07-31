# Trade Board mobile visual redesign

## Scope

This change restores visual hierarchy to the compact Trade Board summaries
without restoring the former full trade reports. Recommendation generation,
ordering, values, Trust, caching, and the existing lazy detail dialog are not
changed.

## Proven rendering cause

The compact summary is a Streamlit v2 component with isolated styles. The
component previously received semantic HTML but no component stylesheet.
Application-level CSS cannot cross that isolation boundary, so the production
summary rendered as largely unstyled text.

The component now receives one token-backed, locally scoped stylesheet. No raw
design values are duplicated from the application theme.

## Summary hierarchy

Each collapsed recommendation contains:

1. Recommendation title and partner
2. Sending and receiving asset identities with compact imagery or a pick marker
3. Prominent estimated value difference
4. At most three existing recommendation signals
5. A two-line rationale
6. A clear `View trade` affordance

Full football assets, valuation detail, team fit, confidence evidence, rationale,
and actions remain inside the existing detail dialog and are created only after
the selected summary is activated.

## Responsive contract

At widths through 430px the isolated card fills its available width, uses a
250px compact-height floor, stacks header metadata, reduces avatar size, wraps
asset chips, and clamps the rationale to two lines. The entire card retains a
native button role, keyboard activation, and visible token-backed focus state.

The deterministic visual harness is available with:

```text
streamlit run scripts/trade_board_visual_harness.py
```

It contains synthetic data only and is not imported by production.
