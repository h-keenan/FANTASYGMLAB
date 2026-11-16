import React, { useMemo } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import PressableScale from './PressableScale';
import { Ionicons } from '@expo/vector-icons';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useQuery } from '@tanstack/react-query';

import AccentCard from './AccentCard';
import AppText from './AppText';
import OpponentProfileCard from './OpponentProfileCard';
import PickPlate from './PickPlate';
import SectionHeading from './SectionHeading';
import TeamAvatar from './TeamAvatar';
import { TeamSheetFrame, TeamSheetOverview } from './TeamSheet';
import ToneBadge from './ToneBadge';
import { api, type TeamSheetPlayer } from '../lib/api';
import { gradeToneSlug, sampleFill, TENDENCY_SIGNALS, tendencyBadgeText, tendencyTone, tradeDateLabel, type ManagerRecentTradeAsset } from '../lib/managerTendencies';
import { teamSheetNextGameLine, teamSheetPoints, teamSheetSeasonLine, tradeStyleFromSignals, type TeamSheetChip } from '../lib/teamSheet';
import { queryKeys } from '../lib/queryKeys';
import type { OpponentTradeTarget } from '../lib/opponentProfile';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors, scrim } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';
import CompactPlayerCard from './CompactPlayerCard';
import { SkeletonText } from './Skeleton';

interface Props {
  visible: boolean;
  onClose: () => void;
  leagueId: string;
  /** For the "Offer this" Trade Analyzer prefill. */
  leagueName?: string;
  rosterId: string | number;
  teamName: string;
  ownerName?: string | null;
  avatarId?: string | null;
}

/**
 * The Desk team sheet: tapping any team (Teams, Recap, Matchup opponent, Trade Hub partner) opens this with REAL
 * Sleeper data, rendered through the shared TeamSheet the Fantasy Sim team sheet also uses. Record, power rank,
 * strengths/needs, injuries, roster and past seasons are free (GET .../teams/{id}/sheet); the trade-style tag,
 * tendencies and recent trades are Pro (GET .../managers/{id}/tendencies) and show the upsell for Free. Fetches
 * only while open. Twin of web-next's ManagerProfileSheet.
 */
