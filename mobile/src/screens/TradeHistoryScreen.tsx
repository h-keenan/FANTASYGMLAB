import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import AnimatedCard from '../components/AnimatedCard';
import AppText from '../components/AppText';
import BrandedSpinner from '../components/BrandedSpinner';
import EmptyState from '../components/EmptyState';
import GridBackground from '../components/GridBackground';
import ScreenInfoNote from '../components/ScreenInfoNote';
import { api, type PastTradeOutcome, type TradeOutcomeAnswer } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'TradeHistory'>;

const OUTCOME_LABEL: Record<Exclude<TradeOutcomeAnswer, 'still_pending'>, string> = {
  yes: 'Made it',
  no: "Didn't make it",
  didnt_send: "Didn't send",
};

const VERDICT_ICON: Record<string, React.ComponentProps<typeof Ionicons>['name']> = {
  worked_out: 'trending-up',
  didnt_pan_out: 'trending-down',
  mixed: 'swap-vertical',
  neutral: 'remove',
};

/**
 * Trade History — the quiet, pull-based home for Trade Outcomes' "did it
 * actually work?" follow-up. Reachable from More only (same "standalone,
 * not embedded in a flow the user didn't choose" placement TeamStanceScreen
 * already uses), by design: coridian_'s brief was explicit that this real
 * before/after comparison should be visible if a user goes looking, never
 * pushed at them — no new popup, no new push notification, no badge/dot
 * anywhere prompting a visit. This screen is the entire surface for it.
 *
 * Every row here already exists as a trade_outcomes record (the existing
 * "did this happen?" loop — modules.push_triggers /
 * TradeOutcomePrompt.tsx); this screen just also renders whichever quiet
 * result modules.trade_outcome_results's sweep has computed so far. A
 * confirmed ('yes') trade with nothing computed yet, or with a real but
 * inconclusive read, simply shows no result section — never a fake
 * "checking..." placeholder promising something not yet decided.
 */
export default function TradeHistoryScreen({ navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);

  const [outcomes, setOutcomes] = useState<PastTradeOutcome[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (isRefresh: boolean) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const result = await api.getTradeOutcomeHistory();
      setOutcomes(result.outcomes);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load Trade History.');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load(false);
  }, [load]);

  if (loading) {
    return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  }

  return (
    <View style={styles.root}>
      <GridBackground />
      <FlatList
        style={styles.container}
        data={outcomes ?? []}
        keyExtractor={(item) => item.id}
        contentContainerStyle={[styles.content, { paddingTop: headerHeight + spacing.md, paddingBottom: orbClearance }]}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void load(true)} />}
        ListHeaderComponent={
          <ScreenInfoNote text="Trades you've confirmed you made. Once a confirmed trade has had a few weeks to play out, we'll show a real before/after read here — using actual points scored and value trend, never a guess. Nothing here is pushed to you; it only shows up when you check this screen." />
        }
        renderItem={({ item }) => <TradeHistoryRow outcome={item} />}
        ListEmptyComponent={
          !error ? (
            <EmptyState
              icon="swap-horizontal-outline"
              title="No trade history yet"
              subtitle="Answer 'Did this trade happen?' the next time it comes up, and it'll show up here — along with how it worked out, once there's enough real data."
            />
          ) : null
        }
        ListFooterComponent={error ? <AppText style={styles.error}>{error}</AppText> : null}
      />
    </View>
  );
}

