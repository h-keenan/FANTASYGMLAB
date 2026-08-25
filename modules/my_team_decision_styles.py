"""My Team decision-first IA styles — route-owned, not APP_CSS."""

MY_TEAM_DECISION_CSS = """
div[class*="st-key-my_team_alerted_player_focus"] {
    background: color-mix(in srgb, var(--color-warning) 7%, var(--color-surface));
    border: 1px solid color-mix(in srgb, var(--color-warning) 52%, transparent);
    border-radius: var(--radius-panel);
    padding: var(--space-3);
}
div[class*="st-key-my_team_alerted_player_focus"] .player-support-chip-warning {
    background: color-mix(in srgb, var(--color-warning) 18%, transparent);
    border-color: color-mix(in srgb, var(--color-warning) 55%, transparent);
    color: var(--color-warning);
}
<style>
.my-team-strategy-identity {
    display: flex;
    flex-direction: column;
    gap: var(--space-2xs);
    margin: 0 0 var(--space-sm);
    max-width: 100%;
    min-width: 0;
}
.my-team-strategy-kicker {
    color: var(--color-text-muted);
    font: var(--type-supporting-metadata);
    letter-spacing: var(--letter-spacing-badge);
    text-transform: uppercase;
}
.my-team-strategy-primary {
    color: var(--color-text-primary);
    font: var(--type-section-title);
    letter-spacing: 0.04em;
    text-transform: uppercase;
}
.my-team-strategy-support {
    color: var(--color-text-muted);
    font: var(--type-supporting-metadata);
    line-height: var(--line-height-caption);
    overflow-wrap: anywhere;
}
.my-team-strategy-note {
    color: var(--color-text-muted);
    font: var(--type-supporting-metadata);
    line-height: var(--line-height-caption);
    max-width: 36rem;
}
.st-key-my_team_strategy_gateway [data-testid="stVerticalBlock"] {
    gap: var(--space-xs);
}
.st-key-my_team_strategy_panel {
    margin: 0 0 var(--space-md);
}
.st-key-my_team_roster_decisions .compact-player-row,
.st-key-my_team_roster_decisions .dg-football-asset--dense {
    min-height: 0;
}
div[class*="st-key-my_team_decisions_"] .dg-football-asset,
.st-key-my_team_roster_decisions .dg-football-asset {
    align-items: start;
    grid-template-columns: 4.25rem minmax(0, 1fr);
}
div[class*="st-key-my_team_decisions_"] .dg-player-portrait,
div[class*="st-key-my_team_decisions_"] .dg-football-asset__avatar {
    height: 4.25rem;
    width: 4.25rem;
}
div[class*="st-key-my_team_decisions_"] .dg-player-portrait.dg-tier-frame {
    box-shadow: 0 0 0 2px var(--dg-tier-a), 0 0 8px 1px color-mix(in srgb, var(--dg-tier-a) 48%, transparent);
}
div[class*="st-key-my_team_decisions_"] .dg-football-asset__value {
    grid-column: 2;
    text-align: left;
}
.st-key-my_team_decisions_hold .dg-football-asset__insight,
.st-key-my_team_decisions_untouchables .dg-football-asset__insight {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    overflow: hidden;
}
.st-key-my_team_decisions_drop .dg-football-asset__insight {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 1;
    overflow: hidden;
}
.st-key-my_team_decisions_trade .dg-football-asset__insight {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 3;
    overflow: hidden;
}
.summary-tile-unavailable,
.st-key-my_team_roster_signals .summary-tile-unavailable {
    opacity: 0.58;
}
.summary-tile-unavailable .summary-tile-value {
    color: var(--color-text-muted);
    font-weight: var(--font-weight-body);
}
.st-key-my_team_roster_signals,
.st-key-my_team_roster_decisions {
    margin: 0 0 var(--space-sm);
}
.st-key-my_team_strategy_panel .dg-ui-section-header,
div[class*="st-key-my_team_"] .dg-ui-section-header {
    margin: var(--space-sm) 0 var(--space-xs) !important;
    padding-bottom: var(--space-2xs) !important;
}
@media (max-width: 430px) {
    .my-team-strategy-primary {
        font-size: 1.05rem;
    }
    .st-key-my_team_roster_decisions .dg-football-asset__body {
        min-width: 0;
    }
}
</style>
"""
