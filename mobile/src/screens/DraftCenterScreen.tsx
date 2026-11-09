import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ScrollView, StyleSheet, View } from 'react-native';
import AppText from '../components/AppText';
import ErrorState from '../components/ErrorState';
import SectionHeading from '../components/SectionHeading';
import BrandHeaderBar from '../components/BrandHeaderBar';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';
import { Ionicons } from '@expo/vector-icons';

import AccentCard from '../components/AccentCard';
import CircularProgressRing from '../components/CircularProgressRing';
import EmptyState from '../components/EmptyState';
import IconRow from '../components/IconRow';
import ToneBadge from '../components/ToneBadge';
import BrandedSpinner from '../components/BrandedSpinner';
import DraftPickAssetRow from '../components/DraftPickAssetRow';
import EvaluationLensHeaderButton from '../components/EvaluationLensHeaderButton';
import GmStanceHeaderButton from '../components/GmStanceHeaderButton';
import LeagueSwitcherHeaderButton from '../components/LeagueSwitcherHeaderButton';
import GridBackground from '../components/GridBackground';
import SegmentedTabBar from '../components/SegmentedTabBar';
import PickGroupList from '../components/PickGroupList';
import CollegeScoutingPanel from '../components/CollegeScoutingPanel';
import { needPositionsFrom } from '../lib/scoutingLens';
import { pickProvenance } from '../lib/pickGroups';
import ValuesCredit from '../components/ValuesCredit';
import { api, type DraftCard, type DraftPickAsset, type DraftPosture } from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
import { useOrbClearance } from '../lib/orbLayout';
import { formatRank, percentileFromRank } from '../lib/percentile';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import PremiumLock from '../components/PremiumLock';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'DraftCenter'>;

type PickScope = 'mine' | 'league';
type DraftTab = 'overview' | 'picks' | 'scouting';

