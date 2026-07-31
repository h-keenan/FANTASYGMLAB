# DynastyGM Football Asset Framework

## Principle

Every football asset should behave identically throughout DynastyGM. A user
should learn one scan-to-detail interaction and carry it from Dashboard to My
Team, Trade Hub, Waivers, Explorer, Search, News, and future modules.

Players are the first production asset. Rookie picks, future picks, teams,
recommendations, and news remain future extensions; this framework does not
change their domain behavior.

## Player contract

`FootballPlayerAsset` is a frozen presentation model. It accepts resolved
football meaning and never calculates prestige, injury status, value, rank, or
recommendation context. The canonical renderer has three densities (`compact`,
`standard`, and `dense`) and two interaction modes (`read-only` and
`action-enabled`), while retaining one hierarchy:

1. player identity;
2. team and position;
3. prestige;
4. current status;
5. primary football insight;
6. value and quick action.

An action-enabled card carries a stable player identifier and opens the existing
canonical Player Quick View. The component does not own modal state.

## Football primitives

The player implementation formalizes reusable, escaped primitives for:

- prestige indicator and aligned semantic rail;
- injury status;
- position;
- team;
- general status;
- value display.

All geometry and color are provided by semantic design tokens. Injury and
prestige meaning is communicated in text and accessible labels, never by color
alone. Internal rendered slots are trusted component HTML; all model text is
escaped by default.

## Production migration inventory

- Dashboard, My Team, workspace decision cards, Draft Center, and Explorer
  already entered through `player_scan_card_html` or `compact_player_row_html`;
  both now delegate to the canonical football-asset renderer.
- The Waivers position snapshot now uses the same canonical compact player
  renderer. Full waiver recommendation cards remain recommendation containers,
  while their player details continue to open the same Quick View.
- Trade Hub recommendation cards remain recommendation containers. Their player
  tap targets continue to resolve through the same canonical Quick View callback.
- The value injury marker now uses the canonical injury component without
  changing the existing injury-impact decision.
- Player Quick View remains the one shared detail renderer. Its sections,
  disclosures, modal ownership, and entry context are unchanged.

Legacy CSS class names remain on compatibility boundaries during migration.
They are not additional renderers and can be removed only in a later,
visual-regression-backed cleanup.

## Misuse boundaries

- Do not derive football status or value in this module.
- Do not pass unescaped user content through HTML slots.
- Do not create page-specific card hierarchies.
- Do not use list position as player identity.
- Do not add alternate player modal entry points.
- Do not import page modules into the framework.
