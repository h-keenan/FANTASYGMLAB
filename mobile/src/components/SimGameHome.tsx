import React, { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import ErrorState from './ErrorState';
import PositionBadge from './PositionBadge';
import SimGlyph from './SimGlyph';
import SegmentedTabBar from './SegmentedTabBar';
import { SkeletonCard } from './SkeletonBlock';
import {
  SimByeCard,
  SimHotColdCard,
  SimInboxCard,
  SimInjuriesCard,
  SimLeagueMovesCard,
  SimStandingsCard,
  SimWaiverCard,
} from './SimGameHomeCards';
import { SimMiniPlayer, SimSectionTitle, SimTeamLink, SimToneBadge, createSimStyles, simToneColor, type SimCtx } from './SimGameParts';
import { ClaimSheet } from './SimGameTeam';
import ToneBadge from './ToneBadge';
import { useSimAutoSet } from './useSimAutoSet';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import {
  simChecklistProgress,
  simChecklistTone,
  simFmtPts,
  simFmtRecord,
  simRowEdge,
  simSlotLabels,
  simWinChanceLabel,
  simWinChanceTone,
  type SimGamePlayer,
  type SimHomeMatchup,
  type SimHomeResponse,
  type SimWaiverClaim,
} from '../lib/simGame';
import type { SimTab } from '../lib/simGameFlow';
import { SIM_HOME_VIEWS, type SimHomeView } from '../lib/simLayout';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * The game's landing tab: this week's head-to-head, what to do this week,
 * bye-week cover, waiver targets for your holes, your trade inbox, injuries,
 * the standings and playoff picture, hot/cold players and what happened
 * around the league. One read-only call (GET /home); each card links to the
 * tab that handles it. Mirrors web-next's SimHomeTab.
 */
export function SimHomeTab({ ctx, setClaims, onTab }: { ctx: SimCtx; setClaims: (claims: SimWaiverClaim[]) => void; onTab: (tab: SimTab) => void }) {
  const { gameId } = ctx;
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [home, setHome] = useState<SimHomeResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [claiming, setClaiming] = useState<{ player: SimGamePlayer; roster: SimGamePlayer[] } | null>(null);
  const teamId = ctx.game.you?.team_id;
  const [view, setView] = useState<SimHomeView>('week');

  useEffect(() => {
    let cancelled = false;
    api
      .getSimHome(gameId)
      .then((body) => {
        if (cancelled) return;
        if (body.reason) setFailed(true);
        else {
          setFailed(false);
          setHome(body);
        }
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, ctx.tick, attempt]);

  // Auto-set best lineup (shared hook): names the swap in a toast; the matchup card refreshes in place.
  const auto = useSimAutoSet(ctx, (applied) =>
    setHome((prev) =>
      prev?.matchup
        ? { ...prev, matchup: { ...prev.matchup, you_projection: applied.projected_total ?? prev.matchup.you_projection, rows: prev.matchup.rows.map((row, i) => ({ ...row, you: applied.slots?.[i]?.player ?? row.you })) } }
        : prev,
    ),
  );

  async function claim(player: SimGamePlayer) {
    let roster: SimGamePlayer[] = [];
    if (teamId) {
      try {
        roster = (await api.getSimGameTeam(gameId, teamId)).players ?? [];
      } catch {
        roster = [];
      }
    }
    setClaiming({ player, roster });
  }

  if (failed && !home) {
    return (
      <ErrorState
        title="Home did not load"
        message="Check your connection and try again."
        onRetry={() => {
          setFailed(false);
          setAttempt((n) => n + 1);
        }}
      />
    );
  }
  if (!home) return <SkeletonCard rows={6} />;

  const names = Object.fromEntries((home.standings?.rows ?? []).map((r) => [r.team_id, r.name]));
  const inboxCount = home.inbox?.count ?? 0;
  return (
    <View style={common.stack} testID="sim-home">
      <SegmentedTabBar
        options={SIM_HOME_VIEWS.map((v) => ({ key: v.value, label: v.value === 'week' && inboxCount > 0 ? `${v.label} · ${inboxCount}` : v.label, glyph: v.glyph }))}
        active={view}
        onChange={setView}
      />
      {view === 'week' ? (
        <>
          {home.matchup ? <SimMatchupCard ctx={ctx} matchup={home.matchup} onTab={onTab} /> : null}
          <SimChecklistCard home={home} onTab={onTab} onAuto={home.matchup && !home.matchup.bye ? auto.run : undefined} autoBusy={auto.busy} optimal={auto.optimal} />
          <SimInboxCard ctx={ctx} inbox={home.inbox} onTab={onTab} />
          <SimWaiverCard ctx={ctx} suggestions={home.waiver_suggestions ?? []} onClaim={claim} onTab={onTab} />
          <SimByeCard ctx={ctx} alerts={home.bye_alerts ?? []} onTab={onTab} onClaim={claim} />
          <SimInjuriesCard ctx={ctx} injuries={home.injuries ?? []} />
        </>
      ) : (
        <>
          <SimStandingsCard standings={home.standings} onTab={onTab} />
          <SimHotColdCard ctx={ctx} hotCold={home.hot_cold} onClaim={claim} />
          <SimLeagueMovesCard league={home.league} names={names} onTab={onTab} />
        </>
      )}
      {claiming ? (
        <ClaimSheet
          ctx={ctx}
          player={claiming.player}
          roster={claiming.roster}
          onClose={() => setClaiming(null)}
          onClaimed={(next) => {
            setClaims(next);
            ctx.bump();
          }}
        />
      ) : null}
    </View>
  );
}

function SimMatchupCard({ ctx, matchup, onTab }: { ctx: SimCtx; matchup: SimHomeMatchup; onTab: (tab: SimTab) => void }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  const you = ctx.game.you;
  const opp = matchup.opponent;
  const [showLineups, setShowLineups] = useState(false);
  if (matchup.bye || !opp) {
    return (
      <AccentCard accent={colors.warning}>
        <SimSectionTitle glyph="bye" tone="warning" title={`Week ${matchup.week} bye`} />
        <AppText style={common.small}>You do not play this week. Use it to work the wire and your trades.</AppText>
      </AccentCard>
    );
  }
  const prob = matchup.win_prob ?? 0.5;
  const tone = simWinChanceTone(prob);
  const youProj = matchup.you_projection ?? 0;
  const oppProj = matchup.opp_projection ?? 0;
  const labels = simSlotLabels(matchup.rows);
  const flagged = (matchup.you_flagged ?? 0) + (matchup.opp_flagged ?? 0);
  const lineupsOpen = showLineups;
  return (
    <AccentCard accent={colors.accent} glow>
      <SimSectionTitle
        glyph="matchup"
        title={matchup.kind === 'playoff' ? 'Playoff matchup' : `Week ${matchup.week} matchup`}
        right={<Button label="Set lineup" size="sm" variant="secondary" onPress={() => onTab('team')} />}
      />
      <View style={styles.versus}>
        <View style={styles.versusSide}>
          <SimTeamLink teamId={you?.team_id} name={you?.name ?? 'You'} isYou size={36} stacked />
          <AppText style={common.muted}>{matchup.you_record ? simFmtRecord(matchup.you_record) : ''}</AppText>
        </View>
        <AppText style={styles.vs}>VS</AppText>
        <View style={styles.versusSide}>
          <SimTeamLink teamId={opp.team_id} name={opp.name} size={36} stacked />
          <AppText style={[common.muted, common.center]}>
            {opp.record ? simFmtRecord(opp.record) : ''} · {opp.persona.label}
          </AppText>
        </View>
      </View>

      <View style={common.tight} testID="win-chance">
        <View style={styles.chanceRow}>
          <AppText style={common.muted}>Your win chance</AppText>
          <AppText style={[styles.chance, { color: simToneColor(tone, colors) }]}>{simWinChanceLabel(prob)}</AppText>
        </View>
        <View style={styles.track} accessibilityRole="progressbar" accessibilityLabel={`Win chance ${simWinChanceLabel(prob)}`}>
          <View style={[styles.fill, { width: `${Math.round(prob * 100)}%` }]} />
        </View>
        <View style={common.rowBetween}>
          <AppText style={[styles.proj, youProj >= oppProj && { color: colors.success }]} testID="your-projection">
            {simFmtPts(youProj)}
          </AppText>
          <AppText style={common.muted}>projected points</AppText>
          <AppText style={[styles.proj, oppProj > youProj && { color: colors.danger }]}>{simFmtPts(oppProj)}</AppText>
        </View>
      </View>

      {flagged > 0 ? (
        <View style={common.row} accessibilityLiveRegion="polite">
          <SimGlyph name="alert" color={colors.warning} size={14} />
          <AppText style={[common.small, { color: colors.warning, flex: 1 }]}>
            {(matchup.you_flagged ?? 0) > 0 ? `${matchup.you_flagged} of your starters are out or on bye. ` : ''}
            {(matchup.opp_flagged ?? 0) > 0 ? `${matchup.opp_flagged} of theirs ${matchup.opp_flagged === 1 ? 'is' : 'are'} too.` : ''}
          </AppText>
        </View>
      ) : null}

      <Pressable
        accessibilityRole="button"
        accessibilityState={{ expanded: lineupsOpen }}
        onPress={() => setShowLineups(!lineupsOpen)}
        style={{ minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' }}
      >
        <AppText style={{ fontSize: 12.5, fontWeight: '800', color: colors.accent }}>{lineupsOpen ? 'Hide lineups' : `Show lineups (${matchup.rows.length} slots)`}</AppText>
      </Pressable>
      {lineupsOpen ? (
        <View style={common.tight}>
      <View accessibilityLabel="Lineups head to head">
          {matchup.rows.map((row, index) => {
            const edge = simRowEdge(row);
            return (
              <View key={`${row.slot}-${index}`} style={styles.slotRow}>
                <Side player={row.you} win={edge === 'you'} lose={edge === 'opp'} align="left" ctx={ctx} />
                <View style={styles.slotMid}>
                  <PositionBadge position={row.slot} label={labels[index]} />
                </View>
                <Side player={row.opp} win={edge === 'opp'} lose={edge === 'you'} align="right" ctx={ctx} />
              </View>
            );
          })}
        </View>
        <AppText style={common.muted}>Their lineup is what their manager will start. Projections update when injuries or byes change.</AppText>
        </View>
      ) : null}
    </AccentCard>
  );
}

function Side({ player, win, lose, align, ctx }: { player: SimGamePlayer | null; win: boolean; lose: boolean; align: 'left' | 'right'; ctx: SimCtx }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const tint = win ? colors.success : lose ? colors.danger : colors.textSecondary;
  const end = align === 'right';
  if (!player) {
    return (
      <View style={[styles.side, end && styles.sideRight]}>
        <AppText style={styles.empty}>Empty</AppText>
      </View>
    );
  }
  // Projection above the name so the name keeps the whole cell width (two lines allowed).
  return (
    <View style={[styles.side, end && styles.sideRight, win && { backgroundColor: colors.successMuted }]}>
      <AppText style={[styles.sideProj, { color: player.status === 'healthy' ? tint : colors.textTertiary }]}>{simFmtPts(player.projection)}</AppText>
      <SimMiniPlayer player={player} align={align} onOpen={ctx.openPlayer} size={24} wrap />
    </View>
  );
}

function SimChecklistCard({ home, onTab, onAuto, autoBusy = false, optimal = false }: { home: SimHomeResponse; onTab: (tab: SimTab) => void; onAuto?: () => void; autoBusy?: boolean; optimal?: boolean }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  const items = home.checklist ?? [];
  const { done, total } = simChecklistProgress(items);
  const allDone = total > 0 && done === total;
  const accent = allDone ? colors.success : colors.warning;
  return (
    <AccentCard accent={accent}>
      <SimSectionTitle glyph="checklist" tone={allDone ? 'success' : 'warning'} title="What to do this week" right={<ToneBadge label={`${done}/${total} done`} color={accent} />} />
      <View style={styles.thinTrack}>
        <View style={[styles.thinFill, { width: total ? `${(done / total) * 100}%` : '0%', backgroundColor: accent }]} />
      </View>
      {onAuto ? (
        <Button label={optimal ? 'Lineup is optimal' : 'Auto-set best lineup'} variant="secondary" loading={autoBusy} disabled={optimal} onPress={onAuto} />
      ) : null}
      {items.map((item, index) => {
        const color = simToneColor(simChecklistTone(item.severity), colors);
        return (
          <View key={item.id} style={index > 0 ? common.divider : undefined}>
            <AccentTap onPress={() => onTab(item.target)} label={`${item.label}. ${item.detail}`}>
              <View style={[styles.check, { backgroundColor: item.done ? colors.success : colors.glassInset }]}>
                <SimGlyph name={item.done ? 'check' : item.severity === 'accent' ? 'trade' : 'alert'} color={item.done ? colors.onAccent : color} size={14} />
              </View>
              <View style={common.grow}>
                <AppText style={[common.bodyStrong, item.done && { color: colors.textTertiary, textDecorationLine: 'line-through' }]}>{item.label}</AppText>
                {item.done ? null : <AppText style={common.small}>{item.detail}</AppText>}
              </View>
              <SimToneBadge label={item.done ? 'Done' : item.severity === 'danger' ? 'Fix' : item.severity === 'accent' ? 'New' : 'To do'} tone={item.done ? 'success' : simChecklistTone(item.severity)} />
            </AccentTap>
          </View>
        );
      })}
    </AccentCard>
  );
}

function AccentTap({ onPress, label, children }: { onPress: () => void; label: string; children: React.ReactNode }) {
  return (
    <Pressable onPress={onPress} accessibilityRole="button" accessibilityLabel={label} style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.md, minHeight: 48, paddingVertical: spacing.sm }}>
      {children}
    </Pressable>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    versus: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    versusSide: { flex: 1, alignItems: 'center', gap: 2, minWidth: 0 },
    vs: { fontSize: 12.5, fontWeight: '800', color: colors.textTertiary },
    chanceRow: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'space-between' },
    chance: { fontSize: 28, fontWeight: '800' },
    track: { height: 8, borderRadius: radii.pill, overflow: 'hidden', backgroundColor: colors.dangerMuted },
    fill: { height: 8, backgroundColor: colors.success },
    proj: { fontSize: 16, fontWeight: '800', color: colors.textPrimary },
    slotRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, paddingVertical: spacing.xs, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
    slotMid: { width: 50, alignItems: 'center' },
    side: { flex: 1, alignItems: 'flex-start', gap: 2, minWidth: 0, borderRadius: radii.md, paddingHorizontal: 6, paddingVertical: 4 },
    sideRight: { alignItems: 'flex-end' },
    sideProj: { fontSize: 14, fontWeight: '800' },
    empty: { fontSize: 12.5, color: colors.textTertiary },
    thinTrack: { height: 6, borderRadius: radii.pill, overflow: 'hidden', backgroundColor: colors.glassInset },
    thinFill: { height: 6 },
    check: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  });
}
