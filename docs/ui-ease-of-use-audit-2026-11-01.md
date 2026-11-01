# UI ease-of-use audit, 2026-11-01

Scope: coridian_'s request, "ui organizational audit end to end for user ease of use". Owner uses web at 390px.

## Method and honest limits

- Navigation, labels, tap targets, parity: read from code (`web-next/src/lib/navDestinations.ts`, `GmOrb.tsx` web + mobile, `DesktopSidebar.tsx`, `TradesTabBar.tsx`, `MoreScreen.tsx`, `RootNavigator.tsx`, `SectionHeading` web + mobile, `PublicPricingContent.tsx`).
- Screenshots: production `next build` + `next start`, Chrome for Testing at 390 and 360 wide, plus a DOM scan for `a`/`button` under 40px. Only routes that render without a session or backend could be captured: landing `/`, `/sample-league`, `/premium` (signed out), `/methodology`, `/dynasty-tools`. Every league-scoped, account, billing and community screen redirects to `/` with no Supabase/backend, so those were assessed from code only and are marked "code only". The mobile app was not run on a device or simulator.
- Screenshots (after the PR's fixes; the "before" renders were overwritten, the before state is described in the findings): `/private/tmp/claude-501/ux-landing-390.png`, `ux-landing-360.png`, `ux-sample-390.png`, `ux-sample-360.png`, `ux-premium-390.png`, `ux-methodology-390.png`, `ux-dynasty-tools-390.png`.
- No horizontal overflow (scrollWidth == viewport) at 390 or 360 on any captured page.

## Navigation map

Web phone (MENU opens the GM orb menu, same list as the desktop sidebar):

- Core league: Dashboard, Alerts, My Team, Matchup, Waivers, Players, League Rankings.
- GM Tools: Trade Hub (tabs: Trade Hub / Trade Finder / Trade Analyzer, plus a "Trade History" link), GM Plan (absorbs GM Targets and Team Situation), Draft Center, Live Draft, League Recaps, Games, Commissioner.
- General: Home, Portfolio, News, Trade History, College Scouting, Community. Founder section is founder-only.
- Header: league switcher ("+ Add another league"), valuation-lens chip, alerts bell, account menu (`/account`).

Mobile (GM orb menu, bottom-anchored): same Core and GM Tools lists, plus Playoff Odds (its own row; on web it lives inside League Rankings), Premium / Manage subscription, and More (settings, legal, push categories, theme, density, experience, delete account, College Scouting when opted in).

## Tap-count table (from the dashboard, phone)

| Goal | Web | App | Note |
|---|---|---|---|
| Analyze a trade | 1 (dashboard "Analyze a trade") | 1 | Good |
| Trade Finder / Trade Analyzer via nav | 3 (MENU, Trade Hub, tab) | 3 | Tab is intentional (coridian_, 2026-10-17) |
| Trade History | 3 (MENU, Trade Hub, link) or 2 (MENU, General) | 3 (Trade Hub, header icon) | Web has two paths, app one |
| Waivers / My Team / Matchup / Players | 2 | 2 | Good |
| Player detail | 2-3 (list then row) | 2-3 | Quick View sheet is one more tap, not a replacement |
| Playoff Odds | 3 (League Rankings, scroll) | 2 | Web not in nav, app is |
| Commissioner | 2 | 2 | Shown for every league, not just commissioners on the app |
| League recaps / history | 2 | 2 | |
| News | 2 | 2 | |
| Settings / account | 2 (MENU or header account menu) | 2 (orb, More) | Different words, see F6 |
| Billing / Premium | 3 (account then Premium) or 2 (MENU has none) | 2 (orb Premium) | Web nav has no Premium entry, F5 |
| Connect another league | 2 (switcher, "+ Add another league") | 2 | |

## Ranked findings

Severity: H = blocks or misleads a main flow, M = friction a typical user hits, L = polish. Effort: S under 1h, M half day, L multi-day. "Fixed" means in this PR.

| # | Sev | Where | Finding | Proposed fix | Effort | Status |
|---|---|---|---|---|---|---|
| F1 | M | Web, every `SectionHeading` with an `action` (View all, Open, Full analysis; GM Plan, Dashboard, Today) | Action links were bare `text-xs` text, 15-16px tall, below the 44px target. Baseline alignment also made them sit off-center. Mobile already uses a hit-slop on the equivalent link. | One rule on the shared component: `.section-heading-action` gives direct a/button children the 44px target (reuses the `--touch-target-min` token that `.tap-link` uses). | S | Fixed |
| F2 | M | Web landing footer links (Dynasty tools, rankings, free trade analyzer, value chart), screenshot `ux-landing-390.png` | Four crawlable links were 16px tall on a wrapped row, easy to mis-tap on a phone. | `tap-link` on each, row gap dropped so spacing stays the same. | S | Fixed |
| F3 | M | `/premium` signed out, `ux-premium-390.png` | Monthly and annual cards repeated the identical six-bullet list, so the page was two screens of the same text before the CTA. Prices were pushed far down. | Features listed once under "Included in every plan" when the plans share the list (falls back to per-card lists if they differ). Prices now visible together above the fold. | S | Fixed |
| F4 | L | `/premium` signed out, "Sign in" link | 15px tall, the only route back for an existing user. | `tap-link`. | S | Fixed |
| F5 | M | Web nav and header | No Premium / Manage plan entry in the web menu (the app has Premium or Manage subscription in the orb). Free users on web find upgrades only through upsell cards or the account page. | Add a General destination to `useNavDestinations` ("Premium" for free, "Plan and billing" for subscribers) mirroring the app. Touches the nav list and sidebar tests, held back to avoid colliding with the nav-adjacent open PRs. | M | Proposal |
| F6 | M | Settings naming | App calls it "More" (orb row and header ellipsis) holding settings, legal and support; web calls it Account. Same job, two names and different groupings (push categories, theme, density live only in app More). | Pick one word. Recommend "Settings" on both with "Account" as its first section. Rename app row and web header menu item; align section order. | M | Proposal |
| F7 | L | Dashboard status chips | Odd chip count: lone chip spans full width (intentional per merged #1592). No action. | none | - | Closed |
| F8 | M | Parity: Playoff Odds | App has a dedicated nav row and screen; web buries it in League Rankings with no nav entry. | Add "Playoff Odds" anchor link or tab to League Rankings header; or nav row. | S-M | Proposal |
| F9 | M | Parity: Community feed | Web has `/community` in the nav; app only shows shared trades inside Trade History, no nav row. Same data, different findability. | Add a Community row (or tab inside Trade History) in the app; or remove from web nav if low use. Needs product call. | M | Proposal |
| F10 | M | Web Watchlist & Alerts rows (sample dashboard, 390px): the TRENDING badge overflowed its 4.25rem column and touched the headline. | Column widened to 5.5rem so the longest tag fits; the app stacks label above headline, so no overlap there. Waivers chip full width on odd count is intentional per #1592 (F7 retracted). | S | Fixed |
| F11 | L | Trade Hub | "Trade History" link is tiny text pinned to the end of the tab row; discoverable only after you are in Trade Hub, and also listed under General. Two paths, three labels ("Trade History", "Trade Outcomes" in some copy). | Keep one entry in General; keep Trade Hub link but style as a secondary tab. Audit copy for "Trade Outcomes" vs "Trade History". | S | Proposal |
| F12 | L | Premium copy | `/premium` signed-out intro uses a double hyphen ("--") and a "Premium" kicker above an H1 that already says it. | Em dash, drop kicker. Tiny but visible on a pricing page. Left alone because #1579 is editing billing copy and fallback prices. | S | Proposal, after #1579 |
| F13 | L | Landing (390px) | Hero is long: headline, sample-league CTA, carousel, trial text and sign-in form stack; the email form sits roughly 2.5 screens down. Primary create-account action is below the carousel. | Move the form (or a sticky "Create account" button) above the carousel on phone width. Product decision. | M | Proposal |
| F14 | L | Jargon | Glossary exists and `GlossaryNote` / `BeginnerHelp` cover the dashboard stat tiles ("What do these mean?"). Terms like "Franchise Rank", "Power Rank", "PQV" on Players and Trade Analyzer have no inline explanation. | Wire `InfoTip` to those labels on Players and Trade Analyzer using the existing glossary entries. | M | Proposal |
| F15 | L | Commissioner nav entry | Listed for every league member on the app; web hides it more selectively (DesktopSidebar.commissioner test). Non-commissioners see a page that has no actions for them. | Make app behavior match web: hide, or show a one-line "commissioner only" state. Code-only observation, verify. | S | Proposal |

Checked and fine: 44px token is used in 43 places on web; nav destinations are a single shared list for orb and sidebar; mobile `SectionHeading` links already carry hit-slop; tap-targets in the trade tab bar, verdict trust buttons and header chips all declare a 44px minimum; no overflow at 360/390.

## What this PR fixes

F1, F2, F3, F4, F10 (web only; the app already satisfied F1/F2 equivalents: hit-slop links, no duplicated plan lists, so there is no app change needed. The paywall on the app uses a Free vs Pro comparison rather than repeated lists).

## Not checked

League-scoped screens, account, billing, checkout, alerts, news and onboarding were not rendered (no session or backend in the audit environment). Contrast was not measured with a tool beyond visual inspection of the light-mode captures. The app was not run.
