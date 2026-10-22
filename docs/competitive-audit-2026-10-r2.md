# Competitive audit, round 2: closing the gap and what to advertise

Checked 2026-10-21 (US Central). This builds on round 1,
`docs/competitive-audit-2026-10.md` (#1327), and doesn't repeat its research.
Read round 1 for the full competitor profiles and the feature matrix.

Our side comes from the code on `main` at `0195e076` and from PR bodies. A
feature counts as **live** only if a user can reach it on web-next or mobile.
API-only or bot-only work is marked **backend only**. Competitor facts come
from the competitors' own pages, read 2026-10-21. Anything not confirmed is
marked **UNCONFIRMED**.

**Same research limits as round 1.** reddit.com was blocked and
dynastyleaguefootball.com returned 403. Patreon pages didn't render when
fetched directly, so the Dynasty Daddy Club price comes from search snippets
of Patreon's own page.

**Projection accuracy.** The owner's end-to-end logic audit backtested our
weekly projections and start/sit against Sleeper's, and ours trail. That
audit (`docs/logic-audit-2026-10.md`) wasn't on `main` at the time of
writing, and no PR body states the numbers. This doc relies on the owner's
statement of the finding. **Nothing below claims projection or start/sit
accuracy.**

---

## 1. What shipped since round 1

Round 1 was written against `9fa453bd`. Some PRs the brief lists (#1321
Trade Finder picks, #1322 beginner copy, #1324 Portfolio speedup) merged
just before round 1 was finished, so round 1 already counts them. They're
listed again here so this doc is complete.

| PR | Change | Status for users | Platforms | Competitive effect |
|---|---|---|---|---|
| #1321 | Trade Finder can offer your own picks and filter for "picks back". Picks are resolved against the picks you actually own. | **Live** (Pro) | W, M | Matches FantasyPros and Dynasty Daddy trade finders on picks. |
| #1322 | The onboarding experience answer now drives beginner explanations on Dashboard, Trade Analyzer, Trade Hub, Waivers and Player Quick View. You can change it later in Account > Preferences (web) or More > Explanations (mobile). | **Live** (free) | W, M | No competitor found with a plain-language mode (§2.7). |
| #1324, #1316 | Portfolio's cold load is faster and loads progressively. Mobile now caches it the way the other screens do. | **Live** | W, M | Speed and trust. Dynasty Nerds' 2026 reviews complain about loading. |
| #1326 | Trade Analyzer now prices players with the league-adjusted value (Superflex/2QB, TE premium, league size, lineup depth). Before, it used the 1QB base score, so it disagreed with Trade Hub. Re-grading 48 Superflex ideas changed 12 verdicts. | **Live** | W, M | This is what makes the "values fit your league" claim true on every trade screen, not just Trade Hub. |
| #1328 | Spent current-year picks are no longer offered or valued after the rookie draft. Next season's picks get a proper future discount before the draft. | **Live** | W, M | Correctness. Removes a "suggested a pick I already used" embarrassment. |
| #1330 | Lineup slots: `WRRB_FLEX` counts once, `IDP_FLEX` is no longer counted as an offensive flex, and narrow flex slots fill first. This affects suggested lineups, team strength, power ranks, roster needs and the Analyzer's lineup delta. | **Live** | W, M | Correctness for non-standard leagues. |
| #1332 | Alerts read state syncs across phone and web, survives season rollover, and retries reads that failed offline. | **Live** | W, M | Small, but it's what "one account, every device" means. |
| #1333 | Manager Tendencies: per-manager trading profile built from real Sleeper transactions across seasons. Each signal cites the transaction ids behind it and is withheld below a minimum sample. Pro-gated API. | **Backend only.** No web or mobile UI. | API | Not advertisable until there's a UI. Strong future claim (§3, "Next up"). |
| #1335 | Web "Did this trade happen?" prompt, matching mobile. Same server rows, so an answer on one device clears the other. | **Live, but limited.** Web doesn't record shares yet, so only trades shared from the phone get asked about on web. Open PR #1338 fixes that. | W, M | The follow-up loop is now on both platforms once #1338 merges. |
| #1336 | FantasyCalc attribution (`ValuesCredit` component on web and mobile, plus the methodology page and legal text). League Pulse paywall copy now names only the part that's actually gated: the mobile Dashboard leader tiles. | **Live** | W, M | Closes round 1 gap 8 and meets the attribution requirement in FantasyCalc's API terms. The under-1,000-MAU licensing question is still open. |
| #1323 | External weekly recap and week-result endpoints, with per-week box scores kept. | **Backend only** (content bot API) | API | Feeds social and bot posts, not the app. |
| #1318 | Contract timeline from nflverse's public dataset. | **Backend only** (external background profile endpoint). | API | Correction to round 1, which listed it under Player Quick View. PQV shows a "Contract" bio line, not this timeline. |
| #1325, #1331, #1337 | Shared UI components (section headings, badges, injury labels, verdict callouts, error states). | Live, no feature change | W | Consistency only. |
| #1329 | Engagement and retention brainstorm (`docs/engagement-brainstorm-2026-10.md`). | Doc | — | Feeds §4. |

**In progress (not live):**

| Item | Where it stands, 2026-10-21 |
|---|---|
| ESPN league import on web and mobile | **Open PR #1339.** Public ESPN leagues only. An ESPN league gets the features its data can feed, and every other feature says "Not available for ESPN leagues yet." There are no traded picks, transactions, matchups or drafts for ESPN. Import is refused below a 60% player match rate. |
| Web trade-share recording | **Open PR #1338** (finishes #1335). |
| Age-99 placeholder in age averages | **Open PR #1334** (correctness). |
| College prospects seed data | Branch `college-prospects-seed`, no PR. |
| Google/Apple sign-in | **Open PR #1161**, waiting on provider credentials. |
| Our own market values, projections v2, lineup planner | In progress per the owner. **No PR or branch found** on GitHub as of this check. |
| Engagement items (season simulator, Season Review, and others from #1329) | Brainstorm only. Nothing built. |
| iOS app | Still in App Store review. `appStoreUrl` is `null` in `web-next/src/lib/appStoreLinks.ts`. Android is live on Google Play. |

---

## 2. Round 1's unconfirmed items

| # | Question | Finding | Source (checked 2026-10-21) | Status |
|---|---|---|---|---|
| 2.1 | Dynasty Daddy Club price and perks | About **$6/month**. Perks: ad-free, a cheatsheet tool, "league-infused trade values", early access, badges, and a club-exclusive Player Watchlist. About 504 paid members (Graphtreon, a third-party estimate). The site still calls itself "a free all-in-one fantasy football tool". | https://www.patreon.com/cw/DynastyDaddy/membership, https://www.patreon.com/cw/DynastyDaddy/posts | **Partly confirmed.** From search snippets of Patreon's own page; the tier table didn't render. |
| 2.2 | Dynasty Daddy native app | No App Store or Google Play listing found. | App Store and Play searches | **UNCONFIRMED** (likely none) |
| 2.3 | Dynasty Nerds sync list | **Sleeper, MFL, Fleaflicker, FFPC, ESPN.** Yahoo is "planned", and CBS/NFL.com are "possible later". The article was last updated 2026-02-02. Premium is $7.99/month or $79.99/year with **no free trial**. Free gets 1 league. The app is on iOS and Android. | https://support.dynastynerds.com/article/56-league-host-support, https://dynastynerds.com/plans-and-pricing/ | **Confirmed.** Yahoo isn't supported. |
| 2.4 | Sleeper's built-in analysis | **Projections are native.** Projected points show in the matchup tab and on player cards. Sleeper's 2024 redesign post said "trade calculators, start/sit advice, league power rankings, draft analyzers" were "coming soon" through **MINIs**, which are third-party plug-ins (Dynasty Nerds ships one). No support article was found for native power rankings, playoff odds, trade suggestions, trade values or weekly recaps. Sleeper's own feature-request threads still ask for them. | https://support.sleeper.com/en/articles/4126744-how-can-i-see-my-player-s-points-breakdown, https://sleeper.com/blog/sleepers-app-redesign-whats-new/ | Projections **confirmed**. The other absences are **UNCONFIRMED**: none were found, but absence isn't proof, and MINIs may offer third-party versions inside Sleeper. |
| 2.5 | Dynasty Dealer | **iPhone only**, with no Play listing found. 4.4 stars from 7 ratings. First released 2025-10-03, now at v1.1.10. Free with in-app purchases; Premium is $5.99/month or $49.99/year. The trade calculator is capped at 5 per day on free. Features: Fair Trade Finder, Roster Recon, values including Superflex, **Portfolio View**, Lineup Optimizer, Waiver Wire, **Mass Trade Sender**, Trade Database, community "Dispute a Trade" vote, Dispersal Drafts, Redraft Mode. | https://apps.apple.com/app/id6752508038 | Features and price **confirmed**. The release notes only mention Sleeper, so other sync platforms are **UNCONFIRMED**. |
| 2.6 | Fantasy Life | FantasyLife+ Tier 1 is $39.99/year (synced Rankings HQ, Start/Sit, draft tools). Tier 2 is $99.99/year (adds Fantasy HQ, Utilization HQ, best ball, DFS and betting). **No dynasty-specific tools are listed.** Rate My Trade uses rest-of-season projections and is redraft-oriented. There's dynasty and rookie rankings *content*. Fantasy HQ multi-league management names MFL, Fleaflicker, RTSports and Guillotine Leagues as partners. No native app was found. | https://www.fantasylife.com/pricing, https://www.fantasylife.com/tools, https://www.fantasylife.com/tools/rate-my-trade | **Confirmed** that it isn't a dynasty tool. Full sync list and app are **UNCONFIRMED**. |
| 2.7 | Underdog | No dynasty leagues or dynasty tools found. Best ball is draft-only, with no trades or waivers. Its tools are ADP and an advance-rate explorer. | https://www.4for4.com/2023/preseason/underdog-rankings-tools-and-draft-strategy, Underdog news and help pages | **Not a competitor** for dynasty management. Absence is UNCONFIRMED. |
| 2.8 | Did any competitor offer our candidate differentiators? | See the "Competitors beaten" column in §3. Short version: no competitor found for the daily next-move briefing, the trade-happened follow-up with later grading, beginner mode, daily guess-the-player trivia, or trade ideas that respect declared strategy and untouchables. **Playoff simulation isn't unique.** Dynasty Scout, Playoff Machine (a Sleeper app), Dynasty Daddy and FantasyCalc all simulate. **Real-trade feeds aren't unique either.** Dynasty Nerds' trade browser, Dynasty Dealer's trade database, KTC and FantasyCalc all show real trades. | https://www.fantasypros.com/2026/07/best-dynasty-fantasy-football-trade-tools/, https://apps.apple.com/app/id6503407267, https://apps.apple.com/us/app/-/id1599147051 | "Not found" means not found on the competitors' own pages. These are **UNCONFIRMED absences**, so phrase claims as "we do X", not "no one else does X". |

**Still unconfirmed after round 2:** DLF's current prices, tools and app;
FantasyPros' GOAT tier and whether dynasty works in its merged app; Roster
Audit pricing; League Tycoon "Wingman"; Dynasty Owner's status; FantasyCalc's
AI analyzer output; our live Stripe and RevenueCat prices; and the production
`college_prospects` row count.

---

## 3. What to advertise

Rules for this list. Every claim is true in production on `main` today. Each
one is something no named competitor was found to offer, or something it
offers clearly worse. Each can be understood in one read. Claims are phrased
as what **we** do, not "only we", because the competitor absences are
unconfirmed (§2.8).

Placement codes: **H** = landing hero or first fold, **S** = App Store / Play
listing, **P** = social or bot post.

| Rank | Claim (headline) | Proof in code | Competitors it beats | Where |
|---|---|---|---|---|
| 1 | **"Open the app, get your next move."** A ranked to-do list for *your* team: the trade to make, the waiver to claim, the injury to cover. | `modules/dashboard_engine.py`, `modules/daily_gm_briefing.py`, web `app/dashboard`, mobile `DashboardScreen.tsx`; deep-linked CTAs #1293/#1294; GM Plan `modules/gm_plan.py` | KTC, FantasyCalc, Dynasty Daddy, DLF (calculators and lists, no team briefing). Dynasty Nerds and Dynasty Dealer have optimizers and roster analysis, but no daily action list was found. | H, S, P |
| 2 | **"Trade ideas that respect your plan."** Tell us whether you're contending or rebuilding and who's untouchable, and every suggestion follows it. | #1290 (Trade Hub/Finder honor declared Team Situation strategy), #1291/#1289 (GM Targets untouchables), `modules/trade_ideas.py` protection logic, `modules/trade_hub_engine.py` `team_stance` | FantasyPros Trade Finder, Dynasty Daddy Trade Finder, Dynasty Dealer Fair Trade Finder, DLF trade finder. None was found to take declared strategy or untouchables as input. | H, S, P |
| 3 | **"Values that fit your league, on every screen."** Superflex, TE premium, PPR/half/standard, league size and real lineup slots, read straight from your Sleeper settings. The Analyzer and the trade ideas use the same numbers. | `modules/league_value_settings.py` (`apply_valuation_lens`), #1326 (Analyzer uses the league-adjusted score), #1330 (correct flex slots) | KTC (fixed 12-team 0.5 PPR values), FantasyCalc (limited formats), Fantasy Life (redraft ROS trade grades). Weaker vs Dynasty Daddy, DLF and FantasyPros, which also adjust, so lead with "your league's real settings, automatically". | S, P |
| 4 | **"We check whether your trade happened, then grade it as the season plays out."** | `mobile/src/components/TradeOutcomePrompt.tsx`, `web-next/src/components/TradeOutcomePrompt.tsx` (#1335), `modules/trade_outcome_results.py`, web `app/trade-history` | No competitor found with a follow-up loop. KTC, FantasyCalc and Dynasty Dealer's trade databases show other people's trades, not *your* decisions graded later. | H, S, P |
| 5 | **"Every recommendation explains why, in plain English if you want it."** | Rule-based explanations on every recommendation; beginner mode #1322 (`web-next/src/lib/experienceCopy.ts`, `useExperienceCopy`) | All named competitors. No plain-language mode was found anywhere. Dynasty Nerds' 2026 reviews ("AI slop… so much shoved on the screen") show the opposite approach. | H, S |
| 6 | **"Pro is $19.99 a year, with a 7-day free trial."** | `modules/stripe_billing.py` (`$19.99` annual, `$3.99` monthly, `PRO_TRIAL_DAYS = 7`) | Dynasty Nerds ($79.99/yr, no trial), FantasyPros dynasty (MVP and up), Dynasty Dealer and Dynasty Scout ($49.99/yr), DLF (~$59.99/yr), PFF ($99.99/yr), Fantasy Life ($39.99+). Dynasty Daddy Club is about $6/month (~$72/yr). Free tools (KTC, FantasyCalc) are cheaper, so say "the cheapest paid dynasty assistant", not "cheapest". **Check the live Stripe and IAP prices before publishing.** | S, H (pricing section) |
| 7 | **"See how real dynasty trades actually turned out."** A feed of anonymized trades from real leagues, graded in hindsight on both production and value. | `modules/community_trades.py` (only confirmed trades whose two signals agree at high confidence), web `app/community` | KTC, FantasyCalc, Dynasty Nerds and Dynasty Dealer show real trades, **but graded as of trade day, not on how they worked out**. This is a "weaker at competitors" claim, not a unique one. **Web only.** | P, H (secondary) |
| 8 | **"Spot a fading role before your league does."** Sell-high flags fire only after a confirmed multi-week usage decline, not one bad game. | #1308; `modules/rankings.py` `compute_recency_features` (3+ games needed, 4+ before anything is shown to users, injury dips dampened) | KTC and FantasyCalc (market value only, no usage-trend flags found). Dynasty Nerds and DLF have content, not per-player flags. **Always keep the "confirmed multi-week" qualifier.** | P, S |
| 9 | **"Playoff odds on your league's real remaining schedule."** | `modules/playoff_simulator.py` (Monte Carlo over the actual Sleeper schedule, strength fit on the league's own games) | **Not unique.** Dynasty Scout, Playoff Machine, Dynasty Daddy and FantasyCalc simulate too. Beats KTC, DLF, PFF and Sleeper (not found native). Use only as a feature-list line, never a hero claim. | S (bullet) |
| 10 | **"Your dynasty desk in your pocket, with push alerts."** | Android live (`appStoreLinks.ts`); push from `modules/push_triggers.py`; cross-device read state #1332 | KTC, FantasyCalc, Dynasty Daddy, DLF and Fantasy Life (web only); FantasyPros (dynasty is web only); Dynasty Dealer and Dynasty Scout (iOS only, tiny). **Say "Android" until iOS is live.** Dynasty Nerds has both platforms, so beat it on ratings and reliability, not on having an app. | S, H |
| 11 | **"A daily guess-the-player game with a league leaderboard."** | `modules/guess_the_player.py`, `modules/guess_the_player_leaderboard.py` (#1299), "Who is who?" (#1287) | Dynasty Daddy has daily trivia, so this isn't unique. Beats KTC, FantasyCalc, Dynasty Nerds and Dynasty Dealer. The league leaderboard is the hook. | P |

**Top 8 for most uses:** ranks 1–8. Ranks 1, 2 and 4 together are the
story: *we tell you what to do, it fits your plan, and we follow up.* No
competitor was found doing all three.

### 3.1 Don't claim (updated)

- **Projection or start/sit accuracy, in any form.** "Smart lineups",
  "best projections" and "win your week" are all out. The backtest found
  ours trail Sleeper's, which every one of our users already sees for free.
- **"Works with ESPN."** Not until #1339 merges and is deployed. Even then,
  say "ESPN leagues (public) supported for team, trade and value tools". Many
  features say "Not available for ESPN leagues yet."
- **"AI-powered" or "ask your GM."** There's still no LLM. Use "explained" or
  "smart".
- **"Manager Tendencies" or "know how your league-mates trade."** Backend
  only (#1333). There's no UI yet.
- **"Cross-league player exposure" / "Player Portfolio".** Ours is still
  team-level.
- **"Live draft assistant", "mock drafts" and "devy/college scouting".**
  Same as round 1.
- **"Only app that…".** Competitor absences are unconfirmed (§2.8).
- **"On iPhone."** Not until `appStoreUrl` is set.
- **"Web asks you whether your trade happened."** Only after #1338 merges.
  Until then the web prompt only covers trades shared from mobile.

### 3.2 Draft store copy ("what makes us different")

Draft only. **The store listings weren't changed.** Character limits are
noted for each field.

**Google Play short description (80 max):**

> Your dynasty GM: next moves and trade ideas that fit your plan and your league.

That's 79 characters. Check the count again after any edit.

**App Store promotional text (170 max):**

> Open the app, get your next move. FantasyDesk reads your Sleeper league and tells you which trade, waiver or lineup move matters, and why, in plain English.

That's 156 characters.

**"What makes FantasyDesk different" bullets (full description, both
stores):**

- **Your next move, every day.** A ranked list of actions for your team: the
  trade to make, the player to claim, the injury to cover.
- **Trade ideas that respect your plan.** Tell us whether you're contending
  or rebuilding and who's untouchable, and every suggestion follows it.
- **Values that fit your league.** Superflex, TE premium, scoring and lineup
  slots come straight from your Sleeper settings, and every trade tool uses
  the same numbers.
- **We follow up.** Share a trade idea and we'll ask whether it happened,
  then grade how it worked out as the season plays out.
- **Explained, not just scored.** Every recommendation says why, and
  beginner mode puts it in plain English.
- **Spot fading roles early.** Sell-high flags only fire after a confirmed
  multi-week drop in usage, never one bad game.
- **Playoff odds on your real schedule,** plus five power boards for your
  league.
- **Pro is $19.99 a year** and comes with a 7-day free trial. *(Confirm the
  live IAP price before publishing.)*

Leave out until true: ESPN, iPhone, cross-league exposure, live draft, and
anything about projection accuracy.

---

## 4. Closing the gap

### 4.1 Round 1's gaps, updated

| R1 # | Gap | Status 2026-10-21 | What's left |
|---|---|---|---|
| 1a | iOS app | **In review** | Ship it. Then flip `appStoreUrl` and the "Android" wording in the copy above. |
| 1b | ESPN import on web and mobile | **In progress: PR #1339** | Merge and deploy. Then add ESPN transactions and matchups so more features work for ESPN leagues. Decide on D/ST. |
| 2 | Player-exposure Portfolio | **Not started.** Portfolio got faster (#1324) but is still team-level. | Build shares per player across saved leagues, wired to the unused `has_cross_league_exposure` gate. |
| 3 | Rookie draft season kit | **Not started** (college seed branch only) | Verify Live Draft, port it to mobile, add a rookie rankings filter and a mock draft. Due before the spring draft window. |
| 4 | Raise free league cap | **Not done.** `MAX_LEAGUES_FREE = 1`. | A one-line change, and an owner decision. |
| 5 | Dedicated start/sit, plus bulk across leagues | **Not started.** Lineup slot correctness fixed (#1330). Lineup planner in progress per the owner. **Now harder: the backtest shows our projections trail Sleeper's.** | Fix projections (projections v2) first. A start/sit tool on weaker projections than Sleeper's built-in ones hurts trust. |
| 6 | Show the market next to our model | **Partly done.** FantasyCalc attribution shipped (#1336). "Own market values" in progress per the owner. | Show the market value next to ours with a "why we differ" line, fetch Superflex market values, and settle FantasyCalc licensing (or replace it with our own values) before 1,000 MAU. |
| 7 | "Ask your GM" Q&A | Not started | Unchanged. Grounded only in engine outputs. |
| 8 | Paywall copy drift | **Done** (#1336) | — |
| 9 | IDP | Not started | Unchanged. #1330 now correctly ignores `IDP_FLEX`. |
| 10 | Season "Wrapped" | Not started. Brainstormed as Season Review in #1329. | Ship before the fantasy playoffs end (late December) to catch the season-end sharing window. |
| 11 | Rewarded ads | Still disabled (`adsAvailable = false`) | Unchanged. |
| new | Projection and start/sit accuracy | **Exposed by the backtest.** Projections v2 in progress per the owner. | **Table stakes.** Sleeper shows projections to every user for free, so ours have to at least match them before any lineup or start/sit feature is pushed. Until then, keep projections out of marketing and lead with trades, values and the next-move workflow. |
| new | Manager Tendencies UI | Backend shipped (#1333) | Add a Trade Hub partner card ("trades picks for vets 4 of 5 times"). Each line already cites the trades behind it, so this is a cheap, believable feature and a future ad claim. |
| new | Web trade-share recording | PR #1338 open | Merge. Needed for claim 4 on web. |
| new | Correctness backlog from the logic audit | #1326, #1328 and #1330 merged; #1334 open | Finish the remaining findings. Wrong verdicts are the fastest way to lose dynasty users (see Dynasty Nerds' reviews). |
| new | Community feed on mobile | Web only | Port it. It's the most shareable surface and fits rank 7. |

### 4.2 Recommended order

1. **Merge the open correctness and loop PRs: #1338 and #1334.** They're
   small and already done. #1338 makes claim 4 true on web.
2. **Ship iOS and ESPN (#1339).** This is still the biggest addressable-
   market gap. Every sync-list competitor has ESPN, and Dynasty Nerds now
   confirms it too.
3. **Projections v2 to at least Sleeper parity, measured with the same
   backtest.** This is table stakes and blocks start/sit, the lineup planner
   and any in-season accuracy claim. Don't ship the lineup planner on the
   current projections.
4. **Raise the free league cap to 2–3.** One line. Dynasty Nerds' cap of 1
   league and no trial is one of its most-cited complaints. Pair it with the
   $19.99 trial claim.
5. **Own market values, and show the market next to our value.** This
   removes the FantasyCalc dependency and licensing risk, and turns the
   value gap into an explanation ("why we differ").
6. **Manager Tendencies UI.** The backend is done. It strengthens claim 2
   ("trade ideas that fit") and is easy to market once live.
7. **Player-exposure Portfolio.** Table stakes against FantasyCalc,
   Dynasty Daddy, Dynasty Nerds and Dynasty Dealer. Combine it with Next
   Moves ("you're 4x on a fading RB") to make it ours.
8. **Season Review / Wrapped, plus the community feed on mobile.** Time it
   for the end of the fantasy season. This is the growth loop.
9. **Rookie draft kit** (Live Draft verified, mobile, mock draft). Must be
   done before the spring rookie draft window.
10. **Later:** grounded Q&A, IDP, rewarded ads, Sleeper trade sending
    (Dynasty Daddy Bulk Trades, Dynasty Dealer Mass Trade Sender).

### 4.3 Top 5 gaps today

1. **iOS still not live, and Sleeper only** (ESPN is in PR #1339).
2. **Weekly projections and start/sit trail Sleeper's** (per the backtest).
3. **No player-exposure Portfolio.** Four competitors have one.
4. **Strictest free tier** (1 league).
5. **Market values depend on FantasyCalc**, with an open licensing
   question, and the market isn't shown next to our value.
