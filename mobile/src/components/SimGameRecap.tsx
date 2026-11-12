import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import ErrorState from './ErrorState';
import PositionBadge from './PositionBadge';
import SectionHeading from './SectionHeading';
import { SkeletonCard } from './SkeletonBlock';
import { SimStandingsList } from './SimGameLeague';
import { SimPlayerLine, SimPopIn, SimStat, SimToneBadge, createSimStyles, simToneColor, type SimCtx } from './SimGameParts';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import {
  simFmtPts,
  normalizeSimResult,
  simGameReasonMessage,
  simGradeTone,
  simPlayoffResultLabel,
  simPlayoffRoundLabel,
  simResultLabel,
  simResultTone,
  simSlotLabels,
  simTeamNameMap,
  type SimGameResult,
  type SimWeekRecap,
} from '../lib/simGame';
import { spacing, type ThemeColors } from '../theme';

/** One week's recap: the score lands first, then your starters, the league and what changed. */
export function SimWeekRecapView({
  recap,
  index,
  total,
  ctx,
  onNext,
  onClose,
}: {
  recap: SimWeekRecap;
  index: number;
  total: number;
  ctx: SimCtx;
  onNext: () => void;
  onClose: () => void;
}) {
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  const names = simTeamNameMap(ctx.game.you ? [{ team_id: ctx.game.you.team_id, name: ctx.game.you.name }] : []);
  const game = recap.your_game;
  const youId = ctx.game.you?.team_id;
  const title = recap.kind === 'playoff' ? `${simPlayoffRoundLabel(recap.week, ctx.game.settings)} recap` : `Week ${recap.week} recap`;
  const slotLabels = game ? simSlotLabels(game.starters.map((s) => ({ slot: s.slot }))) : [];
  const last = index + 1 >= total;
  const tone = simResultTone(game?.result);
  const toneColor = simToneColor(tone, colors);
  const myWaivers = (recap.waivers ?? []).filter((w) => w.team_id === youId);
  return (
    <View style={common.stack} testID="week-recap">
      <AccentCard accent={toneColor} glow={game?.result === 'win'}>
        <AppText style={styles.kicker}>
          {title}
          {total > 1 ? ` · ${index + 1} of ${total}` : ''}
        </AppText>
        {game ? (
          <SimPopIn key={recap.week} style={common.stack}>
            <View style={common.rowBetween}>
              <SimToneBadge label={simResultLabel(game.result)} tone={tone} />
              <AppText style={common.muted}>vs {game.opponent_name}</AppText>
            </View>
            <View style={styles.score} accessible accessibilityLabel={`You ${simFmtPts(game.your_pts)}, ${game.opponent_name} ${simFmtPts(game.opp_pts)}`}>
              <AppText style={[styles.scoreYou, { color: toneColor }]}>{simFmtPts(game.your_pts)}</AppText>
              <AppText style={common.muted}>to</AppText>
              <AppText style={styles.scoreOpp}>{simFmtPts(game.opp_pts)}</AppText>
            </View>
            {game.optimal_pts != null ? (
              <AppText style={[common.muted, common.center]}>
                Your best possible lineup scored {simFmtPts(game.optimal_pts)}
                {game.efficiency != null ? ` (${Math.round(game.efficiency * 100)}% efficiency)` : ''}.
              </AppText>
            ) : null}
          </SimPopIn>
        ) : (
          <AppText style={common.bodyStrong}>You had a bye this week.</AppText>
        )}
        {recap.season_complete ? (
          <AppText style={common.bodyStrong} accessibilityLiveRegion="polite">
            The season is over{recap.champion ? ` and ${names[recap.champion] ?? 'the champion'} won it all` : ''}.
          </AppText>
        ) : null}
      </AccentCard>

      {game ? (
        <View>
          <SectionHeading title="Your starters" />
          {game.starters.map((s, i) => (
            <View key={`${s.slot}-${i}`} style={common.row}>
              <View style={common.slotCol}>
                <PositionBadge position={s.slot} label={slotLabels[i]} />
              </View>
              <View style={common.grow}>
                {s.player ? (
                  <SimPlayerLine
                    player={s.player}
                    trailing={
                      <>
                        {s.flag ? <SimToneBadge label={s.flag === 'bye' ? 'Bye' : 'Out'} tone={s.flag === 'bye' ? 'warning' : 'danger'} /> : null}
                        <SimStat label="Pts" value={simFmtPts(s.pts)} tone={s.pts >= s.player.projection ? 'success' : 'muted'} />
                      </>
                    }
                  />
                ) : (
                  <AppText style={[common.small, { color: colors.warning, paddingVertical: spacing.sm }]}>Empty slot (0 points)</AppText>
                )}
              </View>
            </View>
          ))}
        </View>
      ) : null}

      {recap.mvp || recap.bust ? (
        <View style={common.row}>
          {recap.mvp ? (
            <View style={common.grow}>
              <AccentCard accent={colors.success} compact>
                <AppText style={common.muted}>Week MVP</AppText>
                <AppText style={common.bodyStrong}>{recap.mvp.player.name}</AppText>
                <AppText style={common.small}>{simFmtPts(recap.mvp.pts)} pts</AppText>
              </AccentCard>
            </View>
          ) : null}
          {recap.bust ? (
            <View style={common.grow}>
              <AccentCard accent={colors.warning} compact>
                <AppText style={common.muted}>Biggest bust</AppText>
                <AppText style={common.bodyStrong}>{recap.bust.player.name}</AppText>
                <AppText style={common.small}>{simFmtPts(recap.bust.pts)} pts</AppText>
              </AccentCard>
            </View>
          ) : null}
        </View>
      ) : null}

      {(recap.injuries ?? []).length > 0 ? (
        <View style={common.stack}>
          <SectionHeading title="Injuries" />
          {recap.injuries!.map((inj, i) => (
            <AccentCard key={i} accent={inj.is_yours ? colors.danger : colors.borderStrong} compact>
              <AppText style={common.body}>
                <AppText style={common.bodyStrong}>{inj.player.name}</AppText> is out {inj.weeks} week{inj.weeks === 1 ? '' : 's'}
                {inj.is_yours ? ' (your team)' : ''}.
              </AppText>
            </AccentCard>
          ))}
        </View>
      ) : null}

      {myWaivers.length > 0 ? (
        <View style={common.stack}>
          <SectionHeading title="Your waiver claims" />
          {myWaivers.map((w, i) => (
            <AccentCard key={i} accent={w.ok ? colors.success : colors.danger} compact>
              <AppText style={common.body}>
                {w.ok ? 'Won' : 'Lost'} <AppText style={common.bodyStrong}>{w.add.name}</AppText>
                {!w.ok && w.reason ? <AppText style={common.muted}> ({w.reason.replace(/_/g, ' ')})</AppText> : null}
              </AppText>
            </AccentCard>
          ))}
        </View>
      ) : null}

      {(recap.standings ?? []).length > 0 ? (
        <View style={common.stack}>
          <SectionHeading title="Standings" />
          <SimStandingsList rows={recap.standings!} playoffTeams={ctx.game.settings.playoff_teams} />
        </View>
      ) : null}

      {!last ? <Button label="Next round" onPress={onNext} /> : <Button label={recap.season_complete ? 'See your final grade' : 'Back to your team'} onPress={onClose} />}
    </View>
  );
}

