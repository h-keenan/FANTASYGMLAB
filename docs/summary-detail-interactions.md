# DynastyGM Summary-to-Detail Interactions

DynastyGM uses three levels of detail:

1. **Page summary** for fast scanning and the next decision.
2. **Inline disclosure** for a short explanation that belongs directly to one item.
3. **Modal detail** for structured supporting context that would otherwise make the
   page materially denser.

## Inline disclosure reference

Trade Hub's `Why this trade` control is the production reference. It uses a native
tertiary button, visible closed/open chevrons, a stable hashed trade-and-surface
key, card-local session state, a 44px touch target, and lazy content rendering.
It remains local to `modules/trade_hub_ui.py`; extracting it without a second
consumer would add abstraction without reuse.

Inline disclosure is appropriate when:

- the explanation is short;
- it belongs to exactly one nearby card;
- seeing it alongside the card improves comprehension;
- opening it should not interrupt the current scan.

## Canonical modal

`modules/ui_modal.py` owns the modal shell and content contract:

- frozen `ModalContent`, `ModalSection`, and `ModalListItem` values;
- a visible Streamlit dialog title;
- large, dismissible, focus-managed public `st.dialog` behavior;
- escaped text-only content;
- one summary, optional labeled sections, optional supporting rows, and an
  optional footer;
- a stable `dg_modal_` structural key namespace that cannot collide with
  Trade Hub's `trade_why_` disclosure state.

Modal detail is appropriate when:

- the page already has a useful compact summary;
- supporting context contains several labeled parts or comparison rows;
- inline expansion would create excessive page length;
- the detail does not need to remain visible while comparing adjacent cards.

Do not use a modal for required first-use guidance, primary navigation, a short
one-sentence explanation, or business logic that changes the underlying result.

## Production proof

Only Premium Dashboard League Pulse summary tiles use the canonical modal in this
phase. Their existing values, notes, explanations, and supporting rows are adapted
without recalculation. Every other summary-tile consumer retains the legacy dialog
renderer until migrated and validated intentionally.
