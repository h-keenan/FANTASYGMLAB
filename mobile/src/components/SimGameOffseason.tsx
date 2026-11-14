import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import { OffseasonGlyph } from './OffseasonGlyph';
import Button from './Button';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import SegmentedTabBar from './SegmentedTabBar';
import CompactModule from './CompactModule';
import { SimDraftIconButton, SimDraftRow } from './SimDraftBoard';
import { SimRookieOverview } from './SimDraftOverview';
import { SkeletonCard } from './SkeletonBlock';
import { SimDynastyStrip } from './SimGameDynasty';
import { SimCollapse, SimGeneratedChip, SimGeneratedNoticeSheet, SimPickLine, SimRookieNoticeGate, useSimPicks } from './SimGameDynastyParts';
import { SimRosterLine, SimToneBadge, createSimStyles, simToneColor, type SimCtx } from './SimGameParts';
import { SimReserveButton, SimReserveGroups, SimReserveSheet } from './SimGameReserves';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import { simRookieSummaryParts, simSuppressedBadges } from '../lib/simDraft';
import {
  offseasonAgingParts,
  offseasonLogParts,
  offseasonPickCountParts,
  offseasonPicksParts,
  offseasonRetireParts,
  offseasonRosterParts,
  offseasonSeasonParts,
  offseasonStepper,
  type OffseasonStepperItem,
} from '../lib/simOffseasonSummary';
import {
  simArchiveToYear,
  simFmtPts,
  simMoverText,
  simOffseasonHeading,
  simOffseasonSteps,
  simPicksOf,
  simPlayoffOutcomeTone,
  simPlayoffResultLabel,
  simPositionsFor,
  simReservesOn,
  simRetireesSorted,
  simRookieClassChip,
  simRookieClockLine,
  simRookiePickLine,
  type SimDynastyYear,
  type SimGamePlayer,
  type SimOffseason,
  type SimOffseasonResponse,
  type SimPos,
  type SimTeamRosterResponse,
  simSeasonText,
  simLimitBlocks,
  simOverLimitNote,
} from '../lib/simGame';

type Busy = 'start' | 'pick' | 'auto' | 'season' | null;

/**
 * The dynasty offseason, one screen per stage. Review (last season, retirees,
 * aging, your picks), the rookie draft (the board of available rookies), and
 * the roster check before the next season. Each block is collapsible with a
 * summary line first, and the one big button sits at the bottom of the screen.
 */
export function SimGameOffseason({ ctx, onTrade, onTeam }: { ctx: SimCtx; onTrade: () => void; onTeam: () => void }) {
  const { gameId, call } = ctx;
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [off, setOff] = useState<SimOffseason | null>(null);
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const [pos, setPos] = useState<SimPos | ''>('');
  const [busy, setBusy] = useState<Busy>(null);
  const [years, setYears] = useState<SimDynastyYear[]>([]);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getSimOffseason(gameId, pos)
      .then((body) => {
        if (cancelled) return;
        if (body.offseason) {
          setOff(body.offseason);
          setState('ready');
        } else {
          setState('error');
        }
      })
      .catch(() => {
        if (!cancelled) setState('error');
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, pos, ctx.tick, attempt]);

  // The per-year strip: every finished season (GET /dynasty), loaded once.
  useEffect(() => {
    let cancelled = false;
    api
      .getSimDynasty(gameId)
      .then((body) => {
        if (!cancelled && body.dynasty) setYears(body.dynasty.by_year ?? []);
      })
      .catch(() => {
        /* the strip is optional */
      });
    return () => {
      cancelled = true;
    };
  }, [gameId]);

  const apply = useCallback(
    (body: SimOffseasonResponse) => {
      if (body.offseason) setOff(body.offseason);
      if (body.game) ctx.setGame(body.game);
      ctx.bump();
    },
    [ctx],
  );

  async function run(kind: Exclude<Busy, null>, fn: () => Promise<SimOffseasonResponse>, message?: (body: SimOffseasonResponse) => string) {
    setBusy(kind);
    const body = await call(fn);
    setBusy(null);
    if (body) {
      apply(body);
      const text = message?.(body);
      if (text) ctx.notify(text, 'success');
    }
  }

  if (state === 'loading' && !off) {
    return (
      <View style={common.stack}>
        <SkeletonCard rows={3} />
        <SkeletonCard rows={5} />
      </View>
    );
  }
  if (state === 'error' || !off) {
    return (
      <ErrorState
        title="Could not load the offseason"
        message="Check your connection and try again."
        onRetry={() => {
          setState('loading');
          setAttempt((n) => n + 1);
        }}
      />
    );
  }

  const steps = offseasonStepper(simOffseasonSteps(off.stage));

  return (
    <View style={common.stack} testID="offseason">
      <OffseasonHero off={off} steps={steps} />

      {years.length > 0 && off.stage === 'review' ? <SimDynastyStrip years={years} /> : null}

      {off.stage === 'review' ? <ReviewStage off={off} ctx={ctx} years={years} /> : null}
      {off.stage === 'rookie_draft' ? (
        <RookieStage
          off={off}
          ctx={ctx}
          pos={pos}
          setPos={setPos}
          busy={busy}
          onPick={(player) => run('pick', () => api.pickSimRookie(gameId, player.id), (b) => `Drafted ${player.name}.${(b.made?.length ?? 0) > 1 ? ' The AI picks ran up to your next turn.' : ''}`)}
        />
      ) : null}
      {off.stage === 'cutdown' ? <CutdownStage off={off} ctx={ctx} onTrade={onTrade} onTeam={onTeam} /> : null}
    </View>
  );
}

