import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import PlayerAvatar from './PlayerAvatar';
import ToneBadge from './ToneBadge';
import { Collapse } from './Presence';
import AnimatedCard from './AnimatedCard';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';
import type { TradeOutcomeChip, TradeChipTone } from '../lib/tradeOutcomeChips';

export interface TradeSummaryPlayer {
  key: string;
  playerId: string | null;
  name: string;
  position?: string | null;
  /** A draft pick: shown as a pick chip instead of an avatar. */
  isPick?: boolean;
}

function SideStack({ players, overlap }: { players: TradeSummaryPlayer[]; overlap: object }) {
  const { colors } = useThemeMode();
  const shown = players.slice(0, 3);
  const extra = players.length - shown.length;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 4 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center' }}>
        {shown.map((p, i) =>
          p.isPick ? (
            <ToneBadge key={p.key} label={p.name} color={colors.textSecondary} size="xs" shrink style={i > 0 ? overlap : undefined} />
          ) : (
            <PlayerAvatar key={p.key} playerId={p.playerId} name={p.name} position={p.position} size={32} style={i > 0 ? overlap : undefined} />
          ),
        )}
      </View>
      {extra > 0 ? <AppText style={{ fontSize: 12, fontWeight: '700', color: colors.textTertiary }}>+{extra}</AppText> : null}
    </View>
  );
}

/**
 * The compact one-card trade row (Trade History): an overlapped avatar stack for each side (picks as pick chips), "A for B" on one
 * line, a verdict badge, the value delta number, small chips for the result and the date muted. One calm card: no verdict stripe, no red (a loss is a muted "Down 12" chip, never red).
 * Web twin: web-next/src/components/ui/TradeSummaryRow.tsx.
 */
export default function TradeSummaryRow({
  partner,
  send,
  receive,
  swapText,
  chips,
  verdict,
  delta,
  date,
  children,
}: {
  partner: string;
  send: TradeSummaryPlayer[];
  receive: TradeSummaryPlayer[];
  swapText: string;
  chips: TradeOutcomeChip[];
  /** The verdict badge (green only for "worked out"; never red). */
  verdict?: TradeOutcomeChip | null;
  /** The single value delta number ("+12%"). */
  delta?: { label: string; tone: TradeChipTone } | null;
  date?: string;
  children?: React.ReactNode;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const toneColor = (tone: TradeChipTone) => (tone === 'success' ? colors.successBright : colors.textSecondary);
  return (
    <AnimatedCard style={styles.card}>
      <View style={styles.top}>
        <View style={styles.avatars} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          <SideStack players={send} overlap={styles.overlap} />
          <AppText style={styles.swapGlyph}>⇄</AppText>
          <SideStack players={receive} overlap={styles.overlap} />
        </View>
        <View style={styles.text}>
          <AppText style={styles.swap} numberOfLines={1}>
            {swapText || partner}
          </AppText>
          <AppText style={styles.sub} numberOfLines={1}>
            {date ? `${partner} · ${date}` : partner}
          </AppText>
        </View>
        {delta ? (
          <AppText testID="trade-value-delta" style={[styles.delta, { color: toneColor(delta.tone) }]}>
            {delta.label}
          </AppText>
        ) : null}
      </View>
      <View style={styles.chips}>
        {verdict ? <ToneBadge label={verdict.label} color={toneColor(verdict.tone)} /> : null}
        {chips.map((chip) => (
          <ToneBadge key={chip.key} label={chip.label} color={toneColor(chip.tone)} />
        ))}
      </View>
      {children ? (
        <>
          <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} accessibilityLabel={open ? 'Hide details' : 'Show details'} onPress={() => setOpen((v) => !v)} style={styles.toggle}>
            <AppText style={styles.toggleText}>{open ? 'Hide details' : 'Show details'}</AppText>
          </Pressable>
          <Collapse open={open}><View style={styles.body}>{children}</View></Collapse>
        </>
      ) : null}
    </AnimatedCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: { padding: spacing.md, gap: spacing.xs },
    top: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    avatars: { flexDirection: 'row', alignItems: 'center', gap: 6 },
    swapGlyph: { fontSize: 12, fontWeight: '700', color: colors.textTertiary },
    delta: { fontSize: 18, fontWeight: '900' },
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
