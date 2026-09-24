import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import AppText from '../components/AppText';
import BrandHeaderBar from '../components/BrandHeaderBar';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AnimatedCard from '../components/AnimatedCard';
import BrandedSpinner from '../components/BrandedSpinner';
import DraftPickAssetRow from '../components/DraftPickAssetRow';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import SegmentedTabBar from '../components/SegmentedTabBar';
import { api, type DraftCard, type DraftPickAsset, type DraftPosture } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { contrastTextColor } from '../lib/playerTier';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'DraftCenter'>;

type PickScope = 'mine' | 'league';

function toneColorMap(colors: ThemeColors): Record<string, string> {
  return {
    power: colors.premium,
    strength: colors.success,
    opportunity: colors.success,
    strategy: colors.accent,
    weakness: colors.danger,
    risk: colors.danger,
  };
}

const POSTURE_REASON_MESSAGE: Record<string, string> = {
  no_sleeper_username_linked: "Link your Sleeper account and join this league from Home to see your own draft posture.",
  sleeper_user_not_found: "We couldn't find your linked Sleeper account in this league.",
  not_a_member_of_league: "You don't appear to have a roster in this league.",
  no_draft_capital_row: "Your roster's draft-capital data isn't available yet.",
};

export default function DraftCenterScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;
  const [posture, setPosture] = useState<DraftPosture | null>(null);
  const [postureReason, setPostureReason] = useState('');
  const [decisionCards, setDecisionCards] = useState<DraftCard[]>([]);
  const [partnerCards, setPartnerCards] = useState<DraftCard[]>([]);
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [picks, setPicks] = useState<DraftPickAsset[]>([]);
  const [myRosterId, setMyRosterId] = useState('');
  const [pickScope, setPickScope] = useState<PickScope>('mine');

  useScreenHeaderTitle(navigation, 'Draft Center', leagueName);

  useEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <View style={styles.headerButtonRow}>
          <LeagueSwitcherHeaderButton leagueId={leagueId} leagueName={leagueName} />
          <EvaluationLensHeaderButton leagueId={leagueId} />
          <GmStanceHeaderButton leagueId={leagueId} />
        </View>
      ),
    });
  }, [navigation, leagueId, styles]);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      (async () => {
        try {
          // Picks and the caller's own roster are additive to the screen —
          // neither should be able to blank out the posture/insight cards
          // that were already here, so both degrade to "no pick browser"
          // rather than surfacing an error.
          const [result, picksResult, myRoster] = await Promise.all([
            api.getLeagueDraftCenter(leagueId),
            api
              .getLeagueDraftPicks(leagueId)
              .catch(() => ({ ok: true as const, picks: [] as DraftPickAsset[], reason: 'unavailable' })),
            api.getMyRoster(leagueId).catch(() => null),
          ]);
          if (cancelled) return;
          setPosture(result.posture);
          setPostureReason(result.posture_reason);
          setDecisionCards(result.decision_cards);
          setPartnerCards(result.partner_cards);
          setReason(result.reason);
          setPicks(picksResult.picks);
          const resolvedRosterId = String(myRoster?.roster?.roster_id ?? '');
          setMyRosterId(resolvedRosterId);
          // Nothing to scope to without a resolved roster — don't strand the
          // user on an empty "My Picks" tab they can't fill.
          if (!resolvedRosterId) setPickScope('league');
        } catch (err) {
          if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load Draft Center.');
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [leagueId]),
  );

  const visiblePicks = useMemo(() => {
    const scoped =
      pickScope === 'mine' && myRosterId
        ? picks.filter((pick) => pick.owner_roster_id === myRosterId)
        : picks;
    return [...scoped].sort(
      (a, b) =>
        (a.season ?? 0) - (b.season ?? 0) ||
        (a.round ?? 0) - (b.round ?? 0) ||
        (b.score ?? 0) - (a.score ?? 0),
    );
  }, [picks, pickScope, myRosterId]);

  const pickSeasons = useMemo(() => {
    const bySeason = new Map<number, DraftPickAsset[]>();
    for (const pick of visiblePicks) {
      const season = pick.season ?? 0;
      const bucket = bySeason.get(season);
      if (bucket) bucket.push(pick);
      else bySeason.set(season, [pick]);
    }
    return [...bySeason.entries()].sort(([a], [b]) => a - b);
  }, [visiblePicks]);

  if (loading) {
    return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  }

  if (error) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <AppText style={styles.error}>{error}</AppText>
      </View>
    );
  }

  if (reason) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <AppText style={styles.notReadyText}>
          Draft Center isn't ready for this league yet — try again in a bit.
        </AppText>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}>
        <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
        <AppText style={styles.sectionLabel}>Your Draft Posture</AppText>
        {posture ? (
          <>
            <View style={styles.tileRow}>
              <PostureTile
                label="Draft Capital"
                value={posture.draft_capital_rank != null ? `#${posture.draft_capital_rank}` : '—'}
                note={posture.draft_capital != null ? `${Math.round(posture.draft_capital)} total capital` : ''}
                first={posture.draft_capital_rank === 1}
              />
              <PostureTile
                label="Future Capital"
                value={posture.future_draft_capital_rank != null ? `#${posture.future_draft_capital_rank}` : '—'}
                note={posture.future_draft_capital != null ? `${Math.round(posture.future_draft_capital)} beyond this draft` : ''}
                first={posture.future_draft_capital_rank === 1}
              />
              <PostureTile
                label="Strategy"
                value={posture.strategy_display || '—'}
                note={`Power #${posture.power_rank ?? '—'} · Franchise #${posture.franchise_rank ?? '—'}`}
              />
            </View>
            <AnimatedCard
              style={StyleSheet.flatten([styles.postureCard, { borderColor: toneColorMap(colors)[posture.tone] ?? colors.accent }])}
            >
              <View style={[styles.posturePill, { backgroundColor: toneColorMap(colors)[posture.tone] ?? colors.accent }]}>
                <AppText
                  style={[styles.postureLabel, { color: contrastTextColor(toneColorMap(colors)[posture.tone] ?? colors.accent) }]}
                >
                  {posture.label}
                </AppText>
              </View>
              <AppText style={styles.postureNote}>{posture.note}</AppText>
              <AppText style={styles.postureMeta}>
                {posture.first_rounders ?? 0} tracked first-rounders · {posture.pick_count ?? 0} total picks
              </AppText>
            </AnimatedCard>
          </>
        ) : (
          <AppText style={styles.notice}>
            {POSTURE_REASON_MESSAGE[postureReason] ?? "Your draft posture isn't available right now."}
          </AppText>
        )}

        {picks.length ? (
          <>
            <AppText style={styles.sectionLabel}>Pick Values</AppText>
            {/* Only worth a toggle once there's a resolved roster to scope
                to — otherwise pickScope is already pinned to 'league' and a
                one-option control would just be dead chrome. */}
            {myRosterId ? (
              <View style={styles.scopeRow}>
                <SegmentedTabBar<PickScope>
                  options={[
                    { key: 'mine', label: 'My Picks' },
                    { key: 'league', label: 'League' },
                  ]}
                  active={pickScope}
                  onChange={setPickScope}
                />
              </View>
            ) : null}
            {pickSeasons.length ? (
              pickSeasons.map(([season, seasonPicks]) => (
                <View key={season}>
                  <AppText style={styles.pickSeasonLabel}>{season || 'Future'}</AppText>
                  {/* A plain container, not AnimatedCard: the card here is a
                      list shell, and its rows are what's pressable — an
                      AnimatedCard would spring the whole season group on
                      every row tap. */}
                  <View style={styles.pickCard}>
                    {seasonPicks.map((pick, index) => {
                      const confidence =
                        typeof pick.projection_confidence === 'number' ? pick.projection_confidence : null;
                      return (
                        <DraftPickAssetRow
                          key={pick.pick_id}
                          pickId={pick.pick_id}
                          round={pick.round}
                          label={pick.label}
                          projectedRange={pick.projected_pick_range}
                          pickTier={pick.pick_tier}
                          contextLine={pickScope === 'league' ? pick.owner_team_name : null}
                          trailingValue={pick.score != null ? String(Math.round(pick.score)) : '—'}
                          trailingCaption={confidence !== null ? `${Math.round(confidence * 100)}% conf` : null}
                          showChevron
                          onPress={() => navigation.navigate('PickDetail', { pick, leagueId, leagueName })}
                          showDivider={index < seasonPicks.length - 1}
                        />
                      );
                    })}
                  </View>
                </View>
              ))
            ) : (
              <AppText style={styles.notice}>
                {pickScope === 'mine'
                  ? "You don't hold any tracked picks in this league right now."
                  : 'No draft pick assets available for this league yet.'}
              </AppText>
            )}
          </>
        ) : null}

        <AppText style={styles.sectionLabel}>League Draft Decision Signals</AppText>
        {decisionCards.length ? (
          <AnimatedCard style={styles.insightGroupCard}>
            {decisionCards.map((card, index) => (
              <DraftInsightBlock key={card.label} card={card} showDivider={index < decisionCards.length - 1} />
            ))}
          </AnimatedCard>
        ) : null}

        <AppText style={styles.sectionLabel}>Draft Partner Discovery</AppText>
        {partnerCards.length ? (
          <AnimatedCard style={styles.insightGroupCard}>
            {partnerCards.map((card, index) => (
              <DraftInsightBlock key={card.label} card={card} showDivider={index < partnerCards.length - 1} />
            ))}
          </AnimatedCard>
        ) : null}
      </ScrollView>
    </View>
  );
}