function toneColorMap(colors: ThemeColors): Record<string, string> {
  return {
    power: colors.accent,
    strength: colors.success,
    opportunity: colors.success,
    strategy: colors.accent,
    franchise: colors.premium,
    need: colors.warning,
    health: colors.warning,
    warning: colors.warning,
    weakness: colors.warning,
    risk: colors.warning,
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
  const [tab, setTab] = useState<DraftTab>(route.params.tab ?? 'overview');
  const [needGroups, setNeedGroups] = useState<Array<{ position: string; classification: string }> | null>(null);
  const [posture, setPosture] = useState<DraftPosture | null>(null);
  const [postureReason, setPostureReason] = useState('');
  const [decisionCards, setDecisionCards] = useState<DraftCard[]>([]);
  const [partnerCards, setPartnerCards] = useState<DraftCard[]>([]);
  const [reason, setReason] = useState('');
  const [locked, setLocked] = useState<{ title: string; body: string } | null>(null);
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
          const [result, picksResult, myRoster, needs] = await Promise.all([
            api.getLeagueDraftCenter(leagueId),
            api
              .getLeagueDraftPicks(leagueId)
              .catch(() => ({ ok: true as const, picks: [] as DraftPickAsset[], reason: 'unavailable' })),
            api.getMyRoster(leagueId).catch(() => null),
            // Best-effort: only feeds the Scouting tab's league overlay.
            api.getLeagueMyTeamNeeds(leagueId).catch(() => null),
          ]);
          if (cancelled) return;
          if (result.is_premium === false) {
            setLocked(result.upsell ?? { title: '', body: '' });
            return;
          }
          setPosture(result.posture);
          setPostureReason(result.posture_reason);
          setDecisionCards(result.decision_cards);
          setPartnerCards(result.partner_cards);
          setReason(result.reason);
          setPicks(picksResult.picks);
          setNeedGroups(needs?.position_groups ?? null);
          const resolvedRosterId = String(myRoster?.roster?.roster_id ?? '');
          setMyRosterId(resolvedRosterId);
          // Nothing to scope to without a resolved roster — don't strand the
          // user on an empty "My Picks" tab they can't fill.
          if (!resolvedRosterId) setPickScope('league');
        } catch (err) {
          if (!cancelled) setError(toUserErrorMessage(err, 'Failed to load Draft Center.'));
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

  const myPicks = useMemo(
    () => (myRosterId ? picks.filter((pick) => pick.owner_roster_id === myRosterId) : []),
    [picks, myRosterId],
  );
  const scoutingLens = useMemo(
    () => (needGroups || myPicks.length ? { needPositions: needPositionsFrom(needGroups), myPicks } : null),
    [needGroups, myPicks],
  );

  // Distinct pick-owning rosters stand in for league size (rank -> percentile); null under 2.
  const leagueSize = useMemo(() => {
    const owners = new Set<string>();
    for (const pick of picks) {
      if (pick.owner_roster_id) owners.add(String(pick.owner_roster_id));
      if (pick.original_roster_id) owners.add(String(pick.original_roster_id));
    }
    return owners.size >= 2 ? owners.size : null;
  }, [picks]);

  if (loading) {
    return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  }

  if (error) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <ErrorState title="Couldn't load the draft center" message={error} />
      </View>
    );
  }

  if (locked) {
    return (
      <View style={styles.root}>
        <GridBackground />
        <View style={{ paddingTop: headerHeight, paddingHorizontal: spacing.lg }}>
          <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
          <PremiumLock
            feature="draft_center"
            leagueName={leagueName}
            title={locked.title || 'Know where you stand on draft capital'}
            description={
              locked.body ||
              'Draft Center is a Pro feature: your draft posture, league-wide pick decision signals and the best trade partners for your picks. Start your free trial to unlock it.'
            }
          />
        </View>
      </View>
    );
  }

  if (reason) {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <EmptyState icon="time-outline" title="Draft Center isn't ready yet" subtitle="Try again in a bit." />
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}>
        <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
        <View style={styles.scopeRow}>
          <SegmentedTabBar<DraftTab>
            options={[
              { key: 'overview', label: 'Overview' },
              { key: 'picks', label: 'Picks' },
              { key: 'scouting', label: 'Scouting' },
            ]}
            active={tab}
            onChange={setTab}
          />
        </View>
        {tab === 'overview' ? (
          <>
        <SectionHeading title="Your Draft Posture" topGap={16} />
        {posture ? (
          <AccentCard accent={toneColorMap(colors)[posture.tone] ?? colors.accent}>
            <View style={styles.postureHead}>
              <ToneBadge label={posture.label} color={toneColorMap(colors)[posture.tone] ?? colors.accent} />
              <View style={styles.postureChips}>
                <ToneBadge label={`${posture.first_rounders ?? 0} firsts`} color={colors.premium} />
                <ToneBadge label={`${posture.pick_count ?? 0} picks`} color={colors.accent} />
              </View>
            </View>
            <AppText style={styles.postureNote}>{posture.note}</AppText>
            <View style={styles.tileRow}>
              <CapitalCell
                label="Draft Capital"
                icon="trophy-outline"
                rank={posture.draft_capital_rank}
                tied={posture.draft_capital_rank_tied}
                leagueSize={leagueSize}
                note={posture.draft_capital != null ? `${Math.round(posture.draft_capital)} total capital` : ''}
              />
              <CapitalCell
                label="Future Capital"
                icon="calendar-outline"
                rank={posture.future_draft_capital_rank}
                tied={posture.future_draft_capital_rank_tied}
                leagueSize={leagueSize}
                note={posture.future_draft_capital != null ? `${Math.round(posture.future_draft_capital)} beyond this draft` : ''}
              />
              <PostureTile
                label="Strategy"
                value={posture.strategy_display || '—'}
                note={`Roster Power ${formatRank(posture.power_rank, posture.power_rank_tied)} · Franchise ${formatRank(posture.franchise_rank, posture.franchise_rank_tied)}`}
              />
            </View>
          </AccentCard>
        ) : (
          <EmptyState
            icon="information-circle-outline"
            title={POSTURE_REASON_MESSAGE[postureReason] ?? "Your draft posture isn't available right now."}
          />
        )}

          </>
        ) : null}

        {tab === 'picks' ? (
          <>
            <SectionHeading title="Pick Values" topGap={16} />
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
            {visiblePicks.length ? (
              <PickGroupList
                picks={visiblePicks}
                renderPick={(pick, isLast) => {
                  const confidence =
                    typeof pick.projection_confidence === 'number' ? pick.projection_confidence : null;
                  return (
                    <DraftPickAssetRow
                      pickId={pick.pick_id}
                      round={pick.round}
                      label={pick.label}
                      projectedRange={pick.projected_pick_range}
                      pickTier={pick.pick_tier}
                      contextLine={pickProvenance(pick, { showOwner: pickScope === 'league' })}
                      trailingValue={pick.score != null ? String(Math.round(pick.score)) : '—'}
                      trailingCaption={confidence !== null ? `${Math.round(confidence * 100)}% conf` : null}
                      showChevron
                      onPress={() => navigation.navigate('PickDetail', { pick, leagueId, leagueName })}
                      showDivider={!isLast}
                    />
                  );
                }}
              />
            ) : (
              <EmptyState
                icon="information-circle-outline"
                title={
                  pickScope === 'mine'
                    ? "You don't hold any tracked picks in this league right now."
                    : 'No draft pick assets available for this league yet.'
                }
              />
            )}
          </>
        ) : null}

        {tab === 'overview' ? (
          <>
            <SectionHeading title="League Draft Decision Signals" topGap={16} />
            {decisionCards.map((card) => (
              <DraftInsightCard key={card.label} card={card} />
            ))}

            <SectionHeading title="Draft Partner Discovery" topGap={16} />
            {partnerCards.map((card) => (
              <DraftInsightCard key={card.label} card={card} />
            ))}
          </>
        ) : null}

        {tab === 'scouting' ? (
          <CollegeScoutingPanel
            onOpenProspect={(prospect) => navigation.navigate('CollegeProspectDetail', { prospect })}
            lens={scoutingLens}
          />
        ) : null}
        <ValuesCredit />
      </ScrollView>
    </View>
  );
}

