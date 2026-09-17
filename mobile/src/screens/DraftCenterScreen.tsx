import React, { useCallback, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';

import AnimatedCard from '../components/AnimatedCard';
import GridBackground from '../components/GridBackground';
import { api, type DraftCard, type DraftPosture } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { colors, radii, spacing } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'DraftCenter'>;

const TONE_COLOR: Record<string, string> = {
  power: colors.premium,
  strength: colors.success,
  opportunity: colors.success,
  strategy: colors.accent,
  weakness: colors.danger,
  risk: colors.danger,
};
const DEFAULT_TONE_COLOR = colors.accent;

const POSTURE_REASON_MESSAGE: Record<string, string> = {
  no_sleeper_username_linked: "Link your Sleeper account and join this league from Home to see your own draft posture.",
  sleeper_user_not_found: "We couldn't find your linked Sleeper account in this league.",
  not_a_member_of_league: "You don't appear to have a roster in this league.",
  no_draft_capital_row: "Your roster's draft-capital data isn't available yet.",
};

export default function DraftCenterScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const { leagueId, leagueName } = route.params;
  const [posture, setPosture] = useState<DraftPosture | null>(null);
  const [postureReason, setPostureReason] = useState('');
  const [decisionCards, setDecisionCards] = useState<DraftCard[]>([]);
  const [partnerCards, setPartnerCards] = useState<DraftCard[]>([]);
  const [reason, setReason] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'Draft Center', leagueName);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      (async () => {
        try {
          const result = await api.getLeagueDraftCenter(leagueId);
          if (cancelled) return;
          setPosture(result.posture);
          setPostureReason(result.posture_reason);
          setDecisionCards(result.decision_cards);
          setPartnerCards(result.partner_cards);
          setReason(result.reason);
        } catch (err) {
          if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load Draft Center.');
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      return () => {
        cancelled = true;
      };
    }, [leagueId]),
  );

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.accent} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.center}>
        <Text style={styles.error}>{error}</Text>
      </View>
    );
  }

  if (reason) {
    return (
      <View style={styles.center}>
        <Text style={styles.notReadyText}>
          Draft Center isn't ready for this league yet — try again in a bit.
        </Text>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <GridBackground />
      <ScrollView style={styles.container} contentContainerStyle={[styles.content, { paddingBottom: orbClearance }]}>
        <Text style={styles.sectionLabel}>Your Draft Posture</Text>
        {posture ? (
          <>
            <View style={styles.tileRow}>
              <PostureTile
                label="Draft Capital"
                value={posture.draft_capital_rank != null ? `#${posture.draft_capital_rank}` : '—'}
                note={posture.draft_capital != null ? `${Math.round(posture.draft_capital)} total capital` : ''}
              />
              <PostureTile
                label="Future Capital"
                value={posture.future_draft_capital_rank != null ? `#${posture.future_draft_capital_rank}` : '—'}
                note={posture.future_draft_capital != null ? `${Math.round(posture.future_draft_capital)} beyond this draft` : ''}
              />
              <PostureTile
                label="Strategy"
                value={posture.strategy_display || '—'}
                note={`Power #${posture.power_rank ?? '—'} · Franchise #${posture.franchise_rank ?? '—'}`}
              />
            </View>
            <AnimatedCard
              style={StyleSheet.flatten([styles.postureCard, { borderColor: TONE_COLOR[posture.tone] ?? DEFAULT_TONE_COLOR }])}
            >
              <Text style={[styles.postureLabel, { color: TONE_COLOR[posture.tone] ?? DEFAULT_TONE_COLOR }]}>
                {posture.label}
              </Text>
              <Text style={styles.postureNote}>{posture.note}</Text>
              <Text style={styles.postureMeta}>
                {posture.first_rounders ?? 0} tracked first-rounders · {posture.pick_count ?? 0} total picks
              </Text>
            </AnimatedCard>
          </>
        ) : (
          <Text style={styles.notice}>
            {POSTURE_REASON_MESSAGE[postureReason] ?? "Your draft posture isn't available right now."}
          </Text>
        )}

        <Text style={styles.sectionLabel}>League Draft Decision Signals</Text>
        {decisionCards.map((card) => (
          <DraftInsightCard key={card.label} card={card} />
        ))}

        <Text style={styles.sectionLabel}>Draft Partner Discovery</Text>
        {partnerCards.map((card) => (
          <DraftInsightCard key={card.label} card={card} />
        ))}
      </ScrollView>
    </View>
  );
}

