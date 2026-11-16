import React, { forwardRef } from 'react';
import { Image, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import ShareCardChrome, { ShareGlass } from './ShareCardChrome';
import type { ShareEdge, ShareModel, ShareTeam, ShareValueTone } from '../lib/multiTeamTrade';
import { colors, spacing } from '../theme';

/**
 * Multi-team trade share card: the picture a manager sends to the other
 * managers to pitch a 3 to 6 team deal (web twin:
 * web-next/src/lib/shareCard/multiTradeCard.tsx). A one-line "biggest gain"
 * verdict, who sends what to whom (a table for 3 teams, per-card "from" notes
 * for 4+), then one self-explanatory card per team: what it gets, what it
 * sends, the need it fills, and its true value change (green gain, red loss,
 * neutral even; nothing hidden). No "most hurt" / "loses" words. Cards size
 * to their content and the card height is budgeted from the same content, so
 * nothing spills past a border. Fixed dark palette like every exported share
 * graphic.
 */

const MAX_EDGE_ROWS = 4;
const ASSET_LIMIT = 3;
const CHARS_PER_LINE = 42;

const TONE_COLOR: Record<ShareValueTone, string> = {
  gain: colors.success,
  loss: colors.danger,
  even: colors.textPrimary,
};

function listLabels(labels: string[], limit: number): string {
  return labels.slice(0, limit).join(', ') + (labels.length > limit ? ` +${labels.length - limit}` : '');
}

function getsText(team: ShareTeam, showFrom: boolean): string {
  return `Gets ${listLabels(team.gets.map((a) => (showFrom && a.from_team_name ? `${a.label} (from ${a.from_team_name})` : a.label)), ASSET_LIMIT) || 'nothing'}`;
}

function sendsText(team: ShareTeam): string {
  return `Sends ${listLabels(team.sends.map((a) => a.label), ASSET_LIMIT) || 'nothing'}`;
}

const linesFor = (text: string) => Math.min(2, Math.max(1, Math.ceil(text.length / CHARS_PER_LINE)));

function teamCardHeight(team: ShareTeam, showFrom: boolean): number {
  const needs = team.needs.slice(0, 1).length;
  return 24 + 34 + 6 + linesFor(getsText(team, showFrom)) * 15 + linesFor(sendsText(team)) * 15 + needs * 14 + 2 * 3;
}

/** Card height budgeted from content: header, title block, optional edge table, team cards, QR footer. */
export function multiShareCardHeight(model: ShareModel): number {
  const flow = model.layout === 'flow';
  const edges = flow ? 44 + Math.min(model.edges.length, MAX_EDGE_ROWS) * 42 + (model.edges.length > MAX_EDGE_ROWS ? 14 : 0) : 0;
  const teams = model.teams.reduce((sum, t) => sum + teamCardHeight(t, !flow) + 8, 0);
  return 112 + 74 + edges + teams + 76 + 8;
}

function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? '')
    .join('');
}

function Mark({ name, size, uri }: { name: string; size: number; uri?: string | null }) {
  if (uri) return <Image source={{ uri }} style={[styles.mark, { width: size, height: size, borderRadius: size / 2 }]} />;
  return (
    <View style={[styles.mark, { width: size, height: size, borderRadius: size / 2 }]}>
      <AppText style={[styles.markText, { fontSize: size * 0.34 }]}>{initialsOf(name)}</AppText>
    </View>
  );
}

function EdgeRow({ edge }: { edge: ShareEdge }) {
  return (
    <View style={styles.edgeRow}>
      <View style={styles.edgeTeam}>
        <Mark name={edge.fromName} size={22} uri={edge.fromAvatarUrl} />
        <AppText style={styles.edgeName} numberOfLines={1}>
          {edge.fromName}
        </AppText>
      </View>
      <Ionicons name="arrow-forward" size={14} color={colors.accent} />
      <View style={styles.edgeTeam}>
        <Mark name={edge.toName} size={22} uri={edge.toAvatarUrl} />
        <AppText style={styles.edgeName} numberOfLines={1}>
          {edge.toName}
        </AppText>
      </View>
    </View>
  );
}

