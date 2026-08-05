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

The Notification Center is a Founder Beta **executive inbox** — a floating panel roughly 45–60% of the viewport tall, with internal scrolling only. It is not a nested page.

Priority is presentation-only: urgent/action items first and visually dominant, routine league updates quieter, product announcements lowest. Each compact card carries a strong title, one supporting sentence, an optional destination cue, and a secondary timestamp. Category badges stay on the cards; there is no separate category navigation system inside the inbox.

Deterministic demo notifications ship for Founder Beta; the `NotificationItem` shape is ready for later live events.

## Layout contracts

On mobile, the rendered shell plus command actions must remain at or below 140 pixels at 320, 390, and 430 pixels wide. Desktop uses the same information contract in a **single executive command bar**: identity, page title, War Room league context, account state, alerts, profile (with Feedback), and the league-switch control share one bordered surface rather than separate header bands.

Workspace pages should not restack a second page title under the command bar when the executive shell already names the surface.

Desktop composition (1024 / 1440 / ultrawide) uses one bounded content max-width with intentional multi-column grids and aligned gutters. Content does not stretch to fill ultrawide viewports.
