import React, { useMemo, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { compactSummaryText } from '../lib/compactModule';
import { matchupTickerParts, type MatchupCardModel, type MatchupSwingPlayer } from '../lib/matchupModules';
import { playerSurname } from '../lib/playerNameDisplay';
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

function toneColor(tone: 'success' | 'danger' | 'accent', colors: ThemeColors): string {
  return tone === 'success' ? colors.success : tone === 'danger' ? colors.danger : colors.accent;
}

export function MatchupHeroCard({
  model,
  onOpenPlayer,
  action,
  testID = 'matchup-hero',
  children,
}: {
  model: MatchupCardModel;
  /** Avatar tap: opens the player peek. */
  onOpenPlayer?: (player: MatchupSwingPlayer) => void;
  /** The one primary action ("Open lineup"). */
  action?: ReactNode;
  testID?: string;
  children?: ReactNode;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const winTone = model.win ? toneColor(model.win.tone, colors) : colors.accent;
  return (
    <AccentCard accent={colors.accent}>
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
        {model.swing.length > 0 ? (
          <View style={styles.swing} testID="matchup-swing">
            <AppText style={styles.swingTitle}>Swing players</AppText>
            <View style={styles.swingRow}>
              {model.swing.map((p) => {
                const body = (
                  <>
                    <PlayerAvatar playerId={p.playerId} tier={p.tier} size={36} />
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
                return onOpenPlayer ? (
                  <Pressable key={p.key} accessibilityRole="button" accessibilityLabel={`${p.name}, ${p.label}. Open player`} onPress={() => onOpenPlayer(p)} style={styles.swingItem} testID="matchup-swing-player">
                    {body}
                  </Pressable>
                ) : (
                  <View key={p.key} style={styles.swingItem} testID="matchup-swing-player">
                    {body}
                  </View>
                );
              })}
            </View>
          </View>
        ) : null}
        {action}
        {children}
      </View>
    </AccentCard>
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
    swingItem: { flex: 1, minWidth: 0, minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    swingText: { flex: 1, minWidth: 0 },
    swingName: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
    swingNameText: { flexShrink: 1, fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    swingLabel: { fontSize: 12.5, fontWeight: '700' },
    ticker: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44 },
    tickerWeek: { width: 48, fontSize: 12, fontWeight: '800', color: colors.textTertiary },
    tickerScore: { flex: 1, minWidth: 0, fontSize: 14, fontWeight: '800', color: colors.textPrimary },
  });
}