function TradeHistoryRow({ outcome }: { outcome: PastTradeOutcome }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const summary = outcome.trade_summary;
  const sendNames = summary.send.map((a) => a.name).join(', ') || 'Nothing';
  const receiveNames = summary.receive.map((a) => a.name).join(', ') || 'Nothing';
  const partner = outcome.partner_team_name || summary.partner_team_name || 'your trade partner';
  const date = formatDate(outcome.shared_at);

  const outcomeTone =
    outcome.outcome === 'yes' ? colors.success : outcome.outcome === 'no' ? colors.textSecondary : colors.textTertiary;
  const outcomeLabel = OUTCOME_LABEL[outcome.outcome] ?? outcome.outcome;

  const result = outcome.outcome === 'yes' ? outcome.result_summary : null;
  const verdict = result && result.status === 'ready' ? result.verdict : null;
  const verdictTone =
    verdict === 'worked_out'
      ? colors.success
      : verdict === 'didnt_pan_out'
        ? colors.danger
        : verdict === 'mixed'
          ? colors.violet
          : colors.textSecondary;

  return (
    <AnimatedCard style={styles.card}>
      <View style={styles.headerRow}>
        <AppText style={styles.partner} numberOfLines={1}>
          {partner}
        </AppText>
        <View style={[styles.outcomeBadge, { backgroundColor: `${outcomeTone}22` }]}>
          <AppText style={[styles.outcomeBadgeText, { color: outcomeTone }]}>{outcomeLabel}</AppText>
        </View>
      </View>
      {date ? <AppText style={styles.date}>{date}</AppText> : null}

      {/* Primary insight first when there is one — the real "did it work?"
          read outranks the plain trade summary below it, per the app's
          hierarchy rule of leading with the conclusion. */}
      {verdict && result ? (
        <View style={[styles.verdictRow, { borderColor: `${verdictTone}55`, backgroundColor: `${verdictTone}14` }]}>
          <Ionicons name={VERDICT_ICON[verdict] ?? 'remove'} size={16} color={verdictTone} />
          <View style={styles.verdictTextGroup}>
            <AppText style={[styles.verdictLabel, { color: verdictTone }]}>{result.verdict_label}</AppText>
            <AppText style={styles.verdictDetail}>{verdictDetailText(result)}</AppText>
          </View>
        </View>
      ) : null}

      <View style={styles.exchangeGroup}>
        <AppText style={styles.exchangeLabel}>You sent</AppText>
        <AppText style={styles.exchangeValue}>{sendNames}</AppText>
        <AppText style={styles.exchangeLabel}>You received</AppText>
        <AppText style={styles.exchangeValue}>{receiveNames}</AppText>
      </View>
    </AnimatedCard>
  );
}

function verdictDetailText(result: PastTradeOutcome['result_summary']): string {
  if (!result) return '';
  const parts: string[] = [];
  if (result.production) {
    const avg = result.production.avg_net_per_week;
    const sign = avg > 0 ? '+' : '';
    parts.push(`${sign}${avg.toFixed(1)} PPR pts/wk edge since the trade`);
  }
  if (result.value) {
    const net = result.value.net_delta_pct;
    const sign = net > 0 ? '+' : '';
    parts.push(`${sign}${net.toFixed(0)}% value trend edge`);
  }
  return parts.join(' · ');
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '';
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return '';
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: colors.background },
    container: { flex: 1, backgroundColor: 'transparent' },
    center: { flex: 1, backgroundColor: colors.background },
    content: { paddingHorizontal: spacing.lg, gap: spacing.md },
    error: { color: colors.danger, textAlign: 'center', marginTop: spacing.md },
    card: { padding: spacing.md, gap: spacing.xs },
    headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    partner: { fontSize: 15, fontWeight: '700', color: colors.textPrimary, flexShrink: 1 },
    outcomeBadge: { borderRadius: radii.sm, paddingHorizontal: spacing.sm, paddingVertical: 3 },
    outcomeBadgeText: { fontSize: 11, fontWeight: '700' },
    date: { fontSize: 12, color: colors.textTertiary },
    verdictRow: {
      flexDirection: 'row',
      alignItems: 'flex-start',
      gap: spacing.sm,
      borderWidth: StyleSheet.hairlineWidth,
      borderRadius: radii.md,
      padding: spacing.sm,
      marginTop: spacing.xs,
    },
    verdictTextGroup: { flexShrink: 1, gap: 2 },
    verdictLabel: { fontSize: 13, fontWeight: '700' },
    verdictDetail: { fontSize: 12, color: colors.textSecondary },
    exchangeGroup: { marginTop: spacing.xs, gap: 2 },
    exchangeLabel: { fontSize: 11, fontWeight: '700', color: colors.textTertiary, marginTop: spacing.xs },
    exchangeValue: { fontSize: 13, color: colors.textPrimary },
  });
}