function PostureTile({ label, value, note }: { label: string; value: string; note: string }) {
  return (
    <View style={styles.tile}>
      <Text style={styles.tileValue} numberOfLines={1}>
        {value}
      </Text>
      <Text style={styles.tileLabel}>{label}</Text>
      {note ? (
        <Text style={styles.tileNote} numberOfLines={2}>
          {note}
        </Text>
      ) : null}
    </View>
  );
}

function DraftInsightCard({ card }: { card: DraftCard }) {
  const toneColor = TONE_COLOR[card.tone] ?? DEFAULT_TONE_COLOR;
  return (
    <AnimatedCard style={styles.insightCard}>
      <View style={[styles.insightBadge, { backgroundColor: `${toneColor}26` }]}>
        <Text style={[styles.insightBadgeText, { color: toneColor }]}>{card.label}</Text>
      </View>
      <Text style={styles.insightTitle}>{card.title}</Text>
      {card.items.map((item, index) => (
        <View key={`${card.label}-${index}`} style={styles.insightItemRow}>
          <Text style={styles.insightItemMark}>{'•'}</Text>
          <Text style={styles.insightItemText}>{item}</Text>
        </View>
      ))}
    </AnimatedCard>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.background },
  container: { flex: 1, backgroundColor: 'transparent' },
  content: { padding: spacing.lg, paddingBottom: spacing.xl * 4 },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.background,
    padding: spacing.xl,
  },
  notReadyText: { textAlign: 'center', color: colors.textSecondary, lineHeight: 20 },
  error: { color: colors.danger, textAlign: 'center' },
  notice: {
    fontSize: 13,
    color: colors.textSecondary,
    lineHeight: 19,
    marginBottom: spacing.lg,
  },
  sectionLabel: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.5,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  tileRow: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm, marginBottom: spacing.sm },
  tile: {
    flexBasis: '30%',
    flexGrow: 1,
    backgroundColor: colors.surface,
    borderRadius: radii.sm,
    borderWidth: 1,
    borderColor: colors.border,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.xs,
    alignItems: 'center',
  },
  tileValue: { fontSize: 15, fontWeight: '700', color: colors.textPrimary },
  tileLabel: {
    fontSize: 10,
    fontWeight: '700',
    color: colors.textTertiary,
    textTransform: 'uppercase',
    letterSpacing: 0.4,
    marginTop: 2,
  },
  tileNote: { fontSize: 10, color: colors.textSecondary, marginTop: 4, textAlign: 'center' },
  postureCard: { padding: spacing.lg, borderWidth: 1, gap: spacing.xs },
  postureLabel: { fontSize: 16, fontWeight: '700' },
  postureNote: { fontSize: 13, color: colors.textSecondary, lineHeight: 19 },
  postureMeta: { fontSize: 11, color: colors.textTertiary, marginTop: spacing.xs },
  insightCard: { padding: spacing.lg, marginBottom: spacing.sm },
  insightBadge: {
    alignSelf: 'flex-start',
    borderRadius: radii.pill,
    paddingHorizontal: spacing.sm,
    paddingVertical: 3,
    marginBottom: spacing.xs,
  },
  insightBadgeText: { fontSize: 10, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.4 },
  insightTitle: { fontSize: 14, fontWeight: '600', color: colors.textPrimary, marginBottom: spacing.sm },
  insightItemRow: { flexDirection: 'row', marginBottom: 4 },
  insightItemMark: { color: colors.textSecondary, marginRight: spacing.sm },
  insightItemText: { flex: 1, fontSize: 13, color: colors.textSecondary, lineHeight: 18 },
});