function EdgeAssets({ edge }: { edge: ShareEdge }) {
  return (
    <AppText style={styles.edgeAssets} numberOfLines={1}>
      {listLabels(edge.labels, 2)}
    </AppText>
  );
}

function TeamCard({ team, showFrom }: { team: ShareTeam; showFrom: boolean }) {
  const need = team.needs[0];
  return (
    <ShareGlass style={styles.teamCard}>
      <View style={styles.teamHead}>
        <Mark name={team.name} size={34} uri={team.avatarUrl} />
        <AppText style={styles.teamName} numberOfLines={1}>
          {team.name}
        </AppText>
        <View style={styles.valueCol}>
          <AppText style={styles.valueLabel}>VALUE CHANGE</AppText>
          <AppText style={[styles.valueText, { color: TONE_COLOR[team.valueTone] }]}>{team.valueChangeText}</AppText>
        </View>
      </View>
      <AppText style={styles.gets} numberOfLines={2}>
        {getsText(team, showFrom)}
      </AppText>
      <AppText style={styles.sends} numberOfLines={2}>
        {sendsText(team)}
      </AppText>
      {need ? (
        <AppText style={styles.detail} numberOfLines={1}>
          {`• ${need}`}
        </AppText>
      ) : null}
    </ShareGlass>
  );
}

const MultiTeamTradeShareCard = forwardRef<View, { model: ShareModel; leagueName?: string | null }>(({ model, leagueName }, ref) => {
  const flow = model.layout === 'flow';
  return (
    <ShareCardChrome ref={ref} kind="Trade proposal" height={multiShareCardHeight(model)}>
      <AppText style={styles.title}>{`${model.teams.length}-team trade`}</AppText>
      <AppText style={styles.subtitle}>{`Here is what every team gets and sends${leagueName ? ` in ${leagueName}` : ''}`}</AppText>
      <AppText style={[styles.verdict, { color: model.verdict.topRosterId ? colors.success : colors.textTertiary }]} numberOfLines={1}>
        {model.verdict.text}
      </AppText>
      {flow ? (
        <ShareGlass style={styles.flow}>
          <AppText style={styles.eyebrow}>WHO SENDS WHAT</AppText>
          {model.edges.slice(0, MAX_EDGE_ROWS).map((edge) => (
            <View key={`${edge.fromRosterId}>${edge.toRosterId}`} style={styles.edgeBlock}>
              <EdgeRow edge={edge} />
              <EdgeAssets edge={edge} />
            </View>
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
  subtitle: { fontSize: 12, fontWeight: '600', color: colors.textSecondary },
  verdict: { fontSize: 12, fontWeight: '800', marginBottom: spacing.sm },
  eyebrow: { fontSize: 9, fontWeight: '800', color: colors.accent, letterSpacing: 1.6 },
  flow: { padding: spacing.sm, gap: 6, marginBottom: spacing.sm },
  edgeBlock: { gap: 2 },
  edgeRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
  edgeTeam: { flexDirection: 'row', alignItems: 'center', gap: 4, flex: 1, minWidth: 0 },
  edgeName: { flex: 1, fontSize: 10, fontWeight: '800', color: colors.textPrimary },
  edgeAssets: { marginLeft: 26, fontSize: 9, fontWeight: '600', color: colors.textSecondary },
  teams: { gap: 8 },
  teamCard: { padding: 12, gap: 3, borderColor: 'rgba(103,232,249,0.3)' },
  teamHead: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, marginBottom: 3 },
  teamName: { flex: 1, minWidth: 0, fontSize: 14, fontWeight: '900', color: colors.textPrimary },
  gets: { fontSize: 11, lineHeight: 15, fontWeight: '700', color: colors.accent },
  sends: { fontSize: 11, lineHeight: 15, fontWeight: '700', color: colors.textSecondary },
  detail: { fontSize: 10, lineHeight: 14, fontWeight: '600', color: colors.textTertiary },
  valueCol: { alignItems: 'flex-end' },
  valueLabel: { fontSize: 8, fontWeight: '800', color: colors.textTertiary, letterSpacing: 1 },
  valueText: { fontSize: 18, fontWeight: '900' },
  mark: { alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: colors.borderStrong, backgroundColor: colors.surface },
  markText: { fontWeight: '800', color: colors.textTertiary },
});
