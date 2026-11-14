import React, { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Animated, Easing, ScrollView, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import Button from './Button';
import StoryCarousel, { type StoryPage } from './StoryCarousel';
import { SimWeekRecapView } from './SimGameRecap';
import CircularProgressRing from './CircularProgressRing';
import { Confetti, CountUp, MotionIn } from './Motion';
import { SimPlayerChip, SimPlayerLine, SimToneBadge, createSimStyles, type SimCtx } from './SimGameParts';
import { SimTeamIdentity, SimTeamLogo } from './SimTeamIdentity';
import RecapCard from './RecapCard';
import { recapCardModel, recapRowsFromItems } from '../lib/recapCard';
import TrophyIcon from './TrophyIcon';
import { useThemeMode } from '../context/ThemeModeContext';
import { EASE, HERO_GLOW } from '../lib/motion';
import { simGradeOf } from '../lib/simGrade';
import { simFmtPts, simPlayoffRoundLabel, simTeamNameMap, type SimGamePlayer, type SimWeekRecap } from '../lib/simGame';
import { useReducedMotion } from '../lib/useMotion';
import { positionColor, spacing } from '../theme';
import {
  simLeagueHighlights,
  simNextWeekModel,
  simPositionTotals,
  simRecapInjuryModel,
  simMovementText,
  simRecapOutcome,
  simRecapPageKeys,
  simRecapPageTitle,
  simRecapStandingsModel,
  type SimStandingsRow,
  simRecapProj,
  simRecapResultModel,
  simRecapSeasonModel,
  simTopStarters,
  type SimRecapFacts,
  type SimRecapOutcome,
  type SimRecapPageKey,
} from '../lib/simRecapStory';

const KICKER: Record<SimRecapPageKey, string> = {
  result: 'Result',
  matchup: 'Matchup breakdown',
  injuries: 'Injuries and lineup',
  league: 'Around the league',
  standings: 'Standings',
  season: 'Season complete',
  next: 'Next week',
};

/** One-shot accent glow behind a hero: concentric translucent discs that fade in and rest (never loops); static under reduced motion. */
function HeroGlow({ color }: { color: string }) {
  const reduced = useReducedMotion();
  const t = useRef(new Animated.Value(reduced ? 1 : 0)).current;
  useEffect(() => {
    if (reduced) {
      t.setValue(1);
      return;
    }
    Animated.timing(t, { toValue: 1, duration: HERO_GLOW.ms, easing: Easing.bezier(...EASE.out), useNativeDriver: true }).start();
  }, [reduced, t]);
  return (
    <Animated.View pointerEvents="none" style={[styles.glow, { opacity: t.interpolate({ inputRange: [0, 1], outputRange: [0, HERO_GLOW.rest] }), transform: [{ scale: t.interpolate({ inputRange: [0, 1], outputRange: [0.8, 1] }) }] }]} testID="recap-glow">
      {[1, 0.74, 0.48].map((k, i) => (
        <View key={i} style={{ position: 'absolute', width: 300 * k, height: 300 * k, borderRadius: 150 * k, backgroundColor: color, opacity: 0.1 + i * 0.07 }} />
      ))}
    </Animated.View>
  );
}

/** The Grade stat, only when the player carries a letter grade: a chip with a label and no value is never rendered. */
const gradeStat = (player: SimGamePlayer | null | undefined) => {
  const grade = simGradeOf(player);
  return grade ? [{ key: 'ovr', label: 'Grade', value: '', grade }] : [];
};

function createStyles() {
  return StyleSheet.create({
    hero: { flex: 1, minHeight: 240, alignItems: 'center', justifyContent: 'center', gap: spacing.sm },
    glow: { position: 'absolute', width: 300, height: 300, alignItems: 'center', justifyContent: 'center' },
    versus: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, alignSelf: 'stretch' },
    fact: { borderRadius: 12, paddingHorizontal: 12, paddingVertical: 8, borderLeftWidth: 3 },
    standing: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6, paddingHorizontal: 8, borderRadius: 10, borderLeftWidth: 3, borderLeftColor: 'transparent' },
    cut: { flexDirection: 'row', alignItems: 'center', gap: 8, marginVertical: 2 },
    cutLine: { flex: 1, height: 0, borderTopWidth: 1, borderStyle: 'dashed' },
    chip: { flexDirection: 'row', alignItems: 'baseline', gap: 6, borderRadius: 999, borderWidth: 1, paddingHorizontal: 12, paddingVertical: 5 },
  });
}
const styles = createStyles();