export default function ManagerProfileModal({ visible, onClose, leagueId, leagueName = '', rosterId, teamName, ownerName, avatarId }: Props) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const query = useQuery({
    queryKey: queryKeys.managerTendencyDetail(leagueId, rosterId),
    queryFn: () => api.getManagerTendencyDetail(leagueId, rosterId),
    enabled: visible,
    staleTime: 5 * 60 * 1000,
  });
  const sheetQuery = useQuery({
    queryKey: queryKeys.teamSheet(leagueId, rosterId),
    queryFn: () => api.getTeamSheet(leagueId, rosterId),
    enabled: visible,
    staleTime: 5 * 60 * 1000,
  });
  // Free roster profile (trade angle), independent of the Pro tendencies; a failure just hides the card.
  const profileQuery = useQuery({
    queryKey: queryKeys.teamProfile(leagueId, rosterId),
    queryFn: () => api.getTeamProfile(leagueId, rosterId),
    enabled: visible,
    staleTime: 5 * 60 * 1000,
  });
  const offer = (target: OpponentTradeTarget) => {
    onClose();
    // The target is on this manager's roster: Build an offer builds the package.
    navigation.navigate('TradeOffer', { leagueId, leagueName, playerId: target.player_id });
  };
  const data = query.data;
  const sheet = sheetQuery.data && sheetQuery.data.ok && !sheetQuery.data.reason && sheetQuery.data.record ? sheetQuery.data : null;
  const sheetFailed = sheetQuery.isError || (sheetQuery.data != null && sheet == null);
  const signals = data?.manager?.signals ?? {};
  const toneColors = { success: colors.success, warning: colors.premium, accent: colors.accent, premium: colors.violet };
  const rows = TENDENCY_SIGNALS.filter(([key]) => signals[key]?.status === 'ok');
  const style = data?.is_premium ? tradeStyleFromSignals(signals) : null;

  const upsell = data && !data.is_premium ? (
    <PressableScale
      onPress={() => {
        onClose();
        navigation.navigate('Paywall');
      }}
    >
      <AppText style={styles.upsellTitle}>{data.upsell?.title ?? 'Manager Tendencies'}</AppText>
      <AppText style={styles.upsellCta}>Upgrade</AppText>
    </PressableScale>
  ) : null;

  const record = sheet?.record;
  const chips: TeamSheetChip[] = [];
  if (sheet?.power_rank) chips.push({ label: `Power #${sheet.power_rank}`, tone: 'premium' });
  if (record?.playoff_status) {
    chips.push({ label: record.playoff_status.toUpperCase(), tone: record.playoff_status === 'out' || record.playoff_status === 'eliminated' ? 'muted' : 'success' });
  }
  const tag = style ? (
    <ToneBadge label={style.tag} color={colors.accent} size="xs" />
  ) : data && !data.is_premium ? (
    <ToneBadge label="TRADE STYLE · PRO" color={colors.premium} size="xs" />
  ) : null;
  const tiles = [
    { label: 'Record', value: record?.label || '-' },
    { label: 'Rank', value: record?.standing_rank ? `#${record.standing_rank}` : '-' },
    { label: 'PF', value: teamSheetPoints(record?.points_for) },
    { label: 'Proj', value: teamSheetPoints(sheet?.projected_total) },
  ];
  const roster = sheet?.roster ?? [];
  const by = (slot: TeamSheetPlayer['slot']) => roster.filter((p) => p.slot === slot);
  const nameShown = sheet?.team?.team_name || teamName;
  const owner = sheet?.team?.owner_name || ownerName || null;
  const needLine = [
    (sheet?.strengths ?? []).length ? `Strong at ${sheet!.strengths!.join(', ')}.` : '',
    (sheet?.needs ?? []).length ? `Needs ${sheet!.needs!.join(', ')}.` : '',
  ]
    .filter(Boolean)
    .join(' ');

  const playerRows = (players: TeamSheetPlayer[]) => (
    <View style={styles.tight}>
      {players.map((p) => (
        <CompactPlayerCard
          key={p.player_id}
          player={{ id: p.player_id, name: p.name, position: p.position, team: p.team }}
          detail={[p.team, p.age != null ? `${p.age} yrs` : ''].filter(Boolean).join(' · ')}
          trailing={p.injury_status ? <ToneBadge label={p.injury_status} color={colors.danger} size="xs" /> : undefined}
          testID="team-sheet-player"
        />
      ))}
    </View>
  );

  const tendenciesPanel = (
    <>
      <SectionHeading title="Tendencies" />
      {rows.map(([key, title]) => {
        const signal = signals[key];
        const tone = toneColors[tendencyTone(signal.label)];
        const badge = tendencyBadgeText(signal.label);
        return (
          <AccentCard key={key} accent={tone} compact style={styles.signal}>
            <View style={styles.signalHead}>
              <AppText style={styles.signalTitle}>{title}</AppText>
              {badge ? <ToneBadge label={badge} color={tone} /> : null}
            </View>
            <AppText style={styles.signalSummary}>{signal.summary}</AppText>
            <View style={styles.meterRow}>
              <View style={styles.meterTrack}>
                <View style={[styles.meterFill, { backgroundColor: tone, width: `${Math.round(sampleFill(signal.sample_size, signal.min_sample) * 100)}%` }]} />
              </View>
              <AppText style={styles.muted}>
                {signal.sample_size} trade{signal.sample_size === 1 ? '' : 's'}
              </AppText>
            </View>
          </AccentCard>
        );
      })}
    </>
  );
  const recentTrades = data?.is_premium && data.recent_trades && data.recent_trades.length > 0 ? (
    <>
      <SectionHeading title="Recent trades" />
      {data.recent_trades.map((trade) => (
        <AccentCard key={trade.transaction_id} accent={colors.border} compact style={styles.signal}>
          <View style={styles.signalHead}>
            <AppText style={[styles.muted, styles.tradeMeta]} numberOfLines={2}>
              {tradeDateLabel(trade.date, trade.week)}
              {trade.partners.length ? ` · with ${trade.partners.join(', ')}` : ''}
            </AppText>
            {trade.grade ? (
              <ToneBadge
                label={trade.grade.letter}
                color={{ success: colors.success, accent: colors.accent, danger: colors.danger, muted: colors.textSecondary }[gradeToneSlug(trade.grade.tone)]}
              />
            ) : null}
          </View>
          {([['Got', trade.received], ['Sent', trade.sent]] as Array<[string, ManagerRecentTradeAsset[]]>).map(([label, assets]) =>
            assets.length ? (
              <View key={label} style={styles.tradeSide}>
                <AppText style={styles.signalTitle}>{label}</AppText>
                {assets.map((asset, i) => (
                  <View key={`${asset.player_id ?? asset.label}-${i}`} style={styles.assetLine}>
                    {asset.kind === 'pick' ? (
                      <>
                        <PickPlate round={asset.round} />
                        <AppText style={styles.assetName}>{asset.label || 'Draft pick'}</AppText>
                      </>
                    ) : (
                      <View style={{ flex: 1, minWidth: 0 }}>
                        <CompactPlayerCard
                          player={{ id: asset.player_id ?? null, name: asset.name ?? 'Player', position: asset.position ?? null, team: asset.team ?? null }}
                          detail={asset.team}
                          testID="manager-trade-player"
                        />
                      </View>
                    )}
                  </View>
                ))}
              </View>
            ) : null,
          )}
        </AccentCard>
      ))}
    </>
  ) : null;

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.closeRow}>
            <Pressable onPress={onClose} hitSlop={8} accessibilityLabel="Close">
              <Ionicons name="close" size={20} color={colors.textSecondary} />
            </Pressable>
          </View>
          <ScrollView style={styles.body}>
            <TeamSheetFrame
              id="manager-profile"
              logo={<TeamAvatar avatarId={sheet?.team?.avatar_url || avatarId} name={owner || nameShown} size={48} />}
              name={nameShown}
              nameTestId="team-sheet-name"
              tag={tag}
              chips={chips}
              managedBy={owner}
              tabs={[
                {
                  key: 'overview',
                  label: 'Overview',
                  render: () =>
                    sheetFailed ? (
                      <AppText style={styles.muted}>Couldn&apos;t load this team.</AppText>
                    ) : !sheet ? (
                      <SkeletonText label="team sheet" lines={4} />
                    ) : (
                      <TeamSheetOverview
                        blurb={style?.blurb || upsell}
                        tiles={tiles}
                        streak={sheet.streak}
                        nextGame={teamSheetNextGameLine(sheet.next_game ? { week: sheet.next_game.week, opponent: sheet.next_game.opponent.name } : null)}
                        positions={sheet.positions ?? []}
                        strengthsTitle={<SectionHeading title="Strengths and needs" caption={needLine || undefined} />}
                        injuries={
                          (sheet.injuries ?? []).length > 0 ? (
                            <View style={styles.tight} accessibilityLabel="Injuries">
                              <SectionHeading title="Injuries" />
                              {playerRows(sheet.injuries!)}
                            </View>
                          ) : null
                        }
                      />
                    ),
                },
                {
                  key: 'roster',
                  label: 'Roster',
                  render: () =>
                    !sheet ? (
                      sheetFailed ? <AppText style={styles.muted}>Couldn&apos;t load this roster.</AppText> : <SkeletonText label="roster" lines={4} />
                    ) : roster.length === 0 ? (
                      <AppText style={styles.muted}>No players on this roster yet.</AppText>
                    ) : (
                      <>
                        {(
                          [
                            ['starter', 'Starters'],
                            ['bench', 'Bench'],
                            ['ir', 'Injured reserve'],
                            ['taxi', 'Taxi squad'],
                          ] as const
                        ).map(([slot, label]) =>
                          by(slot).length ? (
                            <View key={slot} style={styles.tight} accessibilityLabel={label}>
                              <SectionHeading title={label} />
                              {playerRows(by(slot))}
                            </View>
                          ) : null,
                        )}
                      </>
                    ),
                },
                {
                  key: 'trades',
                  label: 'Trades',
                  render: () => (
                    <>
                      <OpponentProfileCard profile={profileQuery.data} onOffer={offer} />
                      {query.isError ? (
                        <AppText style={styles.muted}>Couldn&apos;t load trade history.</AppText>
                      ) : !data ? (
                        <SkeletonText label="manager trades" lines={3} />
                      ) : !data.is_premium ? (
                        upsell
                      ) : rows.length === 0 ? (
                        <AppText style={styles.muted}>Not enough trade history yet.</AppText>
                      ) : (
                        <>
                          {tendenciesPanel}
                          {recentTrades}
                        </>
                      )}
                    </>
                  ),
                },
                {
                  key: 'history',
                  label: 'History',
                  render: () =>
                    !sheet ? (
                      sheetFailed ? <AppText style={styles.muted}>Couldn&apos;t load season history.</AppText> : <SkeletonText label="history" lines={3} />
                    ) : (sheet.history ?? []).length === 0 ? (
                      <AppText style={styles.muted}>No past seasons in this league yet.</AppText>
                    ) : (
                      <>
                        {sheet.history!.map((h) => (
                          <AccentCard key={h.league_id} accent={colors.border} compact style={styles.signal}>
                            <View style={styles.signalHead}>
                              <AppText style={styles.signalSummary}>{h.season}</AppText>
                              <AppText style={styles.signalSummary}>{teamSheetSeasonLine(h)}</AppText>
                            </View>
                            <AppText style={styles.muted}>{teamSheetPoints(h.points_for)} points for</AppText>
                          </AccentCard>
                        ))}
                      </>
                    ),
                },
              ]}
            />
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    backdrop: {
      flex: 1,
      backgroundColor: scrim,
      alignItems: 'center',
      justifyContent: 'center',
      padding: spacing.lg,
    },
    sheet: {
      backgroundColor: colors.backgroundElevated,
      borderRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      padding: spacing.lg,
      width: '100%',
      maxWidth: 420,
      maxHeight: '80%',
    },
    closeRow: { flexDirection: 'row', justifyContent: 'flex-end', marginBottom: spacing.xs },
    body: { flexGrow: 0 },
    tight: { gap: spacing.xs },
    signal: { marginBottom: spacing.sm },
    signalHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    meterRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    meterTrack: { flex: 1, height: 4, borderRadius: radii.pill, backgroundColor: colors.cardBorder, overflow: 'hidden' },
    meterFill: { height: 4, borderRadius: radii.pill },
    signalTitle: { fontSize: 12.5, fontWeight: '800', textTransform: 'uppercase', color: colors.textSecondary },
    signalSummary: { fontSize: 15.5, fontWeight: '600', color: colors.textPrimary },
    tradeMeta: { flex: 1 },
    tradeSide: { gap: 4 },
    assetLine: { flexDirection: 'row', alignItems: 'center' },
    assetName: { flex: 1, fontSize: 15.5, fontWeight: '700', color: colors.textPrimary },
    muted: { fontSize: 13.5, color: colors.textSecondary },
    upsellTitle: { fontSize: 15.5, fontWeight: '700', color: colors.textPrimary },
    upsellCta: { fontSize: 14.5, fontWeight: '700', color: colors.premium, marginTop: spacing.xs },
  });
}
