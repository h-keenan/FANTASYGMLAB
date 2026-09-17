import React, { useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View, type ViewStyle } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import GridBackground from '../components/GridBackground';
import PlayerAvatar from '../components/PlayerAvatar';
import { api, type DashboardItem, type DashboardItemCategory, type PresentationAsset } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { diffAndRecordSeen } from '../lib/sinceLastCheckIn';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useDensity } from '../context/DensityContext';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'Dashboard'>;
type DashboardNavigation = Props['navigation'];

const CATEGORY_META: Record<
  DashboardItemCategory,
  { label: string; icon: React.ComponentProps<typeof Ionicons>['name']; color: string }
> = {
  top_priority: { label: 'Top Priority', icon: 'flash', color: colors.accent },
  watch: { label: 'Watch', icon: 'eye-outline', color: colors.danger },
  waiver_opportunity: { label: 'Waiver Opportunity', icon: 'swap-horizontal-outline', color: colors.premium },
  league_movement: { label: 'League Movement', icon: 'trending-up-outline', color: colors.textSecondary },
};

// Only destinations mobile can navigate to with just {leagueId, leagueName} —
// "my_team" would need TeamRoster's ownerName/playerIds params, which this
// screen doesn't have on hand, so it's left without a button rather than
// navigating somewhere wrong.
const DESTINATION_BUTTON_LABEL: Record<string, string> = {
  trade_hub: 'Review in Trade Hub',
  waivers: 'Open Waivers',
};
const DESTINATION_ROUTE: Record<string, string> = {
  trade_hub: 'TradeHub',
  waivers: 'Waivers',
};

const CONFIDENCE_LEVELS: Record<string, number> = { high: 3, medium: 2, low: 1 };

export default function DashboardScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const { leagueId, leagueName } = route.params;
  const [items, setItems] = useState<DashboardItem[] | null>(null);
  const [quiet, setQuiet] = useState(false);
  const [quietReason, setQuietReason] = useState('');
  const [notReadyReason, setNotReadyReason] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [newRecommendationIds, setNewRecommendationIds] = useState<Set<string>>(new Set());
  const [isFirstVisit, setIsFirstVisit] = useState(true);
  const { showExplanations } = useDensity();

  useScreenHeaderTitle(navigation, 'Next Move', leagueName);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const result = await api.getLeagueDashboard(leagueId);
        if (cancelled) return;
        if (result.reason) {
          setNotReadyReason(result.reason);
        } else {
          setItems(result.items);
          setQuiet(result.quiet);
          setQuietReason(result.quiet_reason ?? '');
          const { newIds, isFirstVisit: firstVisit } = await diffAndRecordSeen(
            leagueId,
            result.items.map((item) => item.recommendation_id),
          );
          if (!cancelled) {
            setNewRecommendationIds(newIds);
            setIsFirstVisit(firstVisit);
          }
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load your Next Move briefing.');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  if (notReadyReason) {
    return (
      <View style={styles.center}>
        <Text style={styles.notReadyText}>
          {NOT_READY_MESSAGES[notReadyReason] ?? "Couldn't build your Next Move briefing for this league."}
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>
      <Text style={styles.disclaimer}>
        The real Next Move briefing for {leagueName} — the same roster-pressure, injury, need, and
        waiver signals the web app's Dashboard uses.
      </Text>
      {!isFirstVisit && newRecommendationIds.size > 0 ? (
        <View style={styles.checkInBanner}>
          <Ionicons name="sparkles-outline" size={14} color={colors.accent} />
          <Text style={styles.checkInText}>
            Since your last check-in: {newRecommendationIds.size} new{' '}
            {newRecommendationIds.size === 1 ? 'item' : 'items'} below
          </Text>
        </View>
      ) : null}
      {quiet || !items || items.length === 0 ? (
        <View style={styles.emptyCard}>
          <Ionicons name="checkmark-done-outline" size={22} color={colors.success} />
          <Text style={styles.emptyText}>
            {quietReason || 'Nothing urgent right now — your roster looks steady.'}
          </Text>
        </View>
      ) : (
        items.map((item, index) => (
          <BriefingCard
            key={`${item.category}-${index}`}
            item={item}
            leagueId={leagueId}
            leagueName={leagueName}
            navigation={navigation}
            isNew={newRecommendationIds.has(item.recommendation_id)}
            showExplanations={showExplanations}
          />
        ))
      )}
      </ScrollView>
    </View>
  );
}

const NOT_READY_MESSAGES: Record<string, string> = {
  no_sleeper_username_linked:
    "Link your Sleeper username on the web app first — the Next Move briefing needs to know which roster is yours.",
  sleeper_user_not_found: "Couldn't find that Sleeper account. Double-check the linked username on the web app.",
  not_a_member_of_league: "You don't appear to own a team in this league.",
  empty_roster: "This roster doesn't have any players yet.",
};

