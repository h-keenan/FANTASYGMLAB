import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import TradeSummaryRow from '../components/TradeSummaryRow';
import AppText from '../components/AppText';
import { SkeletonPage } from '../components/Skeleton';
import CompactPlayerModule from '../components/CompactPlayerModule';
import EmptyState from '../components/EmptyState';
import GridBackground from '../components/GridBackground';
import InfoMark from '../components/InfoMark';
import SectionHeading from '../components/SectionHeading';
import SharedTradesFeed from '../components/SharedTradesFeed';
import TrackRecordModule from '../components/TrackRecordModule';
import ValuesCredit from '../components/ValuesCredit';
import { NetEdgeBar } from '../components/TradeOutcomeHeader';
import { api, type PastTradeOutcome, type SharedCommunityTrade, type TradeOutcomeAnswer, type TradeOutcomeAssetSummary } from '../lib/api';
import { tradePointsLine } from '../lib/trackRecordView';
import { isPickAsset, tradeOutcomeChips, tradeValueDelta, tradeVerdictBadge } from '../lib/tradeOutcomeChips';
import { tradeIdeaNamesText } from '../lib/tradeIdeaSummary';
import { abbreviatePlayerName } from '../lib/formatPlayerName';
import { toUserErrorMessage } from '../lib/errorMessages';
import { useLastLeague } from '../lib/useLastLeague';
import { useOrbClearance } from '../lib/orbLayout';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';
import ErrorState from '../components/ErrorState';

type Props = NativeStackScreenProps<RootStackParamList, 'TradeHistory'>;

const OUTCOME_LABEL: Record<Exclude<TradeOutcomeAnswer, 'still_pending'>, string> = {
  yes: 'Made it',
  no: "Didn't make it",
  didnt_send: "Didn't send",
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
  const lastLeague = useLastLeague();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);

  const [outcomes, setOutcomes] = useState<PastTradeOutcome[] | null>(null);
  const [shared, setShared] = useState<{ available: boolean; trades: SharedCommunityTrade[] }>({
    available: false,
    trades: [],
  });
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (isRefresh: boolean) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    // Fail soft: a missing shared-trades table must never break this screen.
    api
      .getSharedCommunityTrades()
      .then((r) => setShared({ available: Boolean(r.available), trades: r.trades }))
      .catch(() => {});
    try {
      const result = await api.getTradeOutcomeHistory();
      setOutcomes(result.outcomes);
    } catch (err) {
      setError(toUserErrorMessage(err, 'Failed to load Trade History.'));
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void load(false);
  }, [load]);

  if (loading) {
    return <SkeletonPage label="Trade History" layout="cards" family="trades" topInset={headerHeight} />;
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
          <View style={styles.headerStack}>
          <SectionHeading
            title="Trade history"
            info={
              <InfoMark
                label="trade history"
                lines={["Trades you've confirmed you made. Once a confirmed trade has had a few weeks to play out, we'll show a real before/after read here. Using actual points scored and value trend, never a guess. Nothing here is pushed to you; it only shows up when you check this screen."]}
              />
            }
          />
          {(outcomes ?? []).length > 0 ? <TrackRecordModule /> : null}
          </View>
        }
        renderItem={({ item }) => <TradeHistoryRow outcome={item} />}
        ListEmptyComponent={
          !error ? (
            <EmptyState
              icon="swap-horizontal-outline"
              title="No trade history yet"
              subtitle="Confirm a trade to see it here."
              actionLabel={lastLeague ? 'Analyze a trade' : undefined}
              onPressAction={
                lastLeague
                  ? () =>
                      navigation.navigate('Trades', {
                        leagueId: lastLeague.leagueId,
                        leagueName: lastLeague.leagueName,
                        initialTab: 'make',
                      })
                  : undefined
              }
            />
          ) : null
        }
        ListFooterComponent={
          <>
            {error ? <ErrorState compact title="Couldn't load Trade History" message={error} onRetry={() => void load(false)} /> : null}
            <SharedTradesFeed
              available={shared.available}
              trades={shared.trades}
              onDelete={(id) => {
                const removed = shared.trades.find((t) => t.id === id);
                setShared((cur) => ({ ...cur, trades: cur.trades.filter((t) => t.id !== id) }));
                // A failed delete must put the trade back (it is still public), not let it vanish until the next reload.
                const restore = () => {
                  if (removed) setShared((cur) => (cur.trades.some((t) => t.id === id) ? cur : { ...cur, trades: [removed, ...cur.trades] }));
                };
                api
                  .deleteSharedCommunityTrade(id)
                  .then((result) => {
                    if (result?.ok === false) restore();
                  })
                  .catch(restore);
              }}
              onReport={(id) => void api.reportSharedCommunityTrade(id).catch(() => {})}
            />
            <ValuesCredit />
          </>
        }
      />
    </View>
  );
}

