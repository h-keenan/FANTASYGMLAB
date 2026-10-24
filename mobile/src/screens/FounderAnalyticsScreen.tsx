import React, { useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { useHeaderHeight } from '@react-navigation/elements';
import { useIsRestoring, useQuery } from '@tanstack/react-query';

import AnimatedCard from '../components/AnimatedCard';
import AppText from '../components/AppText';
import BrandedSpinner from '../components/BrandedSpinner';
import ErrorState from '../components/ErrorState';
import GridBackground from '../components/GridBackground';
import SectionHeading from '../components/SectionHeading';
import SegmentedTabBar from '../components/SegmentedTabBar';
import { useAuth } from '../context/AuthContext';
import { useThemeMode } from '../context/ThemeModeContext';
import { api, FOUNDER_ANALYTICS_WINDOWS } from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
import {
  errorRows,
  featureUseRows,
  funnelRows,
  funnelSummary,
  isFounderSession,
  moduleRows,
  namedCountRows,
  performanceRows,
  platformLine,
  storageBadge,
  summaryTiles,
  type FounderRow,
} from '../lib/founderAnalytics';
import { useOrbClearance } from '../lib/orbLayout';
import { queryKeys } from '../lib/queryKeys';
import { radii, spacing, type ThemeColors } from '../theme';

const WINDOW_LABELS: Record<string, string> = { '24h': '24h', '7d': '7 days', '30d': '30 days', all: 'All' };

/**
 * Founder-only internal product analytics, the mobile twin of web-next's
 * /founder-analytics. Pure presentation over GET /v1/founder/analytics
 * (modules.founder_analytics.build_report); nothing is recomputed here. The
 * `isFounderSession` check only hides/bounces the UI: the endpoint itself
 * returns 403 for any caller without the server-issued founder_ops claim.
 */
export default function FounderAnalyticsScreen() {
  const navigation = useNavigation();
  const { session, loading } = useAuth();
  const founder = isFounderSession(session);
  const headerHeight = useHeaderHeight();
  const orbClearance = useOrbClearance();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [windowKey, setWindowKey] = useState('7d');
  const isRestoring = useIsRestoring();

  useEffect(() => {
    if (!loading && !founder && navigation.canGoBack()) navigation.goBack();
  }, [loading, founder, navigation]);

  const query = useQuery({
    queryKey: queryKeys.founderAnalytics(windowKey),
    queryFn: ({ signal }) => api.getFounderAnalytics(windowKey, signal),
    enabled: founder && !isRestoring,
  });

  if (loading || !founder) return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;

  const report = query.data?.report ?? null;

  const rows = (items: FounderRow[], empty: string, valueColor?: string) =>
    items.length === 0 ? (
      <AppText style={styles.muted}>{empty}</AppText>
    ) : (
      <AnimatedCard disabled style={styles.listCard}>
        {items.map((row, i) => (
          <View key={row.key} style={[styles.row, i > 0 && styles.rowDivider]}>
            <AppText style={styles.rowLabel}>{row.label}</AppText>
            <AppText style={[styles.rowValue, valueColor ? { color: valueColor } : null]}>{row.value}</AppText>
          </View>
        ))}
      </AnimatedCard>
    );

  let body: React.ReactNode;
  if (query.isError && !report) {
    body = <ErrorState message={toUserErrorMessage(query.error, 'Could not load Founder Analytics.')} onRetry={() => void query.refetch()} />;
  } else if (!report) {
    body = <BrandedSpinner style={styles.inlineSpinner} />;
  } else {
    const storage = storageBadge(report.storage);
    const storageColor = storage.durable ? colors.success : colors.premium;
    const funnel = funnelSummary(report);
    const platforms = platformLine(report);
    const features = featureUseRows(report);
    body = (
      <>
        <AnimatedCard disabled style={{ ...styles.storage, borderColor: storageColor }}>
          <AppText style={[styles.storageTitle, { color: storageColor }]}>{storage.title}</AppText>
          <AppText style={styles.body}>{report.storage.scope_label}</AppText>
          <AppText style={styles.muted}>{storage.detail}</AppText>
        </AnimatedCard>

        {report.unavailable.map((note, i) => (
          <AppText key={i} style={styles.note}>
            {note}
          </AppText>
        ))}

        <View style={styles.tiles}>
          {summaryTiles(report).map((tile) => (
            <AnimatedCard key={tile.key} disabled style={styles.tile}>
              <AppText style={styles.tileValue}>{tile.value}</AppText>
              <AppText style={styles.muted}>{tile.label}</AppText>
            </AnimatedCard>
          ))}
        </View>

        <SectionHeading title="Feature adoption" />
        {rows(moduleRows(report), 'No feature-adoption events in this window.')}
        {platforms ? <AppText style={styles.muted}>{platforms}</AppText> : null}

        {features.length > 0 ? (
          <>
            <SectionHeading title="Feature use (web + mobile)" />
            {rows(features, '')}
          </>
        ) : null}

        {funnel ? (
          <>
            <SectionHeading title="Onboarding funnel" />
            <AppText style={styles.muted}>{funnel}</AppText>
            {rows(funnelRows(report), '')}
          </>
        ) : null}

        {report.espn_import_outcomes && report.espn_import_outcomes.total_failed > 0 ? (
          <>
            <SectionHeading title="ESPN import outcomes" />
            <AppText style={styles.muted}>
              {`${report.espn_import_outcomes.total_failed.toLocaleString('en-US')} failed attempts · private ${report.espn_import_outcomes.espn_private} (${report.espn_import_outcomes.private_pct}%) · not found ${report.espn_import_outcomes.espn_not_found} · ESPN error ${report.espn_import_outcomes.espn_error}`}
            </AppText>
          </>
        ) : null}

        <SectionHeading title="Decision engagement" />
        {rows(namedCountRows(report.decision_engagement), 'No events recorded in this window.')}

        <SectionHeading title="Premium funnel" />
        {rows(namedCountRows(report.premium), 'No events recorded in this window.')}
        {Object.keys(report.checkout_intervals).length > 0 ? (
          <AppText style={styles.muted}>
            {`Checkout starts by interval: ${Object.entries(report.checkout_intervals)
              .map(([k, c]) => `${k} (${c.toLocaleString('en-US')})`)
              .join(', ')}`}
          </AppText>
        ) : null}

        <SectionHeading title="Errors" />
        {rows(errorRows(report), 'No errors recorded in this window.', colors.danger)}
        <AppText style={styles.muted}>
          {`${report.error_sessions.toLocaleString('en-US')} session${report.error_sessions === 1 ? '' : 's'} saw at least one error.`}
        </AppText>

        {Object.keys(report.performance).length > 0 ? (
          <>
            <SectionHeading title="Performance (ms)" />
            {rows(performanceRows(report), '')}
          </>
        ) : null}

        {report.partial_notes.map((note, i) => (
          <AppText key={i} style={styles.muted}>
            {note}
          </AppText>
        ))}
      </>
    );
  }

  return (
    <View style={[styles.root, { paddingTop: headerHeight }]}>
      <GridBackground />
      <ScrollView contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>
        <AppText style={styles.muted}>
          {`Internal product usage${report ? ` for ${report.window_label.toLowerCase()}` : ''}. Visible only to founder accounts.`}
        </AppText>
        <SegmentedTabBar
          options={FOUNDER_ANALYTICS_WINDOWS.map((w) => ({ key: w.value, label: WINDOW_LABELS[w.value] ?? w.label }))}
          active={windowKey}
          onChange={setWindowKey}
        />
        {body}
      </ScrollView>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: 'transparent' },
    content: { padding: spacing.lg, gap: spacing.md },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
    inlineSpinner: { paddingVertical: spacing.xl },
    muted: { fontSize: 12, color: colors.textTertiary },
    body: { fontSize: 14, color: colors.textSecondary },
    note: {
      fontSize: 13,
      color: colors.textPrimary,
      padding: spacing.sm,
      borderRadius: radii.sm,
      borderWidth: 1,
      borderColor: colors.premium,
    },
    storage: { gap: 4 },
    storageTitle: { fontSize: 12, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.4 },
    tiles: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    tile: { flexGrow: 1, flexBasis: '45%', padding: spacing.md },
    tileValue: { fontSize: 22, fontWeight: '800', color: colors.textPrimary },
    listCard: { padding: 0 },
    row: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      gap: spacing.md,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
    },
    rowDivider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.glassBorder },
    rowLabel: { flexShrink: 1, fontSize: 14, fontWeight: '600', color: colors.textPrimary },
    rowValue: { flexShrink: 1, fontSize: 12, color: colors.textTertiary, textAlign: 'right' },
  });
}
