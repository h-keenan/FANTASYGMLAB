# Founder Beta Marketing Landing

| Field | Value |
| --- | --- |
| Baseline | `931a7a9` (after PR #173) |
| Module | `modules/marketing_landing.py` |
| Styles | `modules/marketing_landing_styles.py` (landing-only inject) |
| Assets | `assets/marketing/` |

## Hierarchy

1. Hero — FGL Arc Monogram, FantasyGM Lab, Founder Beta, one-line value, CTAs
2. What it does — Game Plan, Trade Hub, Waivers, PQV, Decision Memory, GM Targets
3. Why it's different — league / scoring / recommendation context
4. Founder Beta — included vs experimental
5. Free vs Premium — reuses `#161` `premium_page` rows; billing honesty
6. Trust — concise inspectability framing
7. Next step — auth + Sleeper import (existing launch controls)

## CTAs

| Control | Label | Behavior | Analytics |
| --- | --- | --- | --- |
| Primary | Import your league | Focus get-started / guest import | `primary_cta_clicked` |
| Secondary | See how it works | Expand detail + product screenshot gallery | `secondary_cta_clicked` |
| Pricing | Compare Free & Premium | Expand Free/Premium title lists | `pricing_viewed` (once/session) |

Cold first paint stays compact (hero + what-it-does titles + next step). Detail, pricing lists, and screenshots expand after CTA so protobuf stays under budget.

## Performance

- No league, Trade Hub, or rankings work on the landing path (existing launch early-return)
- Marketing CSS is not appended to global `APP_CSS`
- Public player frame still loads in `main()` before route body (pre-existing)

## Remaining limitations

- Harness viewport captures for Trade/Waivers/PQV can be obscured by Alerts chrome; share-card rasters provide clean product proof
- No separate marketing site / OG meta wiring beyond brand assets
- Support/contact email still an Ops gap outside this PR
