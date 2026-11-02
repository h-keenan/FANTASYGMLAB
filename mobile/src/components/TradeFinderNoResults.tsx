import React, { useMemo, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import EmptyState from './EmptyState';
import SectionHeading from './SectionHeading';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import type { TradeFinderClosestIdea, TradeFinderSearch } from '../lib/api';
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
  const options = closest ?? [];
  return (
    <View style={styles.wrap}>
      <EmptyState
        icon="people-outline"
        title="No realistic trades found for this selection right now."
        subtitle={search?.headline || undefined}
      />
      {reasons.length > 0 ? (
        <View style={styles.reasons}>
          {reasons.map((reason) => (
            <AppText key={reason.code} style={styles.reason}>
              {`• ${reason.text}`}
            </AppText>
          ))}
        </View>
      ) : null}
      {options.length > 0 ? (
        <View>
          <SectionHeading title="Closest options (stretch)" topGap={12} />
          {options.map((idea, index) => (
            <View key={`${idea.partner_team_name}-${index}`} style={styles.option}>
              <View style={styles.noteRow}>
                <ToneBadge label={idea.finder_note?.label ?? 'Stretch'} color={colors.warning} />
                {idea.finder_note?.reason ? (
                  <AppText style={styles.noteText}>{idea.finder_note.reason}</AppText>
                ) : null}
              </View>
              {renderIdea(idea, index)}
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { gap: spacing.sm },
    reasons: { gap: spacing.xs, paddingHorizontal: spacing.xs },
    reason: { fontSize: 12, lineHeight: 17, color: colors.textTertiary },
    option: { gap: spacing.xs },
    noteRow: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm },
    noteText: { flex: 1, fontSize: 12, lineHeight: 17, color: colors.textTertiary },
  });
}
