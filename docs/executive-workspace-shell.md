# Executive Workspace Shell

Every authenticated DynastyGM workspace begins with one compact executive shell.

The shell owns only:

- DynastyGM identity;
- the current page title;
- the active league as the War Room;
- compact account and entitlement state;
- the existing league-switch action.

It deliberately does not own Power Rank, Franchise Rank, Strategy, Archetype, roster summaries, recommendation copy, or page descriptions. Those belong to the Dashboard or the workspace that uses them.

The GM Orb remains the primary full navigation. The integrated league action changes league context using the existing callbacks and persistence path; it does not introduce a second navigation or selector system.

On mobile, the rendered shell plus league control must remain at or below 140 pixels at 320, 390, and 430 pixels wide. Desktop uses the same information contract in a horizontal command-bar composition.
