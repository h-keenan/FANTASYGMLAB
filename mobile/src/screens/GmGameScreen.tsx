import React, { useCallback, useEffect, useMemo, useReducer, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import AccentCard from '../components/AccentCard';
import AppText from '../components/AppText';
import Button from '../components/Button';
import EmptyState from '../components/EmptyState';
import ErrorState from '../components/ErrorState';
import FadeInView from '../components/FadeInView';
import FilterDropdownButton from '../components/FilterDropdownButton';
import GridBackground from '../components/GridBackground';
import Input from '../components/Input';
import PremiumLock from '../components/PremiumLock';
import SectionHeading from '../components/SectionHeading';
import SegmentedTabBar from '../components/SegmentedTabBar';
import { SkeletonCard } from '../components/SkeletonBlock';
import { SimDraftRecapView, SimGameDraft } from '../components/SimGameDraft';
import { SimLeagueTab } from '../components/SimGameLeague';
import { SimPlayerSheet } from '../components/SimGamePlayers';
import { SimNotice, SimPreviewBanner, createSimStyles, type SimCtx } from '../components/SimGameParts';
import { SimFinalView, SimWeekRecapView } from '../components/SimGameRecap';
import { SimPlayersTab, SimTeamTab } from '../components/SimGameTeam';
import { SimTradesTab } from '../components/SimGameTrades';
import Toggle from '../components/Toggle';
import ToneBadge from '../components/ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import {
  SIM_DIFFICULTY_COPY,
  SIM_SCORING_LABELS,
  simAdvanceBlockers,
  simAdvanceLabel,
  simAdvanceWarnings,
  simFmtPts,
  simFmtRecord,
  simGameGate,
  simGameDeleteConfirm,
  simGameDeleteFailure,
  simGameLiteLine,
  simGamePaywalled,
  simGameUnavailableCopy,
  simNewGameBlock,
  simSettingsSummary,
  simSetupAdvancedChanged,
  simSetupBlock,
  simSetupBody,
  simSetupDefaults,
  simSetupSummary,
  simTeamNameChoices,
  simLeagueTeamLabel,
  SIM_NAME_CUSTOM,
  SIM_NAME_RANDOM,
  SIM_TEAM_NAME_MAX,
  simWeekHeading,
  SIM_TE_PREMIUM_LABELS,
  type SimDifficulty,
  type SimTiebreaker,
  SIM_TIEBREAKER_LABELS,
  type SimDraftRecap,
  type SimGame,
  type SimGameCreateBody,
  type SimGameGate,
  type SimGameLite,
  type SimGameOptionsResponse,
  type SimGamePlayer,
  type SimGamePreview,
  type SimGameTone,
  type SimScoring,
  type SimSetupState,
  type SimWaiverClaim,
} from '../lib/simGame';
import { SIM_FLOW_INITIAL, SIM_TABS, simFlowReducer, simRecapsFromAdvance, type SimTab } from '../lib/simGameFlow';
import { useSimGameRequest } from '../lib/useSimGameRequest';
import { useSimLeagueTeams } from '../lib/useSimLeagueTeamPicker';
import { useSimSavedLeagues } from '../lib/useSimSavedLeagues';
import { spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'GmGame'>;

const UPSELL_FALLBACK = {
  title: 'Keep your season going with Pro',
  body: 'The draft and your first 3 weeks are free. Pro unlocks the rest of the season, the playoffs and your final grade. Your save picks up right where you stopped.',
};

type FlowState = typeof SIM_FLOW_INITIAL;

/**
 * Fantasy Sim: the GM Game. Standalone and turn-based (no league). Mirrors
 * web-next's SimGameContent: the screens render from simGameStage /
 * simGameGate / simFlowReducer in lib/simGame*.ts (byte-identical twins), so
 * gating (premium_required is a 200 that did nothing, 409 = reload + retry)
 * behaves the same on both platforms.
 */
export default function GmGameScreen({ navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [flow, dispatch] = useReducer(simFlowReducer, SIM_FLOW_INITIAL);
  const [options, setOptions] = useState<SimGameOptionsResponse | null>(null);
  const [games, setGames] = useState<SimGameLite[]>([]);
  const [game, setGameState] = useState<SimGame | null>(null);
  const [preview, setPreview] = useState<SimGamePreview | null>(null);
  const [notice, setNotice] = useState<{ message: string; tone: SimGameTone } | null>(null);
  const [tick, setTick] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [sheetPlayer, setSheetPlayer] = useState<SimGamePlayer | null>(null);
  const [draftRecap, setDraftRecap] = useState<{ recap: SimDraftRecap | null } | null>(null);
  const [claims, setClaims] = useState<SimWaiverClaim[]>([]);
  const [tradeSeed, setTradeSeed] = useState<{ partner: string; get: string } | null>(null);
  const [advancing, setAdvancing] = useState(false);
  const [creating, setCreating] = useState(false);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [managing, setManaging] = useState(false);

  const notify = useCallback((message: string, tone: SimGameTone = 'warning') => setNotice(message ? { message, tone } : null), []);
  const goPaywall = useCallback(() => navigation.navigate('Paywall'), [navigation]);

  const onGate = useCallback(
    (gate: SimGameGate) => {
      dispatch({ type: 'gate', gate });
      if (gate.kind === 'premium' && gate.preview) setPreview(gate.preview);
      if (gate.kind === 'blocked') notify(gate.message, 'warning');
      if (gate.kind === 'unavailable' && gate.cause === 'busy') notify('The simulator is busy right now. Try again in a few seconds.', 'warning');
    },
    [notify],
  );

  const gameId = flow.gameId;
  const reloadGame = useCallback(async () => {
    if (!gameId) return;
    try {
      const body = await api.getSimGame(gameId);
      if (body.game) {
        setGameState(body.game);
        dispatch({ type: 'game_updated', game: body.game });
        if (body.preview !== undefined) setPreview(body.preview ?? null);
      }
    } catch {
      /* the next action reports the failure */
    }
  }, [gameId]);

  const call = useSimGameRequest(
    onGate,
    (message) => notify(message, 'danger'),
    () => {
      // 409: the game changed somewhere else. Reload it, then the user retries.
      notify('The game changed somewhere else. We reloaded it. Try again.', 'warning');
      void reloadGame();
      setTick((n) => n + 1);
    },
  );

  // Hub data: options (works for Free) and the saved games.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const opts = await api.getSimGameOptions();
        if (cancelled) return;
        const gate = simGameGate(opts);
        if (gate.kind === 'unavailable') {
          dispatch({ type: 'gate', gate });
          return;
        }
        setOptions(opts);
        if (opts.preview !== undefined) setPreview(opts.preview ?? null);
        const list = await api.listSimGames();
        if (cancelled) return;
        const listGate = simGameGate(list);
        if (listGate.kind === 'unavailable') {
          dispatch({ type: 'gate', gate: listGate });
          return;
        }
        setGames(list.games ?? []);
        dispatch({ type: 'hub' });
      } catch (error) {
        if (cancelled) return;
        const status = (error as { status?: number })?.status;
        if (status === 404) dispatch({ type: 'gate', gate: { kind: 'unavailable', cause: 'off' } });
        else dispatch({ type: 'error', message: error instanceof Error ? error.message : 'Fantasy Sim did not load.' });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [attempt]);

  const refreshList = useCallback(async () => {
    try {
      const list = await api.listSimGames();
      setGames(list.games ?? []);
    } catch {
      /* best effort */
    }
  }, []);

  async function deleteSaved(id: string) {
    setDeletingId(id);
    let removed = false;
    try {
      const body = await api.deleteSimGame(id);
      const gate = simGameGate(body);
      if (gate.kind === 'ready') {
        removed = true;
        notify('Game deleted.', 'success');
      } else if (gate.kind === 'blocked') {
        notify(gate.message, 'warning');
      } else if (gate.kind === 'unavailable' && gate.cause === 'busy') {
        notify('The simulator is busy right now. Try again in a few seconds.', 'warning');
      } else {
        notify('Could not delete the game. Try again.', 'danger');
      }
    } catch (error) {
      const failure = simGameDeleteFailure(error);
      removed = failure.remove;
      notify(failure.message, failure.tone);
      if (failure.refresh) void refreshList();
    }
    setDeletingId(null);
    setConfirmDeleteId(null);
    if (removed) {
      // Drop it right away so the count, the limit note and New game update with no reload.
      setGames((prev) => {
        const next = prev.filter((g) => g.id !== id);
        if (next.length === 0) setManaging(false);
        return next;
      });
      void refreshList();
    }
  }

  const openGame = useCallback(
    async (id: string) => {
      setNotice(null);
      const body = await call(() => api.getSimGame(id));
      if (body?.game) {
        setGameState(body.game);
        setPreview(body.preview ?? null);
        setClaims([]);
        setDraftRecap(null);
        dispatch({ type: 'open', game: body.game });
      }
    },
    [call],
  );

  async function createGame(body: SimGameCreateBody) {
    setCreating(true);
    const res = await call(() => api.createSimGame(body));
    setCreating(false);
    if (res?.game) {
      setGameState(res.game);
      setPreview(res.preview ?? null);
      setClaims([]);
      dispatch({ type: 'open', game: res.game });
      void refreshList();
    }
  }

  const setGame = useCallback((next: SimGame) => {
    setGameState(next);
    dispatch({ type: 'game_updated', game: next });
  }, []);

  async function advance() {
    if (!game) return;
    const blockers = simAdvanceBlockers(game, preview);
    if (blockers.some((b) => b.code === 'paywalled')) {
      dispatch({ type: 'gate', gate: { kind: 'premium', upsell: null, preview } });
      return;
    }
    if (blockers.length) {
      notify(blockers[0].message, 'danger');
      dispatch({ type: 'tab', tab: 'team' });
      return;
    }
    setAdvancing(true);
    setNotice(null);
    // The server checks the week we think we are in, so a stale tap cannot double-advance.
    const res = await call(() => api.advanceSimGame(game.id, game.week));
    setAdvancing(false);
    if (res?.recap && res.game) {
      setGameState(res.game);
      if (res.preview !== undefined) setPreview(res.preview ?? null);
      setClaims([]);
      dispatch({ type: 'advanced', recaps: simRecapsFromAdvance(res.recap, res.also_played), game: res.game });
      setTick((n) => n + 1);
      void refreshList();
    }
  }

  const ctx: SimCtx | null = useMemo(
    () =>
      game
        ? {
            gameId: game.id,
            game,
            preview,
            call,
            setGame,
            reloadGame,
            notify,
            tick,
            bump: () => setTick((n) => n + 1),
            openPlayer: setSheetPlayer,
          }
        : null,
    [game, preview, call, setGame, reloadGame, notify, tick],
  );

  const shell = (children: React.ReactNode, sheet?: React.ReactNode) => (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView
        style={styles.container}
        contentContainerStyle={[styles.content, { paddingBottom: orbClearance, paddingTop: headerHeight + spacing.sm }]}
        keyboardShouldPersistTaps="handled"
      >
        {children}
      </ScrollView>
      {sheet}
    </View>
  );

  // ----------------------------------------------------------------- views
  if (flow.view === 'loading') {
    return shell(
      <View style={styles.stack} accessibilityLabel="Loading Fantasy Sim" accessibilityState={{ busy: true }}>
        <SkeletonCard rows={2} />
        <SkeletonCard rows={4} />
      </View>,
    );
  }
  if (flow.view === 'unavailable') {
    const copy = simGameUnavailableCopy(flow.cause ?? 'off');
    return shell(
      <EmptyState
        icon="flask-outline"
        title={copy.title}
        subtitle={copy.subtitle}
        actionLabel={flow.cause === 'off' ? undefined : 'Try again'}
        onPressAction={
          flow.cause === 'off'
            ? undefined
            : () => {
                dispatch({ type: 'hub' });
                setAttempt((n) => n + 1);
              }
        }
      />,
    );
  }
  if (flow.view === 'error') {
    return (
      <View style={[styles.center, { paddingTop: headerHeight }]}>
        <ErrorState
          title="Fantasy Sim did not load"
          message={flow.message || undefined}
          onRetry={() => {
            dispatch({ type: 'setup' });
            setAttempt((n) => n + 1);
          }}
        />
      </View>
    );
  }

  if (flow.view === 'setup') {
    return shell(
      <>
        {flow.paywall ? <PaywallCard flow={flow} onDismiss={() => dispatch({ type: 'dismiss_paywall' })} /> : null}
        {notice ? <SimNotice message={notice.message} tone={notice.tone} onDismiss={() => setNotice(null)} /> : null}
        <SetupForm options={options} creating={creating} onCreate={createGame} onBack={() => dispatch({ type: 'hub' })} />
      </>,
    );
  }

  if (flow.view === 'game' && game && ctx) {
    return shell(
      <GameScreen
        flow={flow}
        game={game}
        ctx={ctx}
        preview={preview}
        advancing={advancing}
        notice={notice}
        clearNotice={() => setNotice(null)}
        onAdvance={advance}
        onGoPro={goPaywall}
        onTab={(tab) => dispatch({ type: 'tab', tab })}
        draftRecap={draftRecap}
        onDraftComplete={(recap) => setDraftRecap({ recap })}
        onStartSeason={() => setDraftRecap(null)}
        claims={claims}
        setClaims={setClaims}
        tradeSeed={tradeSeed}
        setTradeSeed={setTradeSeed}
        onRecapNext={() => dispatch({ type: 'recap_next' })}
        onRecapClose={() => dispatch({ type: 'recap_close' })}
        onDismissPaywall={() => dispatch({ type: 'dismiss_paywall' })}
        onHub={() => {
          dispatch({ type: 'hub' });
          setGameState(null);
          void refreshList();
        }}
        onNewGame={() => {
          dispatch({ type: 'setup' });
          setGameState(null);
        }}
        onDeleted={() => {
          dispatch({ type: 'deleted' });
          setGameState(null);
          void refreshList();
        }}
      />,
      sheetPlayer ? <SimPlayerSheet gameId={game.id} player={sheetPlayer} onClose={() => setSheetPlayer(null)} /> : null,
    );
  }

  // hub
  const block = simNewGameBlock(games.length, options?.max_games ?? 1, options?.is_premium);
  return shell(
    <>
      <SimPreviewBanner preview={preview} />
      {flow.paywall ? <PaywallCard flow={flow} onDismiss={() => dispatch({ type: 'dismiss_paywall' })} /> : null}
      {notice ? <SimNotice message={notice.message} tone={notice.tone} onDismiss={() => setNotice(null)} /> : null}
      <FadeInView>
        <AccentCard accent={colors.accent} glow>
          <AppText style={styles.kicker}>Sandbox</AppText>
          <AppText style={styles.heroTitle}>Be the GM. Win the season.</AppText>
          <AppText style={styles.body}>
            Draft a 12-team league against AI managers, set your lineup, work waivers and trades week by week, and take on the playoffs. At the end you get a grade. Nothing here touches your real leagues.
          </AppText>
          <View style={styles.wrapRow}>
            <Button label="New game" disabled={Boolean(block)} onPress={() => dispatch({ type: 'setup' })} />
            {block && options?.is_premium === false ? <Button label="Go Pro" variant="premiumOutline" size="sm" onPress={goPaywall} /> : null}
            {block ? <Button label="Manage games / delete one" variant="secondary" size="sm" onPress={() => setManaging(true)} /> : null}
          </View>
          {block ? (
            <AppText style={styles.muted} testID="new-game-block">
              {block}
            </AppText>
          ) : null}
        </AccentCard>
      </FadeInView>
      <View style={styles.stack}>
        <SectionHeading title="Your games" caption={games.length ? (managing ? 'Tap the trash can on a game to delete it.' : undefined) : 'Your saved games show up here.'} />
        {games.length === 0 ? (
          <EmptyState icon="american-football-outline" title="No games yet" subtitle="Start a new game to draft your team." />
        ) : (
          games.map((g) => (
            <View key={g.id} style={styles.tight}>
              <View style={styles.wrapRow}>
                <View style={styles.grow}>
                  <AccentCard accent={g.status === 'complete' ? colors.success : colors.accent} compact onPress={() => void openGame(g.id)}>
                    <View style={styles.rowBetween}>
                      <AppText style={[styles.bodyStrong, styles.grow]}>{simGameLiteLine(g)}</AppText>
                      {g.grade_letter ? <ToneBadge label={g.grade_letter} color={colors.success} size="xs" /> : <AppText style={styles.link}>Continue</AppText>}
                    </View>
                    <AppText style={styles.muted}>
                      {simSettingsSummary(g.settings) || `${SIM_SCORING_LABELS[(g.settings.scoring ?? 'ppr') as SimScoring]} · ${g.settings.teams ?? 12} teams`} · {SIM_DIFFICULTY_COPY[g.difficulty]?.label ?? g.difficulty}
                    </AppText>
                  </AccentCard>
                </View>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={`Delete game: ${simGameLiteLine(g)}`}
                  disabled={deletingId !== null}
                  onPress={() => setConfirmDeleteId(confirmDeleteId === g.id ? null : g.id)}
                  hitSlop={6}
                  style={styles.trash}
                >
                  <Ionicons name="trash-outline" size={20} color={colors.danger} />
                </Pressable>
              </View>
              {confirmDeleteId === g.id ? (
                <AccentCard accent={colors.danger} compact>
                  <AppText style={styles.body}>{simGameDeleteConfirm(g)}</AppText>
                  <View style={styles.wrapRow}>
                    <Button size="sm" variant="danger" label="Delete game" loading={deletingId === g.id} onPress={() => void deleteSaved(g.id)} />
                    <Button size="sm" variant="ghost" label="Keep it" disabled={deletingId === g.id} onPress={() => setConfirmDeleteId(null)} />
                  </View>
                </AccentCard>
              ) : null}
            </View>
          ))
        )}
      </View>
    </>,
  );
}

function PaywallCard({ flow, onDismiss }: { flow: FlowState; onDismiss: () => void }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  return (
    <FadeInView style={common.stack}>
      <PremiumLock
        feature="fantasy_sim"
        title={flow.paywall?.upsell?.title || UPSELL_FALLBACK.title}
        description={flow.paywall?.upsell?.body || UPSELL_FALLBACK.body}
      />
      <Button variant="ghost" size="sm" label="Keep looking around" onPress={onDismiss} />
    </FadeInView>
  );
}

function SetupForm({
  options,
  creating,
  onCreate,
  onBack,
}: {
  options: SimGameOptionsResponse | null;
  creating: boolean;
  onCreate: (body: SimGameCreateBody) => void;
  onBack: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const opts = options?.options;
  const defaults = useMemo(() => simSetupDefaults(options), [options]);
  const [state, setState] = useState<SimSetupState>(defaults);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const set = <K extends keyof SimSetupState>(key: K, value: SimSetupState[K]) => setState((prev) => ({ ...prev, [key]: value }));
  const canImport = options?.start_modes?.find((m) => m.id === 'league')?.available ?? false;
  const league = state.start === 'league';
  const leagues = useSimSavedLeagues(league);
  const leagueTeams = useSimLeagueTeams(league ? state.leagueId : '', (rosterId) => set('rosterId', rosterId));
  const nameChoices = simTeamNameChoices(options);
  const nameLabel = (value: string) => nameChoices.find((c) => c.value === value)?.label ?? 'Random';
  const changed = simSetupAdvancedChanged(state, defaults);
  const block = simSetupBlock(state);
  return (
    <View style={styles.stack}>
      <SectionHeading title="New game" caption="Quick start is 12 teams, half PPR and a standard lineup. You can change nothing after the game starts." />
      {canImport ? (
        <View style={styles.tight}>
          <AppText style={styles.label}>How to start</AppText>
          <SegmentedTabBar<string>
            options={[{ key: 'fresh', label: 'Fresh league' }, { key: 'league', label: 'My league' }]}
            active={state.start}
            onChange={(key) => set('start', key as SimSetupState['start'])}
          />
        </View>
      ) : null}
      {league ? (
        <View style={styles.tight}>
          <AppText style={styles.label}>Start from</AppText>
          {leagues === null ? <AppText style={styles.muted}>Loading your leagues...</AppText> : null}
          {leagues !== null && leagues.length === 0 ? <AppText style={styles.muted}>No Sleeper leagues saved.</AppText> : null}
          {(leagues ?? []).map((row) => (
            <Button
              key={row.league_id}
              size="sm"
              variant={state.leagueId === row.league_id ? 'primary' : 'secondary'}
              label={row.league_name || row.league_id}
              onPress={() => setState((prev) => ({ ...prev, leagueId: row.league_id, rosterId: '' }))}
            />
          ))}
        </View>
      ) : null}
      {league && state.leagueId ? (
        <View style={styles.tight}>
          <AppText style={styles.label}>Your team</AppText>
          {leagueTeams.status === 'loading' ? <AppText style={styles.muted}>Loading teams...</AppText> : null}
          {leagueTeams.status === 'error' ? <AppText style={styles.muted}>{leagueTeams.message}</AppText> : null}
          {leagueTeams.status === 'ready' && !leagueTeams.youRosterId ? (
            <AppText style={styles.muted}>We could not tell which team is yours from your Sleeper link. Pick it from the list.</AppText>
          ) : null}
          {leagueTeams.status === 'ready'
            ? leagueTeams.teams.map((team) => (
                <Button
                  key={team.roster_id}
                  size="sm"
                  variant={state.rosterId === team.roster_id ? 'primary' : 'secondary'}
                  label={`${simLeagueTeamLabel(team)}${team.is_you ? ' (you)' : ''}`}
                  onPress={() => set('rosterId', team.roster_id)}
                />
              ))
            : null}
        </View>
      ) : null}
      {!league ? (
        <View style={styles.tight}>
          <AppText style={styles.label}>Your team name</AppText>
          <FilterDropdownButton<string>
            label="Team name"
            options={nameChoices.map((c) => c.label)}
            value={nameLabel(state.nameChoice)}
            allValue="Random"
            onChange={(picked) => set('nameChoice', nameChoices.find((c) => c.label === picked)?.value ?? SIM_NAME_RANDOM)}
          />
          {state.nameChoice === SIM_NAME_CUSTOM ? (
            <Input value={state.name} maxLength={SIM_TEAM_NAME_MAX} placeholder="My Team" onChangeText={(v) => set('name', v)} accessibilityLabel="Custom team name" />
          ) : null}
        </View>
      ) : null}
      <View style={styles.tight}>
        <AppText style={styles.label}>Difficulty</AppText>
        <SegmentedTabBar<string>
          options={(opts?.difficulty.values ?? ['easy', 'normal', 'hard']).map((d) => ({ key: d, label: SIM_DIFFICULTY_COPY[d].label }))}
          active={state.difficulty}
          onChange={(key) => set('difficulty', key as SimDifficulty)}
        />
        <AppText style={styles.muted}>{SIM_DIFFICULTY_COPY[state.difficulty].blurb} Your own scoring is the same at every level.</AppText>
      </View>
      {!league ? (
        <View style={styles.stack}>
          <Button
            variant="ghost"
            size="sm"
            label={`${advancedOpen ? 'Hide' : 'Show'} advanced options${changed ? ` (${changed} changed)` : ''}`}
            onPress={() => setAdvancedOpen((open) => !open)}
            style={styles.start}
          />
          {advancedOpen ? (
            <View style={styles.stack}>
              <View style={styles.tight}>
                <AppText style={styles.label}>League size</AppText>
                <SegmentedTabBar<string>
                  options={(opts?.teams.values ?? [8, 10, 12, 14]).map((n) => ({ key: String(n), label: `${n} teams` }))}
                  active={String(state.teams)}
                  onChange={(key) => setState((prev) => ({ ...prev, teams: Number(key), slot: '' }))}
                />
                <AppText style={styles.muted}>You plus {state.teams - 1} AI managers.</AppText>
              </View>
              <View style={styles.tight}>
                <AppText style={styles.label}>Scoring</AppText>
                <SegmentedTabBar<string>
                  options={(opts?.scoring.values ?? ['ppr', 'half', 'std']).map((s) => ({ key: s, label: SIM_SCORING_LABELS[s] }))}
                  active={state.scoring}
                  onChange={(key) => set('scoring', key as SimScoring)}
                />
              </View>
              <View style={styles.tight}>
                <AppText style={styles.label}>TE premium</AppText>
                <SegmentedTabBar<string>
                  options={(opts?.te_premium?.values ?? [0, 0.5, 1]).map((v) => ({ key: String(v), label: SIM_TE_PREMIUM_LABELS[v] ?? `+${v}` }))}
                  active={String(state.tePremium)}
                  onChange={(key) => set('tePremium', Number(key))}
                />
              </View>
              <SetupToggle styles={styles} label="Superflex" note="A second quarterback can start in an extra flex slot." value={state.superflex} onChange={(v) => set('superflex', v)} />
              <SetupToggle styles={styles} label="Kicker" note="Start a K." value={state.includeK} onChange={(v) => set('includeK', v)} />
              <SetupToggle styles={styles} label="Defense (DEF)" note="Start a team defense (estimated from points allowed)." value={state.includeDef} onChange={(v) => set('includeDef', v)} />
              <View style={styles.tight}>
                <AppText style={styles.label}>Tiebreaker</AppText>
                <SegmentedTabBar<string>
                  options={(opts?.tiebreaker?.values ?? ['points_for', 'head_to_head']).map((v) => ({ key: v, label: SIM_TIEBREAKER_LABELS[v] }))}
                  active={state.tiebreaker}
                  onChange={(key) => set('tiebreaker', key as SimTiebreaker)}
                />
                <AppText style={styles.muted}>Breaks equal records in standings and playoff seeding.</AppText>
              </View>
              <View style={styles.tight}>
                <AppText style={styles.label}>Bench size</AppText>
                <SegmentedTabBar<string>
                  scrollable
                  options={Array.from({ length: (opts?.bench?.max ?? 10) - (opts?.bench?.min ?? 4) + 1 }, (_, i) => String((opts?.bench?.min ?? 4) + i)).map((n) => ({ key: n, label: n }))}
                  active={String(state.bench)}
                  onChange={(key) => set('bench', Number(key))}
                />
              </View>
              <View style={styles.tight}>
                <AppText style={styles.label}>Draft position</AppText>
                <SegmentedTabBar<string>
                  scrollable
                  options={[{ key: '', label: 'Random' }, ...Array.from({ length: state.teams }, (_, i) => ({ key: String(i + 1), label: `Pick ${i + 1}` }))]}
                  active={state.slot}
                  onChange={(key) => set('slot', key)}
                />
              </View>
            </View>
          ) : null}
        </View>
      ) : null}
      <SetupToggle styles={styles} label="Auto-set my lineup" note="Starts your best healthy players each week. You can still change it." value={state.auto} onChange={(v) => set('auto', v)} />
      <AppText style={styles.muted}>
        {simSetupSummary(state, options?.layout)}
        {options?.season ? ` ${options.season.regular_weeks}-week season, then ${options.season.playoff_teams}-team playoffs. Trade deadline week ${options.season.trade_deadline_week}.` : ''}
      </AppText>
      {block ? <AppText style={styles.muted}>{block}</AppText> : null}
      <View style={styles.wrapRow}>
        <Button label={league ? 'Start the season' : 'Start the draft'} loading={creating} disabled={Boolean(block)} onPress={() => onCreate(simSetupBody(state))} />
        <Button variant="ghost" label="Back" onPress={onBack} />
      </View>
    </View>
  );
}

function SetupToggle({
  styles,
  label,
  note,
  value,
  onChange,
}: {
  styles: ReturnType<typeof createStyles>;
  label: string;
  note: string;
  value: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <View style={styles.rowBetween}>
      <View style={styles.grow}>
        <AppText style={styles.label}>{label}</AppText>
        <AppText style={styles.muted}>{note}</AppText>
      </View>
      <Toggle value={value} onValueChange={onChange} label={label} />
    </View>
  );
}

function GameScreen({
  flow,
  game,
  ctx,
  preview,
  advancing,
  notice,
  clearNotice,
  onAdvance,
  onGoPro,
  onTab,
  draftRecap,
  onDraftComplete,
  onStartSeason,
  claims,
  setClaims,
  tradeSeed,
  setTradeSeed,
  onRecapNext,
  onRecapClose,
  onDismissPaywall,
  onHub,
  onNewGame,
  onDeleted,
}: {
  flow: FlowState;
  game: SimGame;
  ctx: SimCtx;
  preview: SimGamePreview | null;
  advancing: boolean;
  notice: { message: string; tone: SimGameTone } | null;
  clearNotice: () => void;
  onAdvance: () => void;
  onGoPro: () => void;
  onTab: (tab: SimTab) => void;
  draftRecap: { recap: SimDraftRecap | null } | null;
  onDraftComplete: (recap: SimDraftRecap | null) => void;
  onStartSeason: () => void;
  claims: SimWaiverClaim[];
  setClaims: (claims: SimWaiverClaim[]) => void;
  tradeSeed: { partner: string; get: string } | null;
  setTradeSeed: (seed: { partner: string; get: string } | null) => void;
  onRecapNext: () => void;
  onRecapClose: () => void;
  onDismissPaywall: () => void;
  onHub: () => void;
  onNewGame: () => void;
  onDeleted: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const paywalled = simGamePaywalled(preview);
  const stage = flow.stage;
  const recap = flow.recaps[flow.recapIndex];
  const warnings = simAdvanceWarnings(game);
  const youLine = game.you;
  const inSeason = (stage === 'week' || stage === 'playoffs') && !draftRecap;

  return (
    <View style={styles.stack}>
      <View style={styles.rowBetween}>
        <View style={styles.grow}>
          <Button variant="ghost" size="sm" label="All games" onPress={onHub} style={styles.back} />
          <AppText style={styles.heading} testID="game-heading">
            {simWeekHeading(game)}
          </AppText>
          {youLine && stage !== 'draft' ? (
            <AppText style={styles.muted}>
              {youLine.name} · {simFmtRecord(youLine)}
              {youLine.rank ? ` · #${youLine.rank}` : ''} · {simFmtPts(youLine.pf)} PF
            </AppText>
          ) : null}
        </View>
        {inSeason && !recap ? (
          paywalled ? (
            <Button label="Go Pro" variant="premium" size="sm" onPress={onGoPro} />
          ) : (
            <Button label={game.phase === 'playoffs' ? 'Play round' : 'Advance week'} loading={advancing} onPress={onAdvance} />
          )
        ) : null}
      </View>
      {inSeason && !recap && !paywalled ? <AppText style={styles.muted}>{simAdvanceLabel(game)}</AppText> : null}

      <SimPreviewBanner preview={preview} />
      {flow.paywall ? <PaywallCard flow={flow} onDismiss={onDismissPaywall} /> : null}
      {notice ? <SimNotice message={notice.message} tone={notice.tone} onDismiss={clearNotice} /> : null}
      {inSeason && !recap && !paywalled && warnings.length > 0 ? (
        <View style={styles.tight}>
          {warnings.map((w) => (
            <AppText key={w} style={styles.muted}>
              {w}
            </AppText>
          ))}
        </View>
      ) : null}

      {stage === 'draft' ? (
        <SimGameDraft ctx={ctx} onComplete={onDraftComplete} />
      ) : draftRecap ? (
        <SimDraftRecapView recap={draftRecap.recap} ctx={ctx} onStart={onStartSeason} />
      ) : recap ? (
        <SimWeekRecapView recap={recap} index={flow.recapIndex} total={flow.recaps.length} ctx={ctx} onNext={onRecapNext} onClose={onRecapClose} />
      ) : stage === 'final' ? (
        <SimFinalView ctx={ctx} onNewGame={onNewGame} onHub={onHub} />
      ) : (
        <>
          <SegmentedTabBar<SimTab>
            options={SIM_TABS.map((t) => ({ key: t.value, label: t.value === 'trades' && (game.pending?.inbox ?? 0) > 0 ? `Trades ${game.pending?.inbox}` : t.label }))}
            active={flow.tab}
            onChange={onTab}
          />
          <FadeInView key={flow.tab}>
            {flow.tab === 'team' ? <SimTeamTab ctx={ctx} onTrade={() => onTab('trades')} /> : null}
            {flow.tab === 'players' ? (
              <SimPlayersTab
                ctx={ctx}
                claims={claims}
                setClaims={setClaims}
                onTradeFor={(player) => {
                  if (player.owner?.team_id) setTradeSeed({ partner: player.owner.team_id, get: player.id });
                  onTab('trades');
                }}
              />
            ) : null}
            {flow.tab === 'trades' ? <SimTradesTab ctx={ctx} seed={tradeSeed} onSeedUsed={() => setTradeSeed(null)} /> : null}
            {flow.tab === 'league' ? <SimLeagueTab ctx={ctx} /> : null}
            {flow.tab === 'more' ? <SimMoreTab ctx={ctx} onDeleted={onDeleted} onHub={onHub} /> : null}
          </FadeInView>
        </>
      )}
    </View>
  );
}

function SimMoreTab({ ctx, onDeleted, onHub }: { ctx: SimCtx; onDeleted: () => void; onHub: () => void }) {
  const { game, gameId, call } = ctx;
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [confirm, setConfirm] = useState<'revert' | 'delete' | null>(null);
  const [busy, setBusy] = useState(false);
  const s = game.settings;

  async function revert() {
    setBusy(true);
    const body = await call(() => api.revertSimWeek(gameId));
    setBusy(false);
    setConfirm(null);
    if (body?.game) {
      ctx.setGame(body.game);
      ctx.bump();
      ctx.notify(body.reverted ? "This week's decisions were reset." : 'Nothing to reset this week.', 'success');
    }
  }
  async function remove() {
    setBusy(true);
    const body = await call(() => api.deleteSimGame(gameId));
    setBusy(false);
    if (body) onDeleted();
  }

  return (
    <View style={styles.stack}>
      <SectionHeading title="This week" />
      <AccentCard accent={colors.warning} compact>
        <AppText style={styles.body}>Undo this week&apos;s lineup edits, claims, cuts and trades back to how the week started. You cannot undo a week you already advanced.</AppText>
        {confirm === 'revert' ? (
          <View style={styles.wrapRow}>
            <Button size="sm" variant="danger" label="Reset this week" loading={busy} onPress={revert} />
            <Button size="sm" variant="ghost" label="Cancel" onPress={() => setConfirm(null)} />
          </View>
        ) : (
          <Button size="sm" variant="secondary" label="Reset this week" onPress={() => setConfirm('revert')} style={styles.start} />
        )}
      </AccentCard>

      <SectionHeading title="League rules" />
      <AccentCard accent={colors.borderStrong} compact>
        <AppText style={styles.body}>
          {simSettingsSummary(s)} · {SIM_DIFFICULTY_COPY[s.difficulty].label}
        </AppText>
        <AppText style={styles.body}>
          Starters: {s.slots.join(', ')} · roster limit {s.roster_limit}
        </AppText>
        <AppText style={styles.body}>
          {s.regular_weeks}-week season, {s.playoff_teams}-team playoffs. Trade deadline: week {s.trade_deadline_week}.
        </AppText>
        <AppText style={styles.body}>Waiver claims resolve when you advance, worst record first.</AppText>
      </AccentCard>

      <SectionHeading title="Game" />
      <View style={styles.wrapRow}>
        <Button size="sm" variant="secondary" label="All games" onPress={onHub} />
        {confirm === 'delete' ? (
          <>
            <Button size="sm" variant="danger" label="Delete this game" loading={busy} onPress={remove} />
            <Button size="sm" variant="ghost" label="Keep it" onPress={() => setConfirm(null)} />
          </>
        ) : (
          <Button size="sm" variant="dangerOutline" label="Delete game" onPress={() => setConfirm('delete')} />
        )}
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { flex: 1 },
    container: { flex: 1 },
    content: { padding: spacing.lg, gap: spacing.md },
    center: { flex: 1, justifyContent: 'center' },
    stack: { gap: spacing.md },
    tight: { gap: spacing.xs },
    wrapRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.sm },
    rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.md },
    grow: { flex: 1, minWidth: 0 },
    trash: { width: 44, height: 44, borderRadius: 12, borderWidth: 1, borderColor: colors.danger, alignItems: 'center', justifyContent: 'center' },
    back: { alignSelf: 'flex-start' },
    start: { alignSelf: 'flex-start' },
    kicker: { fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
    heroTitle: { fontSize: 22, fontWeight: '800', color: colors.textPrimary },
    heading: { fontSize: 19, fontWeight: '800', color: colors.textPrimary },
    label: { fontSize: 14.5, fontWeight: '700', color: colors.textPrimary },
    body: { fontSize: 15, lineHeight: 21, color: colors.textSecondary },
    bodyStrong: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    muted: { fontSize: 13, lineHeight: 18, color: colors.textTertiary },
    link: { fontSize: 13.5, fontWeight: '700', color: colors.accent },
  });
}
