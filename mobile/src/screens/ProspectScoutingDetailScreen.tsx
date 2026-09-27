import React, { useMemo, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, TextInput, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AppText from '../components/AppText';
import BrandHeaderBar from '../components/BrandHeaderBar';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import AnimatedCard from '../components/AnimatedCard';
import PositionBadge from '../components/PositionBadge';
import SectionHeading from '../components/SectionHeading';
import { api, MAX_GRADE, MIN_GRADE, MAX_ROUND_PROJECTION, MIN_ROUND_PROJECTION } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'CollegeProspectDetail'>;

const GRADE_OPTIONS = Array.from({ length: MAX_GRADE - MIN_GRADE + 1 }, (_, i) => MIN_GRADE + i);
const ROUND_OPTIONS = Array.from(
  { length: MAX_ROUND_PROJECTION - MIN_ROUND_PROJECTION + 1 },
  (_, i) => MIN_ROUND_PROJECTION + i,
);
const NOTE_MAX_LENGTH = 280;

/**
 * Submit/edit my own scouting grade for one prospect, see the shared
 * aggregate it's pooling into, and follow/unfollow the personal watchlist.
 * One report per (user, prospect) — resubmitting just replaces mine
 * (modules/college_scouting.py's aggregate always recomputes from every
 * user's latest report, never accumulates duplicates).
 */
export default function ProspectScoutingDetailScreen({ route, navigation }: Props) {
  const { prospect } = route.params;
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);

  const [grade, setGrade] = useState<number | null>(prospect.my_report?.grade ?? null);
  const [roundProjection, setRoundProjection] = useState<number | null>(
    prospect.my_report?.round_projection ?? null,
  );
  const [note, setNote] = useState(prospect.my_report?.note ?? '');
  const [onWatchlist, setOnWatchlist] = useState(prospect.on_watchlist);
  const [submitting, setSubmitting] = useState(false);
  const [removing, setRemoving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useScreenHeaderTitle(navigation, prospect.name, `${prospect.position} · ${prospect.school}`);

  const submit = async () => {
    if (grade == null || submitting) return;
    setSubmitting(true);
    setError(null);
    setSaved(false);
    try {
      const result = await api.submitScoutingReport(prospect.id, {
        grade,
        round_projection: roundProjection,
        note: note.trim(),
      });
      if (result.ok) {
        setSaved(true);
      } else {
        setError('Could not save your grade. Try again in a moment.');
      }
    } catch {
      setError('Could not save your grade. Try again in a moment.');
    } finally {
      setSubmitting(false);
    }
  };

  const removeReport = async () => {
    if (removing) return;
    setRemoving(true);
    setError(null);
    try {
      const result = await api.deleteScoutingReport(prospect.id);
      if (result.ok) {
        setGrade(null);
        setRoundProjection(null);
        setNote('');
        setSaved(false);
      } else {
        setError('Could not remove your grade. Try again in a moment.');
      }
    } catch {
      setError('Could not remove your grade. Try again in a moment.');
    } finally {
      setRemoving(false);
    }
  };

  const toggleWatchlist = async () => {
    const next = !onWatchlist;
    setOnWatchlist(next);
    try {
      const result = next
        ? await api.addProspectToWatchlist(prospect.id)
        : await api.removeProspectFromWatchlist(prospect.id);
      if (!result.ok) setOnWatchlist(!next);
    } catch {
      setOnWatchlist(!next);
    }
  };

  const hadReport = prospect.my_report != null;

  return (
    <View style={[styles.container, { paddingTop: headerHeight }]}>
      <BrandHeaderBar />
      <ScrollView contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>
        <AnimatedCard style={styles.headerCard}>
          <View style={styles.headerRow}>
            <PositionBadge position={prospect.position} size="md" />
            <View style={styles.headerIdentity}>
              <AppText style={styles.name}>{prospect.name}</AppText>
              <AppText style={styles.meta}>
                {prospect.school}
                {prospect.draft_year ? ` · ${prospect.draft_year} class` : ''}
              </AppText>
            </View>
            <TouchableOpacity
              style={styles.watchlistButton}
              onPress={() => void toggleWatchlist()}
              hitSlop={8}
              accessibilityLabel={onWatchlist ? 'Remove from watchlist' : 'Add to watchlist'}
            >
              <Ionicons
                name={onWatchlist ? 'star' : 'star-outline'}
                size={22}
                color={onWatchlist ? colors.premium : colors.textSecondary}
              />
            </TouchableOpacity>
          </View>
          <View style={styles.aggregateRow}>
            <AppText style={styles.aggregateLabel}>Shared scouting signal</AppText>
            <AppText style={styles.aggregateValue}>
              {prospect.aggregate.avg_grade != null
                ? `${prospect.aggregate.avg_grade.toFixed(1)}/5 avg from ${prospect.aggregate.scout_count} ${
                    prospect.aggregate.scout_count === 1 ? 'scout' : 'scouts'
                  }`
                : 'No scouting reports yet — be the first'}
            </AppText>
          </View>
        </AnimatedCard>

        <SectionHeading title="Your Grade" icon="clipboard-outline" />
        <AnimatedCard style={styles.formCard}>
          <AppText style={styles.fieldLabel}>Overall grade (1 = pass, 5 = elite)</AppText>
          <View style={styles.pillRow}>
            {GRADE_OPTIONS.map((value) => (
              <TouchableOpacity
                key={value}
                style={[styles.pill, grade === value && styles.pillActive]}
                onPress={() => setGrade(value)}
              >
                <AppText style={[styles.pillText, grade === value && styles.pillTextActive]}>{value}</AppText>
              </TouchableOpacity>
            ))}
          </View>

          <AppText style={[styles.fieldLabel, styles.fieldLabelSpaced]}>
            Round projection (optional)
          </AppText>
          <View style={styles.pillRow}>
            {ROUND_OPTIONS.map((value) => (
              <TouchableOpacity
                key={value}
                style={[styles.pill, roundProjection === value && styles.pillActive]}
                onPress={() => setRoundProjection(roundProjection === value ? null : value)}
              >
                <AppText style={[styles.pillText, roundProjection === value && styles.pillTextActive]}>
                  {value}
                </AppText>
              </TouchableOpacity>
            ))}
          </View>

          <AppText style={[styles.fieldLabel, styles.fieldLabelSpaced]}>Note (optional)</AppText>
          <TextInput
            style={styles.noteInput}
            placeholder="What stands out on tape?"
            placeholderTextColor={colors.textTertiary}
            multiline
            maxLength={NOTE_MAX_LENGTH}
            value={note}
            onChangeText={setNote}
          />
          <AppText style={styles.noteCounter}>
            {note.length}/{NOTE_MAX_LENGTH}
          </AppText>

          {error ? <AppText style={styles.error}>{error}</AppText> : null}
          {saved ? <AppText style={styles.saved}>Saved — thanks for scouting.</AppText> : null}

          <TouchableOpacity
            style={[styles.submitButton, grade == null && styles.submitButtonDisabled]}
            onPress={() => void submit()}
            disabled={grade == null || submitting}
          >
            {submitting ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <AppText style={styles.submitButtonText}>{hadReport ? 'Update Grade' : 'Submit Grade'}</AppText>
            )}
          </TouchableOpacity>

          {hadReport ? (
            <TouchableOpacity style={styles.removeButton} onPress={() => void removeReport()} disabled={removing}>
              <AppText style={styles.removeButtonText}>
                {removing ? 'Removing…' : 'Remove my report'}
              </AppText>
            </TouchableOpacity>
          ) : null}
        </AnimatedCard>
      </ScrollView>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background },
    content: { paddingHorizontal: spacing.lg, paddingTop: spacing.md },
    headerCard: { padding: spacing.md, marginBottom: spacing.md },
    headerRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    headerIdentity: { flex: 1, minWidth: 0 },
    name: { fontSize: 17, fontWeight: '700', color: colors.textPrimary },
    meta: { fontSize: 12, color: colors.textSecondary, marginTop: 2 },
    watchlistButton: { padding: spacing.xs },
    aggregateRow: {
      marginTop: spacing.md,
      paddingTop: spacing.md,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: colors.border,
    },
    aggregateLabel: { fontSize: 10, fontWeight: '700', letterSpacing: 0.4, color: colors.textTertiary },
    aggregateValue: { fontSize: 14, fontWeight: '600', color: colors.textPrimary, marginTop: 2 },
    formCard: { padding: spacing.md, marginBottom: spacing.xl },
    fieldLabel: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
    fieldLabelSpaced: { marginTop: spacing.md },
    pillRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, marginTop: spacing.sm },
    pill: {
      minWidth: 36,
      paddingHorizontal: spacing.sm,
      paddingVertical: spacing.sm - 2,
      borderRadius: radii.pill,
      borderWidth: 1,
      borderColor: colors.border,
      backgroundColor: colors.surfaceSolid,
      alignItems: 'center',
      justifyContent: 'center',
    },
    pillActive: { backgroundColor: colors.accentMuted, borderColor: colors.accent },
    pillText: { fontSize: 13, fontWeight: '600', color: colors.textSecondary },
    pillTextActive: { color: colors.accentOnTint, fontWeight: '700' },
    noteInput: {
      borderWidth: 1,
      borderColor: colors.border,
      borderRadius: radii.sm,
      paddingHorizontal: spacing.md,
      paddingVertical: spacing.sm,
      fontSize: 14,
      color: colors.textPrimary,
      backgroundColor: colors.surfaceSolid,
      marginTop: spacing.sm,
      minHeight: 72,
      textAlignVertical: 'top',
    },
    noteCounter: { fontSize: 10, color: colors.textTertiary, textAlign: 'right', marginTop: 2 },
    error: { color: colors.danger, fontSize: 12, marginTop: spacing.sm, textAlign: 'center' },
    saved: { color: colors.success, fontSize: 12, marginTop: spacing.sm, textAlign: 'center', fontWeight: '600' },
    submitButton: {
      marginTop: spacing.md,
      borderRadius: radii.md,
      paddingVertical: spacing.md,
      alignItems: 'center',
      justifyContent: 'center',
      backgroundColor: colors.accent,
    },
    submitButtonDisabled: { opacity: 0.5 },
    submitButtonText: { color: '#fff', fontSize: 14, fontWeight: '700' },
    removeButton: { marginTop: spacing.sm, alignItems: 'center', justifyContent: 'center', paddingVertical: spacing.sm },
    removeButtonText: { color: colors.danger, fontSize: 13, fontWeight: '600' },
  });
}
