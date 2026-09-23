# FantasyGM Lab — UI Magna Carta

## Purpose

This document defines the canonical visual language, information architecture principles, component behavior, hierarchy rules, and interaction standards for FantasyGM Lab. Treat it as the default authority for all UI work unless a page-specific requirement explicitly overrides it.

The goal is not merely consistency. FantasyGM Lab should feel like one coherent premium product built for someone managing a football franchise, not a collection of unrelated fantasy-football screens.

The product should visually communicate: **front-office intelligence + sports analytics + actionable GM decision support** — rather than: generic fantasy app + stat tables + decorative cards.

## 1. Core product feel

FantasyGM Lab should feel: premium, serious, intelligent, modern, fast, compact, data-rich, decisive, mobile-native.

It should **not** feel: childish, overly gamer-like, neon for the sake of neon, cluttered, spreadsheet-like, excessively card-heavy, like every metric has equal importance, like a generic fantasy-football clone.

The visual reference point is closer to a **professional front-office analytics dashboard adapted elegantly to mobile**.

## 2. Brand foundation

- Primary background: `#0D1117` / near-black deep navy
- Primary brand accent: `#00D4FF` / FantasyGM cyan

Use subtle navy/blue gradients where useful, but the interface should remain predominantly dark. Do not fill large portions of the UI with bright cyan. Cyan is most effective when reserved for: active controls, navigation selection, important analytical emphasis, GM intelligence, interactive affordances, icons, selective borders/glows. The overall UI should feel dark first, cyan second.

## 3. Semantic color system

Colors must have consistent meaning throughout the entire app.

- **Cyan** — primary interaction, selected states, GM intelligence, analytical emphasis, navigation.
- **Green** — positive value, healthy status, upside, strong opportunity, favorable outcomes.
- **Amber / Gold** — opportunity, pending state, draft capital, moderate caution, FAAB/acquisition context, strategic attention.
- **Red** — injury, urgent risk, negative value, serious concern, unavailable/out states.
- **Purple** — secondary analytical/general category only where already established. Use sparingly.
- **Gray / Slate** — inactive controls, secondary copy, metadata, neutral information.

Do not arbitrarily recolor components per screen. A red badge must mean essentially the same class of thing everywhere. A green state must not mean "good" on one screen and "selected navigation" on another.

## 4. Information hierarchy rule

Do not preserve old layouts just because they already exist. Page structure should be determined by user decision importance.

Before redesigning any screen, ask: **what question did the user come here to answer?** The answer to that question receives the strongest visual emphasis. Supporting context comes second. Reference information comes later.

Examples:
- **Player Detail:** Who is this player? → How valuable are they? → What should I do with them? → Why? → Detailed stats
- **Waivers:** Who should I add? → What should I bid? → Why? → What other players are available?
- **Trade Hub:** What is the trade? → What do I send/receive? → What is its value? → Why does it work? → How realistic is it?
- **Matchup:** How do the teams compare? → What lineup should I start? → What does the opponent look like?
- **Next Move:** What should I do next? → What problems need attention? → What opportunities exist?

Never organize screens solely around backend object structure. Organize them around user decisions.

## 5. Mobile-first rule

FantasyGM Lab is a mobile-first product. Design first for modern iPhone dimensions. Desktop-like layouts must not simply be squeezed onto mobile.

Requirements: readable typography, comfortable touch targets, clear one-handed interaction, no horizontal page overflow, sensible sticky controls, correct safe-area handling, no content hidden beneath overlays, efficient vertical scrolling. Density should come from better grouping, not tiny text.

## 6. Safe area + layering

iOS status-bar and safe-area behavior must be treated as structural layout constraints. Never fix overlap using arbitrary device-specific offsets.

Establish shared tokens/components for: safe-area top, primary app header height, sticky subnavigation offset, modal/sheet safe-area padding, floating-control safe zones. Layering should be deterministic.

Typical hierarchy: system safe area → global app header → optional sticky page subnav → page content → floating GM orb → sheets/modals.

Sticky player tabs must never occupy the iOS status-bar region.

## 7. Global app chrome

These elements are canonical application-wide components and should not be reinvented screen-by-screen:

