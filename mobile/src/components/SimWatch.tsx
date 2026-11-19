import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import SectionHeading from './SectionHeading';
import SegmentedTabBar from './SegmentedTabBar';
import { SeasonWrapped } from './SeasonWrapped';
import { SimPlayerChip, SimToneBadge, type SimCtx } from './SimGameParts';
import { Collapse } from './Presence';
import { SkeletonCard } from './Skeleton';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import type { SimGameCreateBody, SimPos } from '../lib/simGame';
import type { RootStackParamList } from '../navigation/RootNavigator';
import { radii, spacing, type ThemeColors } from '../theme';
import {
  SIM_WATCH_TRADE_OPTIONS,
  SIM_WATCH_WAIVER_OPTIONS,
  normalizeWatchReport,
  simWatchGradeMove,
  simWatchMoves,
  simWatchOutcomeText,
  simWatchPlaybackLine,
  simWatchRerunBody,
  simWatchSliders,
  simWatchTradeLabel,
  simWatchWaiverLabel,
  type SimWatchLine,
  type SimWatchPlayer,
  type SimWatchReport,
  type SimWatchWhatIf,
} from '../lib/simWatch';
import { normalizeWrappedDeck, type WrappedDeck } from '../lib/wrapped';

const MAX_WEEKS = 40;
const SPEEDS = [
  { label: '1X', value: '1', pause: 650 },
  { label: '2X', value: '2', pause: 325 },
  { label: 'Skip to end', value: 'end', pause: 0 },
];

/** The report's player brief as a sim player ref (the server sends the position as a plain string). */
const ref = (p: SimWatchPlayer) => ({ ...p, pos: p.pos as SimPos });

