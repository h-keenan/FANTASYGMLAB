import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import SimGlyph from './SimGlyph';
import { useThemeMode } from '../context/ThemeModeContext';

/**
 * A compact, dismissible warning for the trade builder: a small amber alert glyph, plain text, and Dismiss. Amber is only the glyph (this
 * is a true warning); the words stay in the normal text colour. A new message re-shows it. Twin of web-next/src/components/SimTradeWarning.tsx.
 */
export default function SimTradeWarning({ message }: { message: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(
    () => StyleSheet.create({
      box: { flexDirection: 'row', alignItems: 'flex-start', gap: 8, borderRadius: 10, borderWidth: 1, borderColor: colors.border, paddingHorizontal: 10, paddingVertical: 8 },
      text: { flex: 1, fontSize: 13, color: colors.textPrimary },
      dismiss: { fontSize: 13, fontWeight: '700', color: colors.textSecondary },
    }),
    [colors],
  );
  const [dismissed, setDismissed] = useState<string | null>(null);
  if (!message || dismissed === message) return null;
  return (
    <View style={styles.box} accessibilityLiveRegion="polite" testID="trade-warning">
      <View style={{ marginTop: 2 }}><SimGlyph name="alert" color={colors.warning} size={14} /></View>
      <AppText style={styles.text}>{message}</AppText>
      <Pressable accessibilityRole="button" accessibilityLabel="Dismiss warning" onPress={() => setDismissed(message)} hitSlop={8}>
        <AppText style={styles.dismiss}>Dismiss</AppText>
      </Pressable>
    </View>
  );
}
