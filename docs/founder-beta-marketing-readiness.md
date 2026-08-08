# Founder Beta Marketing Readiness (Gap Identification)

Identify-only checklist. No marketing assets were implemented in the Ops Activation PR.

| Asset / item | Repo / production status | Gap? |
| --- | --- | --- |
| Website / landing | In-app Founder Beta landing via `modules/marketing_landing.py` | Ok for beta — still no separate marketing site |
| Product screenshots | Curated set under `assets/marketing/` | Ok for beta — expand pack for external campaigns |
| App icon | Tab favicon present (Streamlit/FGL) | Partial — confirm branded store/home-screen icon pack |
| Favicon | `favicon.png` 200; `favicon.ico` returns HTML shell | Yes — ship a real `.ico` if browsers matter |
| Open Graph image | No `og:image` meta on Streamlit shell HTML | Yes |
| Social previews | No Twitter/Facebook meta cards observed | Yes |
| Founder Beta announcement | Not in repo | Yes — draft copy outside product |
| Landing page FAQ | No dedicated FAQ destination observed | Yes |
| Privacy | In-app Privacy page present | Ok for beta; add support contact |
| Terms | In-app Terms page present | Ok for beta |
| Support email | Not shown on Privacy; `docs/SUPABASE_SETUP.md` still cites `support@example.com` | Yes — publish real address |
| Contact email | Same gap | Yes |
| Founder Beta onboarding | In-app 3-step onboarding present | Ok — optional email onboarding sequence still external |

## Recommendation

Marketing gaps are **not** launch blockers for Test Mode Founder Beta intake, except publishing a
real support/contact email before charging money. Open Graph / social / screenshot packaging can
follow immediately after Ops P0.