// ---------------------------------------------------------------------------
// Hero: the one big thing on the page. Heading + a compact icon stepper, nothing else.

function OffseasonHero({ off, steps }: { off: SimOffseason; steps: OffseasonStepperItem[] }) {
  const { colors } = useThemeMode();
  return (
    <AccentCard accent={colors.accent} compact>
      <View style={{ flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
        <AppText style={{ flexShrink: 1, fontSize: 14, fontWeight: '800', color: colors.textPrimary }} numberOfLines={1}>{simOffseasonHeading(off)}</AppText>
        <AppText style={{ fontSize: 12, color: colors.textTertiary }}>
          Next: season {off.season_no + 1}/{off.seasons} · {off.year}
        </AppText>
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center' }} accessibilityLabel="Offseason steps" testID="offseason-stepper">
        {steps.map((step, i) => {
          const color = step.state === 'current' ? colors.accent : step.state === 'done' ? colors.success : colors.textTertiary;
          return (
            <View key={step.key} style={{ flexDirection: 'row', alignItems: 'center', flex: i === steps.length - 1 ? 0 : 1 }} accessible accessibilityLabel={step.aria}>
              <View style={{ alignItems: 'center', minWidth: 52, gap: 2 }}>
                <View
                  style={{
                    width: 28,
                    height: 28,
                    borderRadius: 14,
                    alignItems: 'center',
                    justifyContent: 'center',
                    backgroundColor: `${color}22`,
                    borderWidth: step.state === 'current' ? 2 : 1,
                    borderColor: color,
                    opacity: step.state === 'todo' ? 0.8 : 1,
                  }}
                >
                  {step.state === 'done' ? <OffseasonGlyph name="draft" size={14} color={color} /> : <OffseasonGlyph name={step.icon} size={14} color={color} />}
                </View>
                <AppText style={{ fontSize: 12, fontWeight: '700', color: step.state === 'todo' ? colors.textTertiary : colors.textPrimary }} importantForAccessibility="no">
                  {step.short}
                </AppText>
              </View>
              {i < steps.length - 1 ? <View style={{ flex: 1, height: 1, marginHorizontal: 4, marginBottom: 14, backgroundColor: step.state === 'done' ? colors.success : colors.borderStrong, opacity: step.state === 'done' ? 0.7 : 0.4 }} /> : null}
            </View>
          );
        })}
      </View>
    </AccentCard>
  );
}

// ---------------------------------------------------------------------------
// Review

function ReviewStage({ off, ctx, years }: { off: SimOffseason; ctx: SimCtx; years: SimDynastyYear[] }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const last = off.last_season;
  const lastYear = last ? simArchiveToYear(last) : null;
  const retired = simRetireesSorted(off.retired);
  const yours = retired.filter((r) => r.is_yours);
  const movers = off.movers ?? [];
  const mine = off.your_picks_this_draft ?? [];
  const titles = ctx.game.dynasty?.titles ?? years.filter((y) => y.champion?.is_you).length;
  const classChip = simRookieClassChip(off);
  const [notice, setNotice] = useState(false);
  return (
    <>
      {notice ? <SimGeneratedNoticeSheet onClose={() => setNotice(false)} /> : null}
      {last && lastYear ? (
        <SimCollapse
          title={simSeasonText(last)}
          icon="season"
          parts={offseasonSeasonParts(lastYear, last.champion)}
          tone={last.champion?.is_you ? 'success' : 'accent'}
          defaultOpen
          testID="off-last-season"
        >
          <View style={common.wrapRow}>
            <SimToneBadge label={simPlayoffResultLabel(lastYear.playoff_result)} tone={simPlayoffOutcomeTone(lastYear.playoff_result)} />
            <AppText style={common.bodyStrong}>{lastYear.record}</AppText>
            <AppText style={common.muted}>{simFmtPts(lastYear.pf)} PF</AppText>
          </View>
          <AppText style={[common.muted, last.champion?.is_you && { color: colors.success }]}>
            Champion: {last.champion ? `${last.champion.name}${last.champion.is_you ? ' (you)' : ''}` : 'none'}
            {titles > 0 ? ` · ${titles} title${titles === 1 ? '' : 's'} so far` : ''}
          </AppText>
          {lastYear.top_scorers.length > 0 ? <AppText style={common.small}>Top scorers: {lastYear.top_scorers.map((s) => `${s.name} ${s.pts.toFixed(1)}`).join(', ')}</AppText> : null}
        </SimCollapse>
      ) : null}

      <SimCollapse
        title="Retirements"
        icon="retire"
        parts={offseasonRetireParts(retired)}
        tone={yours.length ? 'danger' : 'muted'}
        defaultOpen={yours.length > 0}
        testID="off-retired"
      >
        {retired.length === 0 ? (
          <AppText style={common.muted}>No notable retirements this year.</AppText>
        ) : (
          retired.map((r) => (
            <View key={r.id} style={[common.rowBetween, common.divider, { paddingVertical: 8 }]}>
              <View style={common.grow}>
                <AppText style={common.bodyStrong}>{r.name}</AppText>
                <AppText style={common.muted}>
                  {r.pos}
                  {r.age != null ? ` · age ${r.age}` : ''}
                </AppText>
              </View>
              {r.is_yours ? <SimToneBadge label="Yours" tone="danger" /> : null}
            </View>
          ))
        )}
      </SimCollapse>

      <SimCollapse title="Aging" icon="aging" parts={offseasonAgingParts(movers)} defaultOpen={movers.length > 0} testID="off-aging">
        {movers.length === 0 ? (
          <AppText style={common.muted}>Your roster held steady.</AppText>
        ) : (
          <>
            <AppText style={common.muted}>Change in expected points per game, last season to this one.</AppText>
            {movers.map((m) => {
              const t = simMoverText(m);
              return (
                <SimRosterLine
                  key={m.id}
                  player={m}
                  onOpen={ctx.openPlayer}
                  trailing={
                    <View style={{ alignItems: 'flex-end' }} testID="mover">
                      <AppText style={{ fontSize: 15, fontWeight: '800', color: simToneColor(t.tone, colors) }}>
                        {t.arrow} {t.delta}
                      </AppText>
                      {t.age ? <AppText style={common.muted}>Age {t.age}</AppText> : null}
                    </View>
                  }
                />
              );
            })}
          </>
        )}
      </SimCollapse>

      {classChip ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 8 }} testID="review-class">
          <SimGeneratedChip label={classChip} onInfo={() => setNotice(true)} />
          <AppText style={common.muted}>Preview of the incoming class.</AppText>
        </View>
      ) : null}
      <SimCollapse
        title="Your picks"
        icon="picks"
        parts={offseasonPicksParts(mine, off.draft.round_count)}
        defaultOpen={mine.length > 0}
        testID="off-picks"
      >
        {mine.length === 0 ? (
          <AppText style={common.muted}>You traded them all away. You can still trade for picks before the draft starts.</AppText>
        ) : (
          mine.map((row) => (
            <View key={row.pick} style={[common.rowBetween, common.divider, { paddingVertical: 8 }]}>
              <AppText style={[common.bodyStrong, common.grow]}>{simRookiePickLine(row)}</AppText>
              {row.traded ? <SimToneBadge label="Traded for" tone="accent" /> : null}
            </View>
          ))
        )}
      </SimCollapse>
    </>
  );
}

