import React, { useMemo } from 'react';
import { StyleSheet, View, type StyleProp, type ViewStyle } from 'react-native';

import AppText from './AppText';
import { TradeAssetList } from './TradeAssetRow';
import { useThemeMode } from '../context/ThemeModeContext';
import type { PresentationAsset } from '../lib/api';
import { SIDE_TINT_ALPHA, TRADE_SIDE_LABEL, withAlpha } from '../lib/tradeSideLabels';
import { spacing, type ThemeColors } from '../theme';

/**
 * One side of a trade package: send (red dot) or get (green dot), an
 * uppercase label, an optional side total, and the asset rows on a faint
 * wash of the side's own color. Mirrors web-next's `ExchangeSide`
 * (components/TradeAssetExchange.tsx) so Dashboard, GM Plan, Trade Hub,
 * Finder and Portfolio signals stop carrying five local copies.
 */
export default function ExchangeSide({
  side,
  label,
  assets,
  total,
  onPressPlayer,
  onPressPick,
  style,
}: {
  side: 'send' | 'get';
  /** Override the default label ("You send" / "You get"), e.g. TRADE_SIDE_LABEL.receive. */
  label?: string;
  assets: PresentationAsset[];
  total?: number | null;
  onPressPlayer?: (asset: PresentationAsset) => void;
  onPressPick?: (asset: PresentationAsset) => void;
  style?: StyleProp<ViewStyle>;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const dot = side === 'send' ? colors.danger : colors.success;
  return (
    <View style={[styles.side, style]}>
      <View style={styles.labelRow}>
        <View style={[styles.dot, { backgroundColor: dot }]} />
        <AppText style={styles.label}>{label ?? TRADE_SIDE_LABEL[side]}</AppText>
        {total != null ? <AppText style={styles.total}>{Math.round(total).toLocaleString()}</AppText> : null}
      </View>
      {assets.length === 0 ? (
        <AppText style={styles.none}>None selected</AppText>
      ) : (
        <View style={[styles.list, { backgroundColor: withAlpha(dot, SIDE_TINT_ALPHA) }]}>
          <TradeAssetList assets={assets} onPressPlayer={onPressPlayer} onPressPick={onPressPick} />
        </View>
      )}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    side: { gap: 4, minWidth: 0 },
    labelRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
    dot: { width: 6, height: 6, borderRadius: 3 },
    label: {
      fontSize: 11,
      fontWeight: '700',
      color: colors.textTertiary,
      textTransform: 'uppercase',
      letterSpacing: 0.9,
    },
    total: { marginLeft: 'auto', fontSize: 14, fontWeight: '900', color: colors.textSecondary },
    none: { fontSize: 12, color: colors.textTertiary },
    list: { paddingHorizontal: spacing.sm, paddingVertical: spacing.xs },
  });
}
