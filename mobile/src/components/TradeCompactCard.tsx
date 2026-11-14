import React, { useMemo, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import CompactPlayerCard from './CompactPlayerCard';
import OvrGauge from './OvrGauge';
import { useThemeMode } from '../context/ThemeModeContext';
import PickAvatar from './PickAvatar';
import { avatarSize, fairnessMeter, type FactTone, type PlayerMode, type PlayerRef } from '../lib/playerAnatomy';
import { radii, spacing, type ThemeColors } from '../theme';

export interface TradeCardAsset {
  key: string;
  player?: PlayerRef;
  pickLabel?: string;
  detail?: string | null;
  /** Desk only. */
  value?: number | null;
  /** Desk only. */
  ovr?: number | null;
  /** Tap the card to open the player sheet. */
  onPress?: () => void;
}

function toneColor(tone: FactTone, colors: ThemeColors): string {
  switch (tone) {
    case 'success': return colors.success;
    case 'danger': return colors.danger;
    case 'warning': return colors.warning;
    case 'accent': return colors.accent;
    default: return colors.textTertiary;
  }
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
  children,
  defaultOpen = false,
  giveLabel = 'You send',
  getLabel = 'You get',
  testID = 'trade-compact-card',
}: {
  title: ReactNode;
  give: TradeCardAsset[];
  get: TradeCardAsset[];
  mode?: PlayerMode;
  verdictLabel?: string | null;
  /** The server's net value for the trade (positive = you win); wins over the asset sums, which can miss pick values. */
  netValue?: number | null;
  meta?: string[];
  children?: ReactNode;
  defaultOpen?: boolean;
  giveLabel?: string;
  getLabel?: string;
  testID?: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(defaultOpen);
  const sum = (xs: TradeCardAsset[]) => xs.reduce((n, a) => n + (a.value ?? 0), 0);
  const meter = fairnessMeter(sum(give), sum(get), mode, netValue);
  const hasBody = children != null && children !== false;
  const side = (label: string, assets: TradeCardAsset[]) => (
    <View style={styles.side}>
      <AppText style={styles.kicker}>{label}</AppText>
      {assets.map((a) =>
        a.player ? (
          <Pressable key={a.key} accessibilityRole={a.onPress ? 'button' : undefined} accessibilityLabel={a.onPress ? `Open ${a.player.name}` : undefined} disabled={!a.onPress} onPress={a.onPress}>
          <CompactPlayerCard
            player={a.player}
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
          </Pressable>
        ) : (
          <View key={a.key} style={styles.pickRow} testID="trade-pick-row">
            <PickAvatar label={a.pickLabel} size={avatarSize('row')} />
            <AppText style={styles.pick}>{a.pickLabel}</AppText>
          </View>
        ),
      )}
    </View>
  );
  return (
    <View style={styles.card} testID={testID}>
      <View>{typeof title === 'string' ? <AppText style={styles.title}>{title}</AppText> : title}</View>
      {meta.length > 0 ? <AppText style={styles.meta}>{meta.join(' · ')}</AppText> : null}
      {side(giveLabel, give)}
      {side(getLabel, get)}
      <View style={styles.meterRow} testID="fairness-meter">
        <View style={styles.track} accessible accessibilityRole="image" accessibilityLabel={verdictLabel && mode === 'desk' ? `${meter.description}. Market read: ${verdictLabel}` : meter.description}>
          <View style={[styles.fill, { left: `${Math.min(50, meter.position * 100)}%`, width: `${Math.abs(meter.position - 0.5) * 100}%`, backgroundColor: toneColor(meter.tone, colors) }]} testID="fairness-fill" />
          <View style={styles.mid} />
          <View style={[styles.marker, { left: `${meter.position * 100}%`, backgroundColor: toneColor(meter.tone, colors), borderColor: colors.surfaceSolid }]} testID="fairness-marker" />
        </View>
        <AppText style={[styles.verdict, { color: toneColor(meter.tone, colors) }]}>{meter.label}</AppText>
      </View>
      {hasBody ? (
        <>
          <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} onPress={() => setOpen((v) => !v)} style={styles.toggle}>
            <AppText style={styles.toggleText}>{open ? 'Hide details' : 'Show details'}</AppText>
          </Pressable>
          {open ? <View style={{ gap: spacing.md }}>{children}</View> : null}
        </>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: { gap: spacing.sm, padding: spacing.md, backgroundColor: colors.glass, borderColor: colors.glassBorder, borderWidth: 1, borderRadius: radii.tile },
    title: { fontSize: 15, fontWeight: '800', color: colors.textPrimary },
    meta: { fontSize: 12, color: colors.textTertiary },
    side: { gap: 2 },
    kicker: { fontSize: 12, fontWeight: '800', letterSpacing: 0.6, color: colors.textTertiary, textTransform: 'uppercase' },
    value: { fontSize: 14, fontWeight: '800', color: colors.textPrimary },
    pickRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44 },
    pick: { flex: 1, fontSize: 14, fontWeight: '700', color: colors.textPrimary },
    meterRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    track: { flex: 1, height: 8, borderRadius: 4, backgroundColor: 'rgba(255,255,255,0.12)', justifyContent: 'center' },
    fill: { position: 'absolute', top: 0, height: 8, borderRadius: 4, opacity: 0.55 },
    mid: { position: 'absolute', left: '50%', width: 2, height: 14, marginLeft: -1, backgroundColor: colors.textTertiary },
    marker: { position: 'absolute', width: 14, height: 14, borderRadius: 7, marginLeft: -7, borderWidth: 2 },
    verdict: { fontSize: 12, fontWeight: '800' },
    toggle: { minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' },
    toggleText: { fontSize: 12, fontWeight: '700', color: colors.accent },
  });
}
