import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import AccentCard from '../components/AccentCard';
import AppText from '../components/AppText';
import BrandHeaderBar from '../components/BrandHeaderBar';
import Button from '../components/Button';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import GridBackground from '../components/GridBackground';
import PremiumLock from '../components/PremiumLock';
import SectionHeading from '../components/SectionHeading';
import SegmentedTabBar from '../components/SegmentedTabBar';
import { SkeletonCard } from '../components/SkeletonBlock';
import ToneBadge from '../components/ToneBadge';
import Toggle from '../components/Toggle';
import { useThemeMode } from '../context/ThemeModeContext';
import { api, type LineupPlayer, type TeamRanking } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import {
  DEFAULT_SIM_STRATEGY,
  SIM_DISCLAIMER,
  SIM_LABEL,
  SIM_MODE_OPTIONS,
  SIM_POSTURE_OPTIONS,
  isSimOffError,
  simCompareHeadline,
  simCompareRows,
  simDecisionKindLabel,
  simFormatPercent,
  simFormatPoints,
  simFormatRecord,
  simFormatSigned,
  simGate,
  simGradeTone,
  simLevelLabel,
  simNoteMessages,
  simPlayoffResultLabel,
  simPowerLabel,
  simReasonMessage,
  simRoundLabel,
  simStrategyEqual,
  simStrategySummary,
  simTeamNames,
  simTimeline,
  type SimMode,
  type SimResult,
  type SimStrategy,
  type SimTone,
  type SimUpsell,
  type SimWorld,
} from '../lib/simPresentation';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'FantasySim'>;

type Phase =
  | { kind: 'loading' }
  | { kind: 'unavailable' }
  | { kind: 'premium'; upsell: SimUpsell | null }
  | { kind: 'setup' }
  | { kind: 'running' }
  | { kind: 'result' }
  | { kind: 'error'; message: string };

type ResultTab = 'summary' | 'standings' | 'playoffs' | 'timeline' | 'scouting';

const LEVELS = [0, 0.25, 0.5, 0.75, 1] as const;

function errorText(error: unknown, fallback: string): string {
  if (typeof error === 'object' && error !== null) {
    const e = error as { status?: number; code?: string; message?: string };
    if (e.status === 503 || e.code === 'server_busy') return 'The simulator is busy right now. Try again in a few seconds.';
    if (e.message) return e.message;
  }
  return fallback;
}