// ---------------------------------------------------------------------------
// Rookie draft

function RookieStage({
  off,
  ctx,
  pos,
  setPos,
  busy,
  onPick,
}: {
  off: SimOffseason;
  ctx: SimCtx;
  pos: SimPos | '';
  setPos: (pos: SimPos | '') => void;
  busy: Busy;
  onPick: (player: SimGamePlayer) => void;
}) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const d = off.draft;
  const positions = simPositionsFor(ctx.game.settings.slots);
  const mine = off.your_picks_this_draft ?? [];
  const made = d.order.filter((o) => o.made);
  const toMake = mine.filter((m) => !m.made).length;
  const suppressed = simSuppressedBadges(d.available);
  const classChip = simRookieClassChip(off);
  const [notice, setNotice] = useState(false);
  return (
    <>
      {classChip ? <SimRookieNoticeGate gameId={ctx.gameId} /> : null}
      {notice ? <SimGeneratedNoticeSheet onClose={() => setNotice(false)} /> : null}
      <AppText style={{ position: 'absolute', width: 1, height: 1, opacity: 0 }} accessibilityLiveRegion="polite" testID="rookie-clock">{simRookieClockLine(d)}</AppText>
      <CompactModule
        id="rookie.clock"
        title="Rookie draft"
        testID="rookie-clock-module"
        tone={d.your_turn ? 'action' : 'accent'}
        persist={false}
        parts={simRookieSummaryParts(d, toMake)}
        action={
          d.your_turn && d.available[0] ? (
            <Button size="sm" label={`Draft ${d.available[0].name.split(' ').slice(-1)[0]}`} loading={busy === 'pick'} disabled={busy !== null && busy !== 'pick'} onPress={() => onPick(d.available[0])} />
          ) : null
        }
      >
        {classChip ? <SimGeneratedChip label={classChip} onInfo={() => setNotice(true)} /> : null}
        <View testID="rookie-mine">
          <AppText style={common.muted}>Your picks: {mine.filter((m) => m.made).length} of {mine.length} made</AppText>
          {mine.length === 0 ? (
            <AppText style={common.muted}>You have no picks in this draft.</AppText>
          ) : (
            mine.map((row) => (
              <View key={row.pick} style={[common.rowBetween, common.divider, { paddingVertical: 8 }]}>
                <AppText style={[common.bodyStrong, common.grow]}>{simRookiePickLine(row)}</AppText>
                {row.made ? <SimToneBadge label={row.made.pos} tone="success" /> : d.on_clock?.pick === row.pick ? <SimToneBadge label="On the clock" tone="accent" /> : null}
              </View>
            ))
          )}
        </View>
      </CompactModule>
      <SimRookieOverview order={d.order} onClockPick={d.on_clock?.pick} round={d.on_clock?.round ?? 1} made={made.length} total={d.total} />

      <View style={common.stack}>
        <SegmentedTabBar<string>
          scrollable
          options={[{ key: '', label: 'All' }, ...positions.map((p) => ({ key: p as string, label: p }))]}
          active={pos}
          onChange={(key) => setPos(key as SimPos | '')}
        />
        {d.available.length === 0 ? (
          <EmptyState icon="people-outline" title="No rookies left that match" subtitle="Try a different position." />
        ) : (
          <View>
            {d.available.map((player) => (
              <SimDraftRow
                key={player.id}
                player={player}
                onOpen={ctx.openPlayer}
                onGeneratedInfo={() => setNotice(true)}
                suppressBadges={suppressed}
                actions={d.your_turn ? <SimDraftIconButton icon="checkmark" size={44} width={48} primary label={`Draft ${player.name}`} disabled={busy !== null} onPress={() => onPick(player)} /> : null}
              />
            ))}
          </View>
        )}
      </View>

      <SimCollapse title="Draft log" icon="log" parts={offseasonLogParts(made.length, d.total)} testID="rookie-log">
        {made.length === 0 ? (
          <AppText style={common.muted}>No picks yet.</AppText>
        ) : (
          [...made]
            .reverse()
            .slice(0, 30)
            .map((row) => (
              <View key={row.pick} style={[common.rowBetween, common.divider, { paddingVertical: 6 }]}>
                <AppText style={[common.small, common.grow]}>
                  #{row.n} {row.made?.name} ({row.made?.pos})
                </AppText>
                <AppText style={[common.muted, row.is_yours && { color: colors.accent }]}>{row.is_yours ? 'You' : row.team_name}</AppText>
              </View>
            ))
        )}
      </SimCollapse>
    </>
  );
}

