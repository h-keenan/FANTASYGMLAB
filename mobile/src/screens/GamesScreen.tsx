import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ScrollView, StyleSheet, TouchableOpacity, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import AppText from '../components/AppText';
import BrandedSpinner from '../components/BrandedSpinner';
import BrandHeaderBar from '../components/BrandHeaderBar';
import Button from '../components/Button';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import GridBackground from '../components/GridBackground';
import Input from '../components/Input';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import PremiumLock from '../components/PremiumLock';
import SectionHeading from '../components/SectionHeading';
import SegmentedTabBar from '../components/SegmentedTabBar';
import TeamAvatar from '../components/TeamAvatar';
import ToneBadge from '../components/ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  api,
  type GamesPickemMatchup,
  type GamesPickemResponse,
  type GamesSeasonSimResponse,
  type GamesWhatIfResponse,
  type RankedPlayer,
} from '../lib/api';
import { toUserErrorMessage } from '../lib/errorMessages';
import {
  formatDelta,
  formatOdds,
  gamesReasonAction,
  gamesReasonMessage,
  matchPlayersByName,
  PICKEM_PHASE_LABEL,
  recordLabel,
  seedChangeLabel,
  whatIfSummary,
  whatIfTone,
  withPick,
} from '../lib/gamesPresentation';
import { useOrbClearance } from '../lib/orbLayout';
import { percentileColor } from '../lib/percentile';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { radii, spacing, type ThemeColors } from '../theme';

type Props = NativeStackScreenProps<RootStackParamList, 'Games'>;
type Tab = 'sim' | 'pickem';

const MAX_PLAYERS = 3;

/**
 * Games: the Season Simulator (the shared playoff-odds Monte Carlo plus a
 * Premium what-if) and a weekly Pick'em inside the user's own league.
 * Mirrors web-next's GamesContent; every number comes from modules/games.py.
 */
export default function GamesScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const headerHeight = useHeaderHeight();
  const orbClearance = useOrbClearance();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [tab, setTab] = useState<Tab>('sim');

  useScreenHeaderTitle(navigation, 'Games', leagueName);

  return (
    <View style={[styles.root, { paddingTop: headerHeight }]}>
      <GridBackground />
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
      <ScrollView contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>
        <SegmentedTabBar
          options={[
            { key: 'sim', label: 'Season Sim' },
            { key: 'pickem', label: "Pick'em" },
          ]}
          active={tab}
          onChange={setTab}
        />
        {tab === 'sim' ? (
          <SeasonSim leagueId={leagueId} colors={colors} styles={styles} navigation={navigation} />
        ) : (
          <Pickem leagueId={leagueId} colors={colors} styles={styles} navigation={navigation} />
        )}
      </ScrollView>
    </View>
  );
}

type Shared = {
  leagueId: string;
  colors: ThemeColors;
  styles: ReturnType<typeof createStyles>;
  navigation: Props['navigation'];
};

function ReasonState({ reason, navigation }: { reason: string; navigation: Props['navigation'] }) {
  const toAccount = gamesReasonAction(reason) === 'account';
  return (
    <EmptyState
      icon="dice-outline"
      title={gamesReasonMessage(reason)}
      actionLabel={toAccount ? 'Open Account' : 'Back to Home'}
      onPressAction={() => navigation.navigate(toAccount ? 'More' : 'Home')}
    />
  );
}

function SeasonSim({ leagueId, colors, styles, navigation }: Shared) {
  const [data, setData] = useState<GamesSeasonSimResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getGamesSeasonSim(leagueId)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(toUserErrorMessage(err, 'Could not load the simulator.'));
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId]);

  if (error) return <ErrorState title="Couldn't load the simulator" message={error} />;
  if (!data) return <BrandedSpinner />;
  if (data.reason || !data.my_team) return <ReasonState reason={data.reason || 'unavailable'} navigation={navigation} />;

  const mine = data.my_team;
  const status = mine.clinched ? 'Clinched' : mine.eliminated ? 'Eliminated' : null;
  return (
    <View style={styles.section}>
      <SectionHeading
        title="Your odds"
        caption={
          data.weeks_remaining === 0
            ? 'No games left. These are final results.'
            : `${data.weeks_remaining ?? ''} weeks left, your real schedule and Roster Power.`
        }
      />
      <View style={styles.card}>
        <View>
          <AppText style={[styles.bigOdds, { color: percentileColor(mine.playoff_probability, colors) }]}>
            {formatOdds(mine.playoff_probability)}
          </AppText>
          <AppText style={styles.muted}>Playoff odds</AppText>
        </View>
        <View style={styles.alignEnd}>
          <AppText style={styles.muted}>
            Proj {mine.median_final_wins}-{mine.median_final_losses}
          </AppText>
          <AppText style={styles.muted}>Seed #{mine.median_seed}</AppText>
          {status ? <ToneBadge label={status} color={mine.clinched ? colors.success : colors.danger} /> : null}
        </View>
      </View>

      <WhatIf leagueId={leagueId} data={data} colors={colors} styles={styles} navigation={navigation} />

      <SectionHeading title="Playoff odds" caption="Same simulation for every team." />
      <View style={styles.card2}>
        {data.teams.map((team, index) => (
          <View key={team.roster_id} style={[styles.teamRow, team.mine && styles.teamRowMine, index > 0 && styles.divider]}>
            <AppText style={styles.rank}>{index + 1}</AppText>
            <TeamAvatar avatarId={team.avatar_url} name={team.team_name} size={32} />
            <View style={styles.flex}>
              <AppText style={styles.teamName} numberOfLines={1}>
                {team.team_name}
              </AppText>
              <AppText style={styles.muted}>
                {team.record_label ? `${team.record_label} · ` : ''}Seed #{team.median_seed}
              </AppText>
            </View>
            <AppText style={[styles.metric, { color: percentileColor(team.playoff_probability, colors) }]}>
              {formatOdds(team.playoff_probability)}
            </AppText>
          </View>
        ))}
      </View>
    </View>
  );
}

