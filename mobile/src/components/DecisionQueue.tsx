import React, { useEffect, useMemo, useState, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import BeginnerHelp from './BeginnerHelp';
import Button from './Button';
import CompactModule from './CompactModule';
import CompactPlayerCard from './CompactPlayerCard';
import EmptyState from './EmptyState';
import FreeLimitNote from './FreeLimitNote';
import { MotionIn } from './Motion';
import PressableScale from './PressableScale';
import SectionHeading from './SectionHeading';
import { SkeletonCard } from './SkeletonBlock';
import { useThemeMode } from '../context/ThemeModeContext';
import type { DashboardEntitlementInfo, DashboardItem } from '../lib/api';
import { trackUse } from '../lib/analytics';
import { decisionSummaryParts, seeAllLabel, type Decision, type DecisionPlayer, type DecisionQueue as Queue } from '../lib/decisionQueue';
import { LINK_HIT_SLOP, radii, spacing, type ThemeColors } from '../theme';

const ITEM_ROUTE: Record<string, string> = { trade_hub: 'Trades', waivers: 'Waivers', my_team: 'MyTeam', draft_center: 'DraftCenter' };

/** The screen a decision's one primary action opens (the app has no separate live-draft screen: it opens the Draft Center). */
export function decisionRoute(d: Pick<Decision<DashboardItem>, 'primary' | 'item'>): string {
  switch (d.primary.target) {
    case 'matchup': return 'Matchup';
    case 'waivers': return 'Waivers';
    case 'trade_hub': return 'Trades';
    case 'gm_plan': return 'GmPlan';
    case 'draft_center':
    case 'live_draft': return 'DraftCenter';
    default: return (d.item && ITEM_ROUTE[d.item.destination]) || 'GmPlan';
  }
}

function playerRef(p: DecisionPlayer) {
  return { id: p.id, name: p.name, position: p.position, team: p.team, tier: p.tier };
}

/**
 * The Today Decision Queue (docs/ui-patterns.md, "Decision Queue"): at most three ranked decisions, each a CompactModule
 * with the shared player card, one primary action and the reasons on expand; "See all (N)" opens the rest in place.
 * Ranking and dedupe live in lib/decisionQueue.ts (byte-identical twin of web). Web twin: components/DecisionQueue.tsx.
 */
export default function DecisionQueue({
  queue,
  leagueId,
  leagueName,
  onNavigate,
  pending = false,
  emptyOverride,
  entitlement,
  renderItemCard,
}: {
  queue: Queue<DashboardItem>;
  leagueId: string;
  leagueName: string;
  onNavigate: (name: string, params?: object) => void;
  pending?: boolean;
  emptyOverride?: string;
  entitlement?: DashboardEntitlementInfo | null;
  /** The full briefing card for an item decision (shown when the row expands). */
  renderItemCard?: (item: DashboardItem) => ReactNode;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const hidden = queue.proUpsell?.hidden ?? 0;
  useEffect(() => {
    if (hidden > 0) trackUse('more_next_moves', 'gate_seen', { tier: 'free' });
  }, [hidden]);

  if (pending) return <SkeletonCard rows={3} />;
  const seeAll = seeAllLabel(queue, open);
  const shown = open ? queue.all : queue.visible;

  const trailing = (p: DecisionPlayer) =>
    p.stat ? (
      <View style={styles.stat}>
        <AppText style={[styles.statValue, { color: colors.success }]}>{p.stat.value}</AppText>
        <AppText style={styles.statLabel}>{p.stat.label}</AppText>
      </View>
    ) : undefined;

  return (
    <View style={styles.block} testID="decision-queue">
      <SectionHeading
        title={queue.total > 0 ? `Do next · ${queue.total}` : 'Do next'}
        right={
          <PressableScale onPress={() => onNavigate('GmPlan', { leagueId, leagueName })} hitSlop={LINK_HIT_SLOP} accessibilityRole="link">
            <AppText style={styles.link}>Full GM Plan ›</AppText>
          </PressableScale>
        }
      />
      {queue.total === 0 ? (
        <>
          <EmptyState icon="checkmark-circle-outline" title={emptyOverride ?? queue.empty?.title ?? 'Nothing needs you this week'} subtitle={emptyOverride ? undefined : (queue.empty?.detail ?? undefined)} />
          {!emptyOverride ? <BeginnerHelp term="dashboardNothingUrgent" /> : null}
        </>
      ) : (
        shown.map((d, i) => {
          const [first, ...others] = d.players;
          return (
            <MotionIn key={d.key} index={i >= 3 ? i - 3 : 0} count={Math.max(1, shown.length)}>
              <CompactModule
                id={`today.decision.${d.key}`}
                persist={false}
                title={d.label}
                label={d.title}
                tone={d.tone}
                parts={decisionSummaryParts(d)}
                testID={`decision-${d.kind}`}
                action={
                  <Button
                    label={d.primary.label}
                    size="sm"
                    onPress={() => onNavigate(decisionRoute(d), { leagueId, leagueName, ...(d.primary.playerId ? { playerId: d.primary.playerId } : {}) })}
                  />
                }
                preview={first ? <CompactPlayerCard player={playerRef(first)} detail={first.note} trailing={trailing(first)} testID="decision-player" /> : undefined}
              >
                {d.why ? <AppText style={styles.why}>{d.why}</AppText> : null}
                {others.map((p) => (
                  <CompactPlayerCard key={p.id ?? p.name} player={playerRef(p)} detail={p.note} trailing={trailing(p)} testID="decision-player" />
                ))}
                {d.facts.length > 0 ? <AppText style={styles.facts}>{d.facts.join(' · ')}</AppText> : null}
                {d.item && d.kind !== 'waiver' && renderItemCard ? renderItemCard(d.item) : null}
              </CompactModule>
            </MotionIn>
          );
        })
      )}
      {seeAll ? (
        <PressableScale accessibilityRole="button" accessibilityState={{ expanded: open }} onPress={() => setOpen(!open)} style={styles.seeAll} testID="decision-see-all">
          <AppText style={styles.link}>{seeAll}</AppText>
        </PressableScale>
      ) : null}
      {queue.proUpsell ? (
        <PressableScale
          accessibilityRole="button"
          accessibilityLabel={`${hidden} more move${hidden === 1 ? '' : 's'} on Pro. Upgrade`}
          onPress={() => onNavigate('Paywall')}
          style={styles.upsell}
          testID="more-moves-upsell"
        >
          <AppText style={styles.upsellText}>
            {hidden} more move{hidden === 1 ? '' : 's'} on Pro
          </AppText>
          <AppText style={styles.upsellCta}>Upgrade ›</AppText>
        </PressableScale>
      ) : entitlement ? (
        <FreeLimitNote
          kind="window"
          noun="next moves"
          limit={entitlement.free_limit}
          total={entitlement.visible_count + entitlement.hidden_count}
          shown={entitlement.visible_count}
          isPremium={entitlement.is_premium}
        />
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    block: { gap: spacing.sm },
    link: { color: colors.accent, fontWeight: '700', fontSize: 14 },
    seeAll: { minHeight: 44, justifyContent: 'center' },
    why: { color: colors.textSecondary, fontSize: 14 },
    facts: { color: colors.textTertiary, fontSize: 12, fontWeight: '700' },
    stat: { alignItems: 'flex-end' },
    statValue: { fontSize: 14, fontWeight: '800' },
    statLabel: { fontSize: 12, fontWeight: '800', color: colors.textTertiary },
    upsell: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm, minHeight: 44, paddingHorizontal: spacing.md, borderRadius: radii.md, borderWidth: 1, borderColor: colors.premium, backgroundColor: colors.surface },
    upsellText: { color: colors.textPrimary, fontWeight: '700', flexShrink: 1 },
    upsellCta: { color: colors.premium, fontWeight: '700' },
  });
}