// ---------------------------------------------------------------------------
// Roster check

function CutdownStage({ off, ctx, onTrade, onTeam }: { off: SimOffseason; ctx: SimCtx; onTrade: () => void; onTeam: () => void }) {
  const { gameId, game, call } = ctx;
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const teamId = game.you?.team_id;
  const [roster, setRoster] = useState<SimTeamRosterResponse | null>(null);
  const [cutting, setCutting] = useState<string | null>(null);
  const [moving, setMoving] = useState<SimGamePlayer | null>(null);
  const picks = useSimPicks(ctx);
  const r = off.roster;

  useEffect(() => {
    if (!teamId) return;
    let cancelled = false;
    api
      .getSimGameTeam(gameId, teamId)
      .then((body) => {
        if (!cancelled && !body.reason) setRoster(body);
      })
      .catch(() => {
        /* the summary above still works */
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, teamId, ctx.tick]);

  async function cut(player: SimGamePlayer) {
    setCutting(null);
    const body = await call(() => api.cutSimPlayer(gameId, player.id));
    if (body) {
      ctx.notify(`Cut ${player.name}.`, 'success');
      ctx.bump();
      await ctx.reloadGame();
    }
  }

  const over = r.cuts_needed > 0;
  const blocks = over && simLimitBlocks(r);
  const players = roster?.players ?? [];
  const reservesOn = simReservesOn(game.settings, roster?.reserves ?? r.reserves);
  const reserveState = { reserves: roster?.reserves ?? r.reserves, rosterSize: r.size, rosterLimit: r.limit };
  const myPicks = simPicksOf(picks, teamId);
  const rosterSuppressed = simSuppressedBadges(players);
  return (
    <>
      <AppText style={{ position: 'absolute', width: 1, height: 1, opacity: 0 }} accessibilityRole={blocks ? 'alert' : undefined} testID="roster-check">
        {blocks ? `Cut ${r.cuts_needed} player${r.cuts_needed === 1 ? '' : 's'} to start the season.` : over ? simOverLimitNote(r.cuts_needed) : 'Your roster is ready for the season.'} {r.size} of {r.limit} roster spots. IR and taxi players do not count.
      </AppText>
      <SimCollapse
        title="Roster"
        icon="roster"
        tone={blocks ? 'danger' : over ? 'warning' : 'success'}
        defaultOpen={blocks}
        parts={offseasonRosterParts(r, players)}
        action={
          off.can_trade ? (
            <SimDraftIconButton icon="swap-horizontal" size={44} width={44} label="Shop a trade" onPress={onTrade} />
          ) : (
            <SimDraftIconButton icon="shirt-outline" size={44} width={44} label="Open Team tab" onPress={onTeam} />
          )
        }
        testID="cutdown-roster"
      >
        {off.can_trade ? (
          <View style={{ alignItems: 'flex-end' }}>
            <SimDraftIconButton icon="shirt-outline" size={36} width={36} label="Open Team tab" onPress={onTeam} />
          </View>
        ) : null}
        {players.length === 0 ? (
          <AppText style={common.muted}>Loading your roster.</AppText>
        ) : (
          players.map((player) => (
            <SimRosterLine
              key={player.id}
              player={player}
              suppressBadges={rosterSuppressed}
              onOpen={ctx.openPlayer}
              trailing={
                cutting === player.id ? (
                  <>
                    <Button size="sm" variant="danger" label="Cut" onPress={() => void cut(player)} />
                    <Button size="sm" variant="ghost" label="Keep" onPress={() => setCutting(null)} />
                  </>
                ) : (
                  <>
                    {reservesOn ? <SimReserveButton player={player} onOpen={setMoving} /> : null}
                    <Button size="sm" variant={over ? 'dangerOutline' : 'ghost'} label="Cut" onPress={() => setCutting(player.id)} />
                  </>
                )
              }
            />
          ))
        )}
      </SimCollapse>

      {reservesOn ? <SimReserveGroups ir={roster?.ir ?? r.ir ?? []} taxi={roster?.taxi ?? r.taxi ?? []} state={reserveState} onOpen={setMoving} openPlayer={ctx.openPlayer} cutting={cutting} onAskCut={setCutting} onCut={(p) => void cut(p)} /> : null}

      {game.settings.mode === 'dynasty' && myPicks.length > 0 ? (
        <SimCollapse title="Future picks" icon="picks" parts={offseasonPickCountParts(myPicks.length)} testID="cutdown-picks">
          {myPicks.map((pick) => (
            <SimPickLine key={pick.id} pick={pick} draftYear={picks?.draft_year} />
          ))}
        </SimCollapse>
      ) : null}

      {moving ? (
        <SimReserveSheet
          ctx={ctx}
          player={moving}
          state={reserveState}
          onClose={() => setMoving(null)}
          onMoved={(_, player, to) => {
            setMoving(null);
            ctx.notify(`${player.name} ${to === 'ir' ? 'is on IR' : to === 'taxi' ? 'is on the taxi squad' : 'is back on your roster'}.`, 'success');
            ctx.bump();
          }}
        />
      ) : null}
    </>
  );
}
