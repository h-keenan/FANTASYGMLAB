# UI Magna Carta — FantasyGM Lab Founder Beta

Durable UI and interaction contract for canonical Founder Beta surfaces.
This is a constitution, not a polish checklist.

Rules use **SHALL** / **SHALL NOT**. Presentation only: valuation, Trade Trust,
rankings, injury math, news→value firewall, Stripe, Supabase, DNS, and Premium
are out of scope.

---

## GEOMETRY

1. Chrome **SHALL** be 90° / squared. Panels, cards, buttons, filters, rails,
   and dialogs use `border-radius: 0` unless a semantic exception applies.
2. Surfaces **SHALL NOT** use consumer pill soup (rounded status capsules,
   pill CTAs, pill filters) on canonical routes.
3. Rounding **SHALL** be reserved for portraits (headshot crop) or a narrowly
   defined semantic exception documented at the call site.
4. Trade Analyzer and Trade Hub shells **SHALL** use canonical panel radius
   (`--radius-panel`, which is 0). Fallback `16px` **SHALL NOT** appear.

---

## COLOR

1. **Cyan SHALL mean focus, selection, or the single primary action.**
2. **Danger SHALL mean injury / risk.**
3. **Opportunity SHALL mean a positive edge.**
4. **Tier color SHALL live on portrait / tier-frame treatment**, not as
   decorative chrome on every row.
5. **Muted SHALL be metadata only.**
6. Cyan **SHALL NOT** decorate every button, rail, badge, or empty state.

---

## TYPOGRAPHY

Canonical levels. One visual treatment per level. **SHALL NOT** invent a
sixth “almost title” size on a canonical surface.

| Level | Role |
|---|---|
| PAGE TITLE | One per route. Owned by the page title owner. |
| SECTION TITLE | Primary banding inside a page. |
| SUBSECTION | Nested grouping. |
| IDENTITY | Player / partner / asset name. |
| PRIMARY VALUE | The number a GM compares first. |
| SECONDARY METRIC | Supporting figures. |
| LABEL | Field names, kicker, filter labels. |
| META | Freshness, source, provenance. |
| EXPLANATION | One-line why / empty-state copy. |

---

## DENSITY

Canonical surfaces **SHALL** be dense, skimmable, graphical, and
decision-first.

They **SHALL NOT** present as:

- giant stacked cards
- raw tables as the default path
- a debug dashboard

---

## INFORMATION OWNERSHIP

**ONE FACT → ONE PRIMARY OWNER.**

Duplicate facts **SHALL** be re-owned, not deleted. Example: current-season
PPG lives in Season Snapshot on the default path; complete tables live under
STATS; Career Timeline **SHALL NOT** replay the same current-season block.

---

## ACTION HIERARCHY

| Role | Meaning | Visual |
|---|---|---|
| PRIMARY | The one job of the surface | One cyan-capable CTA |
| SECONDARY | Adjacent management | Quiet square controls |
| TERTIARY | Share / Feedback / disclosure | Text / rail, no cyan left-rail |
| DISCLOSURE | STATS / CAREER / MODEL nav | Segmented square rail, not a CTA |

A surface **SHALL NOT** show four equal full-width CTAs.

---

## INTERACTION OWNERSHIP

**ONE GESTURE → ONE OWNER.**

| Gesture | Owner |
|---|---|
| Player portrait / name / player asset | Canonical Player Quick View |
| Trade chrome / package / FOR / EDGE / Review | Trade detail |
| Filter / detail-nav / disclosure | That control; no competing card click |
| Route change | Navigation (may scroll to top) |

Nested targets **SHALL** `stopPropagation`. A whole-card click owner
**SHALL NOT** wrap nested player targets without a distinct inner owner.

---

## PAGE TITLE OWNERSHIP

**ONE ROUTE → ONE TITLE OWNER.**

Alerts **SHALL** use the shared section header as the H2. A second masthead
**SHALL NOT** restating the page title.

---

## VIEWPORT

Disclosure, filter, modal, dropdown, and dialog interactions **SHALL**
preserve viewport position unless navigation is intentional.

Route changes **MAY** scroll to top. Back / return **MAY** restore the
previous position.

Surfaces **SHALL NOT** jump to the top or bottom because a button remounted,
a dialog took focus, or `innerHTML` was rewritten.

---

## LOADING / EMPTY / STALE

Canonical copy **SHALL NOT** show:

- `Player: Other`
- unbounded minute ages (`60486m` or any 4+ digit minute string)
- `None`
- `Unknown` as a finished product label
- `[]`
- `stale ·`

Empty states **SHALL** be human sentences owned by the filter / surface.

Freshness **SHALL** be humanized:

| Age | Display |
|---|---|
| < 60m | `28m` |
| 1–23h | `3h` |
| 1–6d | `2d` |
| 7d+ | `Aug 10` |
| Stale | `Last confirmed Aug 10` (or equivalent calendar form) |

---

## LEGACY PROHIBITIONS

Canonical surfaces **SHALL NOT** use:

- the old global gradient CTA on `.stButton button`
- default Streamlit blue primary leakage
- arbitrary 12–16px rounded panels
- a dialog-wide cyan left-rail on every button
- old status-pill soup as the live status language

