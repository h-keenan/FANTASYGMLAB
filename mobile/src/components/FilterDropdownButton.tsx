import React, { useMemo, useState } from 'react';
import { Modal, Pressable, StyleSheet, TouchableOpacity } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AppText from './AppText';

import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * One labeled categorical filter — a compact pill that opens a bottom sheet
 * of radio options, replacing the old "four full rows of always-expanded
 * pills" treatment Players/Waivers used to render. coridian_ (Discord,
 * screenshot of Players' Position/Age/Status/Availability rows): "these
 * filter pills need to be grouped and turn into drop down menus because
 * this is ridiculous and if they show up anywhere else it needs to be
 * changed this way as well."
 *
 * Structurally the same pill-button + Modal/backdrop/sheet language
 * EvaluationLensHeaderButton/GmStanceHeaderButton/LeagueSwitcherHeaderButton
 * already use for header pickers, promoted into one reusable, generically
 * typed component instead of a 4th screen-local reimplementation — any
 * player-list filter dimension (today's four; future ones) shares this one
 * control instead of drifting into its own pill row again.
 */
export default function FilterDropdownButton<T extends string>({
  label,
  options,
  value,
  onChange,
  allValue = 'ALL' as T,
}: {
  label: string;
  options: readonly T[];
  value: T;
  onChange: (next: T) => void;
  /** The option value meaning "no filter applied" — rendered as the bare
   * label (no ": value" suffix) in the control's quiet/inactive state.
   * Defaults to the literal string 'ALL', which every existing filter
   * dimension on Players/Waivers already uses as its "no filter" option. */
  allValue?: T;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const isActive = value !== allValue;

  return (
    <>
      <TouchableOpacity
        style={[styles.button, isActive && styles.buttonActive]}
        onPress={() => setOpen(true)}
        activeOpacity={0.7}
        accessibilityRole="button"
        accessibilityLabel={`${label} filter${isActive ? `, ${value}` : ', all'}`}
      >
        <AppText style={[styles.buttonText, isActive && styles.buttonTextActive]} numberOfLines={1}>
          {isActive ? `${label}: ${value}` : label}
        </AppText>
        <Ionicons name="chevron-down" size={12} color={isActive ? colors.accentOnTint : colors.textTertiary} />
      </TouchableOpacity>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <AppText style={styles.title}>{label}</AppText>
            {options.map((option) => {
              const active = option === value;
              return (
                <TouchableOpacity
                  key={option}
                  style={styles.optionRow}
                  onPress={() => {
                    onChange(option);
                    setOpen(false);
                  }}
                >
                  <AppText style={[styles.optionText, active && styles.optionTextActive]}>{option}</AppText>
                  {active ? <Ionicons name="checkmark-circle" size={18} color={colors.accent} /> : null}
                </TouchableOpacity>
              );
            })}
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    button: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 4,
      backgroundColor: colors.background,
      borderRadius: radii.pill,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      paddingHorizontal: spacing.sm,
      paddingVertical: 7,
    },
    buttonActive: { backgroundColor: colors.accentMuted, borderColor: colors.accent, borderWidth: 1.5 },
    buttonText: { fontSize: 12, fontWeight: '600', color: colors.textSecondary, flexShrink: 1 },
    buttonTextActive: { color: colors.accentOnTint, fontWeight: '700' },
    backdrop: {
      flex: 1,
      backgroundColor: 'rgba(0,0,0,0.6)',
      justifyContent: 'flex-end',
    },
    sheet: {
      backgroundColor: colors.backgroundElevated,
      borderTopLeftRadius: radii.lg,
      borderTopRightRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.border,
      padding: spacing.lg,
    },
    title: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.sm },
    optionRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingVertical: spacing.sm + 2,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: colors.border,
    },
    optionText: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
    optionTextActive: { color: colors.accent },
  });
}
