import React, { useMemo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import type { SimDraftBarModel } from '../lib/simDraft';
import { spacing, type ThemeColors } from '../theme';

/**
 * The second line of the pinned draft bar (mirrors web SimDraftBar): the best available player with his avatar,
 * position and letter grade (ADP stays as the figure when the game has no grade). Tapping it opens the player. It is the
 * `preview` of the Sim draft-clock CompactModule. Cyan / neutral only; gold is the clock's.
 */
export function SimDraftBar({ model, onOpen }: { model: SimDraftBarModel; onOpen?: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const body = (
    <>
      <PlayerAvatar playerId={model.playerId} size={36} />
      <View style={styles.text}>
        <AppText style={styles.kicker}>Best available</AppText>
        <View style={styles.nameRow}>
          <AppText style={styles.name}>{model.name}</AppText>
          <PositionBadge position={model.position} />
        </View>
        {model.adp || model.fit ? <AppText style={styles.meta}>{[model.adp, model.fit].filter(Boolean).join(' · ')}</AppText> : null}
      </View>
      {model.grade ? (
        <View style={styles.grade} accessible accessibilityRole="image" accessibilityLabel={`Grade ${model.grade}`} testID="draft-bar-grade">
          <AppText style={styles.gradeText}>{model.grade}</AppText>
        </View>
      ) : null}
    </>
  );
  const label = `Best available: ${model.name}, ${model.position}${model.grade ? `, grade ${model.grade}` : ''}. Open player`;
  return onOpen ? (
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onOpen} style={styles.row} testID="draft-bar-player">
      {body}
    </Pressable>
  ) : (
    <View style={styles.row} testID="draft-bar-player">
      {body}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44 },
    text: { flex: 1, minWidth: 0 },
    kicker: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
    nameRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
    name: { flexShrink: 1, fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    meta: { fontSize: 12.5, color: colors.textTertiary },
    grade: { minWidth: 40, height: 32, paddingHorizontal: 8, alignItems: 'center', justifyContent: 'center', borderRadius: 16, borderWidth: 1.5, borderColor: colors.accent, backgroundColor: colors.accentMuted },
    gradeText: { fontSize: 16, fontWeight: '800', color: colors.accent },
  });
}
