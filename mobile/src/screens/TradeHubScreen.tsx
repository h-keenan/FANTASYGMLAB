import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import PlayerAvatar from '../components/PlayerAvatar';
import { api, type PresentationAsset, type TeamStrategy, type TradeIdea } from '../lib/api';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'TradeHub'>;

const STRATEGIES: Array<{ value: TeamStrategy; label: string }> = [
  { value: 'contender', label: 'Contender' },
  { value: 'fringe_contender', label: 'Fringe Contender' },
  { value: 'retool', label: 'Retool' },
  { value: 'rebuild', label: 'Rebuild' },
  { value: 'tank', label: 'Tank' },
];

const CONFIDENCE_LEVELS: Record<string, number> = { high: 3, medium: 2, low: 1 };
const REALISM_LEVELS: Record<string, number> = { realistic: 3, plausible: 2, thin: 1 };

const NOT_READY_MESSAGES: Record<string, string> = {
  no_sleeper_username_linked:
    "Link your Sleeper username on the web app first — Trade Hub needs to know which roster is yours.",
  sleeper_user_not_found: "Couldn't find that Sleeper account. Double-check the linked username on the web app.",
  not_a_member_of_league: "You don't appear to own a team in this league.",
  empty_roster: "This roster doesn't have any players yet.",
  no_player_data: "Player data isn't available right now.",
};

export default function TradeHubScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const [strategy, setStrategy] = useState<TeamStrategy>('retool');
  const [ideas, setIdeas] = useState<TradeIdea[] | null>(null);
  const [notReadyReason, setNotReadyReason] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'Trade Hub', leagueName);

  const load = useCallback(
    async (nextStrategy: TeamStrategy) => {
      setLoading(true);
      setError(null);
      try {
        const result = await api.getTradeHubIdeas(leagueId, nextStrategy);
        if (result.reason) {
          setNotReadyReason(result.reason);
          setIdeas(null);
        } else {
          setNotReadyReason(null);
          setIdeas(result.ideas);
        }
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load Trade Hub ideas.');
      } finally {
        setLoading(false);
      }
    },
    [leagueId],
  );

  useEffect(() => {
    void load(strategy);
  }, [load, strategy]);

  return (
    <FlatList
      style={styles.container}
      data={loading || error || notReadyReason ? [] : ideas ?? []}
      keyExtractor={(_, index) => String(index)}
      contentContainerStyle={styles.content}
      ListHeaderComponent={
        <View>
          <View style={styles.strategyRow}>
            {STRATEGIES.map((option) => (
              <TouchableOpacity
                key={option.value}
                style={[styles.pill, strategy === option.value && styles.pillActive]}
                onPress={() => setStrategy(option.value)}
              >
                <Text style={[styles.pillText, strategy === option.value && styles.pillTextActive]}>
                  {option.label}
                </Text>
              </TouchableOpacity>
            ))}
          </View>
          <Text style={styles.disclaimer} numberOfLines={1}>
            Real ideas from the same engine and Trust checks as the web app's Trade Hub.
          </Text>
          {loading ? <ActivityIndicator style={styles.loading} color={colors.accent} /> : null}
          {error ? <Text style={styles.error}>{error}</Text> : null}
          {notReadyReason ? (
            <Text style={styles.notReadyText}>
              {NOT_READY_MESSAGES[notReadyReason] ?? "Couldn't build Trade Hub ideas for this league."}
            </Text>
          ) : null}
        </View>
      }
      renderItem={({ item }) => <TradeIdeaCard idea={item} />}
      ListEmptyComponent={
        !loading && !error && !notReadyReason ? (
          <Text style={styles.empty}>
            No trade idea clears the bar for this strategy right now — check back after rosters move.
          </Text>
        ) : null
      }
    />
  );
}

