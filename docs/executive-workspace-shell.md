# Executive Workspace Shell

Every authenticated FantasyGM Lab workspace begins with one compact **Executive Command Header**.

The header owns only:

- FantasyGM Lab identity (FGL mark);
- Founder Beta badge;
- the current page title;
- the active league as the War Room;
- compact account, Premium, and alert chips;
- command actions: league switcher, Notification Center, and profile (Feedback lives inside the profile menu).

It deliberately does not own Power Rank, Franchise Rank, Strategy, Archetype, roster summaries, recommendation copy, or page descriptions. Those belong to the Dashboard or the workspace that uses them.

The GM Orb remains the primary full navigation. Header actions complement the Orb and must not duplicate destination navigation.

## Notification Center

The Notification Center is a Founder Beta **shell**, not a full delivery system. It supports categories such as Trades, Waivers, League, Injuries, Live Draft, and Product updates. Deterministic demo notifications ship for Founder Beta; the `NotificationItem` shape is ready for future live events.

## Layout contracts

On mobile, the rendered shell plus command actions must remain at or below 140 pixels at 320, 390, and 430 pixels wide. Desktop uses the same information contract in a **single executive command bar**: identity, page title, War Room league context, account state, alerts, profile (with Feedback), and the league-switch control share one bordered surface rather than separate header bands.

Desktop composition (1024 / 1440 / ultrawide) uses one bounded content max-width with intentional multi-column grids and aligned gutters. Content does not stretch to fill ultrawide viewports.
