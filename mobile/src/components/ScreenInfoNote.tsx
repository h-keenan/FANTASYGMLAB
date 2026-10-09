import React, { useState } from 'react';
import { Modal, Pressable, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * A compact "ⓘ About this screen" affordance that replaces a screen's old
 * always-visible explanatory paragraph — coridian_, repeatedly, across
 * several screens: "turn all of this information text into an information
 * icon wherever it's relevant instead of just having text on the screen
 * that looks out of place." Same bottom-sheet pattern as
 * EvaluationLensHeaderButton/AwardsSection, just a plain read-only note
 * instead of a picker. Drop-in replacement for `<AppText
 * style={styles.disclaimer}>...</AppText>` — same call site, same text,
 * just hidden behind a tap instead of always on screen.
 */
/** One legend entry — a colored dot, a short bold label, and a one-line
 * definition. Used by screens whose "About this screen" note needs to
 * explain a small fixed set of terms/tags (e.g. Trade Hub's impact tags)
 * rather than just one paragraph of prose. Purely additive: screens that
 * don't pass `legend` render exactly as before. */
export interface ScreenInfoLegendItem {
  label: string;
  color: string;
  description: string;
}

export default function ScreenInfoNote({
  text,
  label = 'About this screen',
  legend,
}: {
  text: string;
  label?: string;
  legend?: ScreenInfoLegendItem[];
}) {
  const { colors } = useThemeMode();
  const styles = createStyles(colors);
  const [open, setOpen] = useState(false);
  return (
    <>
      <TouchableOpacity style={styles.row} onPress={() => setOpen(true)} hitSlop={8}>
        <Ionicons name="information-circle-outline" size={15} color={colors.textTertiary} />
        <AppText style={styles.label}>{label}</AppText>
      </TouchableOpacity>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <Pressable style={styles.sheet} onPress={(event) => event.stopPropagation()}>
            <View style={styles.sheetHeaderRow}>
              <Ionicons name="information-circle-outline" size={18} color={colors.accent} />
              <AppText style={styles.sheetTitle}>{label}</AppText>
            </View>
            <AppText style={styles.sheetBody}>{text}</AppText>
            {legend && legend.length > 0 ? (
              <View style={styles.legendList}>
                {legend.map((item) => (
                  <View key={item.label} style={styles.legendRow}>
                    <View style={[styles.legendDot, { backgroundColor: item.color }]} />
                    <AppText style={styles.legendText}>
                      <AppText style={[styles.legendLabel, { color: item.color }]}>{item.label}</AppText>
                      {'  '}
                      {item.description}
                    </AppText>
                  </View>
                ))}
              </View>
            ) : null}
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { flexDirection: 'row', alignItems: 'center', gap: 5, alignSelf: 'flex-start' },
    label: { fontSize: 12, fontWeight: '600', color: colors.textTertiary },
    backdrop: {
      flex: 1,
      backgroundColor: 'rgba(0,0,0,0.55)',
      justifyContent: 'center',
      padding: spacing.xl,
    },
    sheet: {
      backgroundColor: colors.backgroundElevated,
      borderRadius: radii.lg,
      padding: spacing.lg,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: colors.border,
    },
    sheetHeaderRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginBottom: spacing.sm },
    sheetTitle: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
    sheetBody: { fontSize: 13, color: colors.textSecondary, lineHeight: 19 },
    legendList: { marginTop: spacing.md, gap: spacing.sm },
    legendRow: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
    legendDot: { width: 8, height: 8, borderRadius: 4, marginTop: 5 },
    legendLabel: { fontSize: 13, fontWeight: '700' },
    legendText: { flex: 1, fontSize: 13, color: colors.textSecondary, lineHeight: 19 },
  });
}
