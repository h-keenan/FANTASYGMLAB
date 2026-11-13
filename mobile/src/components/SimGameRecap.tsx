import React, { useEffect, useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import ErrorState from './ErrorState';
import { Confetti, CountUp } from './Motion';
import PositionBadge from './PositionBadge';
import SectionHeading from './SectionHeading';
import SegmentedTabBar from './SegmentedTabBar';
import { SkeletonCard } from './SkeletonBlock';
import { SimDynastyResult } from './SimGameDynasty';
import { SimStandingsList } from './SimGameLeague';
import { SimPlayerChip, SimPlayerLine, SimPopIn, SimStat, SimToneBadge, createSimStyles, simToneColor, type SimCtx } from './SimGameParts';
import { SeasonReviewSections, ReviewDeltaText, ReviewGlyphChip, REVIEW_ICON } from './SeasonReviewSections';
import SimReviewShareModal from './SimReviewShareModal';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import {
  simFmtPts,
  normalizeSimResult,
  simGameReasonMessage,
  simSlotRepeatsPosition,
  simGradeTone,
  simIsDynastyResult,
  simPlayoffOutcomeTone,
  simPlayoffResultLabel,
  simPlayoffRoundLabel,
  simResultLabel,
  simResultTone,
  simSlotLabels,
  simTeamNameMap,
  type SimGameResult,
  type SimWeekRecap,
} from '../lib/simGame';
import { buildReviewShareModel, buildSimReviewSections } from '../lib/simReview';
import { SIM_REVIEW_COLLAPSED_ON_PHONE, SIM_REVIEW_VIEWS, simReviewViewFor, type SimReviewView } from '../lib/simLayout';
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
              <CountUp value={game.your_pts} render={(text) => <AppText style={[styles.scoreYou, { color: toneColor }]}>{text}</AppText>} />
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
        <Confetti wonTitle={recap.season_complete && recap.champion != null && recap.champion === youId} />
        {recap.season_complete ? (
          <View style={common.row}>
            <ReviewGlyphChip glyph="trophy" tone="success" size={24} />
            <AppText style={[common.bodyStrong, common.grow, { color: colors.success }]} accessibilityLiveRegion="polite">
              The season is over{recap.champion ? ` and ${names[recap.champion] ?? 'the champion'} won it all` : ''}.
            </AppText>
          </View>
        ) : null}
      </AccentCard>

      {game ? (
        <View>
          <SectionHeading title="Your starters" icon={REVIEW_ICON.lineup} />
          {game.starters.map((s, i) => (
            <View key={`${s.slot}-${i}`} style={common.row}>
              <View style={common.slotCol}>
                <PositionBadge position={s.slot} label={slotLabels[i]} />
              </View>
              <View style={common.grow}>
                {s.player ? (
                  <SimPlayerLine
                    player={s.player}
                    hidePosition={simSlotRepeatsPosition(s.slot, s.player.pos)}
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
                <View style={common.row}>
                  <ReviewGlyphChip glyph="boom" tone="success" size={22} />
                  <AppText style={[common.small, { color: colors.success, fontWeight: '700' }]}>Week MVP</AppText>
                </View>
                <SimPlayerChip player={recap.mvp.player} />
                <ReviewDeltaText text={`${simFmtPts(recap.mvp.pts)} pts`} tone="success" small />
              </AccentCard>
            </View>
          ) : null}
          {recap.bust ? (
            <View style={common.grow}>
              <AccentCard accent={colors.warning} compact>
                <View style={common.row}>
                  <ReviewGlyphChip glyph="bust" tone="warning" size={22} />
                  <AppText style={[common.small, { color: colors.warning, fontWeight: '700' }]}>Biggest bust</AppText>
                </View>
                <SimPlayerChip player={recap.bust.player} />
                <ReviewDeltaText text={`${simFmtPts(recap.bust.pts)} pts`} tone="warning" small />
              </AccentCard>
            </View>
          ) : null}
        </View>
      ) : null}

      {(recap.injuries ?? []).length > 0 ? (
        <View style={common.stack}>
          <SectionHeading title="Injuries" icon={REVIEW_ICON.injury} />
          {recap.injuries!.map((inj, i) => (
            <AccentCard key={i} accent={inj.is_yours ? colors.danger : colors.borderStrong} compact>
              <SimPlayerChip player={{ ...inj.player, status: 'out', out_weeks: inj.weeks }} />
              <View style={common.row}>
                <AppText style={[common.small, { color: colors.danger, fontWeight: '600' }]}>
                  Out {inj.weeks} week{inj.weeks === 1 ? '' : 's'}
                </AppText>
                {inj.is_yours ? <SimToneBadge label="Your team" tone="danger" /> : null}
              </View>
            </AccentCard>
          ))}
        </View>
      ) : null}

      {myWaivers.length > 0 ? (
        <View style={common.stack}>
          <SectionHeading title="Your waiver claims" icon={REVIEW_ICON.waiver} />
          {myWaivers.map((w, i) => (
            <AccentCard key={i} accent={w.ok ? colors.success : colors.danger} compact>
              <SimPlayerChip player={w.add} />
              <View style={common.wrapRow}>
                <SimToneBadge label={w.ok ? 'Won' : 'Lost'} tone={w.ok ? 'success' : 'danger'} />
                {w.drop ? <AppText style={[common.small, { color: colors.danger, fontWeight: '600' }]}>dropping {w.drop.name}</AppText> : null}
                {!w.ok && w.reason ? <AppText style={common.muted}>({w.reason.replace(/_/g, ' ')})</AppText> : null}
              </View>
            </AccentCard>
          ))}
        </View>
      ) : null}

      {(recap.standings ?? []).length > 0 ? (
        <View style={common.stack}>
          <SectionHeading title="Standings" icon={REVIEW_ICON.rank} />
          <SimStandingsList rows={recap.standings!} playoffTeams={ctx.game.settings.playoff_teams} />
        </View>
      ) : null}

      {!last ? <Button label="Next round" onPress={onNext} /> : <Button label={recap.season_complete ? (ctx.game.status === 'offseason' ? 'Go to the offseason' : ctx.game.settings.mode === 'dynasty' ? 'See your dynasty review' : 'See your final grade') : 'Back to your team'} onPress={onClose} />}
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
  const [sharing, setSharing] = useState(false);
  const [tab, setTab] = useState<SimReviewView>('overview');

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
  // A dynasty result has no grade and no review (both null): the summary stands in their place.
  const dynasty = simIsDynastyResult(result);
  const sections = dynasty ? [] : buildSimReviewSections({ decisions: view.decisions, review: result.review, components: result.grade?.components });
  const tone = simGradeTone(view.letter);
  const toneColor = simToneColor(tone, colors);
  const mine = view.mine;
  const youWon = Boolean(view.championId && view.championId === mine?.team_id);
  const record = mine ? `${mine.wins}-${mine.losses}${mine.ties ? `-${mine.ties}` : ''}` : '';
  const shareModel = buildReviewShareModel({
    letter: view.letter,
    gradeTone: tone,
    teamName: mine?.name ?? '',
    playoffResult: mine?.playoff_result,
    isChampion: youWon,
    record,
    finish: mine ? view.standings.findIndex((row) => row.team_id === mine.team_id) + 1 || null : null,
    summary: result.grade?.summary,
    championName: view.championName,
    sections: sections,
  });
  return (
    <View style={common.stack} testID="final-result">
      {dynasty ? <SimDynastyResult summary={result.dynasty} onNewGame={onNewGame} onHub={onHub} /> : (
      <AccentCard accent={toneColor} glow>
        <AppText style={styles.kicker}>Season in review</AppText>
        <SimPopIn style={common.row}>
          <AppText style={[styles.grade, { color: toneColor }]} accessibilityLabel={`Grade ${view.letter}`}>
            {view.letter || '-'}
          </AppText>
          <View style={common.grow}>
            <View style={common.wrapRow}>
              {record ? <AppText style={common.title}>{record}</AppText> : null}
              {mine ? <SimToneBadge label={simPlayoffResultLabel(mine.playoff_result)} tone={simPlayoffOutcomeTone(mine.playoff_result)} /> : null}
            </View>
            {view.championName ? (
              <View style={common.row}>
                <Ionicons name="trophy-outline" size={14} color={youWon ? colors.success : colors.textTertiary} />
                <AppText style={common.muted}>
                  Champion: {view.championName}
                  {youWon ? ' (you)' : ''}
                </AppText>
              </View>
            ) : null}
          </View>
        </SimPopIn>
        {view.summaryText ? <AppText style={common.body}>{view.summaryText}</AppText> : null}
        <View style={common.wrapRow}>
          <Button label="Play again" onPress={onNewGame} />
          <Button label="All games" variant="secondary" onPress={onHub} />
          <Button label="Share your season" variant="secondary" onPress={() => setSharing(true)} />
        </View>
      </AccentCard>
      )}

      {dynasty ? null : <SegmentedTabBar options={SIM_REVIEW_VIEWS.map((v) => ({ key: v.value, label: v.label, glyph: v.glyph }))} active={tab} onChange={setTab} />}
      {dynasty || tab === 'standings' ? (
        <View style={common.stack} accessibilityLabel="Final standings">
          <SectionHeading title="Final standings" icon="analytics-outline" />
          {view.standings.map((row, i) => (
            <AccentCard key={row.team_id} accent={row.is_you ? colors.accent : simToneColor(simPlayoffOutcomeTone(row.playoff_result), colors)} compact>
              <View style={common.row}>
                <AppText style={[common.body, common.grow]} numberOfLines={1}>
                  {i + 1}. {row.name}
                  {row.is_you ? ' (you)' : ''}
                </AppText>
                <SimToneBadge label={simPlayoffResultLabel(row.playoff_result)} tone={simPlayoffOutcomeTone(row.playoff_result)} />
                <AppText style={[common.bodyStrong, { width: 44, textAlign: 'right' }]}>
                  {row.wins}-{row.losses}
                  {row.ties ? `-${row.ties}` : ''}
                </AppText>
              </View>
            </AccentCard>
          ))}
        </View>
      ) : (
        <SeasonReviewSections sections={sections} only={sections.filter((sec) => simReviewViewFor(sec.id) === tab).map((sec) => sec.id)} closed={SIM_REVIEW_COLLAPSED_ON_PHONE} />
      )}
      <AppText style={common.muted}>
        A game, not a forecast. Season {game.settings.regular_weeks} weeks plus playoffs against AI managers; nothing here touches your real leagues.
      </AppText>
      {dynasty ? null : <SimReviewShareModal visible={sharing} onClose={() => setSharing(false)} model={shareModel} sections={sections} />}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    kicker: { fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
    score: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'center', gap: spacing.md },
    scoreYou: { fontSize: 44, fontWeight: '800' },
    scoreOpp: { fontSize: 32, fontWeight: '700', color: colors.textSecondary },
    grade: { fontSize: 52, lineHeight: 58, fontWeight: '800' },
  });
}
