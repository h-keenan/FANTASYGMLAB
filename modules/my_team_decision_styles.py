"""My Team decision-first IA styles — route-owned, not APP_CSS."""

MY_TEAM_DECISION_CSS = """
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