export default function FantasySimScreen({ route, navigation }: Props) {
  const { leagueId, leagueName } = route.params;
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  useScreenHeaderTitle(navigation, 'Fantasy Sim', leagueName);

  const toneColor = useCallback(
    (tone: SimTone) => ({ success: colors.success, accent: colors.accent, warning: colors.warning, danger: colors.danger })[tone],
    [colors],
  );

  const [phase, setPhase] = useState<Phase>({ kind: 'loading' });
  const [worlds, setWorlds] = useState<SimWorld[]>([]);
  const [teams, setTeams] = useState<TeamRanking[]>([]);
  const [roster, setRoster] = useState<LineupPlayer[]>([]);
  const [mode, setMode] = useState<SimMode>('remaining');
  const [rosterId, setRosterId] = useState('');
  const [strategy, setStrategy] = useState<SimStrategy>(DEFAULT_SIM_STRATEGY);
  const [world, setWorld] = useState<SimWorld | null>(null);
  const [runs, setRuns] = useState<SimResult[]>([]);
  const [notes, setNotes] = useState<string[]>([]);
  const [teamName, setTeamName] = useState('Your team');
  const [notice, setNotice] = useState('');
  const [editing, setEditing] = useState(false);
  const [tab, setTab] = useState<ResultTab>('summary');
  const [onlyMine, setOnlyMine] = useState(true);
  const [showProtected, setShowProtected] = useState(false);
  const [attempt, setAttempt] = useState(0);

  const result = runs.length > 0 ? runs[runs.length - 1] : null;
  const previous = runs.length > 1 ? runs[runs.length - 2] : null;

  const refreshWorlds = useCallback(async () => {
    try {
      const list = await api.listSimWorlds();
      setWorlds(list.worlds ?? []);
    } catch {
      /* best-effort */
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    api
      .getSimStatus()
      .then((status) => {
        if (cancelled) return;
        const gate = simGate(status);
        if (gate.kind === 'premium') setPhase({ kind: 'premium', upsell: gate.upsell });
        else if (gate.kind === 'unavailable') setPhase({ kind: 'unavailable' });
        else setPhase({ kind: 'setup' });
      })
      .catch((error) => {
        if (cancelled) return;
        if (isSimOffError(error)) setPhase({ kind: 'unavailable' });
        else setPhase({ kind: 'error', message: errorText(error, 'Could not load Fantasy Sim.') });
      });
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  useEffect(() => {
    if (phase.kind !== 'setup') return;
    let cancelled = false;
    api
      .listSimWorlds()
      .then((r) => {
        if (!cancelled) setWorlds(r.worlds ?? []);
      })
      .catch(() => {});
    api
      .getLeagueTeamRankings(leagueId)
      .then((r) => {
        if (!cancelled) setTeams(r.teams ?? []);
      })
      .catch(() => {});
    api
      .getLeagueMyTeam(leagueId)
      .then((r) => {
        if (!cancelled) setRoster([...(r.starters ?? []), ...(r.bench ?? [])]);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [phase.kind, leagueId]);

  const finishWith = (response: Awaited<ReturnType<typeof api.runSimWorld>>, append: boolean) => {
    const gate = simGate(response);
    if (gate.kind === 'premium') return setPhase({ kind: 'premium', upsell: gate.upsell });
    if (response.reason || !response.result || !response.world) {
      setNotice(simReasonMessage(response.reason) || 'The simulation did not finish. Try again.');
      return setPhase({ kind: append ? 'result' : 'setup' });
    }
    const next = response.result;
    setWorld(response.world);
    setRuns((current) => (append ? [...current, next] : [next]));
    setTab('summary');
    setEditing(false);
    setPhase({ kind: 'result' });
  };

  const run = async () => {
    setNotice('');
    setPhase({ kind: 'running' });
    try {
      const created = await api.createSimWorld({ league_id: leagueId, mode, strategy, ...(rosterId ? { roster_id: rosterId } : {}) });
      const gate = simGate(created);
      if (gate.kind === 'premium') return setPhase({ kind: 'premium', upsell: gate.upsell });
      if (created.reason || !created.world) {
        setNotice(simReasonMessage(created.reason) || 'Could not start the simulation.');
        if (created.reason === 'world_limit_reached') void refreshWorlds();
        return setPhase({ kind: 'setup' });
      }
      setNotes(created.notes ?? []);
      setTeamName(created.team?.name ?? 'Your team');
      setRuns([]);
      finishWith(await api.runSimWorld(created.world.id), false);
    } catch (error) {
      setNotice(errorText(error, 'The simulation could not run. Try again.'));
      setPhase({ kind: 'setup' });
    }
  };

  const rerun = async () => {
    if (!world) return;
    setNotice('');
    setPhase({ kind: 'running' });
    try {
      const updated = await api.updateSimStrategy(world.id, strategy);
      if (updated.reason || !updated.world) {
        setNotice(simReasonMessage(updated.reason) || 'Could not change the strategy.');
        return setPhase({ kind: 'result' });
      }
      finishWith(await api.runSimWorld(world.id), true);
    } catch (error) {
      setNotice(errorText(error, 'The simulation could not run. Try again.'));
      setPhase({ kind: 'result' });
    }
  };

  const openWorld = async (target: SimWorld) => {
    setNotice('');
    setPhase({ kind: 'running' });
    try {
      const response = await api.getSimResult(target.id);
      if (response.reason || !response.result) {
        setNotice(simReasonMessage(response.reason) || 'Could not open that simulation.');
        return setPhase({ kind: 'setup' });
      }
      setWorld(response.world ?? target);
      setStrategy(response.result.strategy);
      setRuns([response.result]);
      setNotes([]);
      setTeamName(response.result.standings.find((row) => row.is_user)?.name ?? 'Your team');
      setTab('summary');
      setPhase({ kind: 'result' });
    } catch (error) {
      setNotice(errorText(error, 'Could not open that simulation.'));
      setPhase({ kind: 'setup' });
    }
  };

  const removeWorld = async (target: SimWorld) => {
    try {
      await api.deleteSimWorld(target.id);
      setWorlds((current) => current.filter((w) => w.id !== target.id));
      setNotice('');
    } catch (error) {
      setNotice(errorText(error, 'Could not delete that simulation.'));
    }
  };

  const toggleProtected = (playerId: string) => {
    const next = new Set(strategy.protected_player_ids);
    if (next.has(playerId)) next.delete(playerId);
    else if (next.size < 50) next.add(playerId);
    setStrategy({ ...strategy, protected_player_ids: [...next] });
  };

  const shell = (children: React.ReactNode) => (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight }]}>
        <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
        {children}
      </ScrollView>
    </View>
  );

  if (phase.kind === 'loading') {
    return shell(
      <View style={styles.stack}>
        <SkeletonCard rows={4} />
        <SkeletonCard rows={2} />
      </View>,
    );
  }
  if (phase.kind === 'error') {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <ErrorState title="Couldn't load Fantasy Sim" message={phase.message} onRetry={() => {
            setPhase({ kind: 'loading' });
            setAttempt((n) => n + 1);
          }} />
      </View>
    );
  }
  if (phase.kind === 'premium') {
    return shell(
      <PremiumLock
        feature="fantasy_sim"
        leagueName={leagueName}
        title={phase.upsell?.title || 'Play out your season before it happens'}
        description={
          phase.upsell?.body ||
          'Fantasy Sim is a Pro feature: set a strategy for your team, simulate the rest of the season against AI managers, and see your grade and the decisions that mattered. Start your free trial to unlock it.'
        }
      />,
    );
  }
  if (phase.kind === 'unavailable') {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <EmptyState
          icon="flask-outline"
          title="Fantasy Sim is coming soon"
          subtitle="Pick a strategy, play out the season, and see how you would grade. It is not switched on yet. Check back soon."
        />
      </View>
    );
  }

  const names = result ? simTeamNames(result) : {};
  const strategyChanged = result ? !simStrategyEqual(strategy, result.strategy) : false;

  const controls = (
    <View style={styles.stack}>
      <AppText style={styles.label}>Your posture</AppText>
      <SegmentedTabBar<SimStrategy['posture']>
        options={SIM_POSTURE_OPTIONS.map((o) => ({ key: o.value, label: o.label }))}
        active={strategy.posture}
        onChange={(posture) => setStrategy({ ...strategy, posture })}
      />
      <AppText style={styles.help}>{SIM_POSTURE_OPTIONS.find((o) => o.value === strategy.posture)?.blurb}</AppText>
      {(
        [
          ['trade_aggressiveness', 'Trades', 'How often your auto-GM looks for trades. Off means it never trades.'],
          ['waiver_aggressiveness', 'Waivers', 'How hard your auto-GM works the waiver wire. Off ignores it.'],
        ] as const
      ).map(([key, label, help]) => (
        <View key={key} style={styles.stack}>
          <AppText style={styles.label}>
            {label}: {simLevelLabel(strategy[key])}
          </AppText>
          <SegmentedTabBar<string>
            options={LEVELS.map((v) => ({ key: String(v), label: simLevelLabel(v) }))}
            active={String(LEVELS.reduce((best, v) => (Math.abs(v - strategy[key]) < Math.abs(best - strategy[key]) ? v : best), 0 as number))}
            onChange={(value) => setStrategy({ ...strategy, [key]: Number(value) })}
          />
          <AppText style={styles.help}>{help}</AppText>
        </View>
      ))}
      <View style={styles.rowBetween}>
        <View style={styles.flex}>
          <AppText style={styles.label}>Auto lineup</AppText>
          <AppText style={styles.help}>{strategy.lineup_auto_set ? 'Sets your best lineup every week.' : 'Set and forget: only fixes injuries.'}</AppText>
        </View>
        <Toggle value={strategy.lineup_auto_set} onValueChange={(lineup_auto_set) => setStrategy({ ...strategy, lineup_auto_set })} label="Auto lineup" />
      </View>
      <Pressable accessibilityRole="button" onPress={() => setShowProtected((v) => !v)} style={styles.protectedHeader}>
        <AppText style={styles.label}>Protected players ({strategy.protected_player_ids.length})</AppText>
        <AppText style={styles.help}>{showProtected ? 'Hide' : 'Choose'}</AppText>
      </Pressable>
      {showProtected ? (
        <View>
          <AppText style={styles.help}>Protected players are never traded or dropped.</AppText>
          {roster.length === 0 ? (
            <AppText style={styles.help}>Your roster is not available to pick from right now.</AppText>
          ) : (
            roster.map((player) => {
              const on = strategy.protected_player_ids.includes(player.player_id);
              return (
                <Pressable
                  key={player.player_id}
                  accessibilityRole="checkbox"
                  accessibilityState={{ checked: on }}
                  onPress={() => toggleProtected(player.player_id)}
                  style={styles.playerRow}
                >
                  <AppText style={[styles.label, { color: on ? colors.accent : colors.textPrimary }]}>
                    {on ? '[x] ' : '[ ] '}
                    {player.name ?? player.player_id}
                  </AppText>
                  <AppText style={styles.help}>{player.position ?? ''}</AppText>
                </Pressable>
              );
            })
          )}
        </View>
      ) : null}
    </View>
  );

  const banner = (
    <View style={styles.banner} accessibilityRole="summary">
      <ToneBadge label={SIM_LABEL} color={colors.accent} size="xs" />
      <AppText style={[styles.help, styles.flex]}>{SIM_DISCLAIMER}</AppText>
    </View>
  );
  const noticeView = notice ? <AppText style={[styles.help, { color: colors.warning }]}>{notice}</AppText> : null;

  if (phase.kind === 'running') {
    return shell(
      <View style={styles.stack}>
        {banner}
        <AppText style={styles.label} accessibilityLiveRegion="polite">
          Simulating the season…
        </AppText>
        <SkeletonCard rows={4} />
        <SkeletonCard rows={2} />
        <SkeletonCard rows={4} />
      </View>,
    );
  }

  if (phase.kind === 'setup') {
    return shell(
      <View style={styles.stack}>
        {banner}
        {noticeView}
        <AccentCard accent={colors.accent}>
          <SectionHeading title="Set up your sim" caption={`${leagueName}. Set a strategy and play out the season against AI managers.`} />
          <AppText style={styles.label}>How much season</AppText>
          <SegmentedTabBar<SimMode>
            options={SIM_MODE_OPTIONS.map((o) => ({ key: o.value, label: o.label }))}
            active={mode}
            onChange={setMode}
          />
          <AppText style={styles.help}>{SIM_MODE_OPTIONS.find((o) => o.value === mode)?.blurb}</AppText>
          {teams.length > 1 ? (
            <View style={styles.stack}>
              <AppText style={styles.label}>Play as</AppText>
              {[{ roster_id: '', team_name: 'My team' } as Pick<TeamRanking, 'roster_id' | 'team_name'>, ...teams].map((team) => (
                <Pressable
                  key={team.roster_id || 'mine'}
                  accessibilityRole="radio"
                  accessibilityState={{ selected: rosterId === team.roster_id }}
                  onPress={() => setRosterId(team.roster_id)}
                  style={styles.playerRow}
                >
                  <AppText style={[styles.label, { color: rosterId === team.roster_id ? colors.accent : colors.textPrimary }]}>
                    {team.team_name ?? `Team ${team.roster_id}`}
                  </AppText>
                </Pressable>
              ))}
            </View>
          ) : null}
          {controls}
          <Button label="Run simulation" onPress={run} />
        </AccentCard>
        {worlds.length > 0 ? (
          <View style={styles.stack}>
            <SectionHeading title="Your simulations" />
            {worlds.map((saved) => (
              <AccentCard key={saved.id} accent={colors.borderStrong} compact>
                <View style={styles.rowBetween}>
                  <View style={styles.flex}>
                    <AppText style={styles.label}>{saved.league_name}</AppText>
                    <AppText style={styles.help}>
                      {saved.mode === 'full' ? 'Whole season' : 'Rest of season'} · {simStrategySummary(saved.strategy)}
                    </AppText>
                  </View>
                  {saved.grade_letter ? <ToneBadge label={saved.grade_letter} color={toneColor(simGradeTone(saved.grade_letter))} /> : null}
                </View>
                <View style={styles.row}>
                  {saved.grade_letter ? <Button label="Open" size="sm" variant="secondary" onPress={() => openWorld(saved)} /> : null}
                  <Button label="Delete" size="sm" variant="ghost" onPress={() => removeWorld(saved)} />
                </View>
              </AccentCard>
            ))}
          </View>
        ) : null}
      </View>,
    );
  }

  if (!result) return null;
  const gradeColor = toneColor(simGradeTone(result.grade.letter));
  const timeline = simTimeline(result.events, names, { onlyUser: onlyMine });
  const noteLines = simNoteMessages(notes);

  return shell(
    <View style={styles.stack}>
      {banner}
      {noticeView}
      <AppText style={styles.help}>Strategy: {simStrategySummary(result.strategy)}</AppText>
      <SegmentedTabBar<ResultTab>
        scrollable
        options={[
          { key: 'summary', label: 'Summary' },
          { key: 'standings', label: 'Standings' },
          { key: 'playoffs', label: 'Playoffs' },
          { key: 'timeline', label: 'Timeline' },
          { key: 'scouting', label: 'Scouting' },
        ]}
        active={tab}
        onChange={setTab}
      />

      {tab === 'summary' ? (
        <View style={styles.stack}>
          <AccentCard accent={gradeColor} glow>
            <View style={styles.row}>
              <View style={[styles.gradeCircle, { borderColor: gradeColor }]} accessibilityLabel={`Grade ${result.grade.letter}`}>
                <AppText style={[styles.gradeLetter, { color: gradeColor }]}>{result.grade.letter}</AppText>
              </View>
              <View style={styles.flex}>
                <AppText style={styles.help}>SIMULATED SEASON GRADE</AppText>
                <AppText style={styles.title}>{teamName}</AppText>
                <AppText style={styles.help}>
                  {simFormatRecord(result.user)}
                  {result.user.seed ? `, seed ${result.user.seed}` : ''} · {simPlayoffResultLabel(result.user.playoff_result)}
                </AppText>
              </View>
            </View>
            <AppText style={styles.help}>Graded on a curve: a typical manager is a C.</AppText>
            {result.grade.components.map((component) => (
              <View key={component.key} style={styles.stack}>
                <View style={styles.rowBetween}>
                  <AppText style={styles.help}>{component.label}</AppText>
                  <AppText style={styles.help}>{Math.round(component.score)}</AppText>
                </View>
                <View style={styles.barTrack}>
                  <View style={[styles.barFill, { width: `${Math.max(0, Math.min(100, component.score))}%`, backgroundColor: gradeColor }]} />
                </View>
              </View>
            ))}
          </AccentCard>

          {previous ? (
            <View style={styles.stack}>
              <SectionHeading title="Strategy A/B" caption={`Before: ${simStrategySummary(previous.strategy)}. After: ${simStrategySummary(result.strategy)}.`} />
              <AccentCard accent={colors.accent}>
                <AppText style={styles.label}>{simCompareHeadline(previous, result)}</AppText>
                {simCompareRows(previous, result).map((row) => (
                  <View key={row.key} style={styles.rowBetween}>
                    <AppText style={[styles.help, styles.flex]}>{row.label}</AppText>
                    <AppText style={styles.help}>{row.before}</AppText>
                    <AppText style={[styles.label, { marginLeft: spacing.md, color: row.direction > 0 ? colors.success : row.direction < 0 ? colors.danger : colors.textPrimary }]}>
                      {row.after}
                    </AppText>
                  </View>
                ))}
              </AccentCard>
            </View>
          ) : null}

          <SectionHeading title="Your team" />
          <View style={styles.grid}>
            {(
              [
                ['Record', simFormatRecord(result.user)],
                ['Points for', simFormatPoints(result.user.pf)],
                ['Points against', simFormatPoints(result.user.pa)],
                ['Lineup efficiency', simFormatPercent(result.user.lineup_efficiency)],
                ['Expected wins', result.user.expected_wins === undefined ? '-' : result.user.expected_wins.toFixed(1)],
              ] as const
            ).map(([label, value]) => (
              <View key={label} style={styles.tile}>
                <AppText style={styles.help}>{label}</AppText>
                <AppText style={styles.title}>{value}</AppText>
              </View>
            ))}
          </View>

          {result.decisions_that_mattered.length > 0 ? (
            <View style={styles.stack}>
              <SectionHeading title="Decisions that mattered" caption="Each one is a what-if: the season replayed with that one move removed or flipped. Not a probability." />
              {result.decisions_that_mattered.map((decision, index) => {
                const helped = (decision.impact?.season_value ?? 0) >= 0;
                const color = helped ? colors.success : colors.warning;
                return (
                  <AccentCard key={`${decision.kind}-${index}`} accent={color} compact>
                    <View style={styles.row}>
                      <ToneBadge label={simDecisionKindLabel(decision.kind)} color={color} size="xs" />
                      {decision.week ? <AppText style={styles.help}>Week {decision.week}</AppText> : null}
                    </View>
                    <AppText style={styles.label}>{decision.title}</AppText>
                    <AppText style={styles.help}>{decision.detail}</AppText>
                    {decision.impact && typeof decision.impact.points_per_game === 'number' ? (
                      <AppText style={styles.help}>
                        {simFormatSigned(decision.impact.points_per_game)} points per game
                        {decision.impact.playoff_result_with && decision.impact.playoff_result_without
                          ? ` · ${simPlayoffResultLabel(decision.impact.playoff_result_with)} with it, ${simPlayoffResultLabel(decision.impact.playoff_result_without).toLowerCase()} without`
                          : ''}
                      </AppText>
                    ) : null}
                  </AccentCard>
                );
              })}
            </View>
          ) : null}
          {noteLines.map((line) => (
            <AppText key={line} style={styles.help}>
              {line}
            </AppText>
          ))}
        </View>
      ) : null}

      {tab === 'standings' ? (
        <View style={styles.stack}>
          <SectionHeading title="Standings" caption="Final regular-season order in the simulation." />
          {result.standings.map((row, index) => (
            <AccentCard key={row.team_id} accent={row.is_user ? colors.accent : colors.borderStrong} compact>
              <View style={styles.rowBetween}>
                <AppText style={[styles.label, styles.flex]}>
                  {index + 1}. {row.name}
                  {row.is_user ? ' (you)' : ''}
                </AppText>
                <AppText style={styles.label}>{simFormatRecord(row)}</AppText>
              </View>
              <View style={styles.rowBetween}>
                <AppText style={styles.help}>
                  {simFormatPoints(row.pf)} PF · {simFormatPoints(row.pa)} PA
                </AppText>
                <AppText style={styles.help}>{row.made_playoffs ? simPlayoffResultLabel(row.playoff_result) : 'Missed playoffs'}</AppText>
              </View>
            </AccentCard>
          ))}
        </View>
      ) : null}

      {tab === 'playoffs' ? (
        result.playoffs.length === 0 ? (
          <EmptyState icon="trophy-outline" title="No playoffs to show" subtitle="This simulation has no playoff games." />
        ) : (
          <View style={styles.stack}>
            <SectionHeading title="Playoff bracket" caption={result.champion ? `Champion: ${names[result.champion] ?? 'Unknown'}` : undefined} />
            {result.playoffs.map((round, index) => (
              <View key={round.round} style={styles.stack}>
                <AppText style={styles.label}>
                  {simRoundLabel(index, result.playoffs.length)} · Week {round.week}
                </AppText>
                {round.games.map((game) => (
                  <View key={`${game.home}-${game.away}`} style={styles.gameCard}>
                    {([[game.home, game.home_pts], [game.away, game.away_pts]] as const).map(([teamId, pts]) => (
                      <View key={teamId} style={styles.rowBetween}>
                        <AppText style={[game.winner === teamId ? styles.label : styles.help, styles.flex]}>{names[teamId] ?? 'Team'}</AppText>
                        <AppText style={game.winner === teamId ? styles.label : styles.help}>{simFormatPoints(pts)}</AppText>
                      </View>
                    ))}
                  </View>
                ))}
              </View>
            ))}
          </View>
        )
      ) : null}

      {tab === 'timeline' ? (
        <View style={styles.stack}>
          <SectionHeading title="Season timeline" caption="Trades and pickups as the season played out." />
          <SegmentedTabBar<'mine' | 'all'>
            options={[
              { key: 'mine', label: 'Your moves' },
              { key: 'all', label: 'Whole league' },
            ]}
            active={onlyMine ? 'mine' : 'all'}
            onChange={(key) => setOnlyMine(key === 'mine')}
          />
          {timeline.length === 0 ? (
            <EmptyState
              icon="swap-horizontal-outline"
              title="No moves"
              subtitle={onlyMine ? 'Your auto-GM made no trades or pickups. Raise trades or waivers and run again.' : 'No one made a move.'}
            />
          ) : (
            timeline.map((item) => (
              <AccentCard key={item.key} accent={item.involvesUser ? colors.accent : colors.borderStrong} compact>
                <View style={styles.row}>
                  <ToneBadge label={`Week ${item.week}`} color={colors.textSecondary} size="xs" />
                  <ToneBadge label={item.kind} color={item.kind === 'trade' ? colors.premium : colors.opportunity} size="xs" />
                </View>
                <AppText style={styles.label}>{item.title}</AppText>
                <AppText style={styles.help}>{item.detail}</AppText>
              </AccentCard>
            ))
          )}
        </View>
      ) : null}

      {tab === 'scouting' ? (
        <View style={styles.stack}>
          <SectionHeading title="Scouting report" caption="How each AI manager behaved in the simulation." />
          {result.personas
            .filter((persona) => !persona.is_user)
            .map((persona) => (
              <AccentCard key={persona.team_id} accent={colors.accent} compact>
                <View style={styles.rowBetween}>
                  <AppText style={[styles.label, styles.flex]}>{persona.name}</AppText>
                  <ToneBadge label={persona.label ?? persona.persona_id} color={colors.accent} size="xs" />
                </View>
                {persona.blurb ? <AppText style={styles.help}>{persona.blurb}</AppText> : null}
                <AppText style={styles.help}>
                  {simPowerLabel(persona.power_percentile)}
                  {typeof persona.avg_age === 'number' ? ` · average age ${persona.avg_age.toFixed(1)}` : ''}
                </AppText>
              </AccentCard>
            ))}
        </View>
      ) : null}

      <AccentCard accent={colors.premium}>
        <SectionHeading title="Try a different strategy" caption="Change your strategy and run it again. The dice stay the same, so any difference is down to your choices." />
        {editing ? (
          <>
            {controls}
            <Button label="Run again" onPress={rerun} disabled={!strategyChanged} />
          </>
        ) : (
          <Button label="Change strategy" variant="secondary" onPress={() => setEditing(true)} />
        )}
        <Button
          label="Start a new simulation"
          variant="ghost"
          onPress={() => {
            setPhase({ kind: 'setup' });
            setRuns([]);
            setWorld(null);
          }}
        />
      </AccentCard>
    </View>,
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1, backgroundColor: 'transparent' },
    container: { flex: 1, backgroundColor: 'transparent' },
    content: { padding: spacing.lg, paddingBottom: spacing.xl * 4 },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background, padding: spacing.xl },
    stack: { gap: spacing.md },
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
    rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md },
    flex: { flex: 1, minWidth: 0 },
    banner: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    label: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    help: { fontSize: 13, lineHeight: 19, color: colors.textSecondary },
    title: { fontSize: 18, fontWeight: '800', color: colors.textPrimary },
    protectedHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', minHeight: 44 },
    playerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', minHeight: 44 },
    gradeCircle: { width: 88, height: 88, borderRadius: radii.pill, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
    gradeLetter: { fontSize: 40, fontWeight: '800' },
    barTrack: { height: 6, borderRadius: 3, backgroundColor: colors.surface, overflow: 'hidden' },
    barFill: { height: 6, borderRadius: 3 },
    grid: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    gameCard: { gap: spacing.xs, padding: spacing.md, borderRadius: radii.md, backgroundColor: colors.surface },
    tile: { flexBasis: '48%', flexGrow: 1, gap: spacing.xs, padding: spacing.md, borderRadius: radii.md, backgroundColor: colors.surface },
  });
}