function TradeHistoryRow({ outcome }: { outcome: PastTradeOutcome }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const summary = outcome.trade_summary;
  const partner = outcome.partner_team_name || summary.partner_team_name || 'your trade partner';
  const date = formatDate(outcome.shared_at);

  const outcomeLabel = OUTCOME_LABEL[outcome.outcome] ?? outcome.outcome;

  const result = outcome.outcome === 'yes' ? outcome.result_summary : null;
  const verdict = result && result.status === 'ready' ? result.verdict : null;
  const netPct = result && result.status === 'ready' ? (result.value?.net_delta_pct ?? null) : null;
  const netPts = result && result.status === 'ready' ? (result.production?.net_points_ppr ?? null) : null;
  // Per-trade outcome card: real PPR points for you since the trade (free; the sweep already computed it).
  const pointsLine = outcome.outcome === 'yes' ? tradePointsLine(result) : null;
  const names = (xs: TradeOutcomeAssetSummary[]) => tradeIdeaNamesText(xs.map((x) => abbreviatePlayerName(x.name)));
  const people = (xs: TradeOutcomeAssetSummary[], side: string) =>
    xs.map((x, i) => ({ key: `${side}${i}`, playerId: x.player_id || null, name: x.name, position: x.position, isPick: isPickAsset(x) }));
  const sent = names(summary.send);
  const received = names(summary.receive);

  return (
    <TradeSummaryRow
      partner={partner}
      send={people(summary.send, 's')}
      receive={people(summary.receive, 'r')}
      swapText={sent && received ? `${sent} for ${received}` : ''}
      chips={tradeOutcomeChips({ outcomeLabel, netPts })}
      verdict={result && verdict ? tradeVerdictBadge(verdict, result.verdict_label) : null}
      delta={tradeValueDelta(netPct)}
      date={date}
    >
      {pointsLine ? <AppText style={styles.pointsLine}>{pointsLine}</AppText> : null}
      {verdict && result ? (
        <View style={styles.verdictTextGroup}>
          <AppText style={styles.verdictLabel}>{result.verdict_label}</AppText>
          <AppText style={styles.verdictDetail}>{verdictDetailText(result)}</AppText>
        </View>
      ) : null}
      {netPct !== null ? <NetEdgeBar netPct={netPct} leftLabel="Partner ahead" rightLabel="You ahead" /> : null}
      <View style={styles.exchangeGroup}>
        <AppText style={styles.exchangeLabel}>You sent</AppText>
        <AssetList assets={summary.send} />
        <AppText style={styles.exchangeLabel}>You received</AppText>
        <AssetList assets={summary.receive} />
      </View>
    </TradeSummaryRow>
  );
}

/**
 * Real player identity for each asset instead of a plain "You sent: Name,
 * Name" string — every entry here is a real tracked player (draft picks are
 * excluded before a trade share is ever recorded; see
 * TradeSharePreviewModal.recordShare / TradeHubScreen.shareAssetsToPlayers),
 * so the shared compact module always has a genuine player identity to
 * show, not a fabricated one. `value_score` is the value visible on screen
 * at share time — shown as trailing context, same "VALUE" convention
 * Dashboard's injury-impact rows already use, never overriding the verdict
 * above as the row's primary read.
 */
function AssetList({ assets }: { assets: TradeOutcomeAssetSummary[] }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (assets.length === 0) {
    return <AppText style={styles.exchangeValue}>Nothing</AppText>;
  }
  return (
    <View style={styles.assetGroup}>
      {assets.map((asset, index) => (
        <CompactPlayerModule
          key={`${asset.player_id || asset.name}-${index}`}
          playerId={asset.player_id || null}
          name={asset.name}
          position={asset.position}
          value={asset.value_score}
          valueLabel="VALUE"
        />
      ))}
    </View>
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
    root: { flex: 1, backgroundColor: 'transparent' },
    container: { flex: 1, backgroundColor: 'transparent' },
    center: { flex: 1, backgroundColor: 'transparent' },
    content: { paddingHorizontal: spacing.lg, gap: spacing.md },
    error: { color: colors.danger, textAlign: 'center', marginTop: spacing.md },
    card: { padding: spacing.md, gap: spacing.xs },
    headerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    partner: { fontSize: 16.5, fontWeight: '700', color: colors.textPrimary, flexShrink: 1, flexGrow: 1 },
    outcomeBadge: { borderRadius: radii.sm, paddingHorizontal: spacing.sm, paddingVertical: 3 },
    outcomeBadgeText: { fontSize: 12.5, fontWeight: '700' },
    date: { fontSize: 13.5, color: colors.textTertiary },
    headerStack: { gap: spacing.md },
    pointsLine: { fontSize: 15, fontWeight: '700', color: colors.textPrimary, marginTop: spacing.xs },
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
    verdictLabel: { fontSize: 14.5, fontWeight: '700', color: colors.textPrimary },
    verdictDetail: { fontSize: 13.5, color: colors.textSecondary },
    exchangeGroup: { marginTop: spacing.xs, gap: 2 },
    exchangeLabel: { fontSize: 12.5, fontWeight: '700', color: colors.textTertiary, marginTop: spacing.xs },
    exchangeValue: { fontSize: 14.5, color: colors.textPrimary },
    assetGroup: { gap: spacing.xs, marginTop: 2 },
  });
}