function PostureTile({ label, value, note, first }: { label: string; value: string; note: string; first?: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={[styles.tile, first && styles.tileFirst]}>
      <View style={styles.tileValueRow}>
        {first ? <Ionicons name="trophy" size={13} color={colors.premium} /> : null}
        <AppText style={[styles.tileValue, first && styles.tileValueFirst]} numberOfLines={1}>
          {value}
        </AppText>
      </View>
      <AppText style={styles.tileLabel}>{label}</AppText>
      {note ? (
        <AppText style={styles.tileNote} numberOfLines={2}>
          {note}
        </AppText>
      ) : null}
    </View>
  );
}

/**
 * One classification block ("Best Pick Buyers", "Pick-Rich Teams", ...)
 * inside the League Draft Decision Signals / Draft Partner Discovery
 * surfaces. Previously each block was its own separately-bordered
 * AnimatedCard — five-plus identical card shells stacked back to back is
 * exactly the "card → card → card" pattern the Magna Carta calls out (§12);
 * these now render as internal rows of one grouped surface, separated by a
 * hairline divider, the same way PickRow-family lists are grouped.
 */
function DraftInsightBlock({ card, showDivider }: { card: DraftCard; showDivider: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const toneColor = toneColorMap(colors)[card.tone] ?? colors.accent;
  return (
    <View style={showDivider ? styles.insightBlockDivider : undefined}>
      <View style={[styles.insightBadge, { backgroundColor: `${toneColor}26` }]}>
        <AppText style={[styles.insightBadgeText, { color: toneColor }]}>{card.label}</AppText>
      </View>
      <AppText style={styles.insightTitle}>{card.title}</AppText>
      {card.items.map((item, index) => (
        <View key={`${card.label}-${index}`} style={styles.insightItemRow}>
          <AppText style={styles.insightItemMark}>{'•'}</AppText>
          <AppText style={styles.insightItemText}>{item}</AppText>
        </View>
      ))}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  root: { flex: 1, backgroundColor: colors.background },
  container: { flex: 1, backgroundColor: 'transparent' },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 4 },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    padding: spacing.xl,
  },
  notReadyText: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  error: { color: colors.danger, textAlign: 'center' },
  notice: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 19,
    marginBottom: spacing.lg,
  },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  tileRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginBottom: spacing.sm },
  tile: {
    flexBasis: '30%',
    flexGrow: 1,
    backgroundColor: colors.surface,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.xs,
    alignItems: 'center',
  },
  tileValueRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  tileValue: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
  // League #1 in a capital rank gets the same trophy + premium/gold
  // treatment as Teams' top power rank — "most draft capital in the league"
  // should read at a glance, not as just another "#N".
  tileFirst: { backgroundColor: `${colors.premium}1F`, borderColor: `${colors.premium}80` },
  tileValueFirst: { color: colors.premium },
  tileLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginTop: 2,
  },
  tileNote: { fontSize: 10, color: colors.textSecondary, marginTop: 4, textAlign: 'center' },
  postureCard: { padding: spacing.lg, borderWidth: 1, gap: spacing.xs },
  // Solid-fill pill in the posture's tone color (same high-emphasis badge
  // as Player Detail's hero tier pill) — this is the one headline verdict
  // on the screen, so it earns the solid fill the dense insight badges
  // below deliberately don't get.
  posturePill: {
    alignSelf: 'flex-start',
    borderRadius: radii.pill,
    paddingHorizontal: spacing.md,
    paddingVertical: 4,
    marginBottom: spacing.xs,
  },
  postureLabel: { fontSize: 13, fontWeight: '800', letterSpacing: 0.3 },
  postureNote: { fontSize: 13, color: colors.textSecondary, lineHeight: 19 },
  postureMeta: { fontSize: 11, color: colors.textTertiary, marginTop: spacing.xs },
  scopeRow: { marginBottom: spacing.sm },
  pickSeasonLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.textSecondary,
    letterSpacing: 0.4,
    marginTop: spacing.xs,
    marginBottom: spacing.xs,
  },
  pickCard: {
    backgroundColor: colors.surface,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.sm,
  },
  insightGroupCard: { padding: spacing.lg, marginBottom: spacing.sm },
  insightBlockDivider: {
    paddingBottom: spacing.md,
    marginBottom: spacing.md,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.hairline,
  },
  insightBadge: {
    alignSelf: 'flex-start',
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    marginBottom: spacing.xs,
  },
  insightBadgeText: { fontSize: 10, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.4 },
  insightTitle: { fontSize: 14, fontWeight: '600', color: colors.textPrimary, marginBottom: spacing.sm },
  insightItemRow: { flexDirection: 'row', marginBottom: 4 },
  insightItemMark: { color: colors.textSecondary, marginRight: spacing.sm },
  insightItemText: { flex: 1, fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
  });
}
