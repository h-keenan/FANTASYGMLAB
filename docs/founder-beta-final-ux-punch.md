# Founder Beta Final UX Punch List (PR #121)

Presentation-only polish from the founder’s accumulated UX punch list. No football, ranking, valuation, Trust, recommendation ordering, auth, entitlement, Stripe, Sleeper, Supabase schema, caching, API, or business-rule changes.

## Items addressed

| # | Area | Change |
|---|---|---|
| 1 | Executive Header | One cohesive shell + action strip; removed duplicate Premium/unread chips; tightened desktop rail gap |
| 2 | League Switching | Immediate “Switching to…”, then “Loading league…”, then “League ready”; transient Trade Hub/PQV clear retained |
| 3 | Player Quick View | Quieter hero cyan; section rails use border-strong; decision rails keep semantic accents |
| 4 | Trade Hub | Clearer Premium single-approval caption (nothing hidden by entitlement); badges/filters unchanged |
| 5 | Loading | Phase copy “Loading league…”; clearer status typography; phase-locked progress retained |
| 6 | GM Orb | Stronger chrome + “Menu” hint; help text discoverability; nav behavior unchanged |
| 7 | Notification Center | CTA buttons wired to destination open; category coverage retained for future live delivery |
| 8 | Typography | Stronger title/subtitle/metadata contrast via consistency tokens |
| 9 | Founder Beta Identity | Customer strings remain FantasyGM Lab / Founder Beta / Premium / Experimental |
| 10 | Mobile | Touch-target floor on command actions; denser ≤430 strip |

## Remaining open (from durable FQA list)

| ID | Note |
|---|---|
| FQA-001 | League switcher remains a native Streamlit control adjacent to the shell (platform constraint) |
| FQA-002 | Comparative dialog density at 320px in large leagues |
| FQA-004 | Synthetic harness footer noise (fixture-only) |
| FQA-005 | Harness `?surface=` history vs GM Orb |
| FQA-006 | Local AppTest players.db restore hygiene |

## Rollback

Revert the merge commit on `main`.
