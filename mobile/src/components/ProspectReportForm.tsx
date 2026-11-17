import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import Button from './Button';
import ConfirmInPlace from './ConfirmInPlace';
import Input from './Input';
import PressableScale from './PressableScale';
import { MAX_GRADE, MAX_ROUND_PROJECTION, MIN_GRADE, MIN_ROUND_PROJECTION, type CollegeProspect } from '../lib/api';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * Your own scouting report on a college prospect (grade, round projection, note): the one form, shown in the prospect
 * sheet's Overview. Same POST/DELETE /v1/scouting/prospects/{id}/report the board always used. Web twin:
 * web-next/src/components/ProspectReportForm.tsx.
 */
const GRADE_OPTIONS = Array.from({ length: MAX_GRADE - MIN_GRADE + 1 }, (_, i) => MIN_GRADE + i);
const ROUND_OPTIONS = Array.from({ length: MAX_ROUND_PROJECTION - MIN_ROUND_PROJECTION + 1 }, (_, i) => MIN_ROUND_PROJECTION + i);
export const NOTE_MAX_LENGTH = 280;

export interface ReportDraft {
  grade: number | null;
  roundProjection: number | null;
  note: string;
}

export interface ReportFlash {
  tone: 'success' | 'error';
  message: string;
}

export function draftFromProspect(prospect: CollegeProspect): ReportDraft {
  return {
    grade: prospect.my_report?.grade ?? null,
    roundProjection: prospect.my_report?.round_projection ?? null,
    note: prospect.my_report?.note ?? '',
  };
}

export default function ProspectReportForm({
  hasReport,
  draft,
  flash,
  busy,
  onDraftChange,
  onSubmit,
  onRemove,
}: {
  hasReport: boolean;
  draft: ReportDraft;
  flash: ReportFlash | null;
  busy: boolean;
  onDraftChange: (next: ReportDraft) => void;
  onSubmit: () => void;
  onRemove: () => Promise<boolean>;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View testID="prospect-report-form">
      <AppText style={styles.fieldLabel}>Overall grade (1 = pass, 5 = elite)</AppText>
      <View style={styles.pillRow}>
        {GRADE_OPTIONS.map((value) => (
          <PressableScale
            accessibilityRole="button"
            accessibilityLabel={`Grade ${value}`}
            key={value}
            style={[styles.pill, draft.grade === value && styles.pillActive]}
            onPress={() => onDraftChange({ ...draft, grade: value })}
          >
            <AppText style={[styles.pillText, draft.grade === value && styles.pillTextActive]}>{value}</AppText>
          </PressableScale>
        ))}
      </View>

      <AppText style={[styles.fieldLabel, styles.fieldLabelSpaced]}>Round projection (optional)</AppText>
      <View style={styles.pillRow}>
        {ROUND_OPTIONS.map((value) => (
          <PressableScale
            accessibilityRole="button"
            accessibilityLabel={`Round ${value}`}
            key={value}
            style={[styles.pill, draft.roundProjection === value && styles.pillActive]}
            onPress={() => onDraftChange({ ...draft, roundProjection: draft.roundProjection === value ? null : value })}
          >
            <AppText style={[styles.pillText, draft.roundProjection === value && styles.pillTextActive]}>{value}</AppText>
          </PressableScale>
        ))}
      </View>

      <AppText style={[styles.fieldLabel, styles.fieldLabelSpaced]}>Note (optional)</AppText>
      <Input
        style={styles.noteInput}
        placeholder="What stands out on tape?"
        multiline
        maxLength={NOTE_MAX_LENGTH}
        value={draft.note}
        onChangeText={(note) => onDraftChange({ ...draft, note })}
      />
      <AppText style={styles.noteCounter}>
        {draft.note.length}/{NOTE_MAX_LENGTH}
      </AppText>

      {flash ? <AppText style={flash.tone === 'success' ? styles.saved : styles.error}>{flash.message}</AppText> : null}

      <Button label={hasReport ? 'Update Grade' : 'Submit Grade'} onPress={onSubmit} disabled={draft.grade == null} loading={busy} style={styles.submitButton} />

      {hasReport ? (
        <ConfirmInPlace
          variant="row"
          mode="ask"
          label="Remove my report"
          prompt="Remove your report?"
          confirmLabel="Remove"
          errorText="Could not remove your grade. Try again in a moment."
          disabled={busy}
          onConfirm={onRemove}
          style={styles.removeButton}
        />
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    fieldLabel: { fontSize: 13.5, fontWeight: '600', color: colors.textSecondary },
    fieldLabelSpaced: { marginTop: spacing.md },
    pillRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginTop: spacing.sm },
    pill: {
      minWidth: 44,
      minHeight: 44,
      paddingHorizontal: spacing.sm,
      borderRadius: radii.pill,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.surfaceSolid,
      alignItems: 'center',
      justifyContent: 'center',
    },
    pillActive: { backgroundColor: colors.accentMuted, borderColor: colors.accent },
    pillText: { fontSize: 14.5, fontWeight: '600', color: colors.textSecondary },
    pillTextActive: { color: colors.accentOnTint, fontWeight: '700' },
    noteInput: {
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: radii.sm,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
      fontSize: 15.5,
      color: colors.textPrimary,
      backgroundColor: colors.surfaceSolid,
      marginTop: spacing.sm,
      minHeight: 72,
      textAlignVertical: 'top',
    },
    noteCounter: { fontSize: 12, color: colors.textTertiary, textAlign: 'right', marginTop: 2 },
    error: { color: colors.danger, fontSize: 13.5, marginTop: spacing.sm, textAlign: 'center' },
    saved: { color: colors.success, fontSize: 13.5, marginTop: spacing.sm, textAlign: 'center', fontWeight: '600' },
    submitButton: { marginTop: spacing.md },
    removeButton: { marginTop: spacing.sm },
  });
}
