# App Store assets and growth plan (iOS, com.fantasygmlab.app)

Status: PLAN ONLY. Nothing here has been uploaded to App Store Connect (ASC), no fastlane lane was run, no signing touched.
Researched 2026-10-25 from Apple's own pages (URLs below). Items Apple's pages did not state are marked UNVERIFIED.

## 1. Verified specs

### 1.1 Screenshots
Source: https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications

- Formats .jpeg/.jpg/.png, no alpha/transparency. 1 required, up to 10 per device size. If UI is consistent, only the highest required resolution is needed; ASC scales down.
- Required: at least one for iPhone "Dynamic Island (medium)"; iPad 13" required "if your app runs on iPad".
- Our app.json has `supportsTablet: true`, so iPad 13" screenshots ARE required unless we drop iPad.

| Class | Portrait (px) | Notes |
|---|---|---|
| iPhone Dynamic Island (large) | 1260x2736, 1290x2796, 1320x2868 | optional; falls back to scaled Face ID (large) |
| iPhone Face ID (large) | 1284x2778, 1242x2688 | required if Dynamic Island (large) not provided |
| iPhone Dynamic Island (medium) | 1179x2556, 1206x2622 | REQUIRED (at least one) |
| iPhone Face ID (medium) | 1170x2532, 1125x2436, 1080x2340 | optional |
| iPhone Home Button classes | 1242x2208, 750x1334, 640x1096/1136, 640x920/960 | optional legacy |
| iPhone Duo outer display | 1398x2034 (landscape 2034x1398) | see 1.5 |
| iPhone Duo inner display | 2007x2853 (landscape 2853x2007) | see 1.5 |
| iPad 13" | 2064x2752 or 2048x2732 (landscape swap) | required if app runs on iPad |
| iPad 11" | 1488x2266, 1668x2420, 1668x2388, 1640x2360 | optional, falls back to scaled 13" |

(Landscape = swap width/height. Full legacy iPad rows on the Apple page.)

### 1.2 App previews (video)
Source: https://developer.apple.com/help/app-store-connect/reference/app-information/app-preview-specifications

- Up to 3 per device size and language. 15-30 s. Max 500 MB. H.264 (.mov/.m4v/.mp4, 10-12 Mbps target, High Profile L4.0, max 30 fps, AAC 256 kbps stereo 44.1/48 kHz) or ProRes 422 HQ (.mov). Poster frame default 5 s. Processing up to 24 h.
- iPhone accepted resolutions: 886x1920 portrait / 1920x886 landscape for Dynamic Island (large/medium), Face ID (large/medium) AND iPhone Duo. Home Button (large) 1080x1920; (medium) 750x1334.
- iPad 13": 1200x1600 portrait / 1600x1200 landscape.
- Previews are optional. Fallback: scaled from next larger class.

### 1.3 Creative assets (new, iOS 27 / iPadOS 27+ only)
Source: https://developer.apple.com/help/app-store-connect/reference/app-information/creative-assets-specifications

| Asset | Aspect | Image | Video |
|---|---|---|---|
| Product page header | 21:9 | 3840x1646, jpg/jpeg/png (alt 16:9 5244x2950 png) | 3840x1646, 30 or 60 fps, 5-30 s, mov/m4v/mp4 |
| Search results creative | 3:2 | min 1920x1280, max 3840x2560, jpg/jpeg/png (alt 16:9 5244x2950 png) | same res range, 30/60 fps, 5-30 s |

- No alpha. Search videos are muted (cannot be unmuted); product-page videos muted by default; all loop.
- Universal asset: one asset can serve both header and search results (the 16:9 5244x2950 option is the universal format per Apple's table; Apple's page lists it as the second option. Confirm in the ASC upload UI).
- The spec page lists NO safe-area numbers, file size limit, or template links. UNVERIFIED: exact safe-area geometry. Apple says download its templates (Figma, Photoshop, Pixelmator, Sketch per best-practices page; Aug 5 news names Figma/Photoshop/Pixelmator) from https://developer.apple.com/app-store/asset-best-practices/ and use the ASC Preview tool to check cropping. TODO for the designer: download templates (needs a browser; links are on that page, not retrievable via text fetch) and record safe areas here.

### 1.4 In-App Events
Sources: https://developer.apple.com/app-store/in-app-events/ and creative-assets-specifications