function PostureTile({ label, value, note }: { label: string; value: string; note: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.tile}>
      <View style={styles.tileLabelRow}>
        <Ionicons name="flash-outline" size={11} color={colors.accent} />
        <AppText style={styles.tileLabel}>{label}</AppText>
      </View>
      <AppText style={styles.tileValue} numberOfLines={1}>
        {value}
      </AppText>
      {note ? (
        <AppText style={styles.tileNote} numberOfLines={3}>
          {note}
        </AppText>
      ) : null}
    </View>
  );
}

/** One capital metric: rank as the headline, a percentile ring when the league size is known. */
function CapitalCell({
  label,
  icon,
  rank,
  tied,
  leagueSize,
  note,
}: {
  label: string;
  icon: React.ComponentProps<typeof Ionicons>['name'];
  rank: number | null;
  tied: boolean;
  leagueSize: number | null;
  note: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const percentile = leagueSize ? percentileFromRank(rank, leagueSize) : null;
  const first = rank === 1;
  const ringColor = percentile === null ? colors.accent : percentile < 34 ? colors.danger : percentile < 67 ? colors.warning : colors.success;
  return (
    <View style={[styles.tile, first && styles.tileFirst]}>
      <View style={styles.tileLabelRow}>
        <Ionicons name={icon} size={11} color={first ? colors.premium : colors.accent} />
        <AppText style={styles.tileLabel}>{label}</AppText>
      </View>
      <View style={styles.capitalValueRow}>
        <AppText style={[styles.tileValue, first && styles.tileValueFirst]} numberOfLines={1}>
          {formatRank(rank, tied)}
        </AppText>
        {percentile !== null ? (
          <CircularProgressRing percent={percentile} size={34} strokeWidth={4} color={ringColor} valueLabel={`${percentile}`} valueFontScale={0.34} />
        ) : null}
      </View>
      {note ? (
        <AppText style={styles.tileNote} numberOfLines={2}>
          {note}
        </AppText>
      ) : null}
    </View>
  );
}

/**
 * One classification card ("Best Pick Buyers", "Pick-Rich Teams", ...): an
 * AccentCard railed and badged in the tone's semantic color, items as icon
 * rows. Mirrors web-next's DraftCardSection (PR #1696).
 */
function DraftInsightCard({ card }: { card: DraftCard }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const toneColor = toneColorMap(colors)[card.tone] ?? colors.accent;
  return (
    <AccentCard accent={toneColor} style={styles.insightCard}>
      <ToneBadge label={card.label} color={toneColor} />
      <AppText style={styles.insightTitle}>{card.title}</AppText>
      {card.items.map((item, index) => (
        <IconRow key={`${card.label}-${index}`} icon="arrow" color={toneColor}>
          {item}
        </IconRow>
      ))}
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  headerButtonRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  root: { flex: 1, backgroundColor: 'transparent' },
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
  tileRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
  tile: {
    flexBasis: '30%',
    flexGrow: 1,
    minWidth: 100,
    backgroundColor: colors.glass,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    padding: spacing.sm,
    gap: 2,
  },
  tileLabelRow: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  tileLabel: { fontSize: 10, fontWeight: '700', color: colors.textTertiary, textTransform: 'uppercase', letterSpacing: 0.4 },
  tileValue: { fontSize: 16, fontWeight: '800', color: colors.textPrimary },
  capitalValueRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.xs },
  // League #1 in a capital rank keeps the premium/gold treatment.
  tileFirst: { backgroundColor: `${colors.premium}1F`, borderColor: `${colors.premium}80` },
  tileValueFirst: { color: colors.premium },
  tileNote: { fontSize: 10, color: colors.textSecondary },
  postureHead: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.sm },
  postureChips: { flexDirection: 'row', gap: spacing.xs, marginLeft: 'auto' },
  postureNote: { fontSize: 13, color: colors.textSecondary, lineHeight: 19 },
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
    backgroundColor: colors.glass,
    borderRadius: radii.md,
    borderWidth: 1,
    borderColor: colors.glassBorder,
    paddingHorizontal: spacing.md,
    marginBottom: spacing.sm,
  },
  insightCard: { marginBottom: spacing.sm },
  insightTitle: { fontSize: 14, fontWeight: '600', color: colors.textPrimary, marginBottom: 0 },
  });
}