- **Global header** — back button, page title, league context, league-format selector, Dynasty/Keeper/Redraft context, strategy controls (Auto/Retool), favorite/overflow controls when relevant.
- **GM Orb** — a core product identity and navigation/intelligence element. It must remain globally consistent. Do not redesign it per page. Do not replace it with a footer. There is no generic persistent bottom navigation bar — do not introduce one because a concept image happens to contain one.
- **"Where to Go" navigation sheet** — the canonical expanded application navigation. Should use one implementation globally.

## 8. GM orb rule

The GM orb is permanent application chrome. It should: use one canonical size, use one canonical visual treatment, remain within safe areas, avoid covering important content, retain consistent placement behavior, open the canonical navigation/intelligence experience.

Page designs must accommodate the orb. The orb should not be moved simply because a page has a card in its usual location — the page should adapt around it.

## 9. Global header rule

There should not be five slightly different header systems. Reuse one shared implementation with configurable content. Page-specific changes should be driven by props/configuration rather than forks. The header should remain visually calm and should not compete with primary page content.

## 10. Typography hierarchy

Typography should do much of the organizational work. Use a consistent hierarchy approximately equivalent to:

- **Display/hero** — important player names or major numbers.
- **Page title** — screen identity.
- **Section title** — Fantasy Scoring, Priority Adds, Production, Awards, etc.
- **Card/row title** — player name, recommendation headline, team.
- **Metric value** — score, rank, yardage, value, bid.
- **Metric label** — PASS YARDS, POSITION RANK, SNAP %, etc.
- **Secondary metadata** — team, age, opponent, year, league context.
- **Supporting explanation** — concise analytical prose.

Avoid excessive uppercase text — it works well for small labels/categories, not paragraphs.

## 11. Spacing system

Use a canonical spacing scale. Avoid random margins/padding values. The app should feel compact but never cramped. Preferred rhythm: tight spacing inside strongly related information, moderate spacing between related modules, larger spacing between major page sections. Do not use excessive blank space merely to make a page feel "premium" — premium comes from hierarchy and restraint.

## 12. Card philosophy

Not everything needs a card. Avoid `card → card → card → card → card`, especially when every card has the same border/background/radius/visual weight.

Prefer: one grouped surface containing related rows with internal dividers, compact metric grids, insight rows, chips, horizontally scrolling strips, nested hierarchy only when it adds meaning. Use strong card boundaries only when the object genuinely behaves like an independent unit.

## 13. Surface system

Maintain a small number of canonical surfaces:

- **Base** — main app background.
- **Elevated surface** — main content module.
- **Secondary surface** — metrics or nested elements.
- **Interactive surface** — buttons, selected controls.
- **Alert surface** — risk/opportunity states using semantic tinting.

Avoid dozens of subtly different dark grays. Put surface colors into the global theme/token layer.

## 14. Border rule

Do not surround every component with bright cyan outlines. Cyan borders should indicate: focus, selection, an important analytical module, an interactive affordance. Normal content should rely more on surface contrast and subtle neutral borders/internal dividers. Bright borders lose meaning when everything has one.

## 15. Glow rule

Glow is allowed but restrained. Appropriate: an active cyan control, a key OVR/value visualization, a GM-intelligence highlight, an important selected element. Inappropriate: every card, every icon, every border, large neon backgrounds. Think premium sci-fi analytics, not arcade machine.

## 16. Radius system

Use canonical radius tokens. Typical hierarchy: large radius → major cards/sheets, medium radius → controls/metric groups, pill radius → badges/filters/segmented controls. Do not invent different corner radii per page.

## 17. Button hierarchy

Establish shared button variants: **Primary** (most important action), **Secondary** (important but not dominant), **Tertiary/ghost** (lightweight supporting action), **Destructive/danger** (only when actual destructive/risk behavior exists). Buttons should not all have cyan borders by default. Pages should rarely have multiple equally dominant CTAs.

## 18. Segmented controls + filters

Use one shared style for: Stats/Trends/Schedule/Career/Model, For You/All Trades, All/QB/RB/WR/TE and similar filters. Active: cyan emphasis, subtle fill/glow. Inactive: dark/neutral, clear but quiet. Avoid giant outlined rectangular tabs.

## 19. Player identity component

Player identity is one of the most important reusable systems in FantasyGM Lab. It should have one canonical visual language.

Shared player identity should support: portrait, portrait ring/state, player name, position badge, NFL team, age where appropriate, tier/classification, injury/status, opportunity/state, optional supporting context. It should have variants: compact row, standard row, hero — but all variants must clearly belong to the same component family. Do not invent separate player styling for Waivers, Matchup, Trade Hub, Rankings, Roster.

