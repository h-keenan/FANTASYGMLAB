import React, { useEffect, useMemo, useState, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import InfoMark from './InfoMark';
import { useExperienceCopy } from '../context/ExperienceLevelContext';
import Button from './Button';
import { ExpandRow, ExpandRowGroup } from './ExpandRow';
import PlayerAvatarSlot from './PlayerAvatarSlot';
import CompactPlayerCard from './CompactPlayerCard';
import EmptyState from './EmptyState';
import FreeLimitNote from './FreeLimitNote';
import PressableScale from './PressableScale';
import SectionHeading from './SectionHeading';
import { SkeletonCard } from './Skeleton';
import { useThemeMode } from '../context/ThemeModeContext';
import type { DashboardEntitlementInfo, DashboardItem } from '../lib/api';
import { trackUse } from '../lib/analytics';
import { seeAllLabel, type Decision, type DecisionPlayer, type DecisionSwap, type DecisionQueue as Queue } from '../lib/decisionQueue';
import { swapGainLabel, swapReplacementLine, todayActionRow, todayFixAll } from '../lib/todayView';
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

const SWAP_VISIBLE = 4;

/**
 * The lineup row's detail (behind its tap): one row per lineup problem (the shared player card: avatar, status, who to
 * start instead, the projected gain) with a one-tap Swap, plus "Fix all N · +X proj". Swap opens the Matchup screen's lineup
 * planner already on that move (FantasyDesk plans, it cannot set a Sleeper lineup). Locked players (game started) are never
 * in `swaps`; see lib/decisionQueue.ts lineupSwaps. Web twin: SwapDetail in components/DecisionQueue.tsx.
 */
function SwapDetail({ d, onOpen }: { d: Decision<DashboardItem>; onOpen: (swap: DecisionSwap | null) => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [all, setAll] = useState(false);
  const shown = all ? d.swaps : d.swaps.slice(0, SWAP_VISIBLE);
  const fixAll = todayFixAll(d.swaps);
  const hidden = d.swaps.length - shown.length;
  return (
    <View testID="swap-stack">
      {shown.map((swap, i) => {
        const gain = swapGainLabel(swap);
        const detail = (
          <>
            <AppText style={{ color: swap.tone === 'danger' ? colors.danger : colors.warning, fontWeight: '800', fontSize: 12 }}>{swap.status.toUpperCase()}</AppText>
            {` → ${swapReplacementLine(swap)}`}
          </>
        );
        const gainFigure = gain ? <AppText style={[styles.statValue, { color: colors.success }]}>{gain}</AppText> : undefined;
        return (
          <View key={swap.key} style={[styles.swapRow, i > 0 ? styles.swapDivider : null]} testID="swap-row">
            <View style={styles.swapPlayer}>
              {swap.out ? (
                <CompactPlayerCard player={playerRef(swap.out)} detail={detail} trailing={gainFigure} testID="swap-player" />
              ) : (
                <View style={styles.emptySlot}>
                  <View style={[styles.emptyDot, { borderColor: colors.warning }]}>
                    <AppText style={{ color: colors.warning, fontWeight: '800' }}>+</AppText>
                  </View>
                  <View style={{ flex: 1 }}>
                    <AppText style={styles.emptyTitle}>Empty starter slot</AppText>
                    <AppText style={styles.facts}>{swapReplacementLine(swap)}</AppText>
                  </View>
                  {gainFigure}
                </View>
              )}
            </View>
            <Button label="Swap" size="sm" onPress={() => onOpen(swap)} />
          </View>
        );
      })}
      {hidden > 0 ? <Button label={`+${hidden} more`} variant="ghost" size="sm" onPress={() => setAll(true)} /> : null}
      {fixAll ? <Button label={fixAll.label} onPress={() => onOpen(null)} /> : null}
    </View>
  );
}

/**
 * "Do this now" (docs/ui-patterns.md, "Decision Queue"): the lineup's swap stack first, then the other ranked decisions
 * (waivers, deadline, draft, injuries) as compact modules, the rest behind "See all (N)". The queue says "nothing needs you"
 * only when it has no decision at all. Ranking and dedupe live in lib/decisionQueue.ts (byte-identical twin of web).
 * Web twin: components/DecisionQueue.tsx.
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
  const copy = useExperienceCopy();
  const [open, setOpen] = useState(false);
  const hidden = queue.proUpsell?.hidden ?? 0;
  useEffect(() => {
    if (hidden > 0) trackUse('more_next_moves', 'gate_seen', { tier: 'free' });
  }, [hidden]);

  if (pending) return <SkeletonCard rows={3} />;
  const seeAll = seeAllLabel(queue, open);
  const shown = open ? queue.all : queue.visible;
  // The count is the number of rows (a lineup's swaps are one row).
  const count = queue.total;

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
        title={queue.total > 0 ? `Do this now · ${count}` : 'Do this now'}
        info={queue.total === 0 && !emptyOverride ? <InfoMark label="Do this now" beginnerOnly lines={[copy.help('dashboardNothingUrgent')]} /> : undefined}
        right={
          <PressableScale onPress={() => onNavigate('GmPlan', { leagueId, leagueName })} hitSlop={LINK_HIT_SLOP} accessibilityRole="link">
            <AppText style={styles.link}>Full GM Plan ›</AppText>
          </PressableScale>
        }
      />
      {queue.total === 0 ? (
        <>
          <EmptyState icon="checkmark-circle-outline" title={emptyOverride ?? queue.empty?.title ?? 'Nothing needs you this week'} subtitle={emptyOverride ? undefined : (queue.empty?.detail ?? undefined)} />
        </>
      ) : (
        <ExpandRowGroup accent={shown.some((d) => d.tone === 'danger') ? colors.danger : colors.accent} testID="decision-rows">
          {shown.map((d) => {
            const row = todayActionRow(d);
            const [first, ...others] = d.players;
            const openSwap = (swap: DecisionSwap | null) =>
              onNavigate('Matchup', swap?.out?.id && swap.replacement?.id ? { leagueId, leagueName, plan: 'swap', out: swap.out.id, in: swap.replacement.id } : { leagueId, leagueName, plan: 'all' });
            return (
              <ExpandRow
                key={d.key}
                testID={`decision-${d.kind}`}
                label={`${d.label}: ${row.reason}`}
                leading={row.player ? <PlayerAvatarSlot player={playerRef(row.player)} tier="row" nonInteractive="the row's toggle is the tap target" /> : <View style={[styles.dot, { backgroundColor: d.tone === 'danger' ? colors.danger : colors.warning }]} />}
                title={row.reason}
                action={
                  <Button
                    label={row.button}
                    size="sm"
                    onPress={() => (d.swaps.length > 0 ? openSwap(d.swaps.length === 1 ? d.swaps[0] : null) : onNavigate(decisionRoute(d), { leagueId, leagueName, ...(d.primary.playerId ? { playerId: d.primary.playerId } : {}) }))}
                  />
                }
              >
                {d.swaps.length > 0 ? (
                  <SwapDetail d={d} onOpen={openSwap} />
                ) : (
                  <>
                    {row.reason !== d.title ? <AppText style={styles.fullTitle}>{d.title}</AppText> : null}
                    {d.why ? <AppText style={styles.why}>{d.why}</AppText> : d.summary ? <AppText style={styles.why}>{d.summary}</AppText> : null}
                    {first ? <CompactPlayerCard player={playerRef(first)} detail={first.note} trailing={trailing(first)} testID="decision-player" /> : null}
                    {others.map((p) => (
                      <CompactPlayerCard key={p.id ?? p.name} player={playerRef(p)} detail={p.note} trailing={trailing(p)} testID="decision-player" />
                    ))}
                    {d.facts.length > 0 ? <AppText style={styles.facts}>{d.facts.join(' · ')}</AppText> : null}
                    {d.item && d.kind !== 'waiver' && renderItemCard ? renderItemCard(d.item) : null}
                  </>
                )}
              </ExpandRow>
            );
          })}
        </ExpandRowGroup>
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
