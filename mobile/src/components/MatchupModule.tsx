import React, { useEffect, useMemo, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import { PlayerTap } from './PlayerOpenContext';
import { Collapse } from './Presence';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { compactSummaryText } from '../lib/compactModule';
import { matchupTickerParts, type MatchupCardModel, type MatchupSwingPlayer } from '../lib/matchupModules';
import { playerSurname } from '../lib/playerNameDisplay';
import { feedAgeLabel, feedPointsLabel } from '../lib/liveFeed';
import { quietLabel, type LiveGame, type LivePlay } from '../lib/matchupLive';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * THE matchup module (mirrors web-next/src/components/ui/MatchupModule.tsx; docs/ui-patterns.md, "Matchup hero and
 * ticker"). One model (`matchupCardModel`), two forms:
 *   MatchupHeroCard  the page form (Matchup screen, Fantasy Sim Home): week + live state, win chance chip, both
 *                    scores, the win bar, a projection / players-left line and two swing players with avatars.
 *                    Tapping a swing player opens the player peek.
 *   MatchupTicker    the compact form for stacks, one tap to the Matchup screen.
 * Cyan / neutral only, gold never.
 */

function toneColor(tone: 'success' | 'warning' | 'danger' | 'accent', colors: ThemeColors): string {
  return tone === 'success' ? colors.success : tone === 'danger' ? colors.danger : tone === 'warning' ? colors.warning : colors.accent;
}

/** The widest-range player still to play on each side, with avatars; tapping one opens the player peek. Shared by the Matchup hero and Today's matchup card. */
export function SwingPlayers({ swing, onOpenPlayer }: { swing: MatchupSwingPlayer[]; onOpenPlayer?: (player: MatchupSwingPlayer) => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <>
        {swing.length > 0 ? (
          <View style={styles.swing} testID="matchup-swing">
            <AppText style={styles.swingTitle}>Swing players</AppText>
            <View style={styles.swingRow}>
              {swing.map((p) => {
                const body = (
                  <>
                    <PlayerAvatar playerId={p.playerId} name={p.name} position={p.position} team={p.team} tier={p.tier} size={36} />
                    <View style={styles.swingText}>
                      <View style={styles.swingName}>
                        <AppText style={styles.swingNameText}>{playerSurname(p.name) || p.name}</AppText>
                        {p.position ? <PositionBadge position={p.position} /> : null}
                      </View>
                      <AppText style={[styles.swingLabel, { color: p.side === 'mine' ? colors.accent : colors.textSecondary }]} numberOfLines={1}>
                        {p.label}
                      </AppText>
                    </View>
                  </>
                );
                return (
                  <PlayerTap key={p.key} player={{ id: p.playerId, name: p.name, position: p.position }} onOpen={onOpenPlayer ? () => onOpenPlayer(p) : undefined} style={styles.swingItem}>
                    <View style={styles.swingItemInner} testID="matchup-swing-player">
                      {body}
                    </View>
                  </PlayerTap>
                );
              })}
            </View>
          </View>
        ) : null}
    </>
  );
}

/** What the live sections read; built by the screen (mirrors web MatchupLiveSections). */
export interface MatchupLiveSections {
  live: boolean;
  games: LiveGame[];
  plays: LivePlay[];
  ageSeconds: number | null;
  projectedLine: string | null;
  projected: { mine: string; opponent: string } | null;
}

function SectionRow({ id, title, summary, children, defaultOpen = false }: { id: string; title: string; summary: string; children: ReactNode; defaultOpen?: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(defaultOpen);
  return (
    <View style={styles.swing} testID={`matchup-section-${id}`}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`${title}. ${summary}. ${open ? 'Collapse' : 'Expand'}`}
        accessibilityState={{ expanded: open }}
        onPress={() => setOpen((v) => !v)}
        style={styles.bigHeader}
        testID={`matchup-section-${id}-toggle`}
      >
        <AppText style={[styles.swingTitle, { paddingTop: 0 }]}>{title}</AppText>
        <AppText style={[styles.swingLabel, { flex: 1, textAlign: 'right', color: colors.textSecondary }]} numberOfLines={1}>{summary}</AppText>
        <AppText style={[styles.swingLabel, { color: colors.accent }]}>{open ? 'Hide' : 'Show'}</AppText>
      </Pressable>
      <Collapse open={open} style={{ gap: spacing.sm, paddingBottom: spacing.sm }}>{children}</Collapse>
    </View>
  );
}

/**
 * Compact, tap-to-expand sections inside the top Matchup module (mirrors web MatchupLiveSectionsView): Win odds,
 * Projected finals, Games (real clock) and Plays (server big plays + client-derived feed, one list). Replaces the
 * separate big-play line and Live feed card. Green only for you; the opponent's plays are neutral, never red.
 */
export function MatchupLiveSectionsView({ model, sections, mineName, opponentName }: { model: MatchupCardModel; sections: MatchupLiveSections; mineName: string; opponentName: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 15000);
    return () => clearInterval(timer);
  }, []);
  const { plays, games } = sections;
  const realPlays = plays.filter((p) => !p.soFar);
  const liveGame = games.find((g) => g.live);
  const playsSummary = plays.length === 0 ? quietLabel(sections.ageSeconds) : realPlays.length > 0 ? `${realPlays[0].name.split(' ').slice(-1)[0]} · ${realPlays[0].detail}` : `${plays.length} so far`;
  return (
    <View testID="matchup-live-sections">
      {model.win ? (
        <SectionRow id="odds" title="Win odds" summary={model.win.label}>
          <AppText style={styles.detail}>
            {sections.live ? 'Updates as the games play: points so far plus what each player has left, on the real game clock.' : "Based on this week's projections."}
          </AppText>
        </SectionRow>
      ) : null}
      {sections.projected ? (
        <SectionRow id="projected" title="Projected finals" summary={`${sections.projected.mine} - ${sections.projected.opponent}`}>
          <View style={styles.scores}>
            <View style={styles.side}><AppText style={styles.detail}>{mineName}</AppText><AppText style={styles.swingNameText}>{sections.projected.mine}</AppText></View>
            <View style={[styles.side, styles.sideEnd]}><AppText style={styles.detail}>{opponentName}</AppText><AppText style={styles.swingNameText}>{sections.projected.opponent}</AppText></View>
          </View>
          {sections.projectedLine ? <AppText style={styles.detail}>{sections.projectedLine}</AppText> : null}
        </SectionRow>
      ) : null}
      {games.length > 0 ? (
        <SectionRow id="games" title="Games" summary={liveGame?.clock ? `${liveGame.clock} · ${games.filter((g) => g.live).length} live` : `${games.length} played`} defaultOpen={Boolean(liveGame)}>
          {games.map((g) => (
            <View key={g.key} testID="matchup-game">
              <View style={styles.bigRow}>
                <AppText style={[styles.swingNameText, { flex: 1 }]}>{g.score}</AppText>
                <AppText style={[styles.swingLabel, { color: g.live ? colors.success : colors.textTertiary }]}>{`${g.live ? '● ' : ''}${g.clock ?? ''}`}</AppText>
              </View>
              {g.situation ? <AppText style={styles.detail}>{g.situation}</AppText> : null}
            </View>
          ))}
        </SectionRow>
      ) : null}
      {sections.live || plays.length > 0 ? (
        <SectionRow id="plays" title="Plays" summary={playsSummary} defaultOpen={realPlays.length > 0}>
          {plays.length === 0 ? (
            <AppText style={styles.detail} testID="matchup-plays-quiet">{quietLabel(sections.ageSeconds)}</AppText>
          ) : (
            plays.map((play) => {
              const mine = play.side === 'mine';
              const meta = [play.clock, play.soFar ? 'so far' : feedAgeLabel(play.at, now), play.approx && !play.soFar ? 'approx.' : null, `for ${mine ? mineName : opponentName}`].filter(Boolean).join(' · ');
              return (
                <View key={play.id} style={styles.bigRow} testID="matchup-big-play-item">
                  <PlayerAvatar playerId={play.playerId ?? ''} size={32} name={play.name} />
                  <View style={styles.swingText}>
                    <AppText style={styles.swingNameText}>{`${playerSurname(play.name) || play.name} · ${play.detail}`}</AppText>
                    <AppText style={styles.detail}>{meta}</AppText>
                  </View>
                  <AppText style={[styles.bigPoints, { color: mine && play.points >= 0 ? colors.success : colors.textSecondary }]} testID="matchup-big-play-points">
                    {feedPointsLabel(play.points)}
                  </AppText>
                </View>
              );
            })
          )}
          <AppText style={styles.detail}>Built from score changes between refreshes, so times are when we noticed.</AppText>
        </SectionRow>
      ) : null}
    </View>
  );
}

