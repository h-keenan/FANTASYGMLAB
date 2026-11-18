import React, { useMemo, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import CompactPlayerCard from './CompactPlayerCard';
import OvrGauge from './OvrGauge';
import { useThemeMode } from '../context/ThemeModeContext';
import PickAvatar from './PickAvatar';
import { PickTap } from './PlayerOpenContext';
import FairnessMeterRow from './FairnessMeterRow';
import { SkeletonTradeCard } from './Skeleton';
import { avatarSize, fairnessMeter, type FairnessMeter, type PlayerMode, type PlayerRef } from '../lib/playerAnatomy';
import { radii, spacing, type ThemeColors } from '../theme';
import { Collapse, PresenceSwap } from './Presence';
import TradeResolvedRow from './TradeResolvedRow';

export interface TradeCardAsset {
  key: string;
  player?: PlayerRef;
  pickLabel?: string;
  detail?: string | null;
  /** Desk only. */
  value?: number | null;
  /** Desk only. */
  ovr?: number | null;
  /** Overrides the default tap (the shared opener: Desk quick view, or the sim's sheet inside Fantasy Sim). */
  onPress?: () => void;
  /** A pick: its id (the sim pick sheet), detail line and an override opener. */
  pickId?: string;
  pickDetail?: string | null;
  onOpenPick?: () => void;
  /** Opt out of the tap, with the reason (a picker row that selects). */
  nonInteractive?: string;
}

/** One asset as a compact player card (avatar included, tap opens the sheet) or a pick row with the round pick avatar. Shared by the trade card and the builder. */
export function TradeAssetCard({ asset: a, mode }: { asset: TradeCardAsset; mode: PlayerMode }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (a.player) {
    return (
      <CompactPlayerCard
        player={a.player}
        shortName
        onOpen={a.onPress}
        nonInteractive={a.nonInteractive}
        detail={a.detail}
        trailing={
          mode === 'desk' && (a.value != null || a.ovr != null) ? (
            <>
              {a.ovr != null ? <OvrGauge rating={a.ovr} size="sm" /> : null}
              {a.value != null ? <AppText style={styles.value}>{Math.round(a.value).toLocaleString('en-US')}</AppText> : null}
            </>
          ) : undefined
        }
      />
    );
  }
  return (
    <PickTap label={a.pickLabel ?? ''} id={a.pickId} detail={a.pickDetail} onOpen={a.onOpenPick} nonInteractive={a.nonInteractive}>
      <View style={styles.pickRow} testID="trade-pick-row">
        <PickAvatar label={a.pickLabel} size={avatarSize('row')} />
        <View style={styles.pickText}>
          <AppText style={styles.pick}>{a.pickLabel}</AppText>
          {a.pickDetail ? <AppText style={styles.pickDetail}>{a.pickDetail}</AppText> : null}
        </View>
        {mode === 'desk' && a.value != null ? <AppText style={styles.value}>{Math.round(a.value).toLocaleString('en-US')}</AppText> : null}
      </View>
    </PickTap>
  );
}

/**
 * Trade card (idea / offer / inbox): compact player cards on a give and a get side, a fairness meter row, and details
 * that expand in place. `mode="sim"` shows plain words, never the hidden value. Twin of web ui/TradeCompactCard.tsx.
 */
export default function TradeCompactCard({
  title,
  give,
  get,
  mode = 'desk',
  verdictLabel,
  netValue,
  meta = [],
  note,
  children,
  defaultOpen = false,
  giveLabel = 'You send',
  getLabel = 'You get',
  testID = 'trade-compact-card',
  meter: meterOverride,
  resolved,
}: {
  title: ReactNode;
  give: TradeCardAsset[];
  get: TradeCardAsset[];
  mode?: PlayerMode;
  verdictLabel?: string | null;
  /** The server's net value for the trade (positive = you win); wins over the asset sums, which can miss pick values. */
  netValue?: number | null;
  meta?: string[];
  /** One short neutral line under the meta line (a trade idea's partner-fit reason). */
  note?: string | null;
  children?: ReactNode;
  defaultOpen?: boolean;
  giveLabel?: string;
  getLabel?: string;
  testID?: string;
  /** Replaces the computed fairness meter; null hides it (a card whose verdict is stated elsewhere, e.g. their counter). */
  meter?: FairnessMeter | null;
  /** The card was answered (accepted / declined): it collapses into one `TradeResolvedRow` instead of vanishing. */
  resolved?: { kind: 'accepted' | 'declined'; label: string } | null;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(defaultOpen);
  const sum = (xs: TradeCardAsset[]) => xs.reduce((n, a) => n + (a.value ?? 0), 0);
  const meter = meterOverride === undefined ? fairnessMeter(sum(give), sum(get), mode, netValue) : meterOverride;
  const hasBody = children != null && children !== false;
  const side = (label: string, assets: TradeCardAsset[]) => (
    <View style={styles.side}>
      <AppText style={styles.kicker}>{label}</AppText>
      {assets.map((a) => (
        <TradeAssetCard key={a.key} asset={a} mode={mode} />
      ))}
    </View>
  );
  return (
    <View style={styles.card} testID={testID}>
      <PresenceSwap swapKey={resolved ? 'resolved' : 'open'} style={{ gap: spacing.sm }}>
      {resolved ? <TradeResolvedRow kind={resolved.kind} label={resolved.label} /> : <>
      <View>{typeof title === 'string' ? <AppText style={styles.title}>{title}</AppText> : title}</View>
      {meta.length > 0 ? <AppText style={styles.meta}>{meta.join(' · ')}</AppText> : null}
      {note ? <AppText style={styles.note} testID="trade-idea-partner-fit">Their side: {note}</AppText> : null}
      {side(giveLabel, give)}
      {side(getLabel, get)}
      {meter ? <FairnessMeterRow meter={meter} accessibilityLabel={verdictLabel && mode === 'desk' ? `${meter.description}. Market read: ${verdictLabel}` : undefined} /> : null}
      {hasBody ? (
        <>
          <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} onPress={() => setOpen((v) => !v)} style={styles.toggle}>
            <AppText style={styles.toggleText}>{open ? 'Hide details' : 'Show details'}</AppText>
          </Pressable>
          <Collapse open={open}>
            <View style={{ gap: spacing.md }}>{children}</View>
          </Collapse>
        </>
      ) : null}
      </>}
      </PresenceSwap>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: { gap: spacing.sm, padding: spacing.md, backgroundColor: colors.glass, borderColor: colors.glassBorder, borderWidth: 1, borderRadius: radii.tile },
    title: { fontSize: 15, fontWeight: '800', color: colors.textPrimary },
    meta: { fontSize: 12, color: colors.textTertiary },
    note: { fontSize: 12, color: colors.textSecondary },
    side: { gap: 2 },
    kicker: { fontSize: 12, fontWeight: '800', letterSpacing: 0.6, color: colors.textTertiary, textTransform: 'uppercase' },
    value: { fontSize: 14, fontWeight: '800', color: colors.textPrimary },
    pickRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44 },
    pickText: { flex: 1 },
    pick: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    pickDetail: { fontSize: 12, color: colors.textSecondary },
    toggle: { minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' },
    toggleText: { fontSize: 12, fontWeight: '700', color: colors.accent },
  });
}

/** The loading silhouette of a `TradeCompactCard` (title, give and get avatar rows, meter). */
export function TradeCompactCardSkeleton({ assets = 2 }: { assets?: number }) {
  return <SkeletonTradeCard assets={assets} />;
}
