# Accessibility audit, 2026-11

Scope: owner-approved pass over web-next and the Expo app. Verification is static plus headless Chromium only (no device, no VoiceOver / TalkBack run). Findings marked "fixed" shipped in the same PR.

## Automated checks added

| Check | Where | What it fails on |
| --- | --- | --- |
| axe-core on Today, Team, Trades, Matchup, Waivers, GM Plan at 390px | `route-overflow` CI job, `AXE=1 node scripts/sim_layout_playwright/module_scan.mjs` | any serious / critical WCAG 2.0/2.1 A/AA violation |
| App icon-only pressables | `scripts/check_app_a11y_labels.mjs` (`lib-twins` job) | a Pressable / PressableScale / Touchable* whose children are only an icon and that has no `accessibilityLabel` |
| Reduce Motion | `scripts/check_motion_usage.mjs` (existed, now also in `lib-twins`) | an animation without a reduced-motion path |
| Onboarding copy | `scripts/check_onboarding_copy.mjs` | em-dash in onboarding / experience copy |

Local: `LARGE=1 LARGE_PCT=200 GUARD=1 OVERFLOW=1 node scripts/sim_layout_playwright/module_scan.mjs` re-runs the layout guard with the root font at 200% (`LARGE_PCT` is new; default stays 125).

## Fixed (P0/P1)

1. **P1, web, keyboard**: the header ribbon (`.shell-header-ribbon-inner`, ShellHeader and SimGameHeader) scrolls sideways but was not focusable (axe `scrollable-region-focusable`, serious, every page). Now `tabIndex={0}`.
2. **P1, web, dialogs**: `PopupShell` and `StoryCarousel` were `aria-modal` dialogs with Escape and focus-in/restore but no Tab trap, so keyboard focus could leave behind the dialog. Both now use the new `lib/focusTrap.ts` (same logic as `ui/Sheet`). `ui/Sheet`, `PlayerQuickView` and `TradePickerSheet` already trapped, closed on Escape and restored focus.
3. **P1, web, live region**: Matchup win % and margin updated silently. The status block is now `role="status"` (polite).
4. **P1, app, VoiceOver**: four icon-only or label-less pressables had no accessibility label: All Awards close, Trade idea "Why this works" close, league rename pencil, and the season-stats header (now labelled, `expanded` state). The two close buttons and the pencil also get `hitSlop` 12 so the target is >= 44pt (was 38pt).
5. **P1, 200% text**: Today matchup card (kicker truncated with an ellipsis, "projected" caption pushed 21px past the card), team hero badge ("Win-Now Contender" past the card), Waivers top-target FAAB range, Sim home waiver rows (player chip squeezed to 37px) now wrap instead of overflowing.
6. **P1, onboarding (separate PR #2072)**: level step cards had doubled padding and the content was top-aligned; tightened and centered on web, same spacing on the app.

## Checked, no change needed

- Contrast, dark: muted text `#a8adb7` is 9.3:1 on the page and 4.5:1 on the raised glass surface; secondary 8.2:1+; accent 7.0:1+; warning 4.7:1.
- Contrast, light: every text token is >= 5.4:1 on the page and 7.1:1 on white.
- axe color-contrast reports nothing on the six routes (axe cannot resolve contrast through `backdrop-filter`, so it lands as "incomplete"; the numbers above are computed from the tokens).
- Layout guard (controls >= 44px, no clipping) clean at 390px and 125% text on Today, Team, Trades, Matchup, Waivers and GM Plan (one cosmetic offscreen marker on Trades); other widths not run.
- Web sheets: `ui/Sheet` has `role="dialog"`, `aria-modal`, Tab trap, Escape, restores focus to the trigger.
- Reduce Motion: web has 28 `prefers-reduced-motion` blocks, app 90 `reduceMotion` uses, guard green.

## Left (P2 and notes)

- **Danger red text on glass (dark mode)**: `--color-danger #ef4444` is about 3.8:1 on `--color-surface-primary` and 2.7:1 on the raised surface, under AA for small text (fine for icons and large text). Fix is a token change (`modules/design_tokens.py`, `mobile/src/theme.ts`, `globals.css`, the share-card tokens and their tests): add a lighter danger-text token (`#f87171` is 5.4:1) and use it for text only. Also success `#22c55e` is 4.45:1 on the raised surface (just under).
- **200% root font, bottom tab bar** overflows the viewport by 15-40px (rem insets plus five tabs). Synthetic: iOS text size does not change px layout, so real impact is Android font scale and desktop zoom. Needs the tab bar insets moved to px or `min()`.
- **200% root font, long names** (Sim home "Colton Rhodes Jr.", waiver "Strong Opportunity" chips) still break into many lines; they no longer overflow except on the Sim home player rows (407 vs 390px).
- `ui/Sheet`'s Tab-trap code is duplicated in `lib/focusTrap.ts`; fold Sheet onto the helper next time it is touched.
- Not covered by axe: sheets (PQV, GM orb), Sim home, Account, signed-out landing. Add routes when the fixtures allow; each extra route costs about 5s in CI.
- App: no automated check for `accessibilityRole` on tab rows or `accessibilityState` on toggles; the scan only covers labels on icon-only pressables. The orb and avatar labels were not audited in this pass.
- No VoiceOver / TalkBack or physical Dynamic Type run was possible.

**Update (dark danger/success contrast):** dark `--color-danger` `#ef4444` -> `#ff9090` (2.69:1 -> 4.66:1 on `--color-surface-raised` `#3d4248`; 4.24 -> 7.04 on surface-primary) and `--color-success` `#22c55e` -> `#25cc61` (4.45 -> 4.77:1 on raised). Same hue family; soft fills unchanged; light-mode values unchanged. Verdict text stays neutral (#2034); colour is on chips only.
