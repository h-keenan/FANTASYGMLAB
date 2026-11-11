import React, { forwardRef } from 'react';
import { StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import ShareCardChrome, { ShareGlass } from './ShareCardChrome';
import type { ShareEdge, ShareModel, ShareTeam } from '../lib/multiTeamTrade';
import { colors, spacing } from '../theme';

/**
 * Multi-team trade share card: the picture a manager sends to the other
 * managers to pitch a 3 to 6 team deal. Persuasion framed, not a scoreboard
 * (web twin: web-next/src/lib/shareCard/multiTradeCard.tsx): it leads with
 * what each team GETS and the needs that fills, draws who sends what to whom
 * (a flow for 3 teams, a list for 4+), and uses no "most hurt" / "loses"
 * words and no red verdicts. Nothing is hidden: each team's true value change
 * is printed as a plain, neutral number, and a team giving up value says what
 * it gets back. Fixed dark palette like every exported share graphic.
 */

const MAX_EDGE_ROWS = 4;

/** Card height by layout: a flow card carries the edge block, 4+ teams need room for the rows. */
export function multiShareCardHeight(model: ShareModel): number {
  if (model.layout === 'flow') return 700;
  return 200 + model.teams.length * 88 + 70;
}

function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');
}

function Mark({ name, size }: { name: string; size: number }) {
  return (
    <View style={[styles.mark, { width: size, height: size, borderRadius: size / 2 }]}>
      <AppText style={[styles.markText, { fontSize: size * 0.34 }]}>{initialsOf(name)}</AppText>
    </View>
  );
}

function EdgeRow({ edge }: { edge: ShareEdge }) {
  const labels = edge.labels.slice(0, 3).join(', ') + (edge.labels.length > 3 ? ` +${edge.labels.length - 3}` : '');
  return (
    <View style={styles.edgeRow}>
      <View style={styles.edgeTeam}>
        <Mark name={edge.fromName} size={22} />
        <AppText style={styles.edgeName} numberOfLines={2}>
          {edge.fromName}
        </AppText>
      </View>
      <Ionicons name="arrow-forward" size={14} color={colors.accent} />
      <View style={styles.edgeTeam}>
        <Mark name={edge.toName} size={22} />
        <AppText style={styles.edgeName} numberOfLines={2}>
          {edge.toName}
        </AppText>
      </View>
      <AppText style={styles.edgeAssets} numberOfLines={2}>
        {labels}
      </AppText>
    </View>
  );
}

function TeamCard({ team, showFrom }: { team: ShareTeam; showFrom: boolean }) {
  const limit = 3;
  const gets = team.gets
    .slice(0, limit)
    .map((a) => (showFrom && a.from_team_name ? `${a.label} (from ${a.from_team_name})` : a.label))
    .join(', ');
  const more = team.gets.length - limit;
  const detail = [...team.needs, ...(team.getsBack ? [team.getsBack] : [])].slice(0, 2);
  return (
    <ShareGlass style={styles.teamCard}>
      <Mark name={team.name} size={34} />
      <View style={styles.teamBody}>
        <AppText style={styles.teamName} numberOfLines={1}>
          {team.name}
        </AppText>
        <AppText style={styles.gets} numberOfLines={2}>
          {`Gets ${gets || 'nothing'}${more > 0 ? ` +${more} more` : ''}`}
        </AppText>
        {detail.map((line) => (
          <AppText key={line} style={styles.detail} numberOfLines={1}>
            {`• ${line}`}
          </AppText>
        ))}
      </View>
      <View style={styles.valueCol}>
        <AppText style={styles.valueLabel}>VALUE CHANGE</AppText>
        <AppText style={styles.valueText}>{team.valueChangeText}</AppText>
      </View>
    </ShareGlass>
  );
}

const MultiTeamTradeShareCard = forwardRef<View, { model: ShareModel; leagueName?: string | null }>(({ model, leagueName }, ref) => {
  const flow = model.layout === 'flow';
  return (
    <ShareCardChrome ref={ref} kind="Trade proposal" height={multiShareCardHeight(model)}>
      <AppText style={styles.title}>{`${model.teams.length}-team trade`}</AppText>
      <AppText style={styles.subtitle}>{`Here is what every team gets${leagueName ? ` in ${leagueName}` : ''}`}</AppText>
      {flow ? (
        <ShareGlass style={styles.flow}>
          <AppText style={styles.eyebrow}>WHO SENDS WHAT</AppText>
          {model.edges.slice(0, MAX_EDGE_ROWS).map((edge) => (
            <EdgeRow key={`${edge.fromRosterId}>${edge.toRosterId}`} edge={edge} />
          ))}
          {model.edges.length > MAX_EDGE_ROWS ? <AppText style={styles.detail}>{`+${model.edges.length - MAX_EDGE_ROWS} more`}</AppText> : null}
        </ShareGlass>
      ) : null}
      <View style={styles.teams}>
        {model.teams.map((team) => (
          <TeamCard key={team.rosterId} team={team} showFrom={!flow} />
        ))}
      </View>
    </ShareCardChrome>
  );
});
MultiTeamTradeShareCard.displayName = 'MultiTeamTradeShareCard';

export default MultiTeamTradeShareCard;

const styles = StyleSheet.create({
  title: { fontSize: 24, fontWeight: '900', color: colors.textPrimary, marginTop: spacing.xs },
  subtitle: { fontSize: 12, fontWeight: '600', color: colors.textSecondary, marginBottom: spacing.sm },
  eyebrow: { fontSize: 9, fontWeight: '800', color: colors.accent, letterSpacing: 1.6 },
  flow: { padding: spacing.sm, gap: 6, marginBottom: spacing.sm },
  edgeRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  edgeTeam: { flexDirection: 'row', alignItems: 'center', gap: 4, width: 82 },
  edgeName: { flex: 1, fontSize: 10, fontWeight: '800', color: colors.textPrimary },
  edgeAssets: { flex: 1, fontSize: 10, fontWeight: '600', color: colors.textSecondary },
  teams: { gap: spacing.sm },
  teamCard: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, padding: spacing.sm, borderColor: 'rgba(103,232,249,0.3)' },
  teamBody: { flex: 1, minWidth: 0, gap: 2 },
  teamName: { fontSize: 14, fontWeight: '900', color: colors.textPrimary },
  gets: { fontSize: 11, fontWeight: '700', color: colors.accent },
  detail: { fontSize: 10, fontWeight: '600', color: colors.textSecondary },
  valueCol: { alignItems: 'flex-end' },
  valueLabel: { fontSize: 8, fontWeight: '800', color: colors.textTertiary, letterSpacing: 1 },
  valueText: { fontSize: 18, fontWeight: '900', color: colors.textPrimary },
  mark: { alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: colors.borderStrong, backgroundColor: colors.surface },
  markText: { fontWeight: '800', color: colors.textTertiary },
});
