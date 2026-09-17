# Brand source vectors

Source SVGs for the FGL trajectory-arc brand system (cyan/gold/red arcs,
"Plan. Project. Win."), from the FantasyGMLab_PRODUCTION_ASSET_PACK
provided 2026-09-17. These are the editable source files; rasterized
outputs used by the app live directly in `mobile/assets/` (`icon.png`,
`favicon.png`, `android-icon-foreground.png`, `android-icon-monochrome.png`)
via `rsvg-convert`.

`fgl-mark.svg`, `logo-horizontal.svg`, and `logo-stacked.svg` had a bug in
the original pack — every path/circle/polygon's stroke/fill was a literal
`"('#00D4FF', '#FFCA3D', '#FF4D4D')"` string (a Python tuple accidentally
serialized instead of cycling through the three colors), which would have
rendered with no visible stroke/fill at all. Fixed here by assigning each
of the 9 elements (3 paths, 3 circles, 3 polygons) its correct individual
color in order, matching the working pattern already present in
`fgl-symbol.svg`/`app-icon-1024.svg`. Not a redesign — the intended
per-element coloring was unambiguous from the sibling files.

Brand palette: `#00D4FF` (analyze/cyan), `#FFCA3D` (project/gold), `#FF4D4D`
(execute/red), `#0D1117` (background), `#F2F4F7` (text) — matches
`mobile/src/theme.ts`'s existing palette exactly.