function DestinationButton({
  item,
  leagueId,
  leagueName,
  navigation,
}: {
  item: DashboardItem;
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
}) {
  const label = DESTINATION_BUTTON_LABEL[item.destination];
  const routeName = DESTINATION_ROUTE[item.destination];
  if (!label || !routeName) return null;
  return (
    <TouchableOpacity
      style={styles.destButton}
      onPress={() => {
        if (!routeName) return;
        (navigation.navigate as (name: string, params?: object) => void)(routeName, { leagueId, leagueName });
      }}
    >
      <Text style={styles.destButtonText}>{label.toUpperCase()}</Text>
    </TouchableOpacity>
  );
}

function TradeAssetRow({ asset }: { asset: PresentationAsset }) {
  if (asset.asset_type === 'pick') {
    return (
      <View style={styles.assetRow}>
        <View style={styles.pickDisc}>
          <Ionicons name="ticket-outline" size={16} color={colors.premium} />
        </View>
        <Text style={styles.assetName} numberOfLines={1}>
          {asset.label || 'Draft pick'}
        </Text>
      </View>
    );
  }
  return (
    <View style={styles.assetRow}>
      <PlayerAvatar playerId={asset.player_id} size={32} style={styles.assetAvatar} />
      <View style={styles.assetTextGroup}>
        <Text style={styles.assetName} numberOfLines={1}>
          {asset.name ?? 'Unknown'}
        </Text>
        <Text style={styles.assetMeta} numberOfLines={1}>
          {[asset.position, asset.team].filter(Boolean).join(' · ')}
        </Text>
      </View>
    </View>
  );
}

function NewBadge() {
  return (
    <View style={styles.newBadge}>
      <Text style={styles.newBadgeText}>NEW</Text>
    </View>
  );
}

function TopPriorityTradeCard({
  item,
  leagueId,
  leagueName,
  navigation,
  isNew,
  showExplanations,
}: {
  item: DashboardItem;
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
  isNew: boolean;
  showExplanations: boolean;
}) {
  const presentation = item.presentation!;
  const gain = presentation.trade_gain;
  const gainColor = gain > 0 ? colors.successBright : gain < 0 ? colors.danger : colors.textSecondary;
  const confidenceLevel = CONFIDENCE_LEVELS[presentation.trade_confidence_label?.toLowerCase()] ?? 1;

  return (
    <AnimatedCard style={StyleSheet.flatten([styles.card, { borderLeftColor: colors.accent } as ViewStyle])}>
      <View style={styles.cardHeaderRow}>
        <Ionicons name="flash" size={15} color={colors.accent} style={styles.cardIcon} />
        <Text style={[styles.cardLabel, { color: colors.accent }]}>TOP PRIORITY</Text>
        {isNew ? <NewBadge /> : null}
        <View style={styles.tradeBadge}>
          <Ionicons name="swap-horizontal" size={12} color={colors.textSecondary} />
          <Text style={styles.tradeBadgeText}>TRADE</Text>
        </View>
      </View>
      <Text style={styles.cardHeadline}>{presentation.partner_team_name}</Text>

      <View style={styles.sideBlock}>
        <View style={[styles.sideBar, { backgroundColor: colors.danger }]} />
        <View style={styles.sideContent}>
          <Text style={styles.sideLabel}>YOU GIVE</Text>
          {presentation.trade_package.send.map((asset, index) => (
            <TradeAssetRow key={`send-${index}`} asset={asset} />
          ))}
        </View>
      </View>
      <View style={styles.sideBlock}>
        <View style={[styles.sideBar, { backgroundColor: colors.successBright }]} />
        <View style={styles.sideContent}>
          <Text style={styles.sideLabel}>YOU GET</Text>
          {presentation.trade_package.receive.map((asset, index) => (
            <TradeAssetRow key={`receive-${index}`} asset={asset} />
          ))}
        </View>
      </View>

      <View style={styles.valueRow}>
        <Text style={styles.valueLabel}>
          TRADE VALUE / {presentation.trade_market_realism_label.toUpperCase()}
        </Text>
        <Text style={[styles.valueNumber, { color: gainColor }]}>
          {gain > 0 ? '+' : ''}
          {gain}
        </Text>
      </View>
      <View style={styles.meterRow}>
        <Text style={styles.meterLabel}>CONFIDENCE</Text>
        <View style={styles.meterSegments}>
          {[1, 2, 3].map((segment) => (
            <View
              key={segment}
              style={[
                styles.meterSegment,
                { backgroundColor: segment <= confidenceLevel ? colors.accent : colors.borderStrong },
              ]}
            />
          ))}
        </View>
        <Text style={styles.meterValue}>{presentation.trade_confidence_label}</Text>
      </View>

      {showExplanations && item.reason ? <Text style={styles.cardReason}>{item.reason}</Text> : null}
      <DestinationButton item={item} leagueId={leagueId} leagueName={leagueName} navigation={navigation} />
    </AnimatedCard>
  );
}