- Card 16:9 image 1920x1080 to 3840x2160; details 9:16 image 1080x1920 to 2160x3840; jpg/jpeg/png; max 500 MB. Videos same sizes, 30/60 fps, 15-30 s.
- Name 30 chars (title case), short description 50, long description 120. Up to 31 days duration; shows up to 14 days before start; 10 published per app, 15 approved. 7 badges: Challenge, Competition, Live Event, Major Update, New Season, Premiere, Special Event. Purposes: all users / attract new / keep active informed / bring back lapsed. Deep link: universal links recommended, no URL shorteners. No borders/gradients in media (crops/gradients applied automatically).
- Review lead time: not stated by Apple. UNVERIFIED; plan for several days.

### 1.5 iPhone Duo (what Apple actually says)
Sources: https://developer.apple.com/news/?id=kkphp5qo (Oct 5, 2026), screenshot-specifications, https://developer.apple.com/iphone-duo/ , https://developer.apple.com/iphone-duo/prepare/ (linked, not read)

- News text: "iPhone Duo will be available to customers starting October 23, 2026." and "Starting April 2027, any apps or games submitted will need to include screenshots for iPhone Duo." Recompile with Xcode 27.1; Device Hub shows poses/orientations. Submitting Duo screenshots shows an "optimized for iPhone Duo" badge.
- Screenshot spec page wording: "Starting April 2027, screenshots will be required for any app using the iOS 27.1 SDK or later." Sizes in 1.1.
- DISCREPANCY: the news says any app submitted; the spec page ties it to the iOS 27.1 SDK. Plan for the stricter reading (we need Duo screenshots at our first submission on/after April 2027). Exact day in April: UNVERIFIED (Apple says only "April 2027").
- UNVERIFIED: whether Duo screenshots may be scaled from regular iPhone captures. A community forum post (not Apple) claims they must come from Duo/simulator; treat as likely. Apple's page says nothing either way. Do not resize iPhone shots; capture in the Duo simulator (Xcode 27.1).
- Form factor details beyond the pixel sizes (it is described as foldable on the spec page): UNVERIFIED beyond that.
- Our stack: Expo SDK 54 (`mobile/package.json`). Whether it can build with Xcode/iOS 27.1 SDK and how the app lays out on Duo (inner display 2007x2853 is nearly square-ish portrait) is a separate engineering task (Section 6).

### 1.6 Asset Library, CPP, PPO, Apple Ads
Sources: https://developer.apple.com/help/app-store-connect/manage-app-information/manage-your-app-store-assets ; https://developer.apple.com/news/?id=ljpl7kyn ; custom-product-pages ; product-page-optimization