/** Final screen: champion, record, grade and the decisions that mattered. */
export function SimFinalView({ ctx, onNewGame, onHub }: { ctx: SimCtx; onNewGame: () => void; onHub: () => void }) {
  const { gameId, game } = ctx;
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [result, setResult] = useState<SimGameResult | null>(null);
  const [failed, setFailed] = useState(false);
  const [failMessage, setFailMessage] = useState('');
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let cancelled = false;
    api
      .getSimGameResult(gameId)
      .then((body) => {
        if (cancelled) return;
        if (body.result) setResult(body.result);
        else {
          setFailMessage(simGameReasonMessage(body.reason, body));
          setFailed(true);
        }
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [gameId, attempt]);

  if (failed) {
    return (
      <ErrorState
        title="Your final result did not load"
        message={failMessage || 'Your season is saved. Try again in a moment.'}
        onRetry={() => {
          setFailed(false);
          setFailMessage('');
          setAttempt((n) => n + 1);
        }}
      />
    );
  }
  if (!result) {
    return (
      <View style={common.stack}>
        <SkeletonCard rows={2} />
        <SkeletonCard rows={4} />
      </View>
    );
  }

  const view = normalizeSimResult(result);
  const tone = simGradeTone(view.letter);
  const toneColor = simToneColor(tone, colors);
  const mine = view.mine;
  return (
    <View style={common.stack} testID="final-result">
      <AccentCard accent={toneColor} glow>
        <AppText style={styles.kicker}>Season complete</AppText>
        <SimPopIn style={common.row}>
          <AppText style={[styles.grade, { color: toneColor }]} accessibilityLabel={`Grade ${view.letter}`}>
            {view.letter || '-'}
          </AppText>
          <View style={common.grow}>
            <AppText style={common.bodyStrong}>{mine ? `${mine.wins}-${mine.losses}${mine.ties ? `-${mine.ties}` : ''} · ${simPlayoffResultLabel(mine.playoff_result)}` : ''}</AppText>
            {view.championName ? (
              <AppText style={common.muted}>
                Champion: {view.championName}
                {view.championId && view.championId === mine?.team_id ? ' (you)' : ''}
              </AppText>
            ) : null}
          </View>
        </SimPopIn>
        {view.summaryText ? <AppText style={common.body}>{view.summaryText}</AppText> : null}
        <View style={common.wrapRow}>
          <Button label="Play again" onPress={onNewGame} />
          <Button label="All games" variant="secondary" onPress={onHub} />
        </View>
      </AccentCard>

      {view.decisions.length > 0 ? (
        <View style={common.stack}>
          <SectionHeading title="Decisions that mattered" caption="The moves that moved your season most, from replaying it without them." />
          {view.decisions.map((d, i) => (
            <AccentCard key={i} accent={colors.accent} compact>
              {d.kind ? <ToneBadge label={String(d.kind).replace(/_/g, ' ')} color={colors.accent} size="xs" /> : null}
              {d.title ? <AppText style={common.bodyStrong}>{String(d.title)}</AppText> : null}
              {d.detail ? <AppText style={common.small}>{String(d.detail)}</AppText> : null}
            </AccentCard>
          ))}
        </View>
      ) : null}

      <View style={common.stack}>
        <SectionHeading title="Final standings" />
        {view.standings.map((row, i) => (
          <AccentCard key={row.team_id} accent={row.is_you ? colors.accent : colors.borderStrong} compact>
            <View style={common.rowBetween}>
              <AppText style={[common.body, common.grow]}>
                {i + 1}. {row.name}
                {row.is_you ? ' (you)' : ''}
              </AppText>
              <AppText style={common.bodyStrong}>
                {row.wins}-{row.losses}
                {row.ties ? `-${row.ties}` : ''}
              </AppText>
            </View>
            <AppText style={common.small}>
              {simPlayoffResultLabel(row.playoff_result)} · {simFmtPts(row.pf)} PF
            </AppText>
          </AccentCard>
        ))}
      </View>
      <AppText style={common.muted}>
        A game, not a forecast. Season {game.settings.regular_weeks} weeks plus playoffs against AI managers; nothing here touches your real leagues.
      </AppText>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    kicker: { fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
    score: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'center', gap: spacing.md },
    scoreYou: { fontSize: 44, fontWeight: '800' },
    scoreOpp: { fontSize: 32, fontWeight: '700', color: colors.textSecondary },
    grade: { fontSize: 64, lineHeight: 70, fontWeight: '800' },
  });
}
