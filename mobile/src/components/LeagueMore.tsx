import React from 'react';
import { View } from 'react-native';

import CompactModule from './CompactModule';
import DashboardGuessCard from './DashboardGuessCard';
import { ExpandRow } from './ExpandRow';
import LeaguePulseCard from './LeaguePulseCard';
import { leaguePulseHighlights } from '../lib/leaguePulse';
import type { TeamRanking } from '../lib/api';

/**
 * League activity and Guess the Player, collapsed to ONE line each, on the League tab (they are league color and play, not
 * decisions, so they no longer sit on Today). A line opens its full card. Web twin: components/LeagueMore.tsx.
 */
export default function LeagueMore({ teams, leagueId, leagueName, onOpenRecap }: { teams: TeamRanking[] | null | undefined; leagueId: string; leagueName: string; onOpenRecap: () => void }) {
  const hasActivity = Boolean(teams && leaguePulseHighlights(teams).length > 0);
  return (
    <CompactModule
      id="league.more"
      title="League extras"
      testID="league-more"
      tone="muted"
      parts={[
        ...(hasActivity ? [{ key: 'a', text: 'League activity' }] : []),
        { key: 'g', text: 'Mini-game' },
      ]}
    >
      <View testID="more-rows">
        {hasActivity && teams ? (
          <ExpandRow label="League activity" title="League activity" caption="Most active manager, streaks" testID="more-league-activity">
            <LeaguePulseCard teams={teams} leagueId={leagueId} leagueName={leagueName} onPress={onOpenRecap} />
          </ExpandRow>
        ) : null}
        <ExpandRow label="Guess the Player" title="Guess the Player" caption="Today's round" testID="more-guess-player">
          <DashboardGuessCard />
        </ExpandRow>
      </View>
    </CompactModule>
  );
}
