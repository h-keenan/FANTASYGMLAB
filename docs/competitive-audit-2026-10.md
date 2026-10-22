# Competitive feature audit: October 2026

Checked 2026-10-21. Our side of this audit is taken from the code on `main`
at `9fa453bd`, not from docs or marketing copy. The competitor side comes
from each competitor's own site, pricing page and app store listings, read
on 2026-10-21. Anything that couldn't be confirmed is marked
**UNCONFIRMED**.

**Research limits.** reddit.com was blocked to every research tool used (both
search and direct fetch), so this audit has **no r/DynastyFF sentiment**.
User sentiment comes from Apple App Store and Google Play reviews and from
third-party write-ups. dynastyleaguefootball.com returned HTTP 403
(Cloudflare), so the DLF facts come from search snippets of DLF's own pages
and from DLF's beehiiv newsletter. Several competitor sites are JavaScript
single-page apps. Their features were read from nav labels and route names
in the shipped bundles, not by using the tools.

---

## 1. Our feature inventory (from code)

### 1.1 Platforms and tiers

| Item | What the code says |
|---|---|
| Surfaces | `web-next/` (Next.js, 31 routes), `mobile/` (Expo, 36 screens), FastAPI `services/mobile_api_service.py` (about 99 routes plus `/v1/external/*`). The legacy Streamlit app (`app.py`) is still deployed as `fantasygm-lab` in `render.yaml`. web-next deep-links into it for some pages (`web-next/src/lib/streamlitLink.ts`). |
| Store status | Android is live on Google Play. iOS is still in App Store review with no public listing (`web-next/src/lib/appStoreLinks.ts`, 2026-10-21). |
| League sync | **Sleeper only** in web-next and mobile. The landing page says "ESPN support is on the way." ESPN import exists **only in the legacy Streamlit app**. It was validated against a live public ESPN league in #1306 with an 89% player match rate, and D/ST is not modelled. It is labelled "limited parity" (`modules/experimental_graduation.py`). No FastAPI route exists for it. Yahoo (`modules/platforms/yahoo.py`) is spike scaffolding that has never been run against the live API. |
| Tiers | `modules/premium.py` defines FREE < PRO < FRONT_OFFICE. **Front Office is no longer sold** (`_BILLING_PLAN_KEYS`, 2026-10-19). Its one real gate, unlimited saved leagues, now also applies to Pro. Front Office's "cross-league player ownership view" flag (`has_cross_league_exposure`) is defined but **not called by any feature**. |
| Pricing | Pro is $3.99/month or $19.99/year, with a 7-day Stripe trial (`modules/stripe_billing.py` `DEFAULT_PLAN_DETAILS`, `PRO_TRIAL_DAYS`). These are fallback constants: the live Stripe Price and the RevenueCat in-app purchase prices weren't checked. |
| Free caps | 1 saved league (`MAX_LEAGUES_FREE = 1`), 4 Dashboard Next Moves, 2 Trade Hub ideas, 3 GM Targets (Pro: 50). |
| Ads | Rewarded ads that unlock +2 Trade Hub ideas (up to 3 per day) are wired up but **disabled**. `adsAvailable = false` in `mobile/src/lib/ads.ts` because of an AdMob/Kotlin build conflict. |
| AI | **No LLM anywhere.** No Anthropic or OpenAI calls in `modules/`, `services/`, `web-next/` or `mobile/`. Every explanation is rule-based text generated from the engine's own signals. |

### 1.2 Features

Tier codes: **F** = free, **F/P** = free with a cap or with deeper content
for Pro, **P** = Pro only. Platform codes: **W** = web-next, **M** = mobile.