## 20. Player portrait rings

Portrait ring colors should represent meaningful global classification/state. Do not use random colors simply for aesthetics. If the existing product already maps tiers to ring colors, preserve or formalize that mapping. Injury and tier should remain distinguishable.

## 21. Badges + chips

Badges should be compact. Examples: GEN, ELITE, IMPACT, STARTER, Questionable, Pending, Buy Low. They should communicate classification/state. Avoid making every label a badge — long sentences should remain text.

## 22. Player hero

Player Detail hero priority: player identity → OVR/value → position/team → meaningful classifications → recommendation → actions. Do not allow buttons or decorative imagery to overpower the player. The hero should generally fit mostly within one viewport.

## 23. OVR / value ring

The circular OVR/value visualization is a canonical Player Detail element. It should: be instantly readable, have a restrained glow, reflect appropriate semantic color, retain consistent geometry. Do not redesign the ring independently on every player type.

## 24. Snapshot component

Player Snapshot should answer: Value Score, Overall Rank, Position Rank, Age, Status, Injury Status. Use one compact cohesive component — avoid six giant independent boxes. Visual emphasis: Value Score → ranks → age/status/injury.

## 25. Analytics sections

Analytics pages should use reusable `AnalyticsSection` / `MetricItem`/`MetricCard` / `PercentileIndicator` components. Sections change by position/context.

- Example QB: Fantasy Output, Passing Production, Rushing, Usage, Efficiency.
- Example RB: Fantasy Output, Rushing Production, Receiving, Usage, Efficiency.

Do not build separate page templates when configuration can determine section composition.

## 26. Metric design

Each metric should normally contain: label, value, percentile/context, optional compact visualization. The numeric value is primary. The percentile is supporting context. The progress bar is tertiary. Avoid making the bar louder than the number.

## 27. Percentile system

Percentiles must use one global component and scale. Preserve model logic. Colors should follow a shared threshold system rather than being manually assigned by pages. Approximate semantics: high → green, above average → lime, middle → restrained neutral/yellow, below average → amber, poor → red when justified. Use arrows/icons consistently.

## 28. Insight row

Short analytical conclusions should use one reusable component. Examples: Role trending down, Starter At Risk, Elite Opportunity, Buy Low. Structure: icon, insight headline, optional supporting context, optional chevron. Do not put every insight into a giant alert card.

## 29. Recommendation component

FantasyGM Lab's value proposition is its recommendations. Recommendation components deserve stronger hierarchy than raw metadata. They should clearly answer: What should I do? Why? How confident is the recommendation? Reuse a common structure across roster recommendations, Next Move, trade recommendations, waiver recommendations. Page-specific variants are allowed, but their visual language must remain related.

## 30. Trade UI

Trade presentation should prioritize: partner/team → assets sent → assets received → value change → rationale → confidence/realism. Send ↔ Receive should be a canonical shared module. Player assets should reuse Player Identity. Draft picks should use a dedicated `DraftPickAsset` component — do not make picks pretend to be players.

## 31. Waiver UI

Personalized Priority Adds should normally appear before generic Best Available browsing. Waiver recommendations should emphasize: player → score/value → reason/tier → status → FAAB/acquisition guidance → breakdown. FAAB guidance should be a reusable module. "Best Available" is market context, not the entire product.

## 32. Matchup UI

Matchup should prioritize: team comparison → matchup verdict → user's recommended lineup → opponent lineup. Individual players should use compact lineup rows rather than giant cards.

## 33. Next Move UI

Next Move is the user's GM action cockpit. It should prioritize: Top Priority → urgent risks → opportunities → secondary context. Important recommendations must visually dominate routine alerts.

## 34. Awards

Awards are supporting information. Use a compact achievement chip/card: icon, award name, count, year. Horizontal scrolling or "View All" is acceptable. Avoid giant empty Awards sections.

## 35. Bio / low-priority information

Bio data should not consume significant vertical space. Present low-priority metadata as: a compact row, a small card, a grouped secondary section — not a large hero-like container.

## 36. Empty states

Empty states should still feel intentional. Include: clear message, concise explanation, relevant action when appropriate. Do not display an empty giant card.

## 37. Loading states

Use shared skeletons/placeholders consistent with final component geometry. Do not allow layout jumps when content loads. Avoid generic full-screen spinners when meaningful skeleton loading is possible.