- Asset Library (ASC > app > Asset Library > +): upload "Creative Assets" or "Previews and Screenshots" with no placement chosen, so they can be pre-approved; submit for review standalone without a version update (reviewed against latest version). Fields: internal Name, Works With, Recent Usage, poster frame (locked after approval). Delete only in Prepared for Submission; otherwise Archive/Unarchive. Reuse via "Browse Assets" in version page, Custom Product Pages, PPO, In-App Events. Roles: Account Holder, Admin, App Manager, Marketing. Guidelines 2.3.3 and 2.3.4 apply.
- Preview tool in ASC: shows header, screenshots, search creative across devices, orientations, Dark Mode, languages (and Duo).
- Custom product pages: up to 70 per app; own URL; vary screenshots, promo text, previews (per Apple's CPP page); keywords can be assigned (each keyword combo unique to one page); deep links (iOS 18+); usable in Apple Ads (Today tab, Search tab, search results); reviewed independently of app updates; analytics in App Analytics Acquisition tab. The Asset Library page says creative assets can be uploaded in Custom Product Pages and PPO, so the new header/search creative IS usable there. Apple's CPP/PPO marketing pages themselves do not mention headers (they predate it).
- PPO: up to 3 treatments, one test at a time, up to 90 days, immutable once started, iOS/iPadOS 15+; treatments vary icon, screenshots, previews (per the PPO page; Asset Library page adds creative assets as testable); alternate icons must ship in the binary; new metadata needs review; 90% confidence guidance.
- Apple Ads: Zach's note says the new creative assets are usable in Apple Ads (Today tab + search). Apple's pages I could read confirm CPP-based Apple Ads only; a third-party source says Apple Ads custom creative is NOT part of this release. UNVERIFIED for headers/search creative in Apple Ads. Don't plan paid spend on it until checked in the ASC/Apple Ads UI. Also no ad budget is authorized.

### 1.7 Content rules (all assets)
Source: https://developer.apple.com/app-store/asset-best-practices/
No pricing/discounts/URLs, no copyright symbols, no unverifiable claims, no other-platform logos (so no Sleeper logo/marks unless covered by guidelines; keep to "your Sleeper league" in text sparingly and verify with Zach; no Android/web logos), no Apple recognitions, 4+ appropriate imagery (fantasy football/trade text is fine, no gambling imagery). Localize images/videos for each country offered. Silent-first videos, seamless loop, avoid quick cuts. Also read new App Review guidance 2.3.3: https://developer.apple.com/help/app-review/guideline-reference/2-3-3-screenshots

## 2. Audit: what we have

| Item | Where | State |
|---|---|---|
| App icon | `mobile/assets/icon.png` | 1024x1024 RGB PNG (no alpha, OK). Needs a visual check at small sizes; no Icon Composer layered/Liquid Glass version exists. `UIDesignRequiresCompatibility: true` in app.json. |
| Store screenshots | none | No App Store screenshots, no `mobile/fastlane/metadata`, no `screenshots` dir, no deliver lane (Fastfile has only app_status, create_app, certs, beta, build_only; `skip_upload_metadata: true` on beta). |
| Web marketing images | `assets/marketing/*.jpg` | 780x1688 phone-width web captures (dashboard, trade-hub, waivers, player-quick-view, decision-memory), 1280x800 desktop, 768x960 share cards. Web (browser) UI, wrong pixel sizes (needs 1179x2556 / 1206x2622 etc.), JPG; not usable as App Store screenshots (also guideline: show the real app). |
| Launch kit | `assets/marketing/launch/` (+ `screenshots/` 390/1440 web captures, social covers) and `docs/founder-beta-launch-marketing-kit.md` | Web/social, not store-sized. Useful as copy/story reference only. |
| Landing assets | `static/landing/assets` | Web only. |
| Listing text (subtitle, keywords, promo text, description) | not in repo | None found in repo or docs. Whatever is in ASC today must be read from ASC by Zach/coridian_ (not accessed here). |
| In-app review prompt | none found | No expo-store-review dependency; no requestReview in `mobile/src`. |
| Analytics | `mobile/src/lib/analytics.ts` | Ships dark; owner decision 2026-10-25 keeps it OFF (App Privacy). |
| Mobile screens available to capture | `mobile/src/screens` | Dashboard, TradeAnalyzer, TradeHub, TradeFinder, PlayerDetail (Quick View), Waivers, Matchup, GmPlan, SampleLeague, DraftCenter, LiveDraft, PlayoffOdds, Alerts, Compare, Games, Paywall, Onboarding. |

Gaps: every screenshot size, iPad 13" set (supportsTablet true), Duo set, previews, header + search creative, IAE media, localized text, listing copy source of truth, icon review.

## 3. Assets to produce

Capture method: real app UI in Xcode simulator (iPhone 17 Pro Max class and 16/17 Pro class), using the SampleLeague/demo data path so no real user data appears. Add short text overlays (captions) only. No device frame requirement from Apple. Always verify each screen exists in the shipped build at capture time.

### 3.1 Screenshot story (10 max; ship 8)
Ordered strongest first; first 3 show in search results.

| # | Screen | Caption (short; no pricing/claims) |
|---|---|---|
| 1 | Dashboard (My Team / GM plan snapshot) | Your whole dynasty, one dashboard |
| 2 | Trade Analyzer verdict | Know who wins the trade |
| 3 | Player Quick View | Values and context in one tap |
| 4 | Waivers | Find the best pickups fast |
| 5 | Matchup / Game Plan | Plan your week |
| 6 | Trade Finder / Trade Hub | Find deals that fit your roster |
| 7 | Draft Center / Live Draft | Draft with real-time values |
| 8 | Sample league | Try it without a league |
| (9-10 optional) | Alerts, Playoff odds | Stay on top of your team; See your playoff path |

Caption rules: no "best", "#1", "free", prices, Sleeper logo, or Apple awards. "Real player valuations" claims need a basis visible on screen; keep to descriptive verbs. Localize captions (en first; Spanish is the obvious second candidate for later).
Sets needed: iPhone 6.9" class (1320x2868 or 1290x2796) + 6.3" class (1206x2622) at minimum the one required (1179x2556 or 1206x2622); iPad 13" (2064x2752); iPhone Duo outer (1398x2034) and inner (2007x2853), captured in the Duo simulator. Light-vs-dark: pick one consistent mode (app is userInterfaceStyle automatic).

### 3.2 Product page header (21:9, 3840x1646)
One idea: a clean brand banner of the Trade Analyzer verdict card plus Dashboard, tagline "Dynasty, decided." (tagline is a draft; coridian_ to approve). Seasonal variants later (draft, deadline). No text near edges until safe areas are taken from Apple's templates. Real UI only.

### 3.3 Search-results creative (3:2, 1920x1280 to 3840x2560)
One idea: single clear Trade Analyzer verdict frame with the app name context. Purpose obvious in a glance: "Dynasty trade help". Consider the universal 16:9 5244x2950 version if we want one asset for both.

### 3.4 App preview outline (optional, 15-30 s, 886x1920, silent-first)
0-4 s Dashboard opens with sample league; 4-10 s Trade Analyzer: add players, verdict appears; 10-15 s Player Quick View tap; 15-21 s Waivers suggestions; 21-27 s Game Plan; 27-30 s back to Dashboard (clean loop). Poster frame: the verdict screen. Record from simulator/device screen capture; no audio or a quiet bed.

### 3.5 Icon check
Confirm icon.png at 29/40/60 px legibility; no alpha (OK); no text claims. Optional: Icon Composer layered icon for iOS 26/27 look (requires a new build; coridian_ approval; would also be PPO-testable only if all variants ship in the binary).

### 3.6 In-App Event media (16:9 and 9:16 each)
See 4.3.

## 4. Growth tools plan

### 4.1 Custom product pages (start with 3-4 of the 70)
| Page | Audience / keywords (to validate in ASC Search Ads or keyword tools) | Lead screens |
|---|---|---|
| Trade analyzer | "dynasty trade calculator", "fantasy trade analyzer" | Trade verdict first |
| Waivers | "waiver wire", "fantasy waiver" | Waivers first |
| Dynasty/League manager | "dynasty fantasy football" | Dashboard first |
| Sleeper users | "sleeper fantasy" (check naming/trademark rules; do not use logos) | Dashboard + sample league |
Each uses a deep link (iOS 18+) to the matching screen if the app supports the route (needs eng check). Headers can differ per page per the Asset Library page. Web/social links use the CPP URL so ASC Acquisition analytics attribute them.

### 4.2 Product page optimization
Test one variable at a time (one test at a time, 90-day cap): Test 1 screenshot order (Dashboard-first vs Trade-first); Test 2 caption style; Test 3 header image vs none; Test 4 icon only if a variant ships in the binary. Treat default confidence 90%. Needs enough traffic; with low impressions expect inconclusive results.

### 4.3 In-App Events (calendar-tied; dates to verify against the NFL calendar for the season)
| Event | Badge | When (verify) | Purpose |
|---|---|---|---|
| Waiver week kickoff | Special Event | Tuesday/Wednesday weekly waiver days (an event max 31 days; use one rolling "Season waivers") | keep active |
| Trade deadline push | Major Update or Special Event | Before typical Sleeper deadlines (mid-season, Oct-Nov) | active/lapsed |
| NFL Draft / rookie draft season | Premiere or Special Event | April rookie-draft window | attract new |
| Playoffs | Competition-adjacent (no real competition: use Special Event) | Dec | lapsed |
| New season launch | New Season | Late Aug-Sept | attract new |
Events must describe things that actually ship; a Major Update badge needs a real feature. Name 30 chars, short 50, long 120. Submit well ahead; Apple states no lead time.

### 4.4 Promotional text and ASO
Promotional text (170-char field is a standard ASC limit, UNVERIFIED on the pages read; editable without review): rotate by NFL calendar: waiver day, deadline, draft. Subtitle (30 chars, standard ASC limit, unverified here) candidates: "Dynasty trades and waivers"; "Dynasty fantasy football help". Keyword field (100 chars standard, unverified here): trade calculator, dynasty, waiver, rookie, rankings, sleeper (check Sleeper term policy). No keyword repetition across title/subtitle. Current live text is not in the repo; baseline from ASC first.
Localization: start en-US only; add es and en-CA/en-GB metadata later; localize screenshot captions along with metadata (Apple asks for it).

### 4.5 Ratings prompt policy
No prompt exists today. Proposal (needs Zach approval): use `expo-store-review` (new dependency, new build), prompt only after a positive moment (e.g. after a trade verdict viewed 3rd time), never in first session, max once per 120 days (the system also caps at 3/365 days). Never ask on error/paywall screens.

### 4.6 Measurement without app analytics
App analytics stay OFF (owner decision 2026-10-25). Use App Store Connect App Analytics only: impressions, product page views, conversion, downloads by source, CPP and PPO reports (Acquisition tab), plus IAE views/opens. Use per-CPP URLs for external links. No new SDKs.

## 5. Production and upload

| Asset | Produced by | Upload | Approver |
|---|---|---|---|
| Screenshots (iPhone, iPad, Duo) | Engineer captures in simulators from a release build with sample-league data; designer adds captions in Figma | ASC Asset Library / version page UI (manual). Fastlane `deliver` could do it (`deliver` with screenshots dir) but this repo has no deliver lane and `mobile/fastlane/.env` is authoritative for ASC; do NOT source `local_secrets`. Recommend manual ASC for the first set | Zach (final), coridian_ (copy/story) |
| Previews | Screen recording, edit | ASC | coridian_ + Zach |
| Header, search creative | Designer from Apple templates | Asset Library > Upload Creative Assets, submit standalone for review | coridian_ + Zach |
| IAE | Designer | ASC Events | coridian_ + Zach |
| CPP / PPO setup | Zach or coridian_ in ASC (Marketing/App Manager role) | ASC | Zach |
Apple App Review reviews the assets; Zach must press submit. No upload without Zach's explicit say-so. Any new build (review prompt, Icon Composer, Duo layout) follows the existing rule: no autonomous TestFlight/fastlane run.

## 6. Timeline (today 2026-10-25; Duo ships 2026-10-23)
- Now to mid-Nov: get Zach's answers to NEEDS list; download Apple templates and record safe areas; baseline current ASC listing; engineering spike: can the mobile app (Expo 54) be built with Xcode 27.1 and how does it lay out on Duo.
- Mid-Nov to Dec: capture iPhone + iPad screenshot sets; produce header and search creative; submit via Asset Library; create 3-4 CPPs.
- Dec to Jan: start PPO test 1; first IAE (tied to the NFL offseason/draft in April).
- Jan to Feb 2027: Duo capture and badge, if the layout spike passes.
- By end of March 2027: Duo screenshots in place for any submission, ahead of the April 2027 requirement (exact date unverified). Do not leave this for April: any version submitted after the cutoff would be blocked.

## 7. Needs from Zach / coridian_
1. Zach: approve this plan; confirm iPad stays supported (drives iPad 13" screenshots) or drop iPad.
2. Zach: go-ahead for the engineering spike on Duo / iOS 27.1 SDK build.
3. Zach: confirm manual ASC upload vs adding a fastlane deliver lane.
4. coridian_: approve story order, captions, tagline, header idea.
5. coridian_/Zach: paste current ASC subtitle, keywords, promo text, description (not in repo).
6. Zach: ratings prompt policy yes/no (needs a build).
7. Zach: whether to use Sleeper name in keywords/captions; any Apple Ads budget (none assumed).

## Sources
- https://developer.apple.com/app-store/asset-best-practices/
- https://developer.apple.com/help/app-store-connect/reference/app-information/screenshot-specifications
- https://developer.apple.com/help/app-store-connect/reference/app-information/app-preview-specifications
- https://developer.apple.com/help/app-store-connect/reference/app-information/creative-assets-specifications
- https://developer.apple.com/help/app-store-connect/manage-app-information/manage-your-app-store-assets
- https://developer.apple.com/news/?id=kkphp5qo , ?id=ljpl7kyn , ?id=kug6m2ea
- https://developer.apple.com/app-store/custom-product-pages/ , /product-page-optimization/ , /in-app-events/
