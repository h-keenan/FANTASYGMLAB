import React, { useEffect, useMemo, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import InfoMark from './InfoMark';
import { useExperienceCopy } from '../context/ExperienceLevelContext';
import Button from './Button';
import { ExpandRow, ExpandRowGroup } from './ExpandRow';
import PlayerAvatarSlot from './PlayerAvatarSlot';
import CompactPlayerCard from './CompactPlayerCard';
import { AddDropPair } from './SuggestedDrop';
import EmptyState from './EmptyState';
import FreeLimitNote from './FreeLimitNote';
import PressableScale from './PressableScale';
import SectionHeading from './SectionHeading';
import { SkeletonCard } from './Skeleton';
import { useThemeMode } from '../context/ThemeModeContext';
import type { DashboardEntitlementInfo, DashboardItem } from '../lib/api';
import { trackUse } from '../lib/analytics';
import type { Decision, DecisionPlayer, DecisionSwap, DecisionQueue as Queue } from '../lib/decisionQueue';
import { swapGainLabel, type TodayAction } from '../lib/todayView';
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
 * "Do this now" (docs/ui-patterns.md, "Decision Queue"): the lineup's swap stack first, then the other ranked decisions
 * (waivers, deadline, draft, injuries) as compact modules, the rest behind "See all (N)". The queue says "nothing needs you"
 * only when it has no decision at all. Ranking and dedupe live in lib/decisionQueue.ts (byte-identical twin of web).
 * Web twin: components/DecisionQueue.tsx.
 */
export default function DecisionQueue({
  queue,
  actions,
  leagueId,
  leagueName,
  onNavigate,
  pending = false,
  emptyOverride,
  entitlement,
  renderItemCard,
}: {
  queue: Queue<DashboardItem>;
  /** The ranked, capped rows (lib/todayView.ts todayActions): lineup fixes, waivers, deadline, injuries, the best trade. */
  actions: { rows: TodayAction<DashboardItem>[]; total: number };
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
  const copy = useExperienceCopy();
  const hidden = queue.proUpsell?.hidden ?? 0;
  useEffect(() => {
    if (hidden > 0) trackUse('more_next_moves', 'gate_seen', { tier: 'free' });
  }, [hidden]);

  if (pending) return <SkeletonCard rows={3} />;
  const more = actions.total - actions.rows.length;

  const trailing = (p: DecisionPlayer) =>
    p.stat ? (
      <View style={styles.stat}>
        <AppText style={[styles.statValue, { color: colors.success }]}>{p.stat.value}</AppText>
        <AppText style={styles.statLabel}>{p.stat.label}</AppText>
      </View>
    ) : undefined;

  const openSwap = (swap: DecisionSwap | null) =>
    onNavigate('Matchup', swap?.out?.id && swap.replacement?.id ? { leagueId, leagueName, plan: 'swap', out: swap.out.id, in: swap.replacement.id } : { leagueId, leagueName, plan: 'all' });
  const press = (a: TodayAction<DashboardItem>) => {
    if (a.swap) return openSwap(a.swap);
    const d = a.decision;
    if (d) {
      if (d.swaps.length > 0) return openSwap(null);
      return onNavigate(decisionRoute(d), { leagueId, leagueName, ...(d.primary.playerId ? { playerId: d.primary.playerId } : {}) });
    }
    return onNavigate('Trades', { leagueId, leagueName, ...(a.player?.id ? { playerId: a.player.id } : {}) });
  };

  return (
    <View style={styles.block} testID="decision-queue">
      <SectionHeading
        title={actions.total > 0 ? `Do this now · ${actions.total}` : 'Do this now'}
        info={actions.total === 0 && !emptyOverride ? <InfoMark label="Do this now" beginnerOnly lines={[copy.help('dashboardNothingUrgent')]} /> : undefined}
      />
      {actions.total === 0 ? (
        <EmptyState icon="checkmark-circle-outline" title={emptyOverride ?? queue.empty?.title ?? 'Nothing needs you this week'} subtitle={emptyOverride ? undefined : (queue.empty?.detail ?? undefined)} />
      ) : (
        <ExpandRowGroup accent={actions.rows.some((a) => a.tone === 'danger') ? colors.danger : colors.accent} testID="decision-rows">
          {actions.rows.map((a) => {
            const d = a.decision;
            const gain = a.swap ? swapGainLabel(a.swap) : null;
            const [first, ...others] = d?.players ?? [];
            return (
              <ExpandRow
                key={a.key}
                testID={`decision-${a.kind === 'swap' ? 'lineup' : a.kind}`}
                label={`${a.kind === 'swap' ? 'LINEUP' : (d?.label ?? 'TRADE')}: ${a.reason}`}
                leading={a.player ? <PlayerAvatarSlot player={playerRef(a.player)} tier="row" nonInteractive="the row's toggle is the tap target" /> : <View style={[styles.dot, { backgroundColor: a.tone === 'danger' ? colors.danger : colors.warning }]} />}
                title={a.reason}
                caption={gain ? `${gain} projected` : d?.kind === 'waiver' && d.drop && first ? <AddDropPair add={{ player_id: first.id ?? '', name: first.name, position: first.position ?? '' }} drop={{ player_id: d.drop.id ?? '', name: d.drop.name, position: d.drop.position ?? '', team: d.drop.team, action: d.drop.note === 'To IR' ? 'move_to_ir' : 'drop' }} showAdd={false} /> : undefined}
                action={<Button label={a.button} size="sm" onPress={() => press(a)} />}
              >
                {a.swap ? (
                  <>
                    {a.detail ? <AppText style={styles.why}>{a.detail}</AppText> : null}
                    {a.swap.replacement?.name ? <CompactPlayerCard player={playerRef(a.swap.replacement)} detail="Best healthy replacement" trailing={gain ? <AppText style={[styles.statValue, { color: colors.success }]}>{gain}</AppText> : undefined} testID="decision-player" /> : null}
                  </>
                ) : d ? (
                  <>
                    {a.reason !== d.title ? <AppText style={styles.fullTitle}>{d.title}</AppText> : null}
                    {d.why ? <AppText style={styles.why}>{d.why}</AppText> : d.summary ? <AppText style={styles.why}>{d.summary}</AppText> : null}
                    {first ? <CompactPlayerCard player={playerRef(first)} detail={first.note} trailing={trailing(first)} testID="decision-player" /> : null}
                    {others.map((p) => (
                      <CompactPlayerCard key={p.id ?? p.name} player={playerRef(p)} detail={p.note} trailing={trailing(p)} testID="decision-player" />
                    ))}
                    {d.facts.length > 0 ? <AppText style={styles.facts}>{d.facts.join(' · ')}</AppText> : null}
                    {d.item && d.kind !== 'waiver' && renderItemCard ? renderItemCard(d.item) : null}
                  </>
                ) : a.detail ? (
                  <AppText style={styles.why}>{a.detail}</AppText>
                ) : null}
              </ExpandRow>
            );
          })}
        </ExpandRowGroup>
      )}
      <PressableScale accessibilityRole="link" onPress={() => onNavigate('GmPlan', { leagueId, leagueName })} hitSlop={LINK_HIT_SLOP} style={styles.seeAll} testID="decision-see-all">
        <AppText style={styles.link}>{more > 0 ? `See all (${actions.total}) ›` : 'Full GM Plan ›'}</AppText>
      </PressableScale>
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
    dot: { width: 10, height: 10, borderRadius: 5 },
    fullTitle: { color: colors.textPrimary, fontSize: 14, fontWeight: '700' },
    why: { color: colors.textSecondary, fontSize: 14 },
    facts: { color: colors.textTertiary, fontSize: 12, fontWeight: '700' },
    swapRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingVertical: spacing.xs },
    swapDivider: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border },
    swapPlayer: { flex: 1, minWidth: 0 },
    emptySlot: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 40 },
    emptyDot: { width: 28, height: 28, borderRadius: 14, borderWidth: 2, borderStyle: 'dashed', alignItems: 'center', justifyContent: 'center' },
    emptyTitle: { color: colors.textPrimary, fontWeight: '700', fontSize: 14 },
    stat: { alignItems: 'flex-end' },
    statValue: { fontSize: 14, fontWeight: '800' },
    statLabel: { fontSize: 12, fontWeight: '800', color: colors.textTertiary },
    upsell: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm, minHeight: 44, paddingHorizontal: spacing.md, borderRadius: radii.md, borderWidth: 1, borderColor: colors.premium, backgroundColor: colors.surface },
    upsellText: { color: colors.textPrimary, fontWeight: '700', flexShrink: 1 },
    upsellCta: { color: colors.premium, fontWeight: '700' },
  });
}