Dormant archived-route CSS **MAY** remain. Do not rewrite `APP_CSS` wholesale.

---

## PLAYER QUICK VIEW IA

Default path **SHALL** answer, in this order:

1. IDENTITY — who is this?
2. DECISION — what should I do?
3. SEASON SNAPSHOT — what is happening this season? (games, PPG, snap/usage,
   3–5 production stats — not full tables)
4. FANTASYGM READ — why does FantasyGM think this?
5. CAREER + ACCOLADES — résumé + emblem system on the normal path
6. PRIMARY ACTION — Open in Trade Hub
7. DETAIL NAV — square rail `STATS | CAREER | MODEL`

Full-detail data **SHALL NOT** stack under those answers.

| Nav | Owns |
|---|---|
| STATS | Complete season tables |
| CAREER | Timeline (not current-season replay), bio, news |
| MODEL | Market, Opportunity, Age, Scarcity, Confidence, health/role as metric rails |

Accolades **SHALL** remain on the default path. Awards **SHALL NOT** be
duplicated inside Timeline.

The legacy full-width **More details / Hide details** `st.button` **SHALL NOT**
exist.

---

## PQV INTERACTION OWNER

There is **one** Player Quick View owner: session keys
`player_quick_view_player_id` / source / note / status, mounted by
`render_player_quick_view_modal` in the parent script.

Trade detail **SHALL** close or suspend and open that canonical PQV.
PQV **SHALL NOT** nest inside the trade dialog.
Product code **SHALL NOT** call `st.rerun()` from inside `st.dialog` to open PQV.

---

## TAP CONTRACT

Product tap grids **SHALL**:

- use a module-level `on_clicked_change` handler (not a per-call `lambda: None` as the contract)
- prefer event delegation on a stable root
- **SHALL NOT** rewrite `root.innerHTML` during the same gesture if the markup is unchanged

First tap **SHALL** be sufficient. A 2–3 tap lifecycle **SHALL NOT** exist.

Player asset touch targets **SHALL** be at least 44px.

---

## ALERTS ROUTE

The Alerts CORE route **SHALL** populate from existing sources only
(no second backend):

| Filter | Source |
|---|---|
| Important | Notification inbox items that are alert-worthy, plus urgent news events |
| My Players | Roster-related news / ROSTER notifications |
| News | News-intelligence timeline / cached news pool events |
| League | League Recap notice and LEAGUE-category inbox items |
| Decisions | DECISIONS-category inventory and cached Decision Memory events |

The page **SHALL NOT** require a Dashboard visit first when sufficient
cached or current event data already exists locally.

Empty states:

- Important — “You’re caught up.”
- My Players — “No recent player-specific alerts.”
- News — “No recent mapped news.”
- League — “No notable league activity recently.”
- Decisions — “No new recommendation changes.”

Unmapped identity **SHALL** use one of:

- Unmapped player update
- League-wide news
- Player mapping unavailable

**SHALL NOT** manufacture a player name. **SHALL NOT** render `Player: Other`.

At 390px, filters **SHALL** fit one row, use a horizontally scrollable
segmented rail, or a compact square select. They **SHALL NOT** accidental-wrap.

Page chrome **SHALL** be: ACTIVITY / Alerts / one-line note → filters → timeline.

---

## TRADE VISUAL LANGUAGE

Trade Trust and math **SHALL NOT** change.

The exchange **SHALL** read as YOU SEND / FOR / YOU RECEIVE with distinct
treatments for player assets, pick assets, values, edge, and confidence.

Player portrait + name **SHALL** afford PQV. Remaining package chrome **SHALL**
afford trade detail.

---

## CANONICAL COMPONENT OWNERS

Do not create a duplicate without a documented reason.

| Role | Owner |
|---|---|
| PLAYER IDENTITY ROW | `modules/player_cards.py` / PQV hero |
| PORTRAIT | `modules/player_profile_ui.py` avatar + tier frame |
| TIER FRAME | `modules/player_tier_identity.py` |
| METRIC TILE | PQV glance / model rails |
| SECTION HEADER | shared `render_section_header` / `dossier_section_heading_html` |
| ANALYSIS RAIL | `pqv-why-factor` / `pqv-model-cell` |
| TRANSACTION ASSET | `modules/compact_fantasy_assets.py` |
| TRADE SIDE | `modules/trade_visual_language.py` + Trade Hub |
| STATUS | square `dg-status-badge` / prestige frame — not pill soup |
| SEGMENTED NAV | square button-group / detail-nav rail |
| PRIMARY BUTTON | `type="primary"` + CTA family |
| SECONDARY BUTTON | quiet square |
| TERTIARY ACTION | text / underline rail |
| MODAL | Streamlit dialog + one PQV owner |
| EMPTY STATE | surface-owned sentence |

---

## PERFORMANCE BOUNDARY

- Explicit `st.rerun()` count **SHALL** stay at or below the Founder Beta
  budget (≤ 58).
- `APP_CSS` **SHALL** remain under 390k.
- No per-player portrait hacks. Portrait geometry is family-owned.
