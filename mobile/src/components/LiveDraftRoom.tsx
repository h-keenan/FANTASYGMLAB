import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import AnimatedCard from './AnimatedCard';
import AdpLine, { AdpCredit } from './AdpLine';
import { adpContext } from '../lib/adpPresentation';
import AppText from './AppText';
import CompactModule from './CompactModule';
import CompactPlayerCard from './CompactPlayerCard';
import { SkeletonList } from './Skeleton';
import Button from './Button';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import FilterDropdownButton from './FilterDropdownButton';
import LiveDraftTradeEvaluator from './LiveDraftTradeEvaluator';
import PickPlate from './PickPlate';
import PlayerIdentityRow from './PlayerIdentityRow';
import PremiumLock from './PremiumLock';
import SectionHeading from './SectionHeading';
import ToneBadge from './ToneBadge';
import ValuesCredit from './ValuesCredit';
import { useThemeMode } from '../context/ThemeModeContext';
import { useValuationLens } from '../context/ValuationLensContext';
import {
  api,
  type LiveDraftDiscoveryResponse,
  type LiveDraftRankingRow,
  type LiveDraftRecommendation,
  type LiveDraftStateResponse,
  type LiveDraftTeamRow,
  type RankedPlayer,
} from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
import {
  diffRankMovement,
  diffTeamRankMovement,
  filterLiveDraftRankings,
  formatLiveDraftScore,
  liveDraftRankFilterOptions,
  movementGlyph,
  liveDraftsOf,
  ranksById,
  teamRanksById,
  type LiveDraftRankFilter,
} from '../lib/liveDraft';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { usePlayerQuickView } from '../context/PlayerQuickViewContext';
import { Collapse } from './Presence';


// Matches modules/live_draft.py LIVE_DRAFT_POLL_INTERVAL_SECONDS and web.
const POLL_INTERVAL_MS = 12_000;
const MAX_RANK_ROWS = 60;

const SCORE_BREAKDOWN_FIELDS: { key: keyof LiveDraftRankingRow; label: string }[] = [
  { key: 'base_value', label: 'Base' },
  { key: 'format_adjustment', label: 'Format' },
  { key: 'scarcity_score', label: 'Scarcity' },
  { key: 'roster_fit_score', label: 'Fit' },
  { key: 'age_strategy_adjustment', label: 'Age/Strategy' },
  { key: 'availability_adjustment', label: 'Availability' },
];

function leanPlayer(row: {
  player_id: string;
  name: string;
  position: string;
  team: string;
  age: number | null;
  tier: string;
  overall_rating?: number | null;
}): RankedPlayer {
  return {
    player_id: row.player_id,
    name: row.name || null,
    position: row.position || null,
    team: row.team || null,
    age: row.age,
    status: null,
    injury_status: null,
    tier: row.tier || null,
    score: null,
    overall_rank: null,
    position_rank: null,
    rank_unavailable_reason: null,
    opportunity_label: null,
    overall_rating: row.overall_rating ?? null,
  };
}

/**
 * The live draft room: Sleeper draft-room assistant (Best Available / Best Fit, on the clock, team board, trade
 * evaluator). Embedded as the "Live room" tab of Draft Center (it only exists while a draft is live), so it renders
 * its content inline and leaves the scrolling, background and header to the host screen.
 */
