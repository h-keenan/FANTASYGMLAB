import React, { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import SegmentedTabBar from './SegmentedTabBar';
import { SimLeaguePlayersView, SimLeagueTeamsView } from './SimLeagueWho';
import { SkeletonCard } from './SkeletonBlock';
import { ReviewGlyphChip } from './SeasonReviewSections';
import { SimPlayerChip, SimSectionTitle, SimSeeAll, SimSheet, SimTeamLink, SimToneBadge, createSimStyles, simToneColor, type SimCtx } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import {
  simFmtPts,
  simFmtRecord,
  simPlayoffRoundLabel,
  simPlayoffStatusLabel,
  simPlayoffStatusTone,
  simStreakTone,
  simTransactionGlyph,
  simTransactionRoleTone,
  simTeamNameMap,
  simTransactionText,
  type SimLeagueResponse,
  type SimRecapScore,
  type SimStandingRow,
} from '../lib/simGame';
import { CountUp, MotionIn } from './Motion';
import SimCrest from './SimCrest';
import { simMatchupMargin, simMatchupStatus, simPreview, simScoreboardLabel } from '../lib/simLayout';
import { useSimLeagueRosters } from '../lib/useSimLeagueRosters';
import { spacing } from '../theme';

type View_ = 'standings' | 'scores' | 'feed' | 'teams' | 'players';

export function SimStandingsList({ rows, playoffTeams }: { rows: SimStandingRow[]; playoffTeams?: number }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  // One dense row per team (rank, crest, name, streak, record) in a single card, dashed line at the playoff cut.
  return (
    <AccentCard accent={colors.success} compact>
      <View accessibilityLabel="Standings">
        {rows.map((row, index) => {
          const inPlayoffs = index < (playoffTeams ?? 0);
          const cut = index === (playoffTeams ?? 0) - 1;
          return (
            <View
              key={row.team_id}
              accessibilityHint={simPlayoffStatusLabel(row.playoff_status) || undefined}
              style={[
                { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 36, paddingHorizontal: 4 },
                row.is_you && { backgroundColor: colors.accentMuted },
                cut ? { borderBottomWidth: 2, borderStyle: 'dashed', borderBottomColor: colors.success } : { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
              ]}
            >
              <AppText style={{ width: 20, fontSize: 12.5, fontWeight: '800', color: inPlayoffs ? colors.success : colors.textTertiary }}>{row.rank ?? index + 1}</AppText>
              <View style={common.grow}>
                <SimTeamLink teamId={row.team_id} name={row.name} isYou={row.is_you} size={22} bold={row.is_you} />
              </View>
              <AppText style={{ fontSize: 12.5, fontWeight: '700', color: simToneColor(simStreakTone(row.streak ?? ''), colors) }}>{row.streak ?? ''}</AppText>
              <AppText style={[common.bodyStrong, { width: 48, textAlign: 'right' }]}>{simFmtRecord(row)}</AppText>
            </View>
          );
        })}
      </View>
    </AccentCard>
  );
}

/**
 * One matchup as a centered module: crest + name on each side, the two scores big in the middle (winner
 * emphasized, loser muted), a status dot + key (FINAL / UPCOMING) under them, my game highlighted. The
 * whole card is pressable and opens the full matchup in a sheet. Web twin: web-next/src/components/SimGameLeague.tsx.
 */
export function SimScoreCard({ g, names, youId, onOpen }: { g: SimRecapScore; names: Record<string, string>; youId?: string; onOpen: () => void }) {
  const { colors } = useThemeMode();
  const mine = g.home === youId || g.away === youId;
  const mineTone = !mine || !g.winner ? 'accent' : g.winner === youId ? 'success' : 'danger';
  const status = simMatchupStatus(g);
  const side = (id: string, pts: number | null) => ({ id, pts, won: g.winner === id, lost: Boolean(g.winner) && g.winner !== id });
  const left = side(g.home, g.home_pts);
  const right = side(g.away, g.away_pts);
  const team = (t: ReturnType<typeof side>) => (
    <View style={{ flex: 1, minWidth: 0, alignItems: 'center', gap: 4, opacity: t.lost ? 0.7 : 1 }}>
      <SimCrest name={names[t.id] ?? 'Team'} size={36} />
      <AppText numberOfLines={2} style={{ fontSize: 12, textAlign: 'center', fontWeight: t.won ? '800' : '600', color: colors.textPrimary }}>{names[t.id] ?? 'Team'}</AppText>
      {t.id === youId ? <ToneBadge label="YOU" color={colors.accent} size="xs" /> : null}
    </View>
  );
  const score = (t: ReturnType<typeof side>) => (
    t.pts == null ? (
      <AppText style={{ fontSize: 20, fontWeight: '600', color: colors.textPrimary }}>-</AppText>
    ) : (
      <CountUp value={t.pts} render={(text) => <AppText style={{ fontSize: 20, fontWeight: t.won ? '900' : '600', color: t.won ? colors.success : t.lost ? colors.textTertiary : colors.textPrimary }}>{text}</AppText>} />
    )
  );
  return (
    <Pressable
      onPress={onOpen}
      accessibilityRole="button"
      accessibilityLabel={`${names[g.home] ?? 'Team'} versus ${names[g.away] ?? 'Team'}. ${status.label}. Open matchup`}
      testID="sim-score-card"
    >
      <AccentCard accent={mine ? simToneColor(mineTone, colors) : colors.borderStrong} compact>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: spacing.sm }}>
          {team(left)}
          <View style={{ width: 150, alignItems: 'center', gap: 4 }}>
            <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: spacing.sm }}>
              {score(left)}
              <AppText style={{ color: colors.textTertiary }}>–</AppText>
              {score(right)}
            </View>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
              <View style={{ width: 6, height: 6, borderRadius: 3, backgroundColor: status.tone === 'success' ? colors.success : colors.textTertiary }} />
              <AppText style={{ fontSize: 12, fontWeight: '800', letterSpacing: 0.6, color: status.tone === 'success' ? colors.success : colors.textTertiary }}>{status.label}</AppText>
            </View>
          </View>
          {team(right)}
        </View>
      </AccentCard>
    </Pressable>
  );
}

