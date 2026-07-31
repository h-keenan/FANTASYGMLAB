# Automatic UI validation and delivery

`Delivery Validation` classifies every pull request, runs the complete Python
safety suite, and adds deterministic Chromium validation when a UI path changes.

## UI path classification

Browser validation is required for:

- `app.py`;
- `modules/*_ui.py` and `modules/*_styles.py`;
- the shared shell, header, style, token, football-asset, HTML-rendering,
  player-card, quick-view, modal, primitive, and workspace modules;
- visual harness and mobile validation scripts;
- UI, visual, responsive, mobile, modal, and shell tests;
- the delivery workflow files themselves.

Other changes receive compile, import, whitespace, focused tests supplied by the
change, the full suite, and existing repository safety tests without installing
or launching Chromium.

## Browser contract

The browser job uses a pinned Playwright release and its pinned compatible
Chromium build. It launches a fixture-only Streamlit application on port 8510,
waits for `/_stcore/health`, and captures Dashboard, League Overview, Trade Hub,
and My Team at 320, 390, and 430 CSS pixels.

The job fails rather than skips on browser startup failure, Streamlit exceptions,
duplicate element keys, horizontal overflow, clipped primary headings,
near-zero-width primary content, unusable critical tap targets, or missing
surface sections. Screenshots and a deterministic JSON report are uploaded as
`ui-mobile-screenshots-<pr>-<sha>`.

## Trusted delivery

PR validation uses a read-only token. After a successful run, a separate
`workflow_run` workflow loaded from trusted `main` marks the PR ready and enables
merge-method auto-merge. Add `human-approval-required` only when the task
explicitly requires human product approval.
