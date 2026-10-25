import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import LeaguePulseCard from './LeaguePulseCard';
import TodayHero from './TodayHero';
import { useDensity } from '../context/DensityContext';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  SAMPLE_BLOCKED_MESSAGE,
  SAMPLE_DASHBOARD_NOTE,
  SAMPLE_LEAGUE_NAME,
} from '../lib/sampleLeague';
import {
  SAMPLE_DASHBOARD_LEAGUE_ID,
  sampleDashboardItems,
  samplePulseTeams,
  sampleTeamSnapshot,
  sampleThisWeek,
} from '../lib/sampleDashboard';
import {
  BriefingCard,
  DashboardStatStrip,
  TeamSnapshotRow,
  WatchlistAlertsSection,
  type DashboardNavigation,
} from '../screens/DashboardScreen';
import { spacing, type ThemeColors } from '../theme';

/**
 * The real Dashboard modules (Today hero, rank strip, Watchlist & Alerts,
 * League Activity, Team Snapshot) fed static fictional data. Navigation is a
 * stub that only reports a blocked tap; nothing is fetched, stored or tracked.
 * Web twin: DashboardContent's `sample` mode.
 */
export default function SampleDashboard() {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { showExplanations } = useDensity();
  const [blocked, setBlocked] = React.useState(false);
  const items = useMemo(sampleDashboardItems, []);
  const thisWeek = useMemo(sampleThisWeek, []);
  const snapshot = useMemo(sampleTeamSnapshot, []);
  const pulseTeams = useMemo(samplePulseTeams, []);
  const block = () => setBlocked(true);
  const navigation = useMemo(
    () => ({ navigate: () => setBlocked(true) }) as unknown as DashboardNavigation,
    [],
  );
  const leagueId = SAMPLE_DASHBOARD_LEAGUE_ID;
  const leagueName = SAMPLE_LEAGUE_NAME;
  const topPriority = items.filter((item) => item.category === 'top_priority');
  const watchItems = items.filter((item) => item.category !== 'top_priority');

  return (
    <View style={styles.wrap} testID="sample-dashboard">
      <AppText style={styles.note}>{SAMPLE_DASHBOARD_NOTE}</AppText>
      {blocked ? (
        <AppText style={styles.blocked} accessibilityRole="alert" testID="sample-blocked">
          {SAMPLE_BLOCKED_MESSAGE}
        </AppText>
      ) : null}
      <TodayHero
        thisWeek={thisWeek}
        items={topPriority}
        leagueId={leagueId}
        leagueName={leagueName}
        onNavigate={block}
        renderCard={(item, index) => (
          <BriefingCard
            key={`top-priority-${index}`}
            item={item}
            leagueId={leagueId}
            leagueName={leagueName}
            navigation={navigation}
            isNew={false}
            showExplanations={showExplanations}
          />
        )}
      />
      <DashboardStatStrip snapshot={snapshot} leagueId={leagueId} leagueName={leagueName} navigation={navigation} />
      <WatchlistAlertsSection
        snapshot={snapshot}
        items={watchItems}
        leagueId={leagueId}
        leagueName={leagueName}
        navigation={navigation}
        newRecommendationIds={new Set<string>()}
        showExplanations={showExplanations}
      />
      <LeaguePulseCard teams={pulseTeams} onPress={block} />
      <TeamSnapshotRow snapshot={snapshot} />
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { gap: spacing.md },
    note: { fontSize: 12, color: colors.textSecondary, lineHeight: 16 },
    blocked: { fontSize: 12, fontWeight: '700', color: colors.accent },
  });
}