function SimMatchupSheet({ g, names, youId, week, label, onClose }: { g: SimRecapScore; names: Record<string, string>; youId?: string; week: number; label: string; onClose: () => void }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const status = simMatchupStatus(g);
  const rows = [
    [g.home, g.home_pts],
    [g.away, g.away_pts],
  ] as const;
  return (
    <SimSheet title={`${names[g.home] ?? 'Team'} vs ${names[g.away] ?? 'Team'}`} onClose={onClose}>
      <AppText style={common.muted}>{`${label} · ${status.label}`}</AppText>
      <View style={common.stack} testID="sim-matchup-sheet">
        {rows.map(([id, pts]) => (
          <View key={id} style={common.rowBetween}>
            <View style={common.grow}>
              <SimTeamLink teamId={id} name={names[id] ?? 'Team'} isYou={id === youId} size={32} bold={g.winner === id} />
            </View>
            <AppText style={{ fontSize: 22, fontWeight: g.winner === id ? '900' : '600', color: g.winner === id ? colors.success : colors.textPrimary }}>{pts == null ? '-' : simFmtPts(pts)}</AppText>
          </View>
        ))}
        <AppText style={common.bodyStrong}>{simMatchupMargin(g, names)}</AppText>
        <AppText style={common.muted}>{`Week ${week}. Tap a team for its scouting sheet.`}</AppText>
      </View>
    </SimSheet>
  );
}

function Scoreboard({ game, schedule, names }: { game: SimCtx['game']; schedule: NonNullable<SimLeagueResponse['schedule']>; names: Record<string, string> }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const played = schedule.filter((w) => w.games.some((g) => g.home_pts != null));
  const [week, setWeek] = useState<number>(() => (played.length ? played[played.length - 1].week : Math.max(1, game.week)));
  const [open, setOpen] = useState<SimRecapScore | null>(null);
  const entry = schedule.find((w) => w.week === week);
  const roundLabel = entry?.kind === 'playoff' ? simPlayoffRoundLabel(week, game.settings) : `Week ${week}`;
  const label = simScoreboardLabel(roundLabel, week);
  const youId = game.you?.team_id;
  return (
    <View style={common.stack}>
      <View style={common.rowBetween}>
        <Button size="sm" variant="secondary" label="Previous" disabled={week <= 1} onPress={() => setWeek((w) => w - 1)} />
        <AppText style={common.bodyStrong} accessibilityLiveRegion="polite">
          {label}
        </AppText>
        <Button size="sm" variant="secondary" label="Next" disabled={week >= schedule.length} onPress={() => setWeek((w) => w + 1)} />
      </View>
      {!entry || entry.games.length === 0 ? (
        <EmptyState icon="calendar-outline" title="No games" subtitle="Nothing is scheduled this week." />
      ) : (
        // The cards rise in a capped stagger; changing the week remounts them (key) so the scores count up again.
        entry.games.map((g: SimRecapScore, i) => (
          <MotionIn key={`${week}-${g.home}-${g.away}`} index={i} count={entry.games.length}>
            <SimScoreCard g={g} names={names} youId={youId} onOpen={() => setOpen(g)} />
          </MotionIn>
        ))
      )}
      {open ? <SimMatchupSheet g={open} names={names} youId={youId} week={week} label={label} onClose={() => setOpen(null)} /> : null}
    </View>
  );
}

