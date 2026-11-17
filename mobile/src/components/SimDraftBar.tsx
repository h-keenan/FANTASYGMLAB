import React, { useMemo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { LetterGrade } from './LetterGrade';
import type { SimDraftBarModel } from '../lib/simDraft';
import type { SimGradeInput } from '../lib/simGrade';
import { spacing, type ThemeColors } from '../theme';

/**
 * The second line of the pinned draft bar (mirrors web SimDraftBar): the best available player with his avatar,
 * position and letter grade (ADP stays as the figure when the game has no grade). Tapping it opens the player. It is the
 * `preview` of the Sim draft-clock CompactModule. Cyan / neutral only; gold is the clock's.
 */
export function SimDraftBar({ model, onOpen, grade, action }: { model: SimDraftBarModel; onOpen?: () => void; grade?: SimGradeInput | null; action?: React.ReactNode }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const body = (
    <>
      <PlayerAvatar playerId={model.playerId} name={model.name} position={model.position} team={model.team} size={36} />
      <View style={styles.text}>
        <View style={styles.nameRow}>
          <AppText style={styles.name}>{model.name}</AppText>
          <PositionBadge position={model.position} />
        </View>
        <AppText style={styles.meta}>{['Best available', model.adp, model.fit].filter(Boolean).join(' · ')}</AppText>
      </View>
      {grade?.grade ? <LetterGrade grade={grade} size="md" /> : null}
    </>
  );
  const label = `Best available: ${model.name}, ${model.position}${model.grade ? `, grade ${model.grade}` : ''}. Open player`;
  // ONE unit: photo, name, position, grade chip and the Draft button on a single row.
  return (
    <View style={styles.unit} testID="draft-bar">
      {onOpen ? (
        <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onOpen} style={styles.row} testID="draft-bar-player">
          {body}
        </Pressable>
      ) : (
        <View style={styles.row} testID="draft-bar-player">
          {body}
        </View>
      )}
      {action}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    unit: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    row: { flex: 1, minWidth: 0, flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44 },
    text: { flex: 1, minWidth: 0 },
    nameRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
    name: { flexShrink: 1, fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    meta: { fontSize: 12.5, color: colors.textTertiary },
  });
}