export function recapFacts(recap: SimWeekRecap, ctx: SimCtx): SimRecapFacts {
  const g = ctx.game;
  const names = simTeamNameMap([...(recap.standings ?? []).map((r) => ({ team_id: r.team_id, name: r.name })), ...(g.you ? [{ team_id: g.you.team_id, name: g.you.name }] : [])]);
  const tw = g.this_week;
  return {
    youId: g.you?.team_id ?? null,
    names,
    lineupWarnings: g.pending?.lineup_warnings ?? 0,
    offers: g.pending?.inbox ?? 0,
    nextOpponent: tw?.opponent?.name ?? null,
    nextProjection: tw && !tw.bye ? { yours: tw.your_projection, theirs: tw.opponent_projection } : null,
    tradeDeadlineWeek: g.trade_deadline_week,
    playoffTeams: g.settings.playoff_teams,
    week: g.week,
  };
}

/** The weekly recap as a story: Result, Matchup, Injuries and lineup, Around the league, Next week. Twin of web-next/src/components/SimRecapStory.tsx. */
export default function SimWeekRecapStory({
  recap,
  index,
  total,
  ctx,
  onNext,
  onClose,
  onFixLineup,
}: {
  recap: SimWeekRecap;
  index: number;
  total: number;
  ctx: SimCtx;
  onNext: () => void;
  onClose: () => void;
  onFixLineup: () => void;
}) {
  const { colors, isDark } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [detail, setDetail] = useState(false);
  const [fullTable, setFullTable] = useState(false);
  const facts = useMemo(() => recapFacts(recap, ctx), [recap, ctx]);
  const keys = useMemo(() => simRecapPageKeys(recap, facts), [recap, facts]);
  const last = index + 1 >= total;
  const title = recap.kind === 'playoff' ? `${simPlayoffRoundLabel(recap.week, ctx.game.settings)} recap` : `Week ${recap.week} recap`;

  if (detail) return <SimWeekRecapView recap={recap} index={index} total={total} ctx={ctx} onNext={onNext} onClose={onClose} />;

  const finishLabel = !last ? 'Next round' : recap.season_complete ? (ctx.game.status === 'offseason' ? 'Go to the offseason' : ctx.game.settings.mode === 'dynasty' ? 'See your dynasty review' : 'See your final grade') : 'Back to your team';
  const finish = (
    <>
      <Button label={finishLabel} onPress={last ? onClose : onNext} />
      <Button label="Full details" variant="ghost" onPress={() => setDetail(true)} />
    </>
  );
  const result = simRecapResultModel(recap);
  const outcome = simRecapOutcome(recap, facts.youId);
  const game = recap.your_game;
  const youName = (facts.youId && facts.names[facts.youId]) || ctx.game.you?.name || 'You';
  const toneColor = (t: SimRecapOutcome['tone']) => colors[t];
  const tc = toneColor(outcome.tone);
  const gold = colors.premium;

  const HeroZone = ({ tone = colors.accent, glow = true, children }: { tone?: string; glow?: boolean; children: ReactNode }) => (
    <View style={styles.hero}>
      {glow ? <HeroGlow color={tone} /> : null}
      {children}
    </View>
  );
  const Hero = ({ value, caption, color }: { value: ReactNode; caption?: string; color?: string }) => (
    <View style={{ alignItems: 'center', gap: 4 }}>
      <AppText style={{ fontSize: 56, lineHeight: 62, fontWeight: '800', color: color ?? colors.textPrimary }}>{value}</AppText>
      {caption ? <AppText style={[common.bodyStrong, { textAlign: 'center', color: colors.textSecondary }]}>{caption}</AppText> : null}
    </View>
  );
  const Fact = ({ label, children, accent }: { label: string; children: ReactNode; accent?: string }) => (
    <View style={[common.rowBetween, styles.fact, { borderLeftColor: accent ?? colors.border, backgroundColor: colors.backgroundElevated ?? 'transparent' }]}>
      <AppText style={[common.muted, { fontWeight: '800', textTransform: 'uppercase' }]}>{label}</AppText>
      <AppText style={[common.bodyStrong, { flexShrink: 1, textAlign: 'right' }]}>{children}</AppText>
    </View>
  );
  const performer = (label: string, p: { name: string; pts: number; player: SimGamePlayer | null }, accent: string) =>
    p.player ? (
      <MotionIn key={label}>
        <AppText style={[common.muted, { fontWeight: '800', textTransform: 'uppercase', color: accent }]}>{label}</AppText>
        <SimPlayerLine player={p.player} stats={[{ key: 'pts', label: 'Pts', value: simFmtPts(p.pts), tone: label === 'Best performer' ? 'success' : undefined }, ...gradeStat(p.player)]} onOpen={ctx.openPlayer} />
      </MotionIn>
    ) : (
      <Fact key={label} label={label} accent={accent}>{`${p.name} · ${simFmtPts(p.pts)}`}</Fact>
    );
  const Team = ({ name }: { name: string }) => (
    <View style={{ flex: 1, minWidth: 0, alignItems: 'center' }}>
      <SimTeamIdentity name={name} size="hero" stacked bold={false} fontSize={13} />
    </View>
  );
  const standingsList = (rows: SimStandingsRow[], spots: number) => (
    <View accessibilityLabel="Standings">
      {rows.map((r, i) => {
        const moveColor = r.delta == null || r.delta === 0 ? colors.textTertiary : r.delta > 0 ? colors.success : colors.danger;
        const edge = r.status === 'out' ? 'transparent' : r.status === 'bubble' ? colors.warning : colors.success;
        return (
          <React.Fragment key={r.teamId}>
            <View style={[styles.standing, { borderLeftColor: edge, opacity: r.status === 'out' && !r.isYou ? 0.62 : 1 }, r.isYou && { backgroundColor: colors.accent + '24' }]} testID="recap-standing-row">
              <AppText style={[common.muted, { width: 24, textAlign: 'center', fontWeight: '800' }]}>{r.rank}</AppText>
              <View style={{ flex: 1, minWidth: 0 }}>
                <SimTeamIdentity name={r.name} size="row" isYou={r.isYou} bold={r.isYou} fontSize={14} />
              </View>
              {r.status === 'bubble' ? <SimToneBadge label="Bubble" tone="warning" /> : null}
              <View style={{ alignItems: 'flex-end' }}>
                <AppText style={{ fontSize: 13, fontWeight: '700', color: colors.textPrimary }}>{r.record}</AppText>
                <AppText style={[common.muted, { fontSize: 12 }]}>{`${simFmtPts(r.pf)} PF`}</AppText>
              </View>
              <AppText style={{ minWidth: 36, textAlign: 'right', fontSize: 13, fontWeight: '800', color: moveColor }}>{simMovementText(r.delta)}</AppText>
            </View>
            {spots > 0 && r.rank === spots && rows[i + 1] ? (
              <View style={styles.cut} accessibilityLabel="Playoff cut line">
                <View style={[styles.cutLine, { borderColor: colors.warning }]} />
                <AppText style={[common.muted, { color: colors.warning, fontWeight: '800', textTransform: 'uppercase', fontSize: 12 }]}>Playoff cut</AppText>
                <View style={[styles.cutLine, { borderColor: colors.warning }]} />
              </View>
            ) : null}
          </React.Fragment>
        );
      })}
    </View>
  );

  const pageFor = (key: SimRecapPageKey): ReactNode => {
    if (key === 'result') {
      return (
        <>
          <HeroZone tone={tc}>
            <Confetti wonTitle={outcome.celebrate} />
            {outcome.trophy ? (
              <MotionIn>
                <TrophyIcon size={outcome.celebrate ? 88 : 64} color={outcome.celebrate || outcome.variant === 'runner_up' ? gold : tc} label={outcome.headline} />
              </MotionIn>
            ) : null}
            <MotionIn>
              <AppText style={{ fontSize: 40, lineHeight: 44, fontWeight: '800', color: tc, textAlign: 'center' }} testID="recap-headline">{outcome.headline}</AppText>
            </MotionIn>
            {outcome.sub ? <AppText style={[common.bodyStrong, { textAlign: 'center', color: colors.textSecondary }]}>{outcome.sub}</AppText> : null}
            {result.kind === 'game' ? (
              <View style={styles.versus} accessible accessibilityLabel={`${youName} ${simFmtPts(result.yours)}, ${result.opponent} ${simFmtPts(result.theirs)}`}>
                <Team name={youName} />
                <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: 8 }}>
                  <CountUp value={result.yours} render={(t) => <AppText style={{ fontSize: 44, lineHeight: 50, fontWeight: '800', color: tc }}>{t}</AppText>} />
                  <AppText style={common.muted}>-</AppText>
                  <CountUp value={result.theirs} render={(t) => <AppText style={{ fontSize: 28, lineHeight: 34, fontWeight: '700', color: colors.textSecondary }}>{t}</AppText>} />
                </View>
                <Team name={result.opponent} />
              </View>
            ) : null}
            {result.kind === 'game' ? <AppText style={[common.bodyStrong, { textAlign: 'center' }]}>{result.margin}</AppText> : null}
          </HeroZone>
          {result.kind === 'game' ? (
            <View style={{ gap: 8 }}>
              {result.best ? performer('Best performer', result.best, colors.success) : null}
              {result.worst ? performer('Worst performer', result.worst, colors.danger) : null}
            </View>
          ) : null}
        </>
      );
    }
    if (key === 'matchup' && game) {
      const totals = simPositionTotals(game.starters);
      const top = simTopStarters(game.starters);
      return (
        <>
          <HeroZone>
            {game.efficiency != null ? (
              <CircularProgressRing percent={Math.round(game.efficiency * 100)} size={96} strokeWidth={9} color={colors.accent} valueLabel={`${Math.round(game.efficiency * 100)}%`} />
            ) : (
              <Hero value={simFmtPts(game.your_pts)} color={colors.accent} />
            )}
            <AppText style={[common.bodyStrong, { textAlign: 'center', color: colors.textSecondary }]}>{game.optimal_pts != null ? `Lineup efficiency. Best possible: ${simFmtPts(game.optimal_pts)}` : 'Your lineup'}</AppText>
            <View style={[common.wrapRow, { justifyContent: 'center' }]} accessibilityLabel="Points by position">
              {totals.map((t) => {
                const c = positionColor(t.pos, isDark);
                return (
                  <View key={t.pos} style={[styles.chip, { borderColor: `${c}66`, backgroundColor: `${c}24` }]}>
                    <AppText style={{ color: c, fontWeight: '800', fontSize: 12 }}>{t.pos}</AppText>
                    <AppText style={common.bodyStrong}>{simFmtPts(t.pts)}</AppText>
                  </View>
                );
              })}
            </View>
          </HeroZone>
          <View>
            {top.map((s, i) => (
              <MotionIn key={`${s.slot}-${i}`} index={i} count={top.length}>
                <SimPlayerLine
                  player={s.player!}
                  stats={[
                    { key: 'pts', label: 'Pts', value: simFmtPts(s.pts), tone: simRecapProj(s) != null && s.pts >= simRecapProj(s)! ? 'success' : undefined },
                    { key: 'proj', label: 'Proj', value: simFmtPts(simRecapProj(s)) },
                    ...gradeStat(s.player),
                  ]}
                  onOpen={ctx.openPlayer}
                />
              </MotionIn>
            ))}
          </View>
        </>
      );
    }
    if (key === 'injuries') {
      const m = simRecapInjuryModel(recap);
      const hero = m.yours > 0 ? `${m.yours}` : m.items.length > 0 ? `${m.items.length} hurt` : `${facts.lineupWarnings}`;
      const bad = m.yours > 0 || facts.lineupWarnings > 0;
      return (
        <>
          <HeroZone tone={bad ? colors.danger : colors.accent}>
            <Hero value={hero} caption={m.yours > 0 ? 'of your players got hurt' : m.items.length > 0 ? 'injuries around the league' : 'lineup issues to fix'} color={bad ? colors.danger : undefined} />
          </HeroZone>
          <View style={{ gap: 8 }}>
            {m.items.map((inj, i) => (
              <MotionIn key={i} index={i} count={m.items.length}>
                {/* ONE marker per player: the chip says OUT, the trailing text only how long. */}
                <View style={[common.rowBetween, styles.fact, { borderLeftColor: inj.is_yours ? colors.danger : colors.border, backgroundColor: colors.backgroundElevated ?? 'transparent' }]}>
                  <View style={common.grow}>
                    <SimPlayerChip player={{ ...inj.player, status: 'out', out_weeks: inj.weeks }} onOpen={ctx.openPlayer} />
                  </View>
                  <AppText style={[common.bodyStrong, { color: inj.is_yours ? colors.danger : colors.textSecondary }]}>{inj.detail}</AppText>
                </View>
              </MotionIn>
            ))}
          </View>
          {m.zeroStarters.length > 0 ? <AppText style={[common.body, { textAlign: 'center', color: colors.warning }]}>{`${m.zeroStarters.map((z) => `${z.name} (${z.flag})`).slice(0, 3).join(', ')} scored 0.`}</AppText> : null}
          {facts.lineupWarnings > 0 ? <AppText style={[common.bodyStrong, { textAlign: 'center', color: colors.warning }]}>{`${facts.lineupWarnings} lineup issue${facts.lineupWarnings === 1 ? '' : 's'} for next week.`}</AppText> : null}
        </>
      );
    }
    if (key === 'league') {
      const h = simLeagueHighlights(recap, facts.names);
      return (
        <>
          <HeroZone tone={colors.success}>
            <AppText style={[common.muted, { fontWeight: '800', textTransform: 'uppercase' }]}>Top score of the week</AppText>
            {h.hero?.value ? <CountUp value={Number(h.hero.value)} render={(t) => <Hero value={t} caption={h.hero?.who ? `Top score: ${h.hero.who}` : undefined} color={colors.success} />} /> : null}
            {h.hero?.who ? <SimTeamLogo name={h.hero.who} size="card" label /> : null}
          </HeroZone>
          <RecapCard model={recapCardModel({ kicker: 'Around the league', rows: recapRowsFromItems(h.items.map((it) => ({ ...it, tone: it.key === 'closest' ? ('warning' as const) : it.key === 'blowout' ? ('danger' as const) : undefined }))) })} />
        </>
      );
    }
    if (key === 'standings') {
      const m = simRecapStandingsModel(recap, facts);
      const you = m.you;
      const moveColor = !you || you.delta == null || you.delta === 0 ? colors.textTertiary : you.delta > 0 ? colors.success : colors.danger;
      if (fullTable) {
        return (
          <>
            <ScrollView style={{ flex: 1 }} showsVerticalScrollIndicator={false}>{standingsList(m.rows, m.spots)}</ScrollView>
            <Button label="Back to summary" variant="secondary" onPress={() => setFullTable(false)} />
          </>
        );
      }
      return (
        <>
          <HeroZone tone={you && you.seed != null ? colors.success : colors.accent}>
            <Hero value={you ? you.rank : ''} caption={m.caption || undefined} color={you && you.seed != null ? colors.success : undefined} />
            {you && you.delta != null ? <AppText style={{ fontSize: 24, fontWeight: '800', color: moveColor }} testID="standings-move">{simMovementText(you.delta)}</AppText> : null}
          </HeroZone>
          {standingsList(m.compact, m.spots)}
          {m.rows.length > m.compact.length ? <Button label="Full standings" variant="secondary" onPress={() => setFullTable(true)} /> : null}
        </>
      );
    }
    if (key === 'season') {
      const m = simRecapSeasonModel(recap, facts);
      return (
        <>
          <HeroZone tone={m.youChampion || outcome.variant === 'runner_up' ? gold : colors.accent}>
            <MotionIn>
              <TrophyIcon size={72} color={gold} />
            </MotionIn>
            <AppText style={[common.muted, { fontWeight: '800', textTransform: 'uppercase' }]}>{m.youChampion ? 'Your finish' : 'Champion'}</AppText>
            <AppText style={{ fontSize: 36, lineHeight: 42, fontWeight: '800', color: m.youChampion ? gold : colors.textPrimary, textAlign: 'center' }} testID="season-headline">{m.youChampion ? 'Champions' : m.championName ?? 'Season complete'}</AppText>
            {m.championName && !m.youChampion ? <SimTeamLogo name={m.championName} size="card" label /> : null}
            <AppText style={[common.bodyStrong, { textAlign: 'center', color: colors.textSecondary }]}>{m.youChampion ? `${youName} won it all.` : `You finished ${m.finish}.`}</AppText>
          </HeroZone>
          <RecapCard model={recapCardModel({ kicker: 'Season complete', badge: m.finish, rows: recapRowsFromItems(m.items) })} />
        </>
      );
    }
    if (key === 'next') {
      const n = simNextWeekModel(recap, facts);
      return (
        <>
          <HeroZone>
            {n.opponent ? <SimTeamLogo name={n.opponent} size="hero" label /> : null}
            <Hero value={n.opponent ?? `Week ${n.week ?? ''}`} caption={n.week != null ? `Week ${n.week}${n.opponent ? ' opponent' : ''}` : undefined} />
            {n.yours != null && n.theirs != null ? <AppText style={[common.bodyStrong, { textAlign: 'center', fontSize: 18 }]}>{`${simFmtPts(n.yours)} proj vs ${simFmtPts(n.theirs)}`}</AppText> : null}
            {n.edge ? <AppText style={[common.bodyStrong, { textAlign: 'center', color: colors.textSecondary }]}>{n.edge}</AppText> : null}
          </HeroZone>
          <RecapCard model={recapCardModel({ kicker: `Week ${n.week ?? ''} plan`.trim(), rows: recapRowsFromItems(n.notes.map((note) => ({ ...note, tone: note.label === 'Lineup' ? ('warning' as const) : undefined }))) })} />
        </>
      );
    }
    return null;
  };

  const pages: StoryPage[] = keys.map((key, i) => ({
    key,
    label: `${title}${total > 1 ? ` · ${index + 1} of ${total}` : ''} · ${KICKER[key]}`,
    header: simRecapPageTitle(key, recap, { roundLabel: recap.kind === 'playoff' ? simPlayoffRoundLabel(recap.week, ctx.game.settings) : null, youId: facts.youId }),
    content: pageFor(key),
    footer:
      i === keys.length - 1 ? (
        <>
          {key === 'injuries' ? <Button label="Fix lineup" variant="secondary" onPress={onFixLineup} /> : null}
          {finish}
        </>
      ) : key === 'injuries' ? (
        <Button label="Fix lineup" variant="secondary" onPress={onFixLineup} />
      ) : undefined,
  }));
  return <StoryCarousel key={`${recap.week}-${recap.kind}`} title={title} pages={pages} onClose={last ? onClose : onNext} testID="week-recap-story" />;
}