| Feature | What it does | Tier | Platforms | Notes |
|---|---|---|---|---|
| Dashboard / "Next Move" briefing | Ranked actions for your team (trade, waiver, health, roster) with a game-plan card and team snapshot | F/P (4 items free) | W, M | |
| League Pulse | Real manager activity and streak tiles from completed trades and waiver moves (#1296) | F | W, M (lighter version) | Paywall copy lists "Full League Pulse" as Pro, but the new web card isn't gated. Copy and gate may disagree. |
| Trade Analyzer | Accept/decline/counter verdict on a proposed trade, players plus picks, league-format adjusted. Counter suggestions can include picks (#1314). | F | W, M | |
| Trade Hub | Generated trade ideas for your roster with partner, fit, realism, confidence and Buy Low / Sell High / High Impact tags. Sell High now also fires on a confirmed declining role (#1308). | F/P (2 ideas free) | W, M | Branded share-card PNG export (free) |
| All Trades | Trade ideas for every roster in the league, paginated | F/P | W, M | |
| Trade Finder | "Find me a deal for X." You can now offer your own picks and filter for "picks back" (#1321). | P | W, M | |
| Trade History / Outcomes | Asks "did this trade happen?" about trades you shared, then grades how they worked out | F | W, M | |
| Community Trade Feed | Anonymized real trades from all users' leagues, graded, with emoji reactions | F | **W only** | Opt-out toggle |
| Players explorer | League-adjusted values/OVR, filters, and a Madden-style stat/percentile sort with Raw/Percentile toggle and "Add to Trade" (#1307) | F | W (sort), M (list only) | **Stat sort is web only** |
| Player profile / Quick View | Stats, Trends, Schedule (with Vegas lines), Career, Model, Awards, Bio, news, contract timeline (nflverse, #1318), declining-role trend colors (#1308) | F | W, M | |
| Player Compare | Side-by-side players | F | W, M | |
| My Team | Starters vs bench (suggested lineup), position groups, Strength & Pressure, biggest need | F | W, M | |
| Team Stance / GM Plan | Saved team strategy, plus a season-arc roadmap (Where You Stand / Trade Opportunities / Roster Construction) | Stance F, Plan P | W, M | |
| Matchup | This week's real lineups, a suggested best lineup and a win-probability verdict | F | W, M | The closest thing we have to start/sit |
| Waivers | Free agents ranked against your roster needs, with FAAB guidance. Pro adds stashes, watchlist depth and a FAAB shortlist. | F/P | W, M | |
| GM Targets | Watchlist with untouchable flag | F (3) / P (50) | W, M | |
| League Rankings | Standings, five power boards (Roster Power, Franchise Value, Draft Capital, Starter Quality, Bench Depth) | F | W, M | |
| Playoff Odds | Monte Carlo simulation over the real remaining Sleeper schedule, using Roster Power (`modules/playoff_simulator.py`) | F | W (inside League Rankings), M (own screen) | |
| Draft Center | Draft posture, pick values (My Picks / League), partner cards | F | W, M | |
| Live Draft | Read-only Sleeper draft-room assistant with an in-draft trade evaluator | P | **W only** | Tagged **"Coming soon"**. The recommendation engine hasn't been verified against a live draft (`docs/roadmap.md`). |
| College Scouting | Crowdsourced prospect grades, round projections and a watchlist | F | W, M | **No licensed data feed.** The catalog is a hand-filled Supabase table and is empty until someone populates it (`modules/college_scouting.py`). |
| League Recaps / History | Weekly recap stories, a season transaction timeline with retrospective grades | F | W, M | |
| Storylines | League storylines | F | API | |
| Alerts | News alerts that touch your roster, with read state | F | W, M | |
| Push notifications | Top-priority and watch Next Moves pushed by a cron sweep, with per-category toggles | F | **M only** | No in-app web notifications (`docs/roadmap.md`) |
| News | Curated NFL feed (injury/role/transaction/off-field) from 6 RSS sources plus Google News | F | W, M | |
| Portfolio | Record, rank, top need and opportunity for every saved league; progressive load (#1324) | P | W, M | **Team-level, not player exposure.** There is no "how many shares of player X" view. |
| Leagues Glance | Compact card per league | P | API, M | |
| Guess the Player | Daily "whose stats are these?" game with streaks, a name-match variant and a league leaderboard | F | W (card), M (popup) | |
| Beginner/Advanced copy | The onboarding experience answer drives plain-language helper text on Dashboard, Trade Analyzer, Trade Hub, Waivers and value labels (#1322) | F | W, M | |
| Methodology ("How we evaluate") | Public explanation of the model | F | W, M | |
| Referrals | Referral code with comped access | F | W, M | |
| External content API | Bearer-key `/v1/external/*`: projections, news evidence, rating history, background profile, week result, weekly recap (#1323) | Internal (bot) | API | For the content bot, not users |

### 1.3 How values are built

`modules/rankings.py` blends a **single cached FantasyCalc dynasty fetch**
(`get_dynasty_values()` with its defaults: 12 teams, 1QB, PPR; 6-hour cache)
with our own model and Sleeper's `search_rank`. On top of that blend we apply
league-format multipliers for Superflex/2QB, TE premium and PPR/half/standard
scoring, all detected from Sleeper settings. Only QB, RB, WR and TE are
valued. There is **no IDP, K or D/ST**.

This has two consequences:

- **Market input depends on another company.** Our market signal comes from
  FantasyCalc's free API, whose terms (read from its bundle) say it is free
  under 1,000 monthly active users with attribution required. If we grow
  past that, this becomes a licensing question.
- **The market input is fetched for 1QB only.** Our multipliers then
  approximate Superflex value from the 1QB market.

---

## 2. Competitors (checked 2026-10-21)

### KeepTradeCut. https://keeptradecut.com
- **Features:**
  - Trade calculator with three value sources: Crowdsourced, Tradesourced, or a blend. It supports Superflex, TE+/++/+++, startup mode and variance settings.
  - Dynasty, rookie, redraft and **devy** rankings.
  - League power rankings with head-to-head comparison and a top free agents list.
  - Trade, waiver and draft databases.
  - A weekly Start/Sit tool.
  - No standalone trade finder. Power Rankings claims to "find compatible trade ideas."
- **Values:** Daily crowd Keep/Trade/Cut votes run through an Elo model, plus real trades. Values are fixed at 12-team, 0.5 PPR.
- **Sync:** Enter a league ID for Sleeper, MFL, FFPC, Fleaflicker or Fantrax. No ESPN or Yahoo.
- **Price:** Free and ad-supported, with donations (https://keeptradecut.com/donate).
- **Mobile:** Web only. No App Store or Play listing found.
- **Sentiment:** Praised for real-time values and startup mode. Criticised for crowd "groupthink" and fixed scoring (https://apexfantasyleagues.com/dynasty-trade-calculators/, https://officepoolstop.com/blog/the-importance-of-trade-calculators-in-dynasty-and-where-they-let-you-down).

### FantasyCalc. https://fantasycalc.com
- **Features:**
  - Trade calculator with values from real trades (2M+ trade database).
  - Trade value chart; trade targets based on redraft-vs-dynasty value gaps.
  - Dynasty, redraft and rookie rankings; waiver rankings; weekly projections; start/sit.
  - Draft app; playoff odds simulator, including post-trade odds.
  - League analyzer.
  - **Player Portfolio**: shares of each player across all your leagues and platforms.
  - An "AI Trade Analyzer." Its output wasn't tested.
  - Public API.
- **Sync:** Sleeper, ESPN, MFL, Fleaflicker, FFPC (FAQ).
- **Price:** Free, with donations.
- **Mobile:** Web only.
- **Sentiment:** Praised because values come from real trades and the tools are free. Criticised for limited league-size and format options (apexfantasyleagues, above).
- **Note:** This is **our own upstream value source** (see 1.3).

### DynastyProcess. https://dynastyprocess.com
- **Features:**
  - Trade calculator (Shiny app) with values derived from FantasyPros ECR via a published formula (https://dynastyprocess.com/values).
  - Crystal Ball season-finish forecast.
  - Open data and R packages (ffscrapr).
- The data repo was still updating daily as of 2026-10-21, but the site and blog content stop around 2020 to 2022.
- **Sync:** None in the calculator. ffscrapr covers MFL, Sleeper, Fleaflicker, ESPN and Yahoo, but it is a tool for developers.
- **Price:** Free and open source. **Mobile:** Web only.
- **Sentiment:** No current reviews found. Today it mainly serves as a data source for other tools, for example as a value market inside Dynasty Daddy.

### Dynasty Nerds. https://dynastynerds.com
- **Features:**
  - Trade calculator, League Analyzer, lineup optimizer and start/sit.
  - AI mock drafts and a draft assistant.
  - **Team Portfolio**.
  - Data Hub: shares, free agents, trade browser.
  - Film-based prospect grades and the Rookie Guide.
  - Podcasts, a premium Discord, and paid 1:1 expert calls.
- **Sync:** Their own pages disagree. Sleeper, MFL, Fleaflicker and FFPC appear consistently. ESPN and Yahoo are **UNCONFIRMED**.
- **Price:**
  - Free: 1 synced league, 3 preview trades per day.
  - Premium: $7.99/month or $79.99/year (https://dynastynerds.com/plans-and-pricing/). The App Store in-app purchase is $8.99 / $89.99.
- **Mobile:** Native.
  - iOS: 4.5 stars, 368 ratings (https://apps.apple.com/us/app/dynasty-nerds/id1570526998).
  - Android: 3.27 stars, 131 ratings.
- **Sentiment (App Store):**
  - 2024–25 praise: "links and connects all my leagues."
  - 2026 reviews are heavily negative:
    - "AI slop… so much shoved on the screen" (2026-09-09).
    - Stuck loading before lineup lock (2026-09-26).
    - Can't cancel and support doesn't respond (2026-09-20).
    - "Sync with sleeper is weeks behind" (2026-01-07).
    - Having to pay just to sync one league (2026-05-07).
- **Name collision:** Dynasty Nerds sold a plan called **"DynastyGM"**, now a legacy plan (https://support.dynastynerds.com/article/82-what-is-the-dynasty-nerds-app-dynastygm). This repo's internal name is DynastyGM. Our public brand is FantasyDesk, so this is only a risk if "DynastyGM" ever shows up publicly.

### Dynasty Daddy. https://dynasty-daddy.com
- **Features:**
  - Trade calculator where you choose among 11 value markets (KTC, FantasyCalc, DynastyProcess, FantasyPros and others).
  - **Trade Finder**, plus **Bulk Trades**, which sends offers into Sleeper.
  - Trade database and trade tree.
  - Power rankings; playoff calculator (10,000 simulations).
  - **Fantasy Portfolio** (player exposure).
  - Waiver rankings, FAAB estimator, start/sit including bulk start/sit across leagues.
  - Mock draft simulator, ADP.
  - "Fantasy Wrapped" season recap; daily trivia games; a Discord.
- **Sync:** Sleeper, MFL, Fleaflicker, ESPN, FFPC, Yahoo (OAuth), Fantrax.
- **Price:** Free core. The paid "Dynasty Daddy Club" is on Patreon; its price is **UNCONFIRMED**.
- **Mobile:** Web only. Capacitor hooks are in the code, but no store listing was found.
- **Sentiment:** Their public feature board (https://dynastydaddy.featurebase.app) shows the top open request is **IDP support (35 votes)**.

### FantasyPros. https://www.fantasypros.com/premium/plans/
- **Features:**
  - Dynasty Trade Analyzer and Trade Finder.
  - Rookie Draft Simulator and Draft Assistant.
  - Monthly dynasty trade value chart; dynasty expert consensus rankings.
  - My Playbook / League Hub: start/sit, waiver and trade assistants, power rankings, playoff odds, matchups, news and alerts.
  - **Coach AI**, a chat assistant that knows your league. It needs the HOF tier, and no dynasty mention was found.
- **Sync:** The widest of any competitor: Sleeper, ESPN, Yahoo, CBS, MFL, Fleaflicker, FFPC, Fantrax, NFL.com, RT Sports and others.
- **Price per month:**
  - PRO: $3.99 annual / $11.99 monthly.
  - MVP: $5.99 / $16.99.
  - HOF: $8.99 / $22.99.
  - Dynasty and keeper support **needs MVP or higher** and is **web only**.
- **Mobile:** Native.
  - iOS: 4.8 stars, about 90K ratings (https://apps.apple.com/us/app/id1141119371).
  - Android: 4.5 stars, 500K+ downloads.
- **Sentiment:** 2026 Play reviews call the merged app "a huge step back," with sync and login problems.

### Dynasty League Football (DLF). https://dynastyleaguefootball.com (403 to fetch)
- **Features** (from snippets):
  - Trade analyzer on proprietary values that adjust for league settings.
  - League analyzer, free agent finder, trade finder.
  - Rankings, tiers and ADP.
  - Rookie and startup draft guides (https://dlf.beehiiv.com/p/the-2026-dlf-rookie-draft-guide-is-now-available).
  - Devy articles; a dedicated devy tool is **UNCONFIRMED**.
  - Podcasts.
- **Sync:** Sleeper, MFL, FFPC, ESPN, Fleaflicker, RTSports, CBS (snippet).
- **Price:** About $59.99/year, frequently discounted or free with sportsbook promos (https://dynastyleaguefootball.com/2026/07/21/get-a-free-year-of-dlf-premium-with-rebet/).
- **Mobile:** No app found (**UNCONFIRMED**).
- **Sentiment:** One roundup lists slow search and "doesn't provide definitive advice" (https://www.fantasypros.com/2026/07/best-dynasty-fantasy-football-trade-tools/).

### PFF fantasy. https://www.pff.com/subscribe
- **Features:**
  - Weekly dynasty rankings, plus Superflex, TE-premium and IDP dynasty lists (https://www.pff.com/news/fantasy-football-dynasty-rankings).
  - Redraft tools: live draft assistant, mock sim, start/sit, waivers.
  - PFF states its draft tools **don't support dynasty** (https://fantasy.pff.com). No trade analyzer was found.
- **Sync:** Sleeper, Yahoo, ESPN (via an extension).
- **Price:** PFF+ $9.99/month or $99.99/year; Pro $199.99/year.
- **Mobile:** Native.
  - iOS: 4.3 stars, 415 ratings (https://apps.apple.com/US/app/id1582525285).
  - Android: 3.9 stars.
- **Sentiment:** Praised for data. Users want "trade analytics, waiver and free agent tools." 2026 Play reviews report slowness and sign-outs.

### Sleeper (built-in). https://sleeper.com/fantasy-football
- **Features:**
  - Hosts dynasty leagues: taxi squads, future-pick trading, multi-team trades, FAAB.
  - Trade Center: trade block, trade-interest hearts, exploding offers.
  - Mock drafts; league chat and polls; roster and start percentages.
- **Not found** (**UNCONFIRMED absences**): built-in power rankings, playoff odds, trade suggestions or player values. These appear only as user requests in Sleeper's feedback thread.
- **Price:** Fantasy is free with no ads. Revenue comes from Picks and Markets.
- **Mobile:** iOS 4.7 stars from about 295K ratings (https://apps.apple.com/us/app/sleeper-fantasy-football/id987367543).
- **Sentiment:** Chat is loved. 2026 complaints are crashes, too many notifications, and betting being pushed ahead of leagues.
- **Position:** This is the platform we sit on, and it doesn't do analysis.

### Others that matter
- **Fantasy Life** (https://www.fantasylife.com/pricing):
  - $39.99 or $99.99 per year.
  - Rate My Trade uses rest-of-season projections with no dynasty or pick inputs; there are dynasty rankings and Fantasy HQ multi-league sync.
  - Its tools are effectively web only (**UNCONFIRMED**).
  - Not a serious dynasty trade competitor.
- **Dynasty Dealer** (https://apps.apple.com/us/app/id6752508038):
  - iOS only. $5.99/month or $49.99/year.
  - Trade calculator, Fair Trade Finder, Roster Recon, **Portfolio View**.
  - Tiny: 7 ratings. Sync platforms **UNCONFIRMED**.
- **Dynasty Scout** (https://apps.apple.com/app/id6503407267):
  - iOS. $6.99/month or $49.99/year; 4.9 stars from 59 ratings.
  - Sleeper and MFL; team analyzer, trade suggestions, "AI Report Cards," season simulator, college prospects.
  - **Feature for feature, the closest native dynasty-app competitor found.**
- **League Tycoon** (https://leaguetycoon.com):
  - A dynasty-first *host* with slow auctions, contracts and anti-tank lottery.
  - Imports from Sleeper, ESPN, CBS, MFL and Fantrax.
  - Native apps rated 4.8 (iOS) and 4.7 (Android).
  - Matters to our "host leagues" roadmap idea, not to analysis.
- **Dynasty Trade Lab** (https://dynastytradelab.com): LLM-generated dynasty trade suggestions on FantasyCalc values, Sleeper and Fantrax, credits model. New.
- **Roster Audit** (https://rosteraudit.com/trade-calculator/): values from daily Sleeper trades; grades a **screenshot of a Sleeper offer**; Discord bot.
- **League Rewind** (https://apps.apple.com/app/id6499177011): AI weekly league recaps in several tones. $24.99 per season.
- **Dynasty Owner:** Last updated Dec 2023. Likely inactive (**UNCONFIRMED**).

---

## 3. Comparison

### 3.1 Feature matrix

✅ = has it, ◐ = partial or limited, ❌ = not found, ? = unconfirmed.
Us = web-next plus mobile (the legacy Streamlit app is ignored except where
noted).

| Area | Us | KTC | FCalc | DProc | DNerds | DDaddy | FPros | DLF | PFF | Sleeper | DDealer | Scout |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Trade calculator | ✅ verdict plus counter | ✅ | ✅ | ✅ | ✅ | ✅ multi-market | ✅ (MVP+) | ✅ | ❌ | ❌ | ✅ | ✅ |
| Trade finder / suggestions | ✅ Hub + Finder (picks), league-wide | ◐ | ◐ targets | ❌ | ✅ | ✅ + bulk send | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ |
| Rankings / values | ✅ league-adjusted (FC-blended) | ✅ own crowd | ✅ own trades | ✅ ECR | ✅ experts | ✅ aggregator | ✅ ECR | ✅ experts | ✅ experts | ❌ | ✅ | ✅ |
| Waivers / FAAB | ✅ need-aware + FAAB | ◐ list | ✅ | ❌ | ◐ | ✅ FAAB est. | ✅ | ✅ | ✅ (redraft) | ✅ host | ❌ | ? |
| Start/sit | ◐ suggested lineup / matchup | ✅ | ✅ | ❌ | ✅ | ✅ bulk | ✅ | ? | ✅ (redraft) | ❌ | ❌ | ? |
| Rookie draft tools / mock | ◐ pick values; live draft "coming soon"; no mock | ✅ rookie ranks | ✅ ADP / draft app | ◐ | ✅ AI mocks + guide | ✅ mock sim | ✅ sim + assistant | ✅ guide | ❌ dynasty | ✅ mock host | ◐ | ✅ rookie board |
| Devy / college | ◐ crowd grades, no data feed | ✅ | ❌ | ❌ | ◐ film / content | ❌ | ❌ | ◐ content | ❌ | ❌ | ❌ | ✅ |
| League power rankings | ✅ 5 boards | ✅ | ✅ | ❌ | ✅ | ✅ | ✅ | ◐ analyzer | ❌ | ❌ | ◐ | ✅ |
| Playoff odds | ✅ Monte Carlo on real schedule | ❌ | ✅ + post-trade | ◐ | ◐ brackets | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ✅ |
| News / alerts | ✅ roster alerts + push (mobile) | ◐ injuries | ❌ | ❌ | ◐ | ◐ | ✅ | ◐ | ✅ | ✅ | ❌ | ? |
| Content / community | ◐ anonymized trade feed, Guess the Player, recaps; no experts / podcasts | ◐ socials | ◐ blog | ❌ | ✅ pods / Discord | ✅ trivia / Discord | ✅ | ✅ pods | ✅ | ✅ chat | ❌ | ❌ |
| Multi-league portfolio | ◐ team-level only | ❌ | ✅ player exposure | ❌ | ✅ | ✅ exposure | ◐ hub | ❌ | ❌ | ❌ | ✅ | ? |
| Platform sync | ❌ **Sleeper only** | 5 | 5 | ◐ | 4+ | 7 | 15+ | 7 | 3 | host | ? | 2 |
| Mobile app | ◐ Android live, iOS in review | ❌ | ❌ | ❌ | ✅ | ❌ | ✅ (dynasty web only) | ❌? | ✅ | ✅ | ✅ iOS | ✅ iOS |
| AI / explanations | ◐ rule-based "why" on every rec, beginner mode; no LLM / chat | ❌ | ◐ AI analyzer | ❌ | ◐ AI mocks | ❌ | ✅ Coach AI (HOF) | ❌ | ◐ draft AI | ❌ | ❌ | ◐ AI report cards |
| Price (paid) | $3.99/mo, $19.99/yr | free | free | free | $7.99 / $79.99 | Patreon ? | $5.99–16.99/mo for dynasty | ~$59.99/yr | $99.99/yr | free | $5.99 / $49.99 | $6.99 / $49.99 |

### 3.2 Where we're clearly better
1. **An opinionated, decision-first workflow.** The Dashboard's "Next
   Move" briefing, GM Plan season arc, Team Stance and trade-outcome
   follow-up go further than the others. Every other tool is a set of
   calculators and lists. None of them we found tells you *what to do next*
   for your team and then checks whether you did it and how it turned out.
2. **Trade ideas built around your roster and league.** Trade Hub, All
   Trades and Trade Finder (now with picks) score fit, realism and
   confidence against real partner rosters, and they're free with a cap
   while the paid tier is cheap. FantasyPros gates dynasty behind MVP at
   $5.99–16.99/month, and Dynasty Nerds is $7.99/month.
3. **Honest data and explanations.** "No fabricated data" rules run
   through the code: the empty college catalog, no-silent-fallback ranks,
   and the declining-role gating that needs 3+ games and dampens injury
   dips. Every recommendation carries a "why," and there's a beginner
   mode. Dynasty Nerds' 2026 reviews ("AI slop," wrong values, players on
   wrong teams) are exactly the trust failure we avoid.
4. **Price.** $19.99/year is the cheapest paid dynasty product in this set,
   and it comes with a 7-day trial.
5. **A native mobile app with dynasty depth.** Of the dynasty-specialist
   tools, only Dynasty Nerds (3.27 stars on Android), Dynasty Dealer and
   Dynasty Scout (both tiny, iOS only) ship native apps. KTC, FantasyCalc,
   Dynasty Daddy and DLF are web only, and FantasyPros marks dynasty support
   as web only. Ours has push alerts, playoff odds and nearly full parity
   with web.

### 3.3 Parity
- Trade calculator, league power rankings, playoff odds, waivers/FAAB,
  player profiles with stats, schedule and career, player compare, news
  feed. All are solid but table stakes against FantasyCalc and Dynasty
  Daddy, which give these away for free.

### 3.4 Where we're behind
- **Platform sync.** We're Sleeper only, while competitors connect 4 to 15+
  platforms. ESPN works only in the legacy Streamlit app.
- **Multi-league portfolio.** Ours is team-level. FantasyCalc, Dynasty
  Daddy, Dynasty Nerds and Dynasty Dealer show *player exposure* across
  leagues, which is what "portfolio" means to dynasty players.
- **Rookie draft season.** No mock draft simulator, no rookie-only
  rankings view, and Live Draft is unverified and web only.
- **Start/sit.** We have a suggested lineup but no dedicated start/sit
  comparison tool, and no bulk start/sit across leagues.
- **Free league count.** 1 saved league is the strictest free cap here,
  alongside Dynasty Nerds. FantasyCalc and Dynasty Daddy sync everything
  for free.
- **Market value transparency.** We blend FantasyCalc's values but don't
  show them. KTC, FantasyCalc and Dynasty Daddy let users see or pick the
  market.
- **iOS.** Still not in the App Store.

### 3.5 Missing entirely
- **IDP, kickers and D/ST valuation.** This is the top open request on
  Dynasty Daddy's own feature board, and PFF publishes IDP dynasty
  rankings.
- **Devy data.** KTC has devy rankings and Dynasty Scout has college
  prospects. Our catalog has no data source.
- **LLM chat or Q&A** ("ask about my team"). FantasyPros Coach AI and
  Dynasty Trade Lab have one.
- **Sending trades into Sleeper** (Dynasty Daddy Bulk Trades).
- **Grading a screenshot of a received offer** (Roster Audit).
- **Expert content, podcasts and a Discord** (Dynasty Nerds, DLF, FantasyPros).
- **Season "wrapped" recap.** Our recaps exist, but there's no shareable
  end-of-season summary (Dynasty Daddy's Fantasy Wrapped, League Rewind).
- **Contract/salary-cap dynasty** (League Tycoon, Dynasty Owner). This is a
  niche.

---

## 4. Recommendations

### 4.1 Gaps worth closing (ranked)

Effort is a rough estimate for this codebase.

| # | Gap | User impact | Effort | Type |
|---|---|---|---|---|
| 1 | **Ship iOS, and expose ESPN import in web-next and mobile.** Port the validated Streamlit ESPN path (#1306) behind a FastAPI route and add it to `SleeperImportForm` and onboarding. Fix the 3 missing-player data-pipeline gap #1306 found. | Very high: ESPN is the largest host after Sleeper, and Sleeper-only caps our addressable market | M (adapter exists; needs an API route, UI and a D/ST decision) | Table stakes |
| 2 | **Player-exposure Portfolio.** Shares of each player across saved leagues, over- and under-exposure, and value at risk. The `has_cross_league_exposure` gate already exists and is unused. Could revive a reason for Front Office to exist. | High for multi-league dynasty players, who are the paying users | S–M (rosters per saved league are already fetched by `/v1/portfolio`) | Table stakes, and a chance to differentiate if combined with Next Moves ("you're 4x on a declining-role RB") |
| 3 | **Rookie draft season kit before the next draft window.** Verify Live Draft end to end, port it to mobile, add a rookie-only rankings filter and a mock draft against league-mate needs. | High seasonally (Apr–Sep is rookie and startup season) | M–L | Table stakes |
| 4 | **Raise the free league cap from 1 to 2 or 3.** | High on conversion and retention: free competitors sync everything, and "pay to sync one league" is a top Dynasty Nerds complaint | XS (`MAX_LEAGUES_FREE`) | Table stakes / growth |
| 5 | **Dedicated start/sit, with a bulk view across leagues.** Build on `/my-team` suggested starters plus matchup win probability. | Medium-high in season, every week | S–M | Table stakes |
| 6 | **Show the market alongside our model.** Display FantasyCalc market value next to our league-adjusted value with a "why we differ" line. Fetch Superflex market values (`num_qbs=2`) instead of only 1QB. Settle FantasyCalc API licensing before passing 1K monthly active users. | Medium for users, high for trust and risk | S | Differentiator (explains our edge) and risk reduction |
| 7 | **"Ask your GM" Q&A over existing engine outputs**, grounded only in our own signals, in keeping with the no-fabrication rule. | Medium: an "AI" checkbox competitors advertise | M–L | Differentiator if grounded, a risk if not |
| 8 | **Fix gating copy drift.** The paywall lists "Full League Pulse" as Pro, but the new League Pulse card is free. Either gate it or drop the line from `MOBILE_PREMIUM_BENEFIT_LINES`. | Low, but it's a trust and App Review risk | XS | Hygiene |
| 9 | **IDP valuation.** | Medium for a vocal niche | L (new player pool, scoring and projections) | Differentiator among the free tools |
| 10 | **Shareable season recap ("Wrapped").** Reuse recaps, trade outcome grades and share cards. | Medium for growth and virality | S–M | Differentiator |
| 11 | **Re-enable rewarded ads** once the AdMob/Kotlin conflict is fixed, so free users can unlock more Trade Hub ideas. | Low-medium for free-user value and revenue | S | Monetization |

Deprioritize for now: devy, until a licensed data feed exists, because
crowd grades on an empty catalog won't compete. Also expert content and
podcasts (not our model) and league hosting (the roadmap already flags the
legal research needed).

### 4.2 Marketing claims the code supports
- "Tells you your next move, not just a trade value." The Dashboard Next
  Move briefing, GM Plan and Team Stance are all shipped on web and mobile.
- "Trade ideas built for your roster and your league's format." Trade Hub,
  All Trades and Trade Finder, with picks; values adjust for Superflex, TE
  premium and PPR/half/standard.
- "Playoff odds simulated on your league's real remaining schedule."
  Monte Carlo in `modules/playoff_simulator.py`.
- "Did that trade work out? We follow up." Trade outcome tracking and
  retrospective grades.
- "Every recommendation explains why, with a beginner mode." The rule-based
  explanations and #1322.
- "Catches declining roles early." Only with the "confirmed multi-week"
  qualifier: the #1308 gating needs 3+ games and damps injury dips.
- "Native mobile app with push alerts." Say Android today; add iOS once it
  is live.
- "$19.99/year with a 7-day free trial." Confirm the live Stripe and IAP
  prices first.

**Don't claim yet:**
- "Works with ESPN/Yahoo." It's Streamlit only for ESPN and untested for Yahoo.
- "AI-powered." There is no LLM; "smart" or "explained" is accurate.
- "Cross-league player exposure." It doesn't exist yet.
- "Live draft assistant." It's labelled coming soon and unverified.
- "College/devy scouting." There's no data feed.
- "Full League Pulse is Premium." See gap 8.

---

## 5. Could not verify
- All Reddit sentiment, because reddit.com was blocked.
- DLF: exact current prices, the tool pages and whether there's an app (the
  site returned 403).
- Dynasty Daddy Club price; whether a native Dynasty Daddy app exists.
- Dynasty Nerds' exact sync list (Yahoo and ESPN conflict across their own
  pages); "DN360" doesn't appear anywhere on their site.
- FantasyPros' "GOAT" tier; whether dynasty features work in the merged app.
- Sleeper: absence of built-in power rankings, playoff odds and trade
  suggestions. None were found, but absence isn't proof.
- Dynasty Dealer's sync platforms and Android availability; Roster Audit
  pricing; what League Tycoon's "Wingman" includes; whether Dynasty Owner
  still operates.
- FantasyCalc's AI analyzer output. Only UI strings were seen.
- Our own live Stripe and RevenueCat prices, and whether the production
  `college_prospects` table has any rows.
