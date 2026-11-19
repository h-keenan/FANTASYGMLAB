import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Animated, Easing, Modal, Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import Button from './Button';
import PlayerAvatar from './PlayerAvatar';
import { SimPlayerChip } from './SimGameParts';
import { useThemeMode } from '../context/ThemeModeContext';
import type { SimDraftPick } from '../lib/simGame';
import { simBoardRows, simMomentShortName, simPickBoardNote, simPickMomentGrade, simWeekStamp, type SimMomentTone } from '../lib/simMoments';
import { useReducedMotion } from '../lib/useMotion';
import { useSimCelebrations } from '../lib/useSimCelebrationsNative';
import { radii, spacing, type ThemeColors } from '../theme';

function toneColor(colors: ThemeColors, tone: SimMomentTone): string {
  return tone === 'good' ? colors.success : tone === 'warm' ? colors.warning : colors.textSecondary;
}

type Phase = 'back' | 'flip' | 'front';

/**
 * The draft-pick moment: the card for your pick lands face down ("Tap to reveal your pick"), flips, and the grade pops in.
 * Your board so far sits underneath. Only mounted when Celebrations is on.
 */
export function SimPickReveal({ pick, board, onDone }: { pick: SimDraftPick; board: SimDraftPick[]; onDone: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const reduced = useReducedMotion();
  const [phase, setPhase] = useState<Phase>(reduced ? 'front' : 'back');
  const turn = useRef(new Animated.Value(0)).current;
  const pop = useRef(new Animated.Value(reduced ? 1 : 0)).current;
  const grade = simPickMomentGrade(pick.value_over_adp);
  const flip = () => {
    if (phase !== 'back') return;
    setPhase('flip');
    Animated.timing(turn, { toValue: 1, duration: 240, easing: Easing.inOut(Easing.quad), useNativeDriver: true }).start(() => {
      setPhase('front');
      turn.setValue(0);
      Animated.spring(pop, { toValue: 1, useNativeDriver: true, friction: 5 }).start();
    });
  };
  useEffect(() => {
    if (reduced) pop.setValue(1);
  }, [reduced, pop]);
  const rows = simBoardRows(board, pick, phase === 'front');
  const rotate = turn.interpolate({ inputRange: [0, 1], outputRange: ['0deg', '90deg'] });
  return (
    <Modal visible transparent animationType="fade" onRequestClose={onDone}>
      <View style={styles.backdrop} testID="pick-reveal">
        <View style={styles.sheet}>
          <AppText style={styles.label}>{`DRAFT ROOM · ROUND ${pick.round}`}</AppText>
          <Pressable onPress={flip} disabled={phase !== 'back'} accessibilityRole="button" accessibilityLabel={phase === 'back' ? 'Tap to reveal your pick' : `${pick.player.name}, grade ${grade.letter}`}>
            <Animated.View style={[styles.card, { transform: [{ perspective: 800 }, { rotateY: rotate }] }]}>
              {phase === 'front' ? (
                <>
                  <PlayerAvatar playerId={pick.player.headshot_id ?? null} name={pick.player.name} position={pick.player.pos} team={pick.player.team} size={64} />
                  <AppText style={styles.name}>{simMomentShortName(pick.player.name)}</AppText>
                  <AppText style={styles.muted}>{`${[pick.player.pos, pick.player.team].filter(Boolean).join(' · ')} · Pick ${pick.pick_no}`}</AppText>
                  <Animated.View style={[styles.gradeDisc, { borderColor: toneColor(colors, grade.tone), transform: [{ scale: pop }] }]}>
                    <AppText style={[styles.gradeLetter, { color: toneColor(colors, grade.tone) }]}>{grade.letter}</AppText>
                  </Animated.View>
                  <View style={[styles.pill, { borderColor: toneColor(colors, grade.tone) }]}>
                    <AppText style={{ color: toneColor(colors, grade.tone), fontSize: 12, fontWeight: '700' }}>{grade.line}</AppText>
                  </View>
                </>
              ) : (
                <>
                  <AppText style={styles.label}>{`ROUND ${pick.round}`}</AppText>
                  <AppText style={styles.big}>{`#${pick.pick_no}`}</AppText>
                  <AppText style={styles.body}>Tap to reveal your pick</AppText>
                </>
              )}
            </Animated.View>
          </Pressable>
          {rows.length ? (
            <View style={styles.board} accessibilityLabel="Your board so far">
              <AppText style={styles.label}>YOUR BOARD SO FAR</AppText>
              {rows.map((r) => {
                const g = simPickMomentGrade(r.value_over_adp);
                return (
                  <Animated.View
                    key={r.pick_no}
                    style={[styles.boardRow, r.pick_no === pick.pick_no ? { opacity: pop, transform: [{ scale: pop.interpolate({ inputRange: [0, 1], outputRange: [0.96, 1] }) }] } : null]}
                    testID="board-row"
                  >
                    <View style={{ flex: 1 }}>
                      <SimPlayerChip player={r.player} size={32} quick shortName extra={<AppText style={styles.muted}>{`Rd ${r.round}, #${r.pick_no}`}</AppText>} />
                    </View>
                    <View style={{ alignItems: 'center' }}>
                      <View style={[styles.smallGrade, { borderColor: toneColor(colors, g.tone) }]}>
                        <AppText style={{ color: toneColor(colors, g.tone), fontSize: 12, fontWeight: '800' }}>{g.letter}</AppText>
                      </View>
                      <AppText style={styles.muted}>{simPickBoardNote(r.value_over_adp)}</AppText>
                    </View>
                  </Animated.View>
                );
              })}
            </View>
          ) : null}
          <Button label={phase === 'front' ? 'Continue' : 'Skip'} variant={phase === 'front' ? 'primary' : 'ghost'} onPress={onDone} />
        </View>
      </View>
    </Modal>
  );
}

const ROLL_MS = 900;

/**
 * The week moment, under the final score: "Scores rolling in..." while the numbers count up, then the win / loss stamp with the
 * record, the move in the standings and one line on why. Renders nothing when Celebrations is off (the plain result stays).
 */
export function SimWeekStamp({ recap }: { recap: Parameters<typeof simWeekStamp>[0] }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [on] = useSimCelebrations();
  const reduced = useReducedMotion();
  const stamp = simWeekStamp(recap);
  const [rolled, setRolled] = useState(reduced);
  const pop = useRef(new Animated.Value(reduced ? 1 : 0)).current;
  useEffect(() => {
    if (reduced) return undefined;
    const id = setTimeout(() => {
      setRolled(true);
      Animated.spring(pop, { toValue: 1, useNativeDriver: true, friction: 5 }).start();
    }, ROLL_MS);
    return () => clearTimeout(id);
  }, [reduced, pop]);
  if (!on || !stamp) return null;
  if (!rolled) return <AppText style={[styles.body, { textAlign: 'center' }]} testID="week-rolling">Scores rolling in...</AppText>;
  return (
    <View style={{ alignItems: 'center', gap: spacing.sm }} testID="week-stamp">
      <Animated.View style={[styles.stamp, { borderColor: toneColor(colors, stamp.tone), transform: [{ scale: pop }] }]} accessibilityLabel={stamp.letter === 'W' ? 'Win' : stamp.letter === 'L' ? 'Loss' : 'Tie'}>
        <AppText style={[styles.stampLetter, { color: toneColor(colors, stamp.tone) }]}>{stamp.letter}</AppText>
      </Animated.View>
      <AppText style={styles.caption}>{stamp.caption}</AppText>
      {stamp.note ? <AppText style={[styles.body, { textAlign: 'center' }]}>{stamp.note}</AppText> : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.72)', alignItems: 'center', justifyContent: 'center', padding: spacing.lg },
    sheet: { width: '100%', maxWidth: 380, gap: spacing.md },
    card: { minHeight: 260, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radii.lg, padding: spacing.lg, alignItems: 'center', justifyContent: 'center', gap: spacing.sm },
    board: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radii.lg, padding: spacing.lg, gap: spacing.sm },
    boardRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    label: { fontSize: 12, fontWeight: '800', letterSpacing: 1, color: colors.textTertiary },
    big: { fontSize: 56, fontWeight: '800', color: colors.textPrimary },
    name: { fontSize: 20, fontWeight: '800', color: colors.textPrimary },
    body: { fontSize: 14, color: colors.textSecondary },
    muted: { fontSize: 12, color: colors.textTertiary },
    caption: { fontSize: 16, fontWeight: '800', color: colors.textPrimary },
    gradeDisc: { width: 56, height: 56, borderRadius: 28, borderWidth: 2, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surface },
    gradeLetter: { fontSize: 24, fontWeight: '800' },
    smallGrade: { minWidth: 26, height: 26, paddingHorizontal: 6, borderRadius: 13, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
    pill: { borderWidth: 1, borderRadius: radii.pill, paddingHorizontal: 12, paddingVertical: 4 },
    stamp: { width: 80, height: 80, borderRadius: 40, borderWidth: 4, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surface },
    stampLetter: { fontSize: 36, fontWeight: '800' },
  });
}
