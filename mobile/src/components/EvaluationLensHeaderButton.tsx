import React, { useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import type { ValuationLens } from '../lib/api';
import { colors, radii, spacing } from '../theme';

const LENS_OPTIONS: { value: ValuationLens; label: string; hint: string }[] = [
  { value: 'Dynasty', label: 'Dynasty', hint: 'Values future upside alongside this year.' },
  { value: 'Rebuild', label: 'Rebuild', hint: 'Weights youth and draft capital most heavily.' },
  { value: 'Non-Dynasty', label: 'Redraft', hint: 'Values this season only — future picks discounted.' },
];

/**
 * Trade Hub's counterpart to GmStanceHeaderButton — coridian_: "the
 * evaluation lens UI is wrong in the header," which turned out to mean it
 * didn't exist at all on mobile. The web app's Trade Hub renders "Strategy"
 * and "Evaluation" as two side-by-side selectboxes (app.py's trade_hub_setup
 * container); mobile only ever shipped the Strategy half (the GM Stance
 * pill). This is the missing Evaluation half, following the same compact
 * pill-plus-sheet pattern rather than reusing PlayersScreen's full
 * horizontal pill row, which doesn't fit in a nav header.
 */
export default function EvaluationLensHeaderButton({
  lens,
  onChange,
}: {
  lens: ValuationLens;
  onChange: (lens: ValuationLens) => void;
}) {
  const [open, setOpen] = useState(false);
  const current = LENS_OPTIONS.find((option) => option.value === lens);

  return (
    <>
      <TouchableOpacity style={styles.button} onPress={() => setOpen(true)} hitSlop={8}>
        <Text style={styles.buttonText} numberOfLines={1}>
          {current?.label ?? 'Dynasty'}
        </Text>
        <Ionicons name="chevron-down" size={12} color={colors.premium} />
      </TouchableOpacity>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <Pressable style={styles.backdrop} onPress={() => setOpen(false)}>
          <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
            <Text style={styles.title}>Evaluation Lens</Text>
            <Text style={styles.subtitle}>
              Which score field decides value in these trades — a second axis from GM Stance, not a replacement for it.
            </Text>
            {LENS_OPTIONS.map((option) => {
              const active = option.value === lens;
              return (
                <TouchableOpacity
                  key={option.value}
                  style={styles.optionRow}
                  onPress={() => {
                    onChange(option.value);
                    setOpen(false);
                  }}
                >
                  <View style={styles.optionTextGroup}>
                    <Text style={[styles.optionText, active && styles.optionTextActive]}>{option.label}</Text>
                    <Text style={styles.optionHint}>{option.hint}</Text>
                  </View>
                  {active ? <Ionicons name="checkmark-circle" size={18} color={colors.premium} /> : null}
                </TouchableOpacity>
              );
            })}
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  button: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    backgroundColor: colors.premiumMuted,
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 5,
    maxWidth: 110,
  },
  buttonText: { fontSize: 12, fontWeight: '700', color: colors.premium, flexShrink: 1 },
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
  title: { fontSize: 16, fontWeight: '700', color: colors.textPrimary },
  subtitle: { fontSize: 13, color: colors.textSecondary, marginTop: 2, marginBottom: spacing.md },
  optionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.sm,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  optionTextGroup: { flexShrink: 1, paddingRight: spacing.sm },
  optionText: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
  optionTextActive: { color: colors.premium },
  optionHint: { fontSize: 12, color: colors.textTertiary, marginTop: 2 },
});
