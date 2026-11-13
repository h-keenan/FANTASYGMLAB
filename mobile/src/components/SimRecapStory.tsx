import React, { useMemo, useState, type ReactNode } from 'react';
import { View } from 'react-native';

import AppText from './AppText';
import Button from './Button';
import StoryCarousel, { type StoryPage } from './StoryCarousel';
import { SimWeekRecapView } from './SimGameRecap';
import { SimPlayerChip, SimPlayerLine, SimToneBadge, createSimStyles, simToneColor, type SimCtx } from './SimGameParts';
import { useThemeMode } from '../context/ThemeModeContext';
import { simListStats } from '../lib/simDraft';
import { simFmtPts, simPlayoffRoundLabel, simResultLabel, simResultTone, simTeamNameMap, type SimWeekRecap } from '../lib/simGame';
import {
  simLeagueHighlights,
  simNextWeekModel,
  simPositionTotals,
  simRecapInjuryModel,
  simRecapPageKeys,
  simRecapResultModel,
  simTopStarters,
  type SimRecapFacts,
  type SimRecapPageKey,
} from '../lib/simRecapStory';

const KICKER: Record<SimRecapPageKey, string> = {
  result: 'Result',
  matchup: 'Matchup breakdown',
  injuries: 'Injuries and lineup',
  league: 'Around the league',
  next: 'Next week',
};

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
  const { colors } = useThemeMode();
  const common = useMemo(() => createSimStyles(colors), [colors]);
  const [detail, setDetail] = useState(false);
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
  const game = recap.your_game;
  const tone = simResultTone(game?.result);

  const Hero = ({ value, caption, color }: { value: ReactNode; caption?: string; color?: string }) => (
    <View style={{ alignItems: 'center', gap: 4 }}>
      <AppText style={{ fontSize: 48, lineHeight: 54, fontWeight: '800', color: color ?? colors.textPrimary }}>{value}</AppText>
      {caption ? <AppText style={[common.bodyStrong, { textAlign: 'center', color: colors.textSecondary }]}>{caption}</AppText> : null}
    </View>
  );
  const Fact = ({ label, children }: { label: string; children: ReactNode }) => (
    <View style={[common.rowBetween, { backgroundColor: colors.backgroundElevated ?? 'transparent', borderRadius: 12, paddingHorizontal: 12, paddingVertical: 8 }]}>
      <AppText style={[common.muted, { fontWeight: '800', textTransform: 'uppercase' }]}>{label}</AppText>
      <AppText style={[common.bodyStrong, { flexShrink: 1, textAlign: 'right' }]}>{children}</AppText>
    </View>
  );

  const pageFor = (key: SimRecapPageKey): ReactNode => {
    if (key === 'result') {
      return result.kind === 'bye' ? (
        <Hero value="Bye" caption="You had a bye this week." />
      ) : (
        <>
          <View style={[common.row, { justifyContent: 'center' }]}>
            <SimToneBadge label={simResultLabel(game?.result)} tone={tone} />
            <AppText style={common.muted}>{`vs ${result.opponent}`}</AppText>
          </View>
          <View style={{ flexDirection: 'row', alignItems: 'baseline', justifyContent: 'center', gap: 12 }} accessibilityLabel={`You ${simFmtPts(result.yours)}, ${result.opponent} ${simFmtPts(result.theirs)}`}>
            <AppText style={{ fontSize: 56, lineHeight: 62, fontWeight: '800', color: simToneColor(tone, colors) }}>{simFmtPts(result.yours)}</AppText>
            <AppText style={common.muted}>to</AppText>
            <AppText style={{ fontSize: 34, lineHeight: 40, fontWeight: '700', color: colors.textSecondary }}>{simFmtPts(result.theirs)}</AppText>
          </View>
          <AppText style={[common.bodyStrong, { textAlign: 'center' }]}>{result.margin}</AppText>
          {result.best ? <Fact label="Best performer">{`${result.best.name} · ${simFmtPts(result.best.pts)}`}</Fact> : null}
          {result.worst ? <Fact label="Worst performer">{`${result.worst.name} · ${simFmtPts(result.worst.pts)}`}</Fact> : null}
        </>
      );
    }
    if (key === 'matchup' && game) {
      const totals = simPositionTotals(game.starters);
      return (
        <>
          <Hero value={game.efficiency != null ? `${Math.round(game.efficiency * 100)}%` : simFmtPts(game.your_pts)} caption={game.optimal_pts != null ? `Lineup efficiency. Best possible: ${simFmtPts(game.optimal_pts)}` : 'Your lineup'} color={colors.accent} />
          <View style={[common.wrapRow, { justifyContent: 'center' }]} accessibilityLabel="Points by position">
            {totals.map((t) => (
              <View key={t.pos} style={{ flexDirection: 'row', gap: 4, borderRadius: 999, paddingHorizontal: 10, paddingVertical: 4, backgroundColor: colors.backgroundElevated ?? 'transparent' }}>
                <AppText style={common.muted}>{t.pos}</AppText>
                <AppText style={common.bodyStrong}>{simFmtPts(t.pts)}</AppText>
              </View>
            ))}
          </View>
          <View>
            {simTopStarters(game.starters).map((s, i) => (
              <SimPlayerLine key={`${s.slot}-${i}`} player={s.player!} stats={[{ key: 'pts', label: 'Pts', value: simFmtPts(s.pts), tone: s.pts >= s.player!.projection ? 'success' : undefined }, ...simListStats(s.player!, { adp: false }).slice(0, 1)]} onOpen={ctx.openPlayer} />
            ))}
          </View>
        </>
      );
    }
    if (key === 'injuries') {
      const m = simRecapInjuryModel(recap);
      const hero = m.yours > 0 ? `${m.yours}` : m.items.length > 0 ? `${m.items.length} hurt` : `${facts.lineupWarnings}`;
      return (
        <>
          <Hero value={hero} caption={m.yours > 0 ? 'of your players got hurt' : m.items.length > 0 ? 'injuries around the league' : 'lineup issues to fix'} color={m.yours > 0 || facts.lineupWarnings > 0 ? colors.danger : undefined} />
          {m.items.map((inj, i) => (
            <View key={i} style={common.rowBetween}>
              <View style={common.grow}>
                <SimPlayerChip player={{ ...inj.player, status: 'out', out_weeks: inj.weeks }} onOpen={ctx.openPlayer} />
              </View>
              <AppText style={[common.bodyStrong, { color: colors.danger }]}>{`Out ${inj.weeks}w${inj.is_yours ? ' · yours' : ''}`}</AppText>
            </View>
          ))}
          {m.zeroStarters.length > 0 ? <AppText style={[common.body, { textAlign: 'center', color: colors.warning }]}>{`${m.zeroStarters.map((z) => `${z.name} (${z.flag})`).slice(0, 3).join(', ')} scored 0.`}</AppText> : null}
          {facts.lineupWarnings > 0 ? <AppText style={[common.bodyStrong, { textAlign: 'center', color: colors.warning }]}>{`${facts.lineupWarnings} lineup issue${facts.lineupWarnings === 1 ? '' : 's'} for next week.`}</AppText> : null}
        </>
      );
    }
    if (key === 'league') {
      const h = simLeagueHighlights(recap, facts.names);
      return (
        <>
          <Hero value={h.hero?.value ?? ''} caption={h.hero?.who ? `Top score: ${h.hero.who}` : undefined} color={colors.success} />
          {h.items.map((it) => (
            <Fact key={it.key} label={it.label}>
              {it.detail}
            </Fact>
          ))}
        </>
      );
    }
    if (key === 'next') {
      const n = simNextWeekModel(recap, facts);
      return (
        <>
          <Hero value={n.opponent ?? `Week ${n.week ?? ''}`} caption={n.week != null ? `Week ${n.week}${n.opponent ? ' opponent' : ''}` : undefined} />
          {n.yours != null && n.theirs != null ? <AppText style={[common.bodyStrong, { textAlign: 'center', fontSize: 18 }]}>{`${simFmtPts(n.yours)} proj vs ${simFmtPts(n.theirs)}`}</AppText> : null}
          {n.edge ? <AppText style={[common.bodyStrong, { textAlign: 'center', color: colors.textSecondary }]}>{n.edge}</AppText> : null}
          {n.notes.map((note) => (
            <Fact key={note.label} label={note.label}>
              {note.text}
            </Fact>
          ))}
        </>
      );
    }
    return null;
  };

  const pages: StoryPage[] = keys.map((key, i) => ({
    key,
    label: `${title}${total > 1 ? ` · ${index + 1} of ${total}` : ''} · ${KICKER[key]}`,
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