## 38. Error states

Error UI should: explain what failed, avoid technical backend language, offer retry when appropriate. Use red sparingly — a whole page should not become bright red.

## 39. Modals + sheets

Reuse a canonical bottom-sheet/modal system. Sheets should: respect safe area, have consistent radius, use consistent grab handles, avoid nested scrolling where possible, preserve clear hierarchy. The "Where to go" navigation sheet is the primary example.

## 40. Microinteractions

Use subtle interaction feedback: press states, selected-chip transitions, smooth sheet presentation, restrained card expansion, subtle loading transitions. Avoid flashy animation that slows navigation. Performance is more important than spectacle.

## 41. Copy style

UI copy should be short, confident, specific, useful. Avoid overly robotic analytics text. Avoid paragraphs where a short headline plus context can work. Prefer, e.g.:

> Elite Opportunity
> Top RB on roster by season value

rather than one long sentence combining everything.

## 42. Data authority

Concept images are not data sources. The production app remains authoritative for: player data, values, percentages, rankings, algorithms, model classifications, statuses, league settings, calculations. Never hardcode values simply because they appear in a visual reference.

## 43. Concept image rule

Page-specific concept images define: visual hierarchy, composition, grouping, density, intended polish. However: **global FantasyGM Lab components override generic elements accidentally depicted in concept images.** Example: if a generated concept contains a footer, ignore it — FantasyGM Lab uses the GM orb/navigation system.

## 44. Shared component first

Before creating a new visual component, inspect the project. If equivalent functionality exists: reuse it. If it almost fits: extend it through props/configuration. If it is genuinely global: refactor it into the shared component system. Only create page-specific visual components when they represent genuinely page-specific information.

## 45. No duplicated design systems

Do not create `tradeColors`, `waiverColors`, `matchupTheme`, custom page-specific spacing scales, when equivalent global tokens exist. There should be one FantasyGM theme. Pages consume the theme.

## 46. Global token layer

The shared style/theme layer should define canonical values for: brand colors, semantic colors, surfaces, borders, typography, spacing, radii, shadows/glows, icon sizes, button heights, chip heights, player portrait sizes, page horizontal padding, header dimensions, sticky offsets, modal/sheet dimensions. Use the implementation appropriate to the current stack. Extend existing architecture rather than introducing a parallel styling solution.

## 47. Component variants

Reusability does not mean every component must look identical. Prefer `PlayerIdentity variant="compact"` / `variant="standard"` / `variant="hero"` rather than three unrelated player components. Likewise for buttons, cards, metrics, recommendations, alerts.

## 48. Accessibility

Every redesign must preserve: readable contrast, clear labels, adequate touch targets, semantic selected states, accessible modal dismissal, accessibility labels for icon-only actions. Do not rely solely on color to communicate important meaning.

## 49. Performance

UI polish must not noticeably harm app performance. Prefer lightweight gradients, borders, native shadows, simple transitions. Avoid excessive blur layers, large animated backgrounds, expensive effects, unnecessary rerender-heavy components.

## 50. Redesign workflow

When asked to redesign a page: first inspect the existing screen architecture and global components. Then determine: what the user is trying to accomplish, what information is most important, what hierarchy best supports that, which global components already exist, what genuinely new component is needed. Then implement. Do not begin by changing colors.

## 51. Functionality protection

UI redesign must not casually alter: valuation logic, recommendation logic, rankings, trade algorithms, FAAB calculations, league logic, API behavior, authentication, navigation destinations, subscription logic. Presentation should be separable from business logic. If UI work exposes an existing business-logic bug, identify it rather than silently rewriting unrelated systems.

## 52. Definition of done

A UI task is not complete simply because the screen renders. Before finishing: inspect the screen at realistic mobile dimensions, verify safe-area behavior, verify scrolling, verify sticky controls, verify GM orb clearance, verify long names/text, verify missing-data states, verify player/status variants, verify shared-component reuse, run relevant type/lint/build/tests, fix regressions introduced by the redesign.

## 53. Final principle

Every FantasyGM Lab screen should answer: **what does the user need to understand or decide here?** Make that obvious first. Everything else supports it. The UI should feel sophisticated because it knows what matters — not because it contains more boxes, more neon, or more decoration.

**One app. One design language. One component system. No generic footer. Keep the GM orb. Actionable intelligence before raw information.**
