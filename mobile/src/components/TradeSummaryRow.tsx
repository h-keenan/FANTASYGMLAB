import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import PlayerAvatar from './PlayerAvatar';
import ToneBadge from './ToneBadge';
import AnimatedCard from './AnimatedCard';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';
import type { TradeOutcomeChip } from '../lib/tradeOutcomeChips';

export interface TradeSummaryPlayer {
  key: string;
  playerId: string | null;
  name: string;
  position?: string | null;
}

/**
 * The compact one-card trade row (Trade History): a PlayerAvatar for each side, "A for B" on one line, small chips for the
 * result and the date muted. One calm card: no verdict stripe, no red (a loss is a muted "Down 12" chip, never red).
 * Web twin: web-next/src/components/ui/TradeSummaryRow.tsx.
 */
export default function TradeSummaryRow({
  partner,
  send,
  receive,
  swapText,
  chips,
  date,
  children,
}: {
  partner: string;
  send: TradeSummaryPlayer[];
  receive: TradeSummaryPlayer[];
  swapText: string;
  chips: TradeOutcomeChip[];
  date?: string;
  children?: React.ReactNode;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  return (
    <AnimatedCard style={styles.card}>
      <View style={styles.top}>
        <View style={styles.avatars}>
          {[...send.slice(0, 2), ...receive.slice(0, 2)].map((p, i) => (
            <PlayerAvatar key={p.key} playerId={p.playerId} name={p.name} position={p.position} size={32} style={i > 0 ? styles.overlap : undefined} />
          ))}
        </View>
        <View style={styles.text}>
          <AppText style={styles.swap} numberOfLines={1}>
            {swapText || partner}
          </AppText>
          <AppText style={styles.sub} numberOfLines={1}>
            {date ? `${partner} · ${date}` : partner}
          </AppText>
        </View>
      </View>
      <View style={styles.chips}>
        {chips.map((chip) => (
          <ToneBadge key={chip.key} label={chip.label} color={chip.tone === 'success' ? colors.successBright : colors.textSecondary} />
        ))}
      </View>
      {children ? (
        <>
          <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} accessibilityLabel={open ? 'Hide details' : 'Show details'} onPress={() => setOpen((v) => !v)} style={styles.toggle}>
            <AppText style={styles.toggleText}>{open ? 'Hide details' : 'Show details'}</AppText>
          </Pressable>
          {open ? <View style={styles.body}>{children}</View> : null}
        </>
      ) : null}
    </AnimatedCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: { padding: spacing.md, gap: spacing.xs },
    top: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    avatars: { flexDirection: 'row', alignItems: 'center' },
    overlap: { marginLeft: -8 },
    text: { flex: 1, minWidth: 0 },
    swap: { fontSize: 15, fontWeight: '800', color: colors.textPrimary },
    sub: { fontSize: 12, color: colors.textTertiary },
    chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs },
    toggle: { alignSelf: 'flex-start', minHeight: 44, justifyContent: 'center' },
    toggleText: { fontSize: 13, fontWeight: '700', color: colors.accent },
    body: { gap: spacing.sm },
  });
}
