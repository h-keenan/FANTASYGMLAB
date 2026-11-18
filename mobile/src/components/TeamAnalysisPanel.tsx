import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import PressableScale from './PressableScale';
import InsightRow from './InsightRow';
import { useThemeMode } from '../context/ThemeModeContext';
import type { TeamRanking } from '../lib/api';
import { formatRank } from '../lib/percentile';
import { spacing, type ThemeColors } from '../theme';

/**
 * The archetype read under My Team's Team Snapshot tiles (shown when the module is opened): the archetype narrative
 * (explanation, strengths, risks, recommendations) and real trade behavior. Every field already exists on `TeamRanking`
 * (services/mobile_api_service.py via modules/team_eval.py + modules/league_rankings.py); nothing is computed client-side.
 * The rank tiles that used to sit in a separate "Team Analytics" module now live in the one Team Snapshot strip.
 * Web twin: components/TeamArchetypeRead.tsx.
 */
export function TeamArchetypeRead({ team, onOpenAge }: { team: TeamRanking; onOpenAge?: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const hasTradeContext = team.trade_tendency && team.trade_tendency !== 'Neutral';
  return (
    <View testID="team-archetype-read">
      {team.average_age != null ? (
        <PressableScale
          onPress={onOpenAge}
          disabled={!onOpenAge}
          accessibilityRole={onOpenAge ? 'link' : 'text'}
          accessibilityLabel={`Average age ${team.average_age.toFixed(1)}${team.age_rank != null ? `, age rank ${formatRank(team.age_rank, team.age_rank_tied)}` : ''}${onOpenAge ? ', open the Roster Age rankings' : ''}`}
          style={{ minHeight: 44, justifyContent: 'center' }}
          testID="team-average-age"
        >
          <AppText style={styles.ageLine}>
            Average age {team.average_age.toFixed(1)}
            {team.age_rank != null ? <AppText style={styles.ageRank}> {'·'} age rank {formatRank(team.age_rank, team.age_rank_tied)}</AppText> : null}
          </AppText>
        </PressableScale>
      ) : null}
      {team.archetype_explanation ? <AppText style={styles.explanation}>{team.archetype_explanation}</AppText> : null}
      {team.archetype_strengths.length > 0 ? (
        <DetailList label="Strengths" items={team.archetype_strengths} color={colors.success} icon="checkmark-circle-outline" />
      ) : null}
      {team.archetype_risks.length > 0 ? (
        <DetailList label="Risks" items={team.archetype_risks} color={colors.warning} icon="alert-circle-outline" />
      ) : null}
      {team.archetype_recommendations.length > 0 ? (
        <DetailList label="Recommendations" items={team.archetype_recommendations} color={colors.accent} icon="bulb-outline" />
      ) : null}
      {hasTradeContext ? (
        <AppText style={styles.tradeLine}>
          Trade behavior: {team.trade_tendency} ({team.trade_tendency_buy_count} acquired {'·'} {team.trade_tendency_sell_count} sent)
        </AppText>
      ) : null}
    </View>
  );
}

/** Whether `team` has an archetype read worth showing under the snapshot tiles. */
export function hasArchetypeRead(team: TeamRanking): boolean {
  return Boolean(
    team.average_age != null ||
      team.archetype_explanation ||
      team.archetype_strengths.length > 0 ||
      team.archetype_risks.length > 0 ||
      team.archetype_recommendations.length > 0 ||
      (team.trade_tendency && team.trade_tendency !== 'Neutral'),
  );
}

/** A labelled group of InsightRows (Magna Carta §28: short analytical conclusions use the one reusable component); never red. */
function DetailList({
  label,
  items,
  color,
  icon,
}: {
  label: string;
  items: string[];
  color: string;
  icon: React.ComponentProps<typeof InsightRow>['icon'];
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.detailGroup}>
      <AppText style={[styles.detailLabel, { color }]}>{label}</AppText>
      {items.map((item, index) => (
        <InsightRow key={`${label}-${index}`} icon={icon} color={color} headline={item} last={index === items.length - 1} />
      ))}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    explanation: {
      fontSize: 14.5,
      color: colors.textSecondary,
      lineHeight: 20,
      marginTop: spacing.md,
      paddingTop: spacing.md,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: colors.border,
    },
    ageLine: { fontSize: 14.5, fontWeight: '700', color: colors.textPrimary, marginTop: spacing.xs },
    ageRank: { fontWeight: '400', color: colors.textTertiary },
    detailGroup: { marginTop: spacing.sm },
    detailLabel: {
      fontSize: 12.5,
      fontWeight: '700',
      textTransform: 'uppercase',
      letterSpacing: 0.4,
      marginBottom: 2,
    },
    tradeLine: {
      fontSize: 13.5,
      color: colors.textTertiary,
      marginTop: spacing.sm,
    },
  });
}
