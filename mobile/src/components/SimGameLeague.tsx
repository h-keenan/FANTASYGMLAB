import React, { useEffect, useMemo, useState } from 'react';
import { View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import EmptyState from './EmptyState';
import ErrorState from './ErrorState';
import SegmentedTabBar from './SegmentedTabBar';
import { SkeletonCard } from './SkeletonBlock';
import { ReviewGlyphChip } from './SeasonReviewSections';
import { SimPlayerChip, SimSectionTitle, SimTeamLink, SimToneBadge, createSimStyles, simToneColor, type SimCtx } from './SimGameParts';
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

type View_ = 'standings' | 'scores' | 'feed' | 'teams';

export function SimStandingsList({ rows, playoffTeams }: { rows: SimStandingRow[]; playoffTeams?: number }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  return (
    <View style={common.stack} accessibilityLabel="Standings">
      {rows.map((row, index) => (
        <AccentCard key={row.team_id} accent={row.is_you ? colors.accent : index < (playoffTeams ?? 0) ? colors.success : colors.borderStrong} compact>
          <View style={common.rowBetween}>
            <View style={[common.row, common.grow]}>
              <AppText style={[common.bodyStrong, { color: index < (playoffTeams ?? 0) ? colors.success : colors.textTertiary }]}>{row.rank ?? index + 1}</AppText>
              <View style={common.grow}>
                <SimTeamLink teamId={row.team_id} name={row.name} isYou={row.is_you} size={28} />
              </View>
            </View>
            <View style={common.row}>
              {simPlayoffStatusLabel(row.playoff_status) ? (
                <SimToneBadge label={simPlayoffStatusLabel(row.playoff_status)} tone={simPlayoffStatusTone(row.playoff_status)} />
              ) : null}
              <AppText style={common.bodyStrong}>{simFmtRecord(row)}</AppText>
            </View>
          </View>
          <View style={common.rowBetween}>
            <AppText style={common.small}>
              {simFmtPts(row.pf)} PF · {simFmtPts(row.pa)} PA
            </AppText>
            {row.streak ? <AppText style={[common.small, { color: simToneColor(simStreakTone(row.streak), colors), fontWeight: '700' }]}>{row.streak}</AppText> : null}
          </View>
        </AccentCard>
      ))}
    </View>
  );
}

function Scoreboard({ game, schedule, names }: { game: SimCtx['game']; schedule: NonNullable<SimLeagueResponse['schedule']>; names: Record<string, string> }) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const played = schedule.filter((w) => w.games.some((g) => g.home_pts != null));
  const [week, setWeek] = useState<number>(() => (played.length ? played[played.length - 1].week : Math.max(1, game.week)));
  const entry = schedule.find((w) => w.week === week);
  const label = entry?.kind === 'playoff' ? simPlayoffRoundLabel(week, game.settings) : `Week ${week}`;
  const youId = game.you?.team_id;
  return (
    <View style={common.stack}>
      <View style={common.rowBetween}>
        <Button size="sm" variant="secondary" label="Previous" disabled={week <= 1} onPress={() => setWeek((w) => w - 1)} />
        <AppText style={common.bodyStrong} accessibilityLiveRegion="polite">
          {label === `Week ${week}` ? label : `${label} · Week ${week}`}
        </AppText>
        <Button size="sm" variant="secondary" label="Next" disabled={week >= schedule.length} onPress={() => setWeek((w) => w + 1)} />
      </View>
      {!entry || entry.games.length === 0 ? (
        <EmptyState icon="calendar-outline" title="No games" subtitle="Nothing is scheduled this week." />
      ) : (
        entry.games.map((g: SimRecapScore) => {
          const mine = g.home === youId || g.away === youId;
          const mineTone = !mine || !g.winner ? 'accent' : g.winner === youId ? 'success' : 'danger';
          const rows = [
            [g.home, g.home_pts],
            [g.away, g.away_pts],
          ] as const;
          return (
            <AccentCard key={`${g.home}-${g.away}`} accent={mine ? simToneColor(mineTone, colors) : colors.borderStrong} compact>
              {rows.map(([id, pts]) => (
                <View key={id} style={[common.rowBetween, { opacity: g.winner && g.winner !== id ? 0.7 : 1 }]}>
                  <View style={common.grow}>
                    <SimTeamLink teamId={id} name={names[id] ?? 'Team'} isYou={id === youId} size={22} bold={g.winner === id} />
                  </View>
                  <AppText style={[g.winner === id ? common.bodyStrong : common.body, g.winner ? { color: g.winner === id ? colors.success : colors.danger } : null]}>{pts == null ? '-' : simFmtPts(pts)}</AppText>
                </View>
              ))}
            </AccentCard>
          );
        })
      )}
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
          { key: 'standings', label: 'Standings' },
          { key: 'scores', label: 'Scores' },
          { key: 'feed', label: 'Feed' },
          { key: 'teams', label: 'Teams' },
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
            (league.transactions ?? []).map((tx, i) => (
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
        </View>
      ) : null}
      {view === 'teams' ? (
        <View style={common.stack}>
          <SimSectionTitle glyph="team" title="Scouting report" caption="Power rank is roster strength right now. Tap a team to scout it." />
          {[...(league.teams ?? [])]
            .sort((a, b) => a.power_rank - b.power_rank)
            .map((team) => (
              <AccentCard key={team.team_id} accent={team.is_you ? colors.accent : colors.borderStrong} compact>
                <View style={common.rowBetween}>
                  <View style={[common.row, common.grow]}>
                    <AppText style={[common.bodyStrong, { color: team.power_rank <= 3 ? colors.success : colors.textTertiary }]}>#{team.power_rank}</AppText>
                    <SimTeamLink teamId={team.team_id} name={team.name} isYou={team.is_you} size={28} />
                  </View>
                  <ToneBadge label={team.persona.label} color={colors.accent} size="xs" />
                </View>
                <AppText style={common.small}>{team.persona.blurb}</AppText>
                {team.avg_age != null ? <AppText style={common.muted}>Average age {team.avg_age.toFixed(1)}</AppText> : null}
              </AccentCard>
            ))}
        </View>
      ) : null}
    </View>
  );
}
