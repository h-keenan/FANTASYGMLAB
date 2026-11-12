import React, { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import FadeInView from './FadeInView';
import SectionHeading from './SectionHeading';
import SegmentedTabBar from './SegmentedTabBar';
import { SkeletonCard } from './SkeletonBlock';
import { SimPlayerBrowser } from './SimGamePlayers';
import { SimPlayerChip, SimPlayerLine, SimPopIn, SimStat, SimToneBadge, createSimStyles, type SimCtx } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import {
  SIM_QUEUE_MAX,
  simDraftClockLine,
  simFmtPts,
  simFmtValue,
  simPickLabel,
  simQueueReducer,
  simPositionsFor,
  simRosterNeeds,
  simValueOverAdpLabel,
  simValueOverAdpTone,
  type SimDraftHint,
  type SimDraftPick,
  type SimDraftRecap,
  type SimDraftState,
  type SimGamePlayer,
} from '../lib/simGame';
import { spacing, type ThemeColors } from '../theme';

type Panel = 'board' | 'queue' | 'roster' | 'picks';

/**
 * The draft room: a big board of every undrafted player (search, position
 * filter, sort), your queue, your roster by need, and the pick log. There is no
 * pick clock. A pick resolves every AI pick up to your next turn in one call.
 */
export function SimGameDraft({ ctx, onComplete }: { ctx: SimCtx; onComplete: (recap: SimDraftRecap | null) => void }) {
  const { gameId, game, call } = ctx;
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [draft, setDraft] = useState<SimDraftState | null>(null);
  const [hint, setHint] = useState<SimDraftHint | null>(null);
  const [loadState, setLoadState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [queue, dispatchQueue] = useReducer(simQueueReducer, { ids: [] });
  const [players, setPlayers] = useState<Record<string, SimGamePlayer>>({});
  const [panel, setPanel] = useState<Panel>('board');
  const [busy, setBusy] = useState<'pick' | 'auto' | null>(null);
  const [confirmAuto, setConfirmAuto] = useState(false);
  const [freshPickNos, setFreshPickNos] = useState<number[]>([]);
  const [attempt, setAttempt] = useState(0);
  const queueLoaded = useRef(false);

  // The first load, and after a conflict/retry.
  useEffect(() => {
    let cancelled = false;
    api
      .getSimDraft(gameId, 'page=1&page_size=1')
      .then((body) => {
        if (cancelled) return;
        if (body.reason) {
          ctx.notify(body.message ?? 'The draft is not ready yet.', 'danger');
          setLoadState('error');
          return;
        }
        setDraft(body.draft ?? null);
        setHint(body.hint ?? null);
        dispatchQueue({ type: 'set', ids: body.draft?.queue ?? [] });
        queueLoaded.current = true;
        if (body.draft) rememberPlayers(body.draft.your_roster, body.draft.picks);
        setLoadState('ready');
      })
      .catch(() => {
        if (!cancelled) setLoadState('error');
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId, attempt]);

  function rememberPlayers(roster: SimGamePlayer[] | undefined, picks: SimDraftPick[] | undefined) {
    setPlayers((prev) => {
      const next = { ...prev };
      for (const p of roster ?? []) next[p.id] = p;
      for (const pick of picks ?? []) next[pick.player.id] = pick.player;
      return next;
    });
  }

  // Persist the queue shortly after it changes (auto-pick reads it server-side).
  const saved = useRef<string>('');
  useEffect(() => {
    if (!queueLoaded.current) return;
    const key = queue.ids.join(',');
    if (key === saved.current) return;
    const id = setTimeout(() => {
      saved.current = key;
      void call(() => api.putSimDraftQueue(gameId, queue.ids));
    }, 500);
    return () => clearTimeout(id);
  }, [queue.ids, gameId, call]);

  const applyResult = useCallback(
    (body: { picks?: SimDraftPick[]; draft?: Partial<SimDraftState>; completed?: boolean; recap?: SimDraftRecap | null; game?: typeof game }) => {
      const made = body.picks ?? [];
      setDraft((prev) => {
        if (!prev) return prev;
        const merged = { ...prev, ...(body.draft ?? {}) } as SimDraftState;
        merged.picks = [...(prev.picks ?? []), ...made];
        return merged;
      });
      rememberPlayers(body.draft?.your_roster, made);
      setFreshPickNos(made.map((m) => m.pick_no));
      if (made.length) dispatchQueue({ type: 'prune', taken: made.map((m) => m.player.id) });
      if (body.game) ctx.setGame(body.game);
      ctx.bump();
      if (body.completed) onComplete(body.recap ?? null);
    },
    [ctx, onComplete],
  );

  async function pick(player: SimGamePlayer) {
    if (busy) return;
    setBusy('pick');
    const body = await call(() => api.simDraftPick(gameId, player.id));
    setBusy(null);
    if (body) {
      applyResult(body);
      // Refresh the hint for the next turn.
      api
        .getSimDraft(gameId, 'page=1&page_size=1')
        .then((next) => setHint(next.hint ?? null))
        .catch(() => {});
    } else {
      // player_taken / conflict: the board is stale. Reload it.
      setAttempt((n) => n + 1);
      ctx.bump();
    }
  }

  async function autoDraft() {
    setConfirmAuto(false);
    setBusy('auto');
    const body = await call(() => api.simDraftAuto(gameId));
    setBusy(null);
    if (body) applyResult(body);
  }

  const teamNames = useMemo(() => {
    const map: Record<string, string> = {};
    for (const t of draft?.teams ?? []) map[t.team_id] = t.is_you ? `${t.name} (you)` : t.name;
    return map;
  }, [draft?.teams]);

  if (loadState === 'loading') {
    return (
      <View style={common.stack}>
        <SkeletonCard rows={2} />
        <SkeletonCard rows={4} />
      </View>
    );
  }
  if (loadState === 'error' || !draft) {
    return (
      <ErrorState
        title="The draft did not load"
        message="Check your connection and try again."
        onRetry={() => {
          setLoadState('loading');
          setAttempt((n) => n + 1);
        }}
      />
    );
  }

  const onClock = Boolean(draft.on_the_clock?.is_you) && draft.status === 'in_progress';
  const queued = queue.ids.map((id) => players[id]).filter(Boolean);
  const picks = draft.picks ?? [];
  const recent = [...picks].reverse().slice(0, 40);
  const needs = simRosterNeeds(draft.your_roster, game.settings.slots);

  const boardActions = (player: SimGamePlayer) => {
    const inQueue = queue.ids.includes(player.id);
    return (
      <View style={common.row}>
        <Button
          size="sm"
          variant="secondary"
          label={inQueue ? 'Queued' : 'Queue'}
          onPress={() => {
            setPlayers((prev) => ({ ...prev, [player.id]: player }));
            dispatchQueue({ type: inQueue ? 'remove' : 'add', id: player.id });
          }}
        />
        {onClock ? <Button size="sm" label="Draft" loading={busy === 'pick'} onPress={() => pick(player)} /> : null}
      </View>
    );
  };

  const board = (
    <SimPlayerBrowser
      gameId={gameId}
      fixedStatus="available"
      initial={{ sort: 'adp' }}
      positions={simPositionsFor(game.settings.slots)}
      onOpen={ctx.openPlayer}
      actions={boardActions}
      refreshKey={ctx.tick}
      emptyTitle="No players left that match"
      onItems={(items) => setPlayers((prev) => ({ ...prev, ...Object.fromEntries(items.map((p) => [p.id, p])) }))}
    />
  );

  const side = () => {
    if (panel === 'queue') {
      return (
        <View style={common.stack}>
          <SectionHeading title="Queue" caption={`Auto-pick drafts from the top of your queue first. ${queue.ids.length}/${SIM_QUEUE_MAX}`} />
          {queued.length === 0 ? (
            <EmptyState icon="list-outline" title="Nothing queued" subtitle="Tap Queue on any player to line up your picks." />
          ) : (
            queued.map((player, index) => (
              <SimPlayerLine
                key={player.id}
                player={player}
                onOpen={ctx.openPlayer}
                trailing={
                  <View style={common.wrapRow}>
                    <Button size="sm" variant="ghost" label="Up" disabled={index === 0} onPress={() => dispatchQueue({ type: 'move', id: player.id, delta: -1 })} />
                    <Button size="sm" variant="ghost" label="Down" disabled={index === queued.length - 1} onPress={() => dispatchQueue({ type: 'move', id: player.id, delta: 1 })} />
                    <Button size="sm" variant="ghost" label="Remove" onPress={() => dispatchQueue({ type: 'remove', id: player.id })} />
                    {onClock ? <Button size="sm" label="Draft" loading={busy === 'pick'} onPress={() => pick(player)} /> : null}
                  </View>
                }
              />
            ))
          )}
        </View>
      );
    }
    if (panel === 'roster') {
      return (
        <View style={common.stack}>
          <SectionHeading title="Your roster" caption={`Starters: ${game.settings.slots.join(', ')}.`} />
          <View style={styles.needs}>
            {needs.map((n) => (
              <View key={n.pos} style={styles.need}>
                <AppText style={common.bodyStrong}>{n.pos}</AppText>
                <AppText style={[styles.needValue, { color: n.have >= n.starters ? colors.success : colors.warning }]}>
                  {n.have}/{n.starters}
                </AppText>
              </View>
            ))}
          </View>
          {draft.your_roster.length === 0 ? (
            <EmptyState icon="people-outline" title="No picks yet" subtitle="Your drafted players show up here." />
          ) : (
            draft.your_roster.map((player) => (
              <SimPlayerLine key={player.id} player={player} onOpen={ctx.openPlayer} trailing={<SimStat label="Proj" value={simFmtPts(player.projection)} />} />
            ))
          )}
        </View>
      );
    }
    return (
      <View style={common.stack}>
        <SectionHeading title="Picks" caption="Newest first. Steal and reach compare a pick to its ADP." />
        {recent.length === 0 ? (
          <EmptyState icon="time-outline" title="No picks yet" subtitle="Picks show up here as the draft moves." />
        ) : (
          recent.map((pk) => {
            const line = (
              <SimPlayerLine
                key={pk.pick_no}
                player={pk.player}
                onOpen={ctx.openPlayer}
                extra={
                  <AppText style={common.muted}>
                    #{pk.pick_no} · {teamNames[pk.team_id] ?? 'Team'}
                  </AppText>
                }
                trailing={
                  pk.value_over_adp != null && simValueOverAdpLabel(pk.value_over_adp) ? (
                    <SimToneBadge label={simValueOverAdpLabel(pk.value_over_adp)} tone={simValueOverAdpTone(pk.value_over_adp)} />
                  ) : null
                }
              />
            );
            return freshPickNos.includes(pk.pick_no) ? <FadeInView key={pk.pick_no}>{line}</FadeInView> : line;
          })
        )}
      </View>
    );
  };

  return (
    <View style={common.stack}>
      <AccentCard accent={onClock ? colors.accent : colors.borderStrong} glow={onClock}>
        <View style={common.rowBetween}>
          <View style={common.grow}>
            <AppText style={styles.kicker}>{draft.status === 'complete' ? 'Draft' : simPickLabel(draft.pick_no, game.settings.teams)}</AppText>
            <AppText style={common.title} accessibilityLiveRegion="polite" testID="draft-clock">
              {simDraftClockLine(draft)}
            </AppText>
            <AppText style={common.muted}>
              Pick {Math.min(draft.pick_no, draft.total_picks)} of {draft.total_picks} · No clock, take your time.
            </AppText>
          </View>
          {onClock ? <ToneBadge label="Your pick" color={colors.accent} /> : null}
        </View>
        {onClock && hint ? (
          <FadeInView>
            <View style={common.rowBetween} testID="draft-hint">
              <View style={common.grow}>
                <AppText style={common.muted}>{hint.why}</AppText>
                <SimPlayerChip player={hint.player} extra={<AppText style={common.muted}>Value {simFmtValue(hint.player.value)}</AppText>} />
              </View>
              <Button size="sm" label={`Draft ${hint.player.name.split(' ').slice(-1)[0]}`} loading={busy === 'pick'} onPress={() => pick(hint.player)} />
            </View>
          </FadeInView>
        ) : null}
        {confirmAuto ? (
          <View style={common.tight}>
            <AppText style={common.small}>Auto-draft the rest of your picks from your queue, then best value and need?</AppText>
            <View style={common.row}>
              <Button size="sm" label="Yes, auto-pick" onPress={autoDraft} />
              <Button size="sm" variant="ghost" label="Cancel" onPress={() => setConfirmAuto(false)} />
            </View>
          </View>
        ) : (
          <Button
            size="sm"
            variant="secondary"
            label="Auto-pick the rest"
            loading={busy === 'auto'}
            disabled={draft.status === 'complete' || busy === 'pick'}
            onPress={() => setConfirmAuto(true)}
            style={styles.autoButton}
          />
        )}
      </AccentCard>
      <SegmentedTabBar<Panel>
        options={[
          { key: 'board', label: 'Board' },
          { key: 'queue', label: `Queue${queue.ids.length ? ` ${queue.ids.length}` : ''}` },
          { key: 'roster', label: 'Roster' },
          { key: 'picks', label: 'Picks' },
        ]}
        active={panel}
        onChange={setPanel}
      />
      {panel === 'board' ? board : side()}
    </View>
  );
}

/** The draft recap: team grades with your best/worst pick, then "Start the season". */
export function SimDraftRecapView({ recap, ctx, onStart }: { recap: SimDraftRecap | null; ctx: SimCtx; onStart: () => void }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  const teams = [...(recap?.teams ?? [])].sort((a, b) => b.starter_projection - a.starter_projection);
  const mine = recap?.your_team ?? teams.find((t) => t.is_you) ?? null;
  const nameOf = (pick: unknown) => (pick as { player?: SimGamePlayer } | null | undefined)?.player;
  return (
    <SimPopIn style={common.stack}>
      <AccentCard accent={colors.success} glow>
        <AppText style={styles.kicker}>Draft complete</AppText>
        <AppText style={common.title}>Your team is set for Week 1.</AppText>
        {mine ? (
          <View style={common.wrapRow}>
            <ToneBadge label={`Draft grade ${mine.grade}`} color={colors.success} />
            <AppText style={common.small}>Starters project {simFmtPts(mine.starter_projection)} a week.</AppText>
          </View>
        ) : null}
        {nameOf(mine?.best_pick) ? (
          <View style={common.stack}>
            <AppText style={common.muted}>Best pick</AppText>
            <SimPlayerChip player={nameOf(mine?.best_pick)!} />
          </View>
        ) : null}
        {nameOf(mine?.worst_pick) ? (
          <View style={common.stack}>
            <AppText style={common.muted}>Biggest reach</AppText>
            <SimPlayerChip player={nameOf(mine?.worst_pick)!} />
          </View>
        ) : null}
        <Button label="Start the season" onPress={onStart} />
      </AccentCard>
      {teams.length > 0 ? (
        <View style={common.stack}>
          <SectionHeading title="How every team drafted" caption="Graded on how strong each team's starting lineup projects." />
          {teams.map((team, index) => (
            <AccentCard key={team.team_id} accent={team.is_you || team.team_id === ctx.game.you?.team_id ? colors.accent : colors.borderStrong} compact>
              <View style={common.rowBetween}>
                <AppText style={[common.bodyStrong, common.grow]}>
                  {index + 1}. {team.name}
                </AppText>
                <View style={common.row}>
                  <AppText style={common.muted}>{simFmtPts(team.starter_projection)}</AppText>
                  <ToneBadge label={team.grade} color={colors.accent} size="xs" />
                </View>
              </View>
            </AccentCard>
          ))}
        </View>
      ) : null}
    </SimPopIn>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    kicker: { fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
    autoButton: { alignSelf: 'flex-start' },
    needs: { flexDirection: 'row', gap: spacing.sm },
    need: {
      flex: 1,
      alignItems: 'center',
      paddingVertical: spacing.sm,
      borderRadius: 12,
      backgroundColor: colors.glass,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: colors.glassBorder,
    },
    needValue: { fontSize: 16, fontWeight: '800' },
  });
}