export default function LiveDraftRoom({ leagueId, leagueName }: { leagueId: string; leagueName: string }) {
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const { openPlayer: openQuickView } = usePlayerQuickView();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { lens } = useValuationLens(leagueId);

  const [discovery, setDiscovery] = useState<LiveDraftDiscoveryResponse | null>(null);
  const [discoveryError, setDiscoveryError] = useState<string | null>(null);
  const [selectedDraftId, setSelectedDraftId] = useState('');
  const [state, setState] = useState<LiveDraftStateResponse | null>(null);
  const [stateError, setStateError] = useState<string | null>(null);
  const [retryTick, setRetryTick] = useState(0);

  // Rank-movement tracking lives in refs: it must persist across polls
  // without causing its own re-render (same design as web).
  const prevRanks = useRef<Record<string, number>>({});
  const prevTeamRanks = useRef<Record<string, number>>({});
  const stateRef = useRef<LiveDraftStateResponse | null>(null);
  stateRef.current = state;

  useEffect(() => {
    let cancelled = false;
    setDiscoveryError(null);
    api
      .getLiveDraftDiscovery(leagueId)
      .then((result) => {
        if (cancelled) return;
        setDiscovery(result);
        const live = liveDraftsOf(result.drafts);
        setSelectedDraftId(result.active_draft_id || live[0]?.draft_id || '');
      })
      .catch((err) => {
        if (!cancelled) setDiscoveryError(toUserErrorMessage(err, 'Could not reach Sleeper.'));
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, retryTick]);

  const fetchSnapshot = useCallback(async () => {
    if (!selectedDraftId) return;
    try {
      const result = await api.getLiveDraftState(leagueId, selectedDraftId, lens);
      // A Free caller gets a locked response with no rankings at all.
      if (!result.is_premium) {
        setState(result);
        setStateError(null);
        return;
      }
      const movement = diffRankMovement(result.rankings, prevRanks.current);
      const teamMovement = diffTeamRankMovement(result.team_rankings, prevTeamRanks.current);
      prevRanks.current = ranksById(result.rankings);
      prevTeamRanks.current = teamRanksById(result.team_rankings);
      setState({
        ...result,
        rankings: result.rankings.map((row) => ({ ...row, movement: movement[row.player_id] ?? 0 })),
        team_rankings: result.team_rankings.map((row) => ({
          ...row,
          movement: teamMovement[String(row.roster_id)] ?? 0,
        })),
      });
      setStateError(null);
    } catch (err) {
      // Keep showing the last valid board on a transient failure.
      if (!stateRef.current) setStateError(toUserErrorMessage(err, 'Could not load the live draft board.'));
    }
  }, [leagueId, selectedDraftId, lens]);

  // Poll only while this screen is focused; stop once the draft completes.
  useFocusEffect(
    useCallback(() => {
      if (!selectedDraftId) return undefined;
      void fetchSnapshot();
      const interval = setInterval(() => {
        if (stateRef.current?.status === 'complete') return;
        void fetchSnapshot();
      }, POLL_INTERVAL_MS);
      return () => clearInterval(interval);
    }, [selectedDraftId, fetchSnapshot]),
  );

  const selectDraft = (draftId: string) => {
    prevRanks.current = {};
    prevTeamRanks.current = {};
    setState(null);
    setSelectedDraftId(draftId);
  };

  const openPlayer = (row: Parameters<typeof leanPlayer>[0]) =>
    openQuickView(leanPlayer(row), { leagueId, leagueName });

  if (!discovery && !discoveryError) {
    return <SkeletonList label="the live draft room" count={5} />;
  }
  if (discoveryError || !discovery) {
    return (
      <View style={styles.center}>
        <ErrorState
          title="Couldn't load the live draft room"
          message={discoveryError}
          onRetry={() => {
            setDiscovery(null);
            setRetryTick((n) => n + 1);
          }}
        />
      </View>
    );
  }

  if (!discovery.is_premium) {
    return (
      <View style={styles.content}>
          <PremiumLock
            title={discovery.upsell?.title || 'Draft with real-time recommendations'}
            description={
              discovery.upsell?.body ||
              'Live Draft is a Pro feature: Best Available/Best Fit picks, a live roster-strength board, and positional-run alerts while your draft is actually happening.'
            }
            feature="live_draft"
            leagueName={leagueName}
          />
      </View>
    );
  }

  const liveOrPaused = liveDraftsOf(discovery.drafts);
  const hasCompleted = discovery.drafts.some((d) => d.status === 'complete');

  return (
    <View style={styles.content}>
        <AppText style={styles.intro}>
          Read-only Sleeper draft-room assistant. Picks and recommendations update automatically. Nothing is
          submitted to Sleeper.
        </AppText>
        <View style={styles.previewNote}>
          <ToneBadge label="Coming soon" color={colors.premium} size="xs" />
          <AppText style={styles.previewText}>
            Still being tested against a real live draft. Treat recommendations as a preview.
          </AppText>
        </View>

        {liveOrPaused.length === 0 ? (
          <EmptyState
            icon="timer-outline"
            title="No live draft right now"
            subtitle={
              discovery.drafts.length === 0
                ? 'No Sleeper drafts were found for this league yet.'
                : hasCompleted
                  ? 'The latest Sleeper draft has ended. Live Draft activates again when a draft is in progress or paused.'
                  : 'No live Sleeper draft is active. This workspace appears only while a draft is in progress or paused.'
            }
          />
        ) : (
          <>
            {liveOrPaused.length > 1 ? (
              <View style={styles.draftPicker}>
                {liveOrPaused.map((draft) => {
                  const active = draft.draft_id === selectedDraftId;
                  return (
                    <Pressable
                      key={draft.draft_id}
                      accessibilityRole="button"
                      accessibilityState={{ selected: active }}
                      onPress={() => selectDraft(draft.draft_id)}
                      style={[styles.draftChip, active && styles.draftChipActive]}
                    >
                      <AppText style={[styles.draftChipText, active && { color: colors.accentOnTint }]} numberOfLines={1}>
                        {draft.name || `Draft ${draft.draft_id}`} · {draft.season} · {draft.status}
                      </AppText>
                    </Pressable>
                  );
                })}
              </View>
            ) : null}

            {stateError ? (
              <ErrorState
                compact
                title="Couldn't load the board"
                message={stateError}
                onRetry={() => {
                  setStateError(null);
                  void fetchSnapshot();
                }}
              />
            ) : null}

            {!state && !stateError ? (
              <SkeletonList label="the draft board" count={5} />
            ) : state && state.is_premium ? (
              <DraftBoard
                state={state}
                leagueId={leagueId}
                leagueName={leagueName}
                selectedDraftId={selectedDraftId}
                lens={lens}
                colors={colors}
                styles={styles}
                onOpenPlayer={openPlayer}
                onCompare={(row) =>
                  navigation.navigate('PlayerCompare', { player: leanPlayer(row), leagueId, leagueName })
                }
                onRefresh={() => void fetchSnapshot()}
              />
            ) : null}
          </>
        )}
        <ValuesCredit />
    </View>
  );
}

type Styles = ReturnType<typeof createStyles>;

function DraftBoard({
  state,
  leagueId,
  selectedDraftId,
  lens,
  colors,
  styles,
  onOpenPlayer,
  onCompare,
  onRefresh,
}: {
  state: LiveDraftStateResponse;
  leagueId: string;
  leagueName: string;
  selectedDraftId: string;
  lens: React.ComponentProps<typeof LiveDraftTradeEvaluator>['lens'];
  colors: ThemeColors;
  styles: Styles;
  onOpenPlayer: (row: Parameters<typeof leanPlayer>[0]) => void;
  onCompare: (row: Parameters<typeof leanPlayer>[0]) => void;
  onRefresh: () => void;
}) {
  const chips = [
    state.status,
    `${state.picks_made} picks logged`,
    `${state.rounds} rounds`,
    `${state.teams} teams`,
    state.league_settings.scoring_format,
    state.league_settings.qb_format,
    state.league_settings.league_format,
    state.score_label,
  ].filter(Boolean);

  return (
    <View style={styles.board}>
      <View style={styles.chipRow}>
        {chips.map((chip, index) => (
          <ToneBadge key={index} label={String(chip)} color={colors.textSecondary} size="xs" />
        ))}
      </View>

      {state.pick_data_stale ? (
        <AppText style={[styles.note, { color: colors.premium }]}>
          Sleeper pick data is temporarily unavailable. Showing the last valid read-only board.
        </AppText>
      ) : null}
      {state.status === 'complete' ? (
        <AppText style={[styles.note, { color: colors.success, fontWeight: '700' }]}>
          Draft complete. Live polling is paused.
        </AppText>
      ) : null}

      <AnimatedCard glow={state.is_my_pick} glowColor={colors.accent} style={styles.clock}>
        <AppText style={styles.kicker}>On the clock</AppText>
        <AppText style={styles.clockTitle}>
          Pick {state.current_pick} · Round {state.current_round}
        </AppText>
        <AppText style={styles.clockSub}>
          {state.current_manager_name} · {state.current_team_name}
        </AppText>
        <AppText style={styles.muted}>
          {state.is_my_pick
            ? 'You are on the clock'
            : state.picks_until_mine !== null
              ? `${state.picks_until_mine} picks away`
              : 'Slot unavailable'}
        </AppText>
        <AppText style={styles.muted}>
          Your next picks:{' '}
          {state.my_upcoming_picks.length > 0 ? state.my_upcoming_picks.map((p) => `#${p}`).join(', ') : 'Unavailable'}
        </AppText>
        <AppText style={styles.muted}>Recent run: {state.positional_run}</AppText>
      </AnimatedCard>

      {state.draft_context ? (
        <CompactModule
          id="live-draft.context"
          title="Your draft context"
          persist={false}
          parts={state.draft_context.parts.map((text, i) => ({ key: `c${i}`, text, strong: i === 0 }))}
        >
          {state.draft_context.lines.map((line) => (
            <AppText key={line} style={styles.muted}>
              {'\u2022 '}
              {line}
            </AppText>
          ))}
        </CompactModule>
      ) : null}

      <View>
        <SectionHeading title="Who should I draft next?" icon="sparkles-outline" />
        {state.recommendations.length === 0 ? (
          <EmptyState icon="bulb-outline" title="No recommendations yet" subtitle="They appear once the board has enough data." />
        ) : (
          <View style={styles.recList}>
            <RecommendationCard rec={state.recommendations[0]} primary styles={styles} colors={colors} onOpen={onOpenPlayer} />
            {state.recommendations.length > 1 ? (
              <>
                <AppText style={styles.kicker}>Also consider</AppText>
                {state.recommendations.slice(1).map((rec) => (
                  <RecommendationCard
                    key={rec.player_id}
                    rec={rec}
                    primary={false}
                    styles={styles}
                    colors={colors}
                    onOpen={onOpenPlayer}
                  />
                ))}
              </>
            ) : null}
          </View>
        )}
      </View>

      <RankingsBoard rows={state.rankings} styles={styles} colors={colors} onOpen={onOpenPlayer} onCompare={onCompare} />
      {state.adp_source ? <AdpCredit asOf={state.adp_source.as_of} style={styles.muted} /> : null}
      {state.adp_est_sf_note ? <AppText style={styles.muted}>Est. SF is modeled, not real ADP. {state.adp_est_sf_note}</AppText> : null}

      <View>
        <SectionHeading
          title="Live Team Rankings"
          icon="podium-outline"
          caption="60% starter strength, 30% total roster value, 7% usable depth, 3% lineup coverage."
        />
        {state.team_rankings.length === 0 ? (
          <AppText style={styles.muted}>Team rankings will appear when draft rosters are available.</AppText>
        ) : (
          <AnimatedCard style={styles.listCard}>
            {state.team_rankings.map((row, index) => (
              <TeamRankingRow
                key={row.roster_id}
                row={row}
                last={index === state.team_rankings.length - 1}
                styles={styles}
                colors={colors}
              />
            ))}
          </AnimatedCard>
        )}
      </View>

      <View>
        <SectionHeading title="Draft Board" icon="list-outline" caption="Latest pick and your picks are highlighted." />
        {state.pick_rows.length === 0 ? (
          <EmptyState icon="list-outline" title="No picks logged yet" subtitle="This board fills as Sleeper reports selections." />
        ) : (
          <AnimatedCard style={styles.listCard}>
            {[...state.pick_rows].reverse().map((row, index, all) => (
              <Pressable
                key={row.pick_no}
                accessibilityRole="button"
                onPress={() =>
                  onOpenPlayer({
                    player_id: row.player_id,
                    name: row.player_name,
                    position: row.position,
                    team: row.team,
                    age: null,
                    tier: '',
                  })
                }
                style={[styles.pickRow, row.is_mine && styles.mineBg, index < all.length - 1 && styles.divider]}
              >
                <PickPlate round={row.round} pickNo={row.pick_no} />
                <View style={styles.flex}>
                  <CompactPlayerCard
                    player={{ id: row.player_id, name: row.player_name, position: row.position, team: row.team }}
                    detail={`${row.team} · ${row.fantasy_team}`}
                    nonInteractive="the pick row Pressable already opens this player"
                    testID="live-draft-pick-player"
                  />
                </View>
              </Pressable>
            ))}
          </AnimatedCard>
        )}
      </View>

      {state.status === 'drafting' || state.status === 'paused' ? (
        <LiveDraftTradeEvaluator leagueId={leagueId} draftId={selectedDraftId} draftedRows={state.pick_rows} lens={lens} />
      ) : null}

      <View style={styles.refreshRow}>
        <Button label="Refresh Draft" variant="secondary" onPress={onRefresh} style={styles.flex} />
      </View>
      <AppText style={[styles.muted, styles.centerText]}>
        Last updated: {state.last_updated} · Polls every 12s
      </AppText>
    </View>
  );
}

function RecommendationCard({
  rec,
  primary,
  styles,
  colors,
  onOpen,
}: {
  rec: LiveDraftRecommendation;
  primary: boolean;
  styles: Styles;
  colors: ThemeColors;
  onOpen: (row: Parameters<typeof leanPlayer>[0]) => void;
}) {
  return (
    <AnimatedCard glow={primary} glowColor={colors.accent} style={styles.recCard} onPress={() => onOpen(rec)}>
      <PlayerIdentityRow
        playerId={rec.player_id}
        name={rec.name || `Player ${rec.player_id}`}
        position={rec.position}
        team={rec.team}
        tier={rec.tier}
        overallRating={rec.overall_rating}
        trailingValue={formatLiveDraftScore(rec.league_adjusted_draft_score)}
        trailingTone="accent"
        nonInteractive="The recommendation card is a button that already opens the player"
        showDivider={false}
      />
      <View style={styles.chipRow}>
        <ToneBadge label={rec.recommendation_role} color={colors.accent} size="xs" />
        {!primary ? <ToneBadge label={`${rec.confidence} confidence`} color={colors.textSecondary} size="xs" /> : null}
        {rec.position_need_impact ? <ToneBadge label={rec.position_need_impact} color={colors.success} size="xs" /> : null}
      </View>
      {primary ? (
        <View style={styles.recDetail}>
          <AppText style={styles.recReason}>{rec.recommendation_reason}</AppText>
          <AppText style={styles.muted}>Roster impact: {rec.immediate_roster_impact}</AppText>
          <AppText style={styles.muted}>
            Value vs ADP: {rec.adp_delta != null ? `${rec.adp_delta > 0 ? '+' : ''}${rec.adp_delta}` : 'unavailable'}
          </AppText>
          {rec.adp != null ? (
            <AdpLine
              style={styles.muted}
              adp={{ adp: rec.adp ?? null, adp_label: rec.adp_label, adp_est_sf: rec.adp_est_sf, adp_est_sf_label: rec.adp_est_sf_label }}
            />
          ) : null}
          {rec.adp_read ? <AppText style={styles.muted}>{rec.adp_read}</AppText> : null}
          <AppText style={styles.muted}>Confidence: {rec.confidence}</AppText>
          {(rec.context_notes ?? []).map((note) => (
            <AppText key={note} style={styles.muted}>
              {'\u2022 '}
              {note}
            </AppText>
          ))}
        </View>
      ) : null}
    </AnimatedCard>
  );
}

function RankingsBoard({
  rows,
  styles,
  colors,
  onOpen,
  onCompare,
}: {
  rows: LiveDraftRankingRow[];
  styles: Styles;
  colors: ThemeColors;
  onOpen: (row: Parameters<typeof leanPlayer>[0]) => void;
  onCompare: (row: Parameters<typeof leanPlayer>[0]) => void;
}) {
  const [filter, setFilter] = useState<LiveDraftRankFilter>('Overall');
  const [expanded, setExpanded] = useState<string | null>(null);
  const options = useMemo(() => liveDraftRankFilterOptions(rows), [rows]);
  const filtered = useMemo(() => filterLiveDraftRankings(rows, filter), [rows, filter]);
  const visible = filtered.slice(0, MAX_RANK_ROWS);

  return (
    <View>
      <SectionHeading
        title="Available Players"
        icon="people-outline"
        caption="Every undrafted player, reranked for this league and your roster. Tap a score for its breakdown."
        right={
          <FilterDropdownButton
            label="Position"
            options={options}
            value={options.includes(filter) ? filter : 'Overall'}
            onChange={setFilter}
            allValue="Overall"
          />
        }
      />
      {visible.length === 0 ? (
        <EmptyState icon="people-outline" title="No available players loaded yet" subtitle="Try another filter or refresh in a moment." />
      ) : (
        <AnimatedCard style={styles.listCard}>
          {visible.map((row, index) => {
            const last = index === visible.length - 1;
            const open = expanded === row.player_id;
            return (
              <View key={row.player_id} style={!last && styles.divider}>
                <PlayerIdentityRow
                  playerId={row.player_id}
                  name={row.name || `Player ${row.player_id}`}
                  position={row.position}
                  team={row.team}
                  tier={row.tier}
                  overallRating={row.overall_rating}
                  positionRank={row.position_rank}
                  contextLine={[
                    `#${row.overall_rank ?? '—'}`,
                    row.position && row.position_rank ? `${row.position}${row.position_rank}` : '',
                    row.recommendation_label,
                    adpContext({ adp: row.adp ?? null, adp_label: row.adp_label, adp_est_sf: row.adp_est_sf, adp_est_sf_label: row.adp_est_sf_label }),
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                  trailingValue={formatLiveDraftScore(row.league_adjusted_draft_score)}
                  trailingTone="accent"
                  trailingCaption={movementGlyph(row.movement)}
                  onPress={() => onOpen(row)}
                  showDivider={false}
                />
                <Pressable
                  accessibilityRole="button"
                  accessibilityState={{ expanded: open }}
                  accessibilityLabel="Score breakdown"
                  onPress={() => setExpanded(open ? null : row.player_id)}
                  style={styles.breakdownToggle}
                >
                  <AppText style={[styles.breakdownToggleText, { color: colors.accent }]}>
                    {open ? 'Hide score breakdown' : 'Score breakdown'}
                  </AppText>
                </Pressable>
                <Collapse open={open}>
                  <View style={styles.breakdown}>
                    <View style={styles.chipRow}>
                      {SCORE_BREAKDOWN_FIELDS.map(({ key, label }) => (
                        <ToneBadge
                          key={key}
                          label={`${label} ${formatLiveDraftScore(row[key] as number | null)}`}
                          color={colors.textSecondary}
                          size="xs"
                        />
                      ))}
                    </View>
                    <Button label="Compare" variant="secondary" onPress={() => onCompare(row)} style={styles.compareBtn} />
                  </View>
                </Collapse>
              </View>
            );
          })}
        </AnimatedCard>
      )}
      {filtered.length > visible.length ? (
        <AppText style={[styles.muted, styles.captionTop]}>
          Showing the top {visible.length} of {filtered.length} ranked players.
        </AppText>
      ) : null}
    </View>
  );
}

function TeamRankingRow({
  row,
  last,
  styles,
  colors,
}: {
  row: LiveDraftTeamRow;
  last: boolean;
  styles: Styles;
  colors: ThemeColors;
}) {
  const moveColor = row.movement >= 2 ? colors.success : row.movement <= -2 ? colors.danger : colors.textTertiary;
  return (
    <View style={[styles.teamRow, row.is_mine && styles.mineBg, !last && styles.divider]}>
      <AppText style={styles.rank}>#{row.team_rank}</AppText>
      <View style={styles.flex}>
        <View style={styles.nameLine}>
          <AppText style={styles.rowName} numberOfLines={1}>
            {row.team_name}
          </AppText>
          {row.is_mine ? <ToneBadge label="You" color={colors.accent} size="xs" /> : null}
        </View>
        <AppText style={styles.muted} numberOfLines={2}>
          {row.trend_label ? `${row.trend_label} · ` : ''}
          {row.positions || 'No players yet'}
        </AppText>
      </View>
      <View style={styles.teamRight}>
        <AppText style={[styles.score, { color: colors.accent }]}>{Math.round(row.live_team_score)}</AppText>
        <AppText style={styles.muted}>{row.pick_count} picks</AppText>
        <AppText style={[styles.move, { color: moveColor }]}>{movementGlyph(row.movement)}</AppText>
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    content: { gap: spacing.lg },
    center: { alignItems: 'center', justifyContent: 'center', padding: spacing.xl },
    flex: { flex: 1 },
    inlineSpinner: { paddingVertical: spacing.xl },
    intro: { fontSize: 14.5, color: colors.textSecondary, lineHeight: 20 },
    previewNote: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, borderLeftWidth: 3, borderLeftColor: colors.premium, paddingLeft: spacing.sm },
    previewText: { flex: 1, fontSize: 13.5, color: colors.textSecondary },
    draftPicker: { gap: spacing.xs },
    draftChip: { minHeight: 44, justifyContent: 'center', borderRadius: radii.pill, borderWidth: 1, borderColor: colors.border, paddingHorizontal: spacing.md },
    draftChipActive: { backgroundColor: colors.accentMuted, borderColor: colors.accent },
    draftChipText: { fontSize: 14.5, fontWeight: '600', color: colors.textSecondary },
    board: { gap: spacing.lg },
    chipRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
    note: { fontSize: 13.5 },
    clock: { padding: spacing.md, gap: 2 },
    kicker: { fontSize: 12.5, fontWeight: '700', color: colors.textTertiary, textTransform: 'uppercase', letterSpacing: 0.5 },
    clockTitle: { fontSize: 21, fontWeight: '700', color: colors.textPrimary, letterSpacing: -0.3 },
    clockSub: { fontSize: 15.5, color: colors.textSecondary, marginBottom: spacing.xs },
    muted: { fontSize: 13.5, color: colors.textTertiary },
    centerText: { textAlign: 'center' },
    captionTop: { marginTop: spacing.xs },
    recList: { gap: spacing.sm },
    recCard: { padding: spacing.md, gap: spacing.sm },
    recDetail: { gap: 2 },
    recReason: { fontSize: 14.5, color: colors.textSecondary, lineHeight: 20 },
    listCard: { paddingVertical: spacing.xs },
    divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    mineBg: { backgroundColor: colors.badgeBackground },
    pickRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingHorizontal: spacing.md, paddingVertical: spacing.sm, minHeight: 52 },
    rowName: { fontSize: 15.5, fontWeight: '700', color: colors.textPrimary, flexShrink: 1 },
    nameLine: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
    teamRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
    rank: { width: 32, fontSize: 13.5, fontWeight: '700', color: colors.textTertiary },
    teamRight: { alignItems: 'flex-end' },
    score: { fontSize: 17, fontWeight: '800' },
    move: { fontSize: 12.5, fontWeight: '700' },
    breakdownToggle: { minHeight: 32, justifyContent: 'center', paddingHorizontal: spacing.md },
    breakdownToggleText: { fontSize: 13.5, fontWeight: '600' },
    breakdown: { paddingHorizontal: spacing.md, paddingBottom: spacing.sm, gap: spacing.sm },
    compareBtn: { alignSelf: 'flex-start', paddingVertical: spacing.sm, minHeight: 36 },
    refreshRow: { flexDirection: 'row' },
  });
}