export function MatchupHeroCard({
  model,
  onOpenPlayer,
  action,
  liveSections,
  testID = 'matchup-hero',
  bare = false,
  children,
}: {
  model: MatchupCardModel;
  /** Avatar tap: opens the player peek. */
  onOpenPlayer?: (player: MatchupSwingPlayer) => void;
  /** The one primary action ("Open lineup"). */
  action?: ReactNode;
  /** Live sections (Matchup screen only): Win odds, Projected finals, Games, Plays; absent elsewhere. */
  liveSections?: MatchupLiveSections;
  testID?: string;
  /** Render the body without its own card, for placing inside a CompactModule (no card inside a card). */
  bare?: boolean;
  children?: ReactNode;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const winTone = model.win ? toneColor(model.win.tone, colors) : colors.accent;
  const wrap = (inner: ReactNode) => (bare ? <>{inner}</> : <AccentCard accent={colors.accent}>{inner}</AccentCard>);
  return wrap(
    <>
      <View testID={testID} style={styles.stack}>
        <View style={styles.kickerRow}>
          <AppText style={styles.kicker} testID="matchup-kicker">{model.kicker}</AppText>
          {model.win ? <ToneBadge label={model.win.label} color={winTone} /> : null}
        </View>
        <View style={styles.scores} accessible accessibilityLabel={`${model.mine.name} ${model.mine.score}, ${model.opponent.name} ${model.opponent.score}`}>
          <View style={styles.side}>
            <AppText style={styles.score} testID="matchup-my-score">{model.mine.score}</AppText>
            <AppText style={styles.name}>{model.mine.name}</AppText>
          </View>
          <AppText style={styles.vs}>vs</AppText>
          <View style={[styles.side, styles.sideEnd]}>
            <AppText style={[styles.score, { color: colors.textSecondary }]} testID="matchup-opp-score">{model.opponent.score}</AppText>
            <AppText style={styles.name}>{model.opponent.name}</AppText>
          </View>
        </View>
        {model.bar != null ? (
          <View style={styles.barTrack} accessible accessibilityRole="image" accessibilityLabel={`Win chance ${model.bar}%`}>
            <View style={[styles.barFill, { width: `${model.bar}%` }]} />
          </View>
        ) : null}
        {model.detail || model.basis === 'projected' ? (
          <AppText style={styles.detail} testID="matchup-detail">
            {[model.basis === 'projected' ? 'Projected points' : null, model.detail].filter(Boolean).join(' · ')}
          </AppText>
        ) : null}
        <SwingPlayers swing={model.swing} onOpenPlayer={onOpenPlayer} />
        {liveSections ? <MatchupLiveSectionsView model={model} sections={liveSections} mineName={model.mine.name} opponentName={model.opponent.name} /> : null}
        {action}
        {children}
      </View>
    </>,
  );
}

export function MatchupTicker({ model, week, onPress, testID = 'matchup-ticker' }: { model: MatchupCardModel; week: number | null; onPress: () => void; testID?: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const parts = matchupTickerParts(model, week);
  const winColor = model.win ? toneColor(model.win.tone, colors) : null;
  return (
    <AccentCard accent={colors.accent} compact>
      <Pressable accessibilityRole="link" accessibilityLabel={`Matchup: ${compactSummaryText(parts)}. Open`} onPress={onPress} style={styles.ticker} testID={testID}>
        <AppText style={styles.tickerWeek}>{parts[0].text}</AppText>
        <AppText style={styles.tickerScore} numberOfLines={1}>{parts[1].text}</AppText>
        {model.win && winColor ? <ToneBadge label={`${model.win.pct}%`} color={winColor} /> : null}
        <AppText style={{ color: colors.accent }}>{'→'}</AppText>
      </Pressable>
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    stack: { gap: spacing.sm },
    kickerRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    kicker: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, color: colors.accent },
    scores: { flexDirection: 'row', alignItems: 'flex-end', gap: spacing.sm },
    side: { flex: 1, minWidth: 0 },
    sideEnd: { alignItems: 'flex-end' },
    score: { fontSize: 30, fontWeight: '800', color: colors.textPrimary },
    name: { fontSize: 14, color: colors.textSecondary },
    vs: { fontSize: 12, fontWeight: '800', color: colors.textTertiary, paddingBottom: 6 },
    barTrack: { height: 8, borderRadius: radii.pill, overflow: 'hidden', backgroundColor: colors.dangerMuted },
    barFill: { height: '100%', backgroundColor: colors.success },
    detail: { fontSize: 13, color: colors.textTertiary },
    swing: { gap: spacing.xs, paddingTop: spacing.xs, borderTopWidth: 1, borderTopColor: colors.border },
    swingTitle: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary, paddingTop: spacing.xs },
    swingRow: { flexDirection: 'row', gap: spacing.sm },
    swingItemInner: { flex: 1, minWidth: 0, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    swingItem: { flex: 1, minWidth: 0, minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    swingText: { flex: 1, minWidth: 0 },
    swingName: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
    swingNameText: { flexShrink: 1, fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    swingLabel: { fontSize: 12.5, fontWeight: '700' },
    bigHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: 44 },
    bigRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    bigPoints: { fontSize: 14, fontWeight: '800' },
    ticker: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44 },
    tickerWeek: { width: 48, fontSize: 12, fontWeight: '800', color: colors.textTertiary },
    tickerScore: { flex: 1, minWidth: 0, fontSize: 14, fontWeight: '800', color: colors.textPrimary },
  });
}