function AssetRow({ asset }: { asset: PresentationAsset }) {
  if (asset.asset_type === 'pick') {
    return (
      <View style={styles.assetRow}>
        <View style={styles.pickDisc}>
          <Ionicons name="ticket-outline" size={18} color={colors.premium} />
        </View>
        <View style={styles.assetTextGroup}>
          <Text style={styles.assetName} numberOfLines={1}>
            {asset.label || 'Draft pick'}
          </Text>
          <Text style={styles.assetMeta} numberOfLines={1}>
            {asset.projected_range || 'Draft pick'}
          </Text>
        </View>
      </View>
    );
  }
  return (
    <View style={styles.assetRow}>
      <PlayerAvatar playerId={asset.player_id} size={36} style={styles.assetAvatar} />
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

function MeterRow({ label, value, level, color }: { label: string; value: string; level: number; color: string }) {
  return (
    <View style={styles.meter}>
      <Text style={styles.meterLabel}>{label}</Text>
      <View style={styles.meterSegments}>
        {[1, 2, 3].map((segment) => (
          <View
            key={segment}
            style={[styles.meterSegment, { backgroundColor: segment <= level ? color : colors.borderStrong }]}
          />
        ))}
      </View>
      <Text style={styles.meterValue}>{value}</Text>
    </View>
  );
}

function TradeIdeaCard({ idea }: { idea: TradeIdea }) {
  const gainColor = idea.trade_gain > 0 ? colors.success : idea.trade_gain < 0 ? colors.danger : colors.textSecondary;
  const confidenceLevel = CONFIDENCE_LEVELS[idea.confidence_label?.toLowerCase()] ?? 1;
  const realismLevel = REALISM_LEVELS[idea.market_realism_label?.toLowerCase()] ?? 1;

  return (
    <AnimatedCard style={styles.card}>
      <View style={styles.partnerRow}>
        <View style={styles.partnerAvatar}>
          <Text style={styles.partnerInitial}>{idea.partner_team_name.charAt(0).toUpperCase()}</Text>
        </View>
        <View style={styles.partnerTextGroup}>
          <Text style={styles.partnerName} numberOfLines={1}>
            {idea.partner_team_name}
          </Text>
        </View>
        <View style={[styles.gainPill, { backgroundColor: `${gainColor}26` }]}>
          <Text style={[styles.gainLabel, { color: gainColor }]}>
            {idea.trade_gain > 0 ? '+' : ''}
            {idea.trade_gain}
          </Text>
        </View>
      </View>

      <View style={styles.exchangeRow}>
        <View style={styles.exchangeSide}>
          <Text style={styles.exchangeLabel}>You Send</Text>
          {idea.package.send.map((asset, index) => (
            <AssetRow key={`send-${index}`} asset={asset} />
          ))}
        </View>
        <View style={styles.exchangeGutter}>
          <View style={styles.swapDisc}>
            <Ionicons name="swap-horizontal" size={16} color={colors.accent} />
          </View>
        </View>
        <View style={styles.exchangeSide}>
          <Text style={styles.exchangeLabel}>You Receive</Text>
          {idea.package.receive.map((asset, index) => (
            <AssetRow key={`receive-${index}`} asset={asset} />
          ))}
        </View>
      </View>

      <Text style={styles.rationaleLabel}>Why this works</Text>
      <Text style={styles.rationale} numberOfLines={3}>
        {idea.rationale}
      </Text>

      <View style={styles.footerRow}>
        <MeterRow label="CONFIDENCE" value={idea.confidence_label} level={confidenceLevel} color={colors.accent} />
        <MeterRow label="REALISM" value={idea.market_realism_label} level={realismLevel} color={colors.premium} />
      </View>
    </AnimatedCard>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.background },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 4 },
  disclaimer: { fontSize: 11, color: colors.textTertiary, marginBottom: spacing.md },
  strategyRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginBottom: spacing.sm },
  pill: {
    paddingHorizontal: spacing.sm,
    paddingVertical: 6,
    borderRadius: radii.pill,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
  },
  pillActive: { backgroundColor: colors.accent, borderColor: colors.accent },
  pillText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  pillTextActive: { color: colors.background, fontWeight: '700' },
  loading: { marginVertical: spacing.xl },
  error: { color: colors.danger, textAlign: 'center', marginTop: spacing.lg },
  notReadyText: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20, marginTop: spacing.xl },
  empty: { textAlign: 'center', color: colors.textSecondary, marginTop: spacing.xl, lineHeight: 20 },
  card: { padding: 0, marginBottom: spacing.md },
  partnerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: spacing.md,
    paddingBottom: spacing.sm,
    gap: spacing.sm,
  },
  partnerAvatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  partnerInitial: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
  partnerTextGroup: { flex: 1 },
  partnerName: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  gainPill: { borderRadius: radii.pill, paddingHorizontal: spacing.sm, paddingVertical: 4 },
  gainLabel: { fontSize: 14, fontWeight: '700' },
  exchangeRow: { flexDirection: 'row', paddingHorizontal: spacing.md, gap: spacing.sm },
  exchangeSide: { flex: 1, gap: spacing.xs },
  exchangeGutter: { width: 28, alignItems: 'center', paddingTop: spacing.lg },
  swapDisc: {
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  exchangeLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginBottom: 2,
  },
  assetRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.xs },
  assetAvatar: {},
  pickDisc: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  assetTextGroup: { flex: 1 },
  assetName: { fontSize: 13, fontWeight: '600', color: colors.textPrimary },
  assetMeta: { fontSize: 11, color: colors.textSecondary, marginTop: 1 },
  rationaleLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textPrimary,
    paddingHorizontal: spacing.md,
    marginTop: spacing.md,
    marginBottom: 2,
  },
  rationale: { fontSize: 13, color: colors.textSecondary, lineHeight: 18, paddingHorizontal: spacing.md },
  footerRow: {
    flexDirection: 'row',
    marginTop: spacing.md,
    paddingHorizontal: spacing.md,
    paddingVertical: spacing.sm,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.hairline,
    gap: spacing.lg,
  },
  meter: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 6 },
  meterLabel: { fontSize: 9, fontWeight: '700', color: colors.textTertiary, letterSpacing: 0.4 },
  meterSegments: { flexDirection: 'row', gap: 3 },
  meterSegment: { width: 14, height: 4, borderRadius: 2 },
  meterValue: { fontSize: 11, fontWeight: '600', color: colors.textSecondary },
});