function WhatIf({ leagueId, data, colors, styles }: Shared & { data: GamesSeasonSimResponse }) {
  const [drops, setDrops] = useState<string[]>([]);
  const [adds, setAdds] = useState<RankedPlayer[]>([]);
  const [pool, setPool] = useState<RankedPlayer[] | null>(null);
  const [search, setSearch] = useState('');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<GamesWhatIfResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loadedPool = useRef(false);

  const rosterIds = useMemo(() => new Set(data.roster.map((p) => p.player_id)), [data.roster]);

  const loadPool = useCallback(() => {
    if (loadedPool.current) return;
    loadedPool.current = true;
    api
      .getLeagueRankings(leagueId)
      .then((response) => setPool(response.players ?? []))
      .catch(() => {
        loadedPool.current = false;
      });
  }, [leagueId]);

  const matches = useMemo(() => {
    if (!pool) return [];
    const taken = new Set(adds.map((p) => p.player_id));
    return matchPlayersByName(
      pool.filter((p) => !rosterIds.has(p.player_id) && !taken.has(p.player_id)),
      search,
    );
  }, [pool, adds, rosterIds, search]);

  if (!data.is_premium) {
    return (
      <PremiumLock
        title={data.upsell?.title ?? 'See how a move changes your season'}
        description={
          data.upsell?.body ?? 'Add or drop players and see the change in your playoff odds before you make the move.'
        }
        feature="games_what_if"
      />
    );
  }

  const toggleDrop = (id: string) =>
    setDrops((current) =>
      current.includes(id) ? current.filter((x) => x !== id) : current.length < MAX_PLAYERS ? [...current, id] : current,
    );

  const run = () => {
    setRunning(true);
    setError(null);
    api
      .postGamesWhatIf(leagueId, { add: adds.map((p) => p.player_id), drop: drops })
      .then(setResult)
      .catch((err) => setError(toUserErrorMessage(err, 'Could not run the what-if.')))
      .finally(() => setRunning(false));
  };

  const change = result?.change;
  const tone = change ? whatIfTone(change) : 'neutral';
  const toneColor = tone === 'positive' ? colors.success : tone === 'negative' ? colors.danger : colors.textTertiary;
  return (
    <View style={styles.section}>
      <SectionHeading title="What if" caption={`Premium. Up to ${MAX_PLAYERS} players on each side.`} />
      <View style={styles.card2}>
        <AppText style={styles.label}>DROP</AppText>
        {data.roster.map((player) => (
          <PlayerIdentityRow
            key={player.player_id}
            playerId={player.player_id}
            name={player.name}
            position={player.position}
            team={player.team}
            tier={player.tier}
            injuryLabel={player.injury_status}
            trailingExtra={
              drops.includes(player.player_id) ? <ToneBadge label="Dropping" color={colors.accent} size="xs" /> : null
            }
            onPress={() => toggleDrop(player.player_id)}
          />
        ))}
      </View>
      <View style={styles.card2}>
        <AppText style={styles.label}>ADD</AppText>
        {adds.map((player) => (
          <PlayerIdentityRow
            key={player.player_id}
            playerId={player.player_id}
            name={player.name}
            position={player.position}
            team={player.team}
            tier={player.tier}
            injuryLabel={player.injury_status}
            trailingExtra={<ToneBadge label="Remove" color={colors.danger} size="xs" />}
            onPress={() => setAdds((c) => c.filter((p) => p.player_id !== player.player_id))}
          />
        ))}
        {adds.length < MAX_PLAYERS ? (
          <>
            <Input
              accessibilityLabel="Search players to add"
              placeholder="Search players to add"
              value={search}
              onFocus={loadPool}
              onChangeText={(text) => {
                loadPool();
                setSearch(text);
              }}
              autoCorrect={false}
            />
            {matches.map((player) => (
              <PlayerIdentityRow
                key={player.player_id}
                playerId={player.player_id}
                name={player.name}
                position={player.position}
                team={player.team}
                tier={player.tier}
                injuryLabel={player.injury_status}
                trailingExtra={<ToneBadge label="Add" color={colors.accent} size="xs" />}
                onPress={() => {
                  setAdds((c) => [...c, player]);
                  setSearch('');
                }}
              />
            ))}
          </>
        ) : null}
      </View>
      <Button
        label="Run what-if"
        onPress={run}
        disabled={(adds.length === 0 && drops.length === 0) || running}
        loading={running}
      />
      {error ? <AppText style={styles.error}>{error}</AppText> : null}
      {result?.reason ? <ReasonText reason={result.reason} styles={styles} /> : null}
      {result && !result.reason && change && result.baseline && result.scenario ? (
        <View style={styles.card2}>
          <View style={styles.rowBetween}>
            <AppText style={styles.muted}>
              {formatOdds(result.baseline.playoff_probability)} {'->'}{' '}
              <AppText style={[styles.metric, { color: toneColor }]}>{formatOdds(result.scenario.playoff_probability)}</AppText>
            </AppText>
            <ToneBadge label={`${formatDelta(change.playoff_probability)} pts`} color={toneColor} />
          </View>
          <AppText style={styles.body}>{whatIfSummary(change)}</AppText>
          <AppText style={styles.muted}>
            Proj {result.scenario.median_final_wins}-{result.scenario.median_final_losses} · {seedChangeLabel(change.median_seed)}
          </AppText>
          {(result.factors ?? []).map((factor) => (
            <View key={factor.label} style={styles.rowBetween}>
              <AppText style={styles.muted}>{factor.label}</AppText>
              <AppText style={styles.factor}>{factor.detail}</AppText>
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function ReasonText({ reason, styles }: { reason: string; styles: ReturnType<typeof createStyles> }) {
  return <AppText style={styles.muted}>{gamesReasonMessage(reason)}</AppText>;
}

function Pickem({ leagueId, colors, styles, navigation }: Shared) {
  const [data, setData] = useState<GamesPickemResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  const load = useCallback(
    (week?: number) => {
      api
        .getGamesPickem(leagueId, week)
        .then(setData)
        .catch((err) => setError(toUserErrorMessage(err, "Could not load Pick'em.")));
    },
    [leagueId],
  );

  useEffect(() => {
    load();
  }, [load]);

  if (error) return <ErrorState title="Couldn't load Pick'em" message={error} />;
  if (!data) return <BrandedSpinner />;
  if (!data.available) {
    return (
      <EmptyState
        icon="dice-outline"
        title="Pick'em is not open yet"
        subtitle="Check back soon."
        actionLabel="Back to Home"
        onPressAction={() => navigation.navigate('Home')}
      />
    );
  }
  if (data.reason || !data.matchups || data.week == null) {
    return <ReasonState reason={data.reason || 'unavailable'} navigation={navigation} />;
  }

  const week = data.week;
  const phase = data.phase ?? 'final';
  const weeks = data.weeks ?? [];
  const index = weeks.indexOf(week);

  const pick = (matchup: GamesPickemMatchup, rosterId: string) => {
    if (phase !== 'open') return;
    setSaveError(null);
    setData((current) =>
      current && current.matchups
        ? { ...current, matchups: withPick(current.matchups, matchup.matchup_id, rosterId) }
        : current,
    );
    api
      .postGamesPick(leagueId, { week, matchup_id: matchup.matchup_id, roster_id: rosterId })
      .then((response) => {
        if (!response.ok) {
          setSaveError(response.reason === 'locked' ? 'This week just locked.' : 'Could not save that pick.');
          load(week);
        }
      })
      .catch(() => {
        setSaveError('Could not save that pick.');
        load(week);
      });
  };

  return (
    <View style={styles.section}>
      <SectionHeading title={`Week ${week}`} caption="Pick winners before the week starts. No money, just bragging rights." />
      <View style={styles.rowBetween}>
        <Button label="Prev" variant="secondary" disabled={index <= 0} onPress={() => load(weeks[index - 1])} />
        <View style={styles.alignEnd}>
          <ToneBadge
            label={PICKEM_PHASE_LABEL[phase]}
            color={phase === 'open' ? colors.success : phase === 'locked' ? colors.violet : colors.textTertiary}
          />
          <AppText style={styles.muted}>Your picks {recordLabel(data.season_record)}</AppText>
        </View>
        <Button
          label="Next"
          variant="secondary"
          disabled={index < 0 || index >= weeks.length - 1}
          onPress={() => load(weeks[index + 1])}
        />
      </View>
      {saveError ? <AppText style={styles.error}>{saveError}</AppText> : null}
      {data.matchups.length === 0 ? (
        <EmptyState icon="calendar-outline" title="No matchups this week" />
      ) : (
        data.matchups.map((matchup) => (
          <View key={matchup.matchup_id} style={styles.card2}>
            <View style={styles.pickRow}>
              {matchup.teams.map((team) => {
                const picked = matchup.my_pick === team.roster_id;
                const won = matchup.winner_roster_id === team.roster_id;
                return (
                  <TouchableOpacity
                    key={team.roster_id}
                    accessibilityRole="button"
                    accessibilityState={{ selected: picked, disabled: phase !== 'open' }}
                    disabled={phase !== 'open'}
                    onPress={() => pick(matchup, team.roster_id)}
                    style={[styles.pickTeam, picked && styles.pickTeamOn]}
                  >
                    <TeamAvatar avatarId={team.avatar_url} name={team.team_name} size={36} />
                    <AppText style={styles.teamName} numberOfLines={2}>
                      {team.team_name}
                    </AppText>
                    {phase !== 'open' ? (
                      <AppText style={[styles.muted, won && { color: colors.success }]}>{team.points.toFixed(1)}</AppText>
                    ) : null}
                  </TouchableOpacity>
                );
              })}
            </View>
            {matchup.correct != null ? (
              <ToneBadge
                label={matchup.correct ? 'Correct' : 'Missed'}
                color={matchup.correct ? colors.success : colors.danger}
              />
            ) : null}
          </View>
        ))
      )}

      <SectionHeading
        title="Leaderboard"
        caption={data.leaderboard_scope === 'you' ? 'Showing your picks only.' : 'League members who made picks.'}
      />
      {data.leaderboard && data.leaderboard.length > 0 ? (
        <View style={styles.card2}>
          {data.leaderboard.map((row, i) => (
            <View key={row.roster_id} style={[styles.teamRow, row.mine && styles.teamRowMine, i > 0 && styles.divider]}>
              <AppText style={styles.rank}>{row.rank}</AppText>
              <TeamAvatar avatarId={row.avatar_url} name={row.team_name} size={32} />
              <View style={styles.flex}>
                <AppText style={styles.teamName} numberOfLines={1}>
                  {row.team_name}
                </AppText>
                <AppText style={styles.muted}>{row.accuracy}%</AppText>
              </View>
              <AppText style={[styles.metric, { color: percentileColor(row.accuracy, colors) }]}>
                {row.correct}/{row.graded}
              </AppText>
            </View>
          ))}
        </View>
      ) : (
        <EmptyState
          icon="trophy-outline"
          title="No graded picks yet"
          subtitle="Standings start once a week you picked is final."
        />
      )}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: colors.background },
    content: { padding: spacing.lg, gap: spacing.md },
    section: { gap: spacing.md },
    flex: { flex: 1 },
    card: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      backgroundColor: colors.surface,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.cardBorder,
      padding: spacing.md,
    },
    card2: {
      backgroundColor: colors.surface,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.cardBorder,
      padding: spacing.md,
      gap: spacing.sm,
    },
    bigOdds: { fontSize: 36, fontWeight: '800' },
    alignEnd: { alignItems: 'flex-end', gap: 4 },
    rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    label: { fontSize: 11, fontWeight: '700', letterSpacing: 0.4, color: colors.textTertiary },
    muted: { fontSize: 12, color: colors.textSecondary },
    body: { fontSize: 14, color: colors.textPrimary },
    factor: { fontSize: 12, color: colors.textPrimary },
    error: { fontSize: 12, color: colors.danger },
    teamRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.sm },
    teamRowMine: { backgroundColor: colors.badgeBackground },
    divider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
    rank: { width: 24, textAlign: 'center', fontSize: 13, fontWeight: '800', color: colors.textTertiary },
    teamName: { fontSize: 14, fontWeight: '600', color: colors.textPrimary, textAlign: 'center' },
    metric: { fontSize: 15, fontWeight: '800' },
    pickRow: { flexDirection: 'row', gap: spacing.sm },
    pickTeam: {
      flex: 1,
      alignItems: 'center',
      gap: spacing.xs,
      padding: spacing.md,
      minHeight: 44,
      borderRadius: radii.sm,
      borderWidth: 1,
      borderColor: colors.border,
    },
    pickTeamOn: { borderColor: colors.accent, backgroundColor: colors.badgeBackground },
  });
}
