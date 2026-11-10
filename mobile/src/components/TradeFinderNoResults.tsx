import React, { useMemo, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import EmptyState from './EmptyState';
import SectionHeading from './SectionHeading';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import type { TradeFinderClosestIdea, TradeFinderNote, TradeFinderSearch } from '../lib/api';
import { spacing, type ThemeColors } from '../theme';

/**
 * Trade Finder's "nothing realistic" state. A bare "no trades found" gave the
 * same dead end whether nothing was priced near the selection, every partner
 * declined on roster fit, or the search itself failed. This shows the measured
 * reason (`search`, from modules.trade_ideas.finder_search_payload) and the
 * closest non-realistic packages, each labelled "Stretch" with what stops it
 * from being realistic. Mirrors web-next's TradeFinderNoResults.tsx.
 */
export default function TradeFinderNoResults({
  search,
  closest,
  renderIdea,
  onRetry,
}: {
  search?: TradeFinderSearch;
  closest?: TradeFinderClosestIdea[];
  renderIdea: (idea: TradeFinderClosestIdea, index: number) => ReactNode;
  onRetry?: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);

  if (search?.status === 'error') {
    return (
      <EmptyState
        icon="alert-circle-outline"
        title="The search hit a problem."
        subtitle={search.headline}
        actionLabel={onRetry ? 'Try again' : undefined}
        onPressAction={onRetry}
      />
    );
  }

  const reasons = (search?.reasons ?? []).filter((reason) => !(search?.headline ?? '').includes(reason.text));
  const blocked = search?.status === 'selected_assets_blocked';
  return (
    <View style={styles.wrap}>
      <EmptyState
        icon="people-outline"
        title={
          blocked
            ? "We couldn't build a trade with everything you selected."
            : 'No realistic trades found for this selection right now.'
        }
        subtitle={search?.headline || undefined}
      />
      {reasons.length > 0 ? (
        <View style={styles.reasons}>
          {reasons.map((reason) => (
            <View key={reason.code} style={styles.reasonRow}>
              <View style={[styles.reasonGlyph, { backgroundColor: colors.warningMuted }]}>
                <Ionicons name="alert-outline" size={12} color={colors.warning} />
              </View>
              <AppText style={styles.reason}>{reason.text}</AppText>
            </View>
          ))}
        </View>
      ) : null}
      <TradeFinderClosestSection options={closest ?? []} renderIdea={renderIdea} />
    </View>
  );
}

/** One plain-English line above Trade Finder results saying what every package
 * contains (or why nothing does). Never blank: the headline comes from
 * modules.trade_ideas.finder_search_payload. */
export function TradeFinderSummary({ search }: { search?: TradeFinderSearch }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!search?.headline) return null;
  return <AppText style={styles.summary}>{search.headline}</AppText>;
}

/** Label + reason above a Trade Finder card ('We added', 'Overpay',
 * 'Without Aaron Jones', 'Stretch'). */
export function TradeFinderNoteRow({ note, fallbackLabel }: { note?: TradeFinderNote; fallbackLabel?: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!note && !fallbackLabel) return null;
  return (
    <View style={styles.noteRow}>
      <ToneBadge label={note?.label ?? fallbackLabel ?? ''} color={note?.stage === 'we_added' ? colors.accent : colors.warning} />
      {note?.reason ? <AppText style={styles.noteText}>{note.reason}</AppText> : null}
    </View>
  );
}

/** Near misses, stretches (overpay) and 'without X' alternatives, each with a
 * label and one honest reason so it is never mistaken for a result that
 * includes everything the user selected. */
export function TradeFinderClosestSection({
  options,
  renderIdea,
}: {
  options: TradeFinderClosestIdea[];
  renderIdea: (idea: TradeFinderClosestIdea, index: number) => ReactNode;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (options.length === 0) return null;
  return (
    <View>
      <SectionHeading title="Closest options (stretch)" topGap={12} />
      {options.map((idea, index) => (
        <View key={`${idea.partner_team_name}-${index}`} style={styles.option}>
          <TradeFinderNoteRow note={idea.finder_note} fallbackLabel="Stretch" />
          {renderIdea(idea, index)}
        </View>
      ))}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { gap: spacing.sm },
    reasons: { gap: spacing.xs, paddingHorizontal: spacing.xs },
    reasonRow: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
    reasonGlyph: { width: 20, height: 20, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
    reason: { flex: 1, fontSize: 13.5, lineHeight: 19, color: colors.textSecondary },
    option: { gap: spacing.xs },
    noteRow: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
    noteText: { flex: 1, fontSize: 13.5, lineHeight: 19, color: colors.textTertiary },
    summary: { fontSize: 15.5, lineHeight: 22, color: colors.textSecondary },
  });
}
