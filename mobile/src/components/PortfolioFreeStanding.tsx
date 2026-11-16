import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import DashboardStatRow from './DashboardStatRow';
import SectionHeading from './SectionHeading';
import ToneBadge from './ToneBadge';
import { api, type TeamSnapshot } from '../lib/api';
import { getLastLeague, type LastLeague } from '../lib/lastLeague';
import { formatRank } from '../lib/percentile';
import { PORTFOLIO_FREE_HEADING, PORTFOLIO_LOCKED_HEADING, PORTFOLIO_LOCKED_ROWS, portfolioRecordText } from '../lib/portfolioFree';
import { TERMS } from '../lib/terms';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

/**
 * Portfolio's Free state (twin of web PortfolioFreeStanding): the one saved league's real standing from the same Today
 * snapshot, then the Pro part locked and named. Renders nothing until the standing loads; the upsell card below it is
 * always the fallback.
 */
export default function PortfolioFreeStanding() {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [league, setLeague] = useState<LastLeague | null>(null);
  const [snapshot, setSnapshot] = useState<TeamSnapshot | null>(null);
  useEffect(() => {
    let cancelled = false;
    getLastLeague()
      .then(async (last) => {
        if (!last || cancelled) return;
        const dashboard = await api.getLeagueDashboard(last.leagueId);
        if (cancelled) return;
        setLeague(last);
        setSnapshot(dashboard.team_snapshot ?? null);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  if (!league || !snapshot) return null;
  return (
    <AccentCard accent={colors.accent} style={styles.card}>
      <SectionHeading title={PORTFOLIO_FREE_HEADING} caption={league.leagueName} />
      <DashboardStatRow
        items={[
          { label: 'Record', value: portfolioRecordText(snapshot) },
          { label: TERMS.thisSeason, value: formatRank(snapshot.power_rank, snapshot.power_rank_tied), why: 'power_rank' },
          { label: TERMS.longTerm, value: formatRank(snapshot.franchise_rank, snapshot.franchise_rank_tied), why: 'franchise_rank' },
        ]}
      />
      <View style={styles.lockedHead}>
        <AppText style={styles.lockedTitle}>{PORTFOLIO_LOCKED_HEADING}</AppText>
        <ToneBadge label="Pro" color={colors.premium} size="xs" />
      </View>
      {PORTFOLIO_LOCKED_ROWS.map((row) => (
        <AppText key={row} style={styles.lockedRow}>
          {row}
        </AppText>
      ))}
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: { gap: spacing.sm },
    lockedHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    lockedTitle: { fontSize: 12, fontWeight: '800', letterSpacing: 0.5, textTransform: 'uppercase', color: colors.textTertiary },
    lockedRow: { minHeight: 36, fontSize: 14, color: colors.textSecondary },
  });
}