function BriefingCard({
  item,
  leagueId,
  leagueName,
  navigation,
  isNew,
  showExplanations,
}: {
  item: DashboardItem;
  leagueId: string;
  leagueName: string;
  navigation: DashboardNavigation;
  isNew: boolean;
  showExplanations: boolean;
}) {
  if (item.presentation?.trade_package) {
    return (
      <TopPriorityTradeCard
        item={item}
        leagueId={leagueId}
        leagueName={leagueName}
        navigation={navigation}
        isNew={isNew}
        showExplanations={showExplanations}
      />
    );
  }
  const meta = CATEGORY_META[item.category] ?? CATEGORY_META.watch;
  return (
    <AnimatedCard style={StyleSheet.flatten([styles.card, { borderLeftColor: meta.color } as ViewStyle])}>
      <View style={styles.cardHeaderRow}>
        <Ionicons name={meta.icon} size={15} color={meta.color} style={styles.cardIcon} />
        <Text style={[styles.cardLabel, { color: meta.color }]}>{meta.label.toUpperCase()}</Text>
        {isNew ? <NewBadge /> : null}
      </View>
      <Text style={styles.cardHeadline}>{item.headline}</Text>
      {showExplanations && item.reason ? <Text style={styles.cardReason}>{item.reason}</Text> : null}
      <DestinationButton item={item} leagueId={leagueId} leagueName={leagueName} navigation={navigation} />
    </AnimatedCard>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  container: { flex: 1, backgroundColor: 'transparent' },
  content: { padding: spacing.xl, paddingBottom: spacing.xl * 4 },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    padding: spacing.xl,
  },
  disclaimer: { fontSize: 12, color: colors.textSecondary, marginBottom: spacing.lg, lineHeight: 16 },
  checkInBanner: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    backgroundColor: colors.accentMuted,
    borderRadius: radii.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    marginBottom: spacing.md,
  },
  checkInText: { fontSize: 12, fontWeight: '600', color: colors.accent, flexShrink: 1 },
  newBadge: {
    backgroundColor: colors.accent,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.xs + 2,
    paddingVertical: 2,
    marginLeft: spacing.xs,
  },
  newBadgeText: { fontSize: 8, fontWeight: '800', color: colors.background, letterSpacing: 0.4 },
  card: {
    borderLeftWidth: 4,
    padding: spacing.lg,
    marginBottom: spacing.sm,
  },
  cardHeaderRow: { flexDirection: 'row', alignItems: 'center', marginBottom: spacing.xs },
  cardIcon: { marginRight: spacing.xs },
  cardLabel: { fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.4 },
  cardHeadline: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: 4 },
  cardReason: { fontSize: 13, color: colors.textSecondary, lineHeight: 18, marginTop: spacing.sm },
  tradeBadge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    marginLeft: 'auto',
    backgroundColor: colors.border,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 2,
  },
  tradeBadgeText: { fontSize: 9, fontWeight: '700', color: colors.textSecondary, letterSpacing: 0.5 },
  sideBlock: { flexDirection: 'row', marginTop: spacing.sm },
  sideBar: { width: 3, borderRadius: 2, marginRight: spacing.sm },
  sideContent: { flex: 1, gap: spacing.xs },
  sideLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
  },
  assetRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
  assetAvatar: {},
  pickDisc: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  assetTextGroup: { flex: 1 },
  assetName: { fontSize: 13, fontWeight: '600', color: colors.textPrimary },
  assetMeta: { fontSize: 11, color: colors.textSecondary, marginTop: 1 },
  valueRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: spacing.md,
    paddingTop: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.hairline,
  },
  valueLabel: { fontSize: 10, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
  valueNumber: { fontSize: 18, fontWeight: '800' },
  meterRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: spacing.xs },
  meterLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
  meterSegments: { flexDirection: 'row', gap: 3 },
  meterSegment: { width: 14, height: 4, borderRadius: 2 },
  meterValue: { fontSize: 11, fontWeight: '600', color: colors.textSecondary },
  destButton: {
    marginTop: spacing.md,
    borderWidth: 1.5,
    borderColor: colors.accent,
    borderRadius: radii.sm,
    paddingVertical: spacing.sm,
    alignItems: 'center',
  },
  destButtonText: { fontSize: 12, fontWeight: '700', color: colors.accent, letterSpacing: 0.4 },
  emptyCard: {
    alignItems: 'center',
    padding: spacing.xl,
    gap: spacing.sm,
  },
  emptyText: { fontSize: 14, color: colors.textSecondary, textAlign: 'center', lineHeight: 20 },
  notReadyText: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  error: { color: colors.danger, textAlign: 'center' },
});
