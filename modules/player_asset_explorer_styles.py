"""Token-backed responsive styles for the unified Player & Asset Explorer.

Pick/result row geometry is owned by dense_list_styles. This module keeps
filter/control chrome only.
"""

PLAYER_ASSET_EXPLORER_CSS = """
div[class*="st-key-player_asset_explorer_"] button,
div[class*="st-key-player_asset_explorer_"] input {
    border-radius: var(--radius-control) !important;
    min-height: var(--touch-target-min);
}

div[class*="st-key-player_asset_explorer_"] [data-testid="stPills"] {
  flex-wrap: wrap;
  gap: var(--space-xs);
}

div[class*="st-key-player_asset_explorer_"] [data-testid="stPills"] button {
    border-radius: var(--radius-segment) !important;
    font-size: var(--font-size-badge) !important;
    white-space: nowrap;
}
""".strip()