/** Standings, scoreboard, transaction feed and AI-team scouting. */
export function SimLeagueTab({ ctx }: { ctx: SimCtx }) {
  const { gameId, game } = ctx;
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [view, setView] = useState<View_>('standings');
  const [league, setLeague] = useState<SimLeagueResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const [allMoves, setAllMoves] = useState(false);
  const [rosterAttempt, setRosterAttempt] = useState(0);
  // One request for every team's roster, only once Teams or Players is opened.
  const rosters = useSimLeagueRosters(gameId, ctx.tick, rosterAttempt, view === 'teams' || view === 'players');

  useEffect(() => {
    let cancelled = false;
    api
      .getSimLeague(gameId)
      .then((body) => {
        if (cancelled) return;
        if (body.reason) setFailed(true);
        else setLeague(body);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, ctx.tick, attempt]);

  const names = useMemo(() => simTeamNameMap(league?.teams), [league?.teams]);

  if (failed) {
    return (
      <ErrorState
        title="The league did not load"
        message="Check your connection and try again."
        onRetry={() => {
          setFailed(false);
          setAttempt((n) => n + 1);
        }}
      />
    );
  }
  if (!league) return <SkeletonCard rows={6} />;

  return (
    <View style={common.stack}>
      <SegmentedTabBar<View_>
        options={[
          { key: 'standings', label: 'Standings', glyph: 'standings' },
          { key: 'scores', label: 'Scores', glyph: 'scores' },
          { key: 'feed', label: 'Feed', glyph: 'feed' },
          { key: 'teams', label: 'Teams', glyph: 'team' },
          { key: 'players', label: 'Players', glyph: 'league' },
        ]}
        active={view}
        onChange={setView}
      />
      {view === 'standings' ? (
        <View style={common.stack}>
          <SimSectionTitle glyph="standings" tone="success" title="Standings" caption={`Top ${game.settings.playoff_teams} make the playoffs. Ties break on ${game.settings.tiebreaker === 'head_to_head' ? 'head-to-head, then points' : 'points for, then head-to-head'}.`} />
          <SimStandingsList rows={league.standings ?? []} playoffTeams={game.settings.playoff_teams} />
        </View>
      ) : null}
      {view === 'scores' ? <Scoreboard game={game} schedule={league.schedule ?? []} names={names} /> : null}
      {view === 'feed' ? (
        <View style={common.stack}>
          <SimSectionTitle glyph="league" title="Around the league" caption="AI trades and waiver moves, newest first." />
          {(league.transactions ?? []).length === 0 ? (
            <EmptyState icon="newspaper-outline" title="Quiet so far" subtitle="Moves show up here once the season gets going." />
          ) : (
            simPreview(league.transactions ?? [], allMoves, 6).shown.map((tx, i) => (
              <AccentCard key={i} accent={simToneColor(simTransactionGlyph(tx).tone, colors)} compact>
                <View style={common.row}>
                  {tx.team_id ? <SimTeamLink teamId={tx.team_id} name={names[tx.team_id] ?? 'Team'} size={24} hideName /> : null}
                  <ReviewGlyphChip glyph={simTransactionGlyph(tx).glyph} tone={simTransactionGlyph(tx).tone} size={24} />
                  {tx.week != null ? <ToneBadge label={`Week ${tx.week}`} color={colors.textSecondary} size="xs" /> : null}
                  <ToneBadge label={String(tx.type ?? tx.kind ?? 'move').replace(/_/g, ' ')} color={simToneColor(simTransactionGlyph(tx).tone, colors)} size="xs" />
                </View>
                <AppText style={common.body}>{simTransactionText(tx)}</AppText>
                {(tx.players ?? []).map((p) => (
                  <View key={`${p.role}-${p.id}`} style={common.row}>
                    <ToneBadge label={p.role} color={simToneColor(simTransactionRoleTone(p.role), colors)} size="xs" />
                    <SimPlayerChip player={p} size={28} />
                  </View>
                ))}
              </AccentCard>
            ))
          )}
          <SimSeeAll hidden={simPreview(league.transactions ?? [], allMoves, 6).hidden} expanded={allMoves} onToggle={() => setAllMoves((v) => !v)} />
        </View>
      ) : null}
      {view === 'teams' ? <SimLeagueTeamsView ctx={ctx} state={rosters} onRetry={() => setRosterAttempt((n) => n + 1)} /> : null}
      {view === 'players' ? <SimLeaguePlayersView ctx={ctx} state={rosters} onRetry={() => setRosterAttempt((n) => n + 1)} /> : null}
    </View>
  );
}