/** The Draft & Watch settings (setup): lineups are always on, then a waiver slider and a trade slider, three options each so tabs. */
export function SimWatchSliders({ waivers, trades, onWaivers, onTrades }: { waivers: string; trades: string; onWaivers: (value: string) => void; onTrades: (value: string) => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const waiverNote = SIM_WATCH_WAIVER_OPTIONS.find((o) => o.value === waivers)?.note;
  const tradeNote = SIM_WATCH_TRADE_OPTIONS.find((o) => o.value === trades)?.note;
  return (
    <View style={styles.gap} testID="watch-sliders">
      <View style={styles.card}>
        <View style={styles.spread}>
          <AppText style={styles.cardTitle}>Lineups</AppText>
          <SimToneBadge label="Always on" tone="success" />
        </View>
        <AppText style={styles.body}>Best projected lineup every week.</AppText>
      </View>
      <View style={styles.card}>
        <AppText style={styles.cardTitle}>Waiver activity</AppText>
        <SegmentedTabBar<string> options={SIM_WATCH_WAIVER_OPTIONS.map((o) => ({ key: o.value, label: o.label }))} active={waivers} onChange={onWaivers} />
        {waiverNote ? <AppText style={styles.body}>{waiverNote}</AppText> : null}
        <View style={{ alignSelf: 'flex-start' }}><SimToneBadge label="Need-based" tone="accent" /></View>
      </View>
      <View style={styles.card}>
        <AppText style={styles.cardTitle}>Trade activity</AppText>
        <SegmentedTabBar<string> options={SIM_WATCH_TRADE_OPTIONS.map((o) => ({ key: o.value, label: o.label }))} active={trades} onChange={onTrades} />
        {tradeNote ? <AppText style={styles.body}>{tradeNote}</AppText> : null}
      </View>
    </View>
  );
}

/** After the draft: one button plays the season back week by week (1X, 2X or straight to the end). */
export function SimWatchPlayback({ ctx }: { ctx: SimCtx }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const sliders = simWatchSliders(ctx.game.settings);
  const [lines, setLines] = useState<SimWatchLine[]>([]);
  const [moves, setMoves] = useState<{ title: string; sub: string }[]>([]);
  const [running, setRunning] = useState(false);
  const [latestYou, setLatestYou] = useState<SimCtx['game']['you'] | null>(null);
  const [speed, setSpeed] = useState('1');
  const speedRef = useRef('1');
  const paused = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  async function play() {
    paused.current = false;
    setRunning(true);
    let game = ctx.game;
    for (let i = 0; i < MAX_WEEKS && !paused.current; i += 1) {
      const res = await ctx.call(() => api.advanceSimGame(game.id, game.week));
      if (!res?.recap || !res.game) break;
      const recaps = [res.recap, ...(res.also_played ?? [])];
      const added = recaps.map(simWatchPlaybackLine).filter((l): l is SimWatchLine => l !== null);
      const made = recaps.flatMap((r) => simWatchMoves(r, res.game?.you?.team_id ?? ctx.game.you?.team_id));
      if (mounted.current) {
        setLines((prev) => [...prev, ...added]);
        if (made.length) setMoves((prev) => [...prev, ...made].slice(-6));
      }
      game = res.game;
      if (mounted.current && res.game.you) setLatestYou(res.game.you);
      ctx.setGame(res.game);
      if (res.game.status === 'complete' || res.game.status === 'offseason') break;
      const pause = SPEEDS.find((sp) => sp.value === speedRef.current)?.pause ?? 650;
      if (pause > 0) await new Promise((resolve) => setTimeout(resolve, pause));
    }
    if (mounted.current) setRunning(false);
  }

  // The record comes from the same answer as each results row (the game the advance call returned), not from a re-render that may lag it.
  const you = latestYou ?? ctx.game.you;
  const total = ctx.game.settings.regular_weeks || 14;
  const started = lines.length > 0;
  const record = you ? `${you.wins}-${you.losses}${you.ties ? `-${you.ties}` : ''}` : '0-0';
  const weeksPlayed = Math.min(total, lines.length);
  return (
    <View style={styles.gap} testID="watch-playback">
      <AppText style={styles.label}>{started ? 'WATCHING THE SEASON' : 'DRAFT & WATCH'}</AppText>
      <AppText style={styles.hero}>{started ? `Week ${Math.min(total, weeksPlayed + (running ? 1 : 0))} of ${total}` : 'Your draft is in'}</AppText>
      <View style={[styles.card, styles.center]}>
        <AppText style={styles.label}>RECORD</AppText>
        <AppText style={styles.record}>{record}</AppText>
        <View style={styles.track}><View style={{ height: 8, borderRadius: 4, width: `${(weeksPlayed / total) * 100}%`, backgroundColor: colors.accent }} /></View>
        <SegmentedTabBar<string>
          options={SPEEDS.map((sp) => ({ key: sp.value, label: sp.label }))}
          active={speed}
          onChange={(v) => { speedRef.current = v; setSpeed(v); }}
        />
        {sliders ? (
          <View style={styles.badges}>
            <SimToneBadge label={`Waivers: ${simWatchWaiverLabel(sliders.waivers)}`} tone="muted" />
            <SimToneBadge label={`Trades: ${simWatchTradeLabel(sliders.trades)}`} tone="muted" />
          </View>
        ) : null}
      </View>
      {started ? (
        <View style={styles.card} accessibilityLabel="Results">
          <AppText style={styles.label}>RESULTS</AppText>
          {[...lines].reverse().map((l) => (
            <View key={`${l.week}-${l.text}`} style={styles.resultRow}>
              <View style={[styles.dot, { borderColor: l.result === 'W' ? colors.success : colors.borderStrong }]}>
                <AppText style={{ fontSize: 12, fontWeight: '800', color: l.result === 'W' ? colors.success : colors.textSecondary }}>{l.result || '-'}</AppText>
              </View>
              <AppText style={[styles.row, { flex: 1 }]}>{l.label}</AppText>
              <AppText style={styles.body}>{l.score}</AppText>
            </View>
          ))}
        </View>
      ) : null}
      {moves.length ? (
        <View style={styles.card} accessibilityLabel="Moves we made">
          <AppText style={styles.label}>MOVES WE MADE</AppText>
          {[...moves].reverse().map((m, i) => (
            <View key={i}>
              <AppText style={styles.row}>{m.title}</AppText>
              <AppText style={styles.muted}>{m.sub}</AppText>
            </View>
          ))}
        </View>
      ) : null}
      {running ? <Button label="Pause" variant="secondary" onPress={() => { paused.current = true; }} /> : <Button label={started ? 'Keep going' : 'Sim the season'} onPress={() => void play()} />}
    </View>
  );
}

function GradeChip({ grade, colors }: { grade: string; colors: ThemeColors }) {
  const good = /^[AB]/.test(grade);
  const color = good ? colors.success : colors.textSecondary;
  return (
    <View style={{ minWidth: 40, height: 40, paddingHorizontal: 12, borderRadius: 20, borderWidth: 2, borderColor: good ? colors.success : colors.borderStrong, alignItems: 'center', justifyContent: 'center' }}>
      <AppText style={{ color, fontSize: 18, fontWeight: '800' }}>{grade}</AppText>
    </View>
  );
}

function WhatIf({ item, colors, styles }: { item: SimWatchWhatIf; colors: ThemeColors; styles: ReturnType<typeof createStyles> }) {
  const [open, setOpen] = useState(false);
  return (
    <AccentCard accent={colors.accent} compact>
      <Pressable onPress={() => setOpen((v) => !v)} accessibilityRole="button" accessibilityState={{ expanded: open }} style={styles.spread}>
        <AppText style={styles.row}>{item.title}</AppText>
        <SimToneBadge label={`+${item.delta.toFixed(1)} pts`} tone="success" />
      </Pressable>
      <Collapse open={open}>
        <View style={styles.tight}>
          <AppText style={styles.body}>{item.text}</AppText>
          {item.players.map((p) => <SimPlayerChip key={p.id} player={ref(p)} size={28} quick />)}
        </View>
      </Collapse>
    </AccentCard>
  );
}

/** The end of Draft & Watch: the report card story opens by itself; the page behind it keeps the same facts and the next-run actions. */
export function SimWatchReportCard({ ctx, onStartGame, onHub }: { ctx: SimCtx; onStartGame: (body: SimGameCreateBody) => void; onHub: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const navigation = useNavigation<NativeStackNavigationProp<RootStackParamList>>();
  const [report, setReport] = useState<SimWatchReport | null>(null);
  // Plan: the report's own `is_premium`, else the game's free-season preview (null preview = Pro). A failed read never hides the next-run actions.
  const [planFromReport, setPlanFromReport] = useState<boolean | null>(null);
  const isPro = planFromReport ?? ctx.preview == null;
  const [failed, setFailed] = useState(false);
  const [story, setStory] = useState(true);
  useEffect(() => {
    let cancelled = false;
    api
      .getSimWatchReport(ctx.gameId)
      .then((body) => {
        if (cancelled) return;
        if (typeof body.is_premium === 'boolean') setPlanFromReport(body.is_premium);
        const parsed = normalizeWatchReport(body.report);
        if (parsed) setReport(parsed);
        else setFailed(true);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [ctx.gameId]);

  const deck: WrappedDeck | null = useMemo(
    () => (report ? normalizeWrappedDeck({ kind: 'sim', partial: false, season_label: 'Draft & Watch', team_name: ctx.game.you?.name ?? '', cards: report.cards }) : null),
    [report, ctx.game.you?.name],
  );

  const rerun = (same: boolean) => onStartGame(simWatchRerunBody(ctx.game.settings, same) as SimGameCreateBody);
  const goPro = () => {
    setStory(false);
    navigation.navigate('Paywall');
  };
  const actions = (
    <>
      {isPro ? (
        <>
          <Button label="Run it back" onPress={() => rerun(true)} />
          <AppText style={[styles.muted, { textAlign: 'center' }]}>Same draft, new luck</AppText>
          <Button label="Draft again" variant="secondary" onPress={() => rerun(false)} />
        </>
      ) : (
        <>
          <Button label="Run it back · Pro" variant="premium" onPress={goPro} />
          <AppText style={[styles.muted, { textAlign: 'center' }]}>Same draft, new luck</AppText>
          <Button label="Draft again · Pro" variant="premiumOutline" onPress={goPro} />
        </>
      )}
    </>
  );
  if (failed) {
    // The report could not be read or parsed: say so, and keep the next-run actions (the Pro upsell for Free) instead of a blank.
    return (
      <View style={styles.gap} testID="watch-report-error">
        <AppText style={styles.muted}>Your season is saved, but the report card could not load. Try again in a moment.</AppText>
        {actions}
        <Button label="All games" variant="ghost" onPress={onHub} />
      </View>
    );
  }
  if (!report) return <View style={styles.gap}><SkeletonCard rows={4} /><SkeletonCard rows={6} /></View>;

  const move = simWatchGradeMove(report.draft.then?.grade, report.draft.now.grade);
  return (
    <View style={styles.gap} testID="watch-report">
      <AccentCard accent={colors.accent}>
        <AppText style={styles.label}>DRAFT REPORT CARD</AppText>
        <AppText style={styles.title}>{simWatchOutcomeText(report.standing.outcome)}</AppText>
        <AppText style={styles.body}>{`${report.standing.record} · #${report.standing.rank} of ${report.standing.teams}`}</AppText>
        <View style={styles.gradeRow} accessibilityLabel="Draft grade, then and now">
          {report.draft.then ? (
            <View style={styles.center}><GradeChip grade={report.draft.then.grade} colors={colors} /><AppText style={styles.muted}>Draft day</AppText></View>
          ) : null}
          {report.draft.then ? <AppText style={{ color: move === 'up' ? colors.success : colors.textTertiary, fontSize: 18 }}>{move === 'up' ? '↗' : move === 'down' ? '↘' : '→'}</AppText> : null}
          <View style={styles.center}><GradeChip grade={report.draft.now.grade} colors={colors} /><AppText style={styles.muted}>After the season</AppText></View>
        </View>
        {deck ? <Button label="Open your report card" variant="accentOutline" onPress={() => setStory(true)} /> : null}
      </AccentCard>

      {report.best_value?.player ? (
        <View style={styles.tight}>
          <SectionHeading title="Best value pick" />
          <AccentCard accent={colors.success} compact>
            <SimPlayerChip player={ref(report.best_value.player)} quick extra={<AppText style={{ color: colors.success, fontSize: 12 }}>{`${report.best_value.pick} · +${report.best_value.over_round.toFixed(1)} over his round`}</AppText>} />
          </AccentCard>
        </View>
      ) : null}

      {report.bust?.player ? (
        <View style={styles.tight}>
          <SectionHeading title="Biggest bust" />
          <AccentCard accent={colors.borderStrong} compact>
            <SimPlayerChip player={ref(report.bust.player)} quick extra={<AppText style={styles.muted}>{`${report.bust.pick} · ${report.bust.actual.toFixed(1)} of ${report.bust.projected.toFixed(1)} projected`}</AppText>} />
            <AppText style={styles.row}>{`Why: ${report.bust.why}`}</AppText>
          </AccentCard>
        </View>
      ) : null}

      <View style={styles.tight}>
        <SectionHeading title="What if" />
        {report.what_ifs.map((w) => <WhatIf key={w.id} item={w} colors={colors} styles={styles} />)}
      </View>

      <AppText style={styles.muted}>
        {`Played on ${simWatchWaiverLabel(report.sliders.waivers)} waivers and ${simWatchTradeLabel(report.sliders.trades)} trades: ${report.moves.waivers} add${report.moves.waivers === 1 ? '' : 's'}, ${report.moves.trades} trade${report.moves.trades === 1 ? '' : 's'}.`}
      </AppText>

      <View style={styles.tight}>
        {actions}
        <Button label="All games" variant="ghost" onPress={onHub} />
      </View>
      {deck && story ? <SeasonWrapped deck={deck} visible onClose={() => setStory(false)} lastFooter={actions} /> : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    gap: { gap: spacing.md },
    tight: { gap: spacing.sm },
    center: { alignItems: 'center', gap: 6 },
    spread: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    badges: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, justifyContent: 'center' },
    gradeRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
    card: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radii.lg, padding: spacing.lg, gap: spacing.sm },
    cardTitle: { fontSize: 16, fontWeight: '800', color: colors.textPrimary },
    label: { fontSize: 12, fontWeight: '800', letterSpacing: 1, color: colors.textTertiary },
    hero: { fontSize: 26, fontWeight: '800', color: colors.textPrimary },
    record: { fontSize: 48, fontWeight: '800', color: colors.textPrimary },
    title: { fontSize: 20, fontWeight: '800', color: colors.textPrimary },
    body: { fontSize: 14, color: colors.textSecondary },
    muted: { fontSize: 12, color: colors.textTertiary },
    row: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    track: { height: 8, borderRadius: 4, backgroundColor: colors.backgroundElevated, alignSelf: 'stretch' },
    resultRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.md },
    dot: { width: 24, height: 24, borderRadius: 12, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  });
}
