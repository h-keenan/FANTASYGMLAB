import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import PositionBadge from './PositionBadge';
import { Collapse } from './Presence';
import PressableScale from './PressableScale';
import { useThemeMode } from '../context/ThemeModeContext';
import type { TodayRoomChip, TodayStandingPart } from '../lib/todayView';
import { LINK_HIT_SLOP, radii, spacing, type ThemeColors } from '../theme';

type Tone = 'success' | 'danger' | 'warning' | 'accent' | 'muted' | 'neutral';

function toneColor(tone: Tone, colors: ThemeColors): string {
  switch (tone) {
    case 'success': return colors.success;
    case 'danger': return colors.danger;
    case 'warning': return colors.warning;
    case 'accent': return colors.accent;
    case 'muted': return colors.textTertiary;
    default: return colors.textPrimary;
  }
}

/**
 * The standing as ONE slim line under "Do this now" ("8th of 12 · 6-4 · Playoffs 72% · Rank #3", model:
 * lib/todayView.ts todayStandingLine). A single control that opens My Team (rank bars, position rooms, tiles). Web twin:
 * components/TodayGlance.tsx.
 */
export function TodayStandingLine({ parts, onOpen }: { parts: TodayStandingPart[]; onOpen: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (parts.length === 0) return null;
  return (
    <PressableScale accessibilityRole="button" accessibilityLabel={`${parts.map((p) => p.text).join(', ')}. Open My Team`} onPress={onOpen} style={styles.standingLine} testID="today-tiles">
      <View style={styles.standingParts}>
        {parts.map((p, i) => (
          <View key={p.key} style={styles.standingPart} testID={`today-tile-${p.key}`}>
            {i > 0 ? <AppText style={styles.standingDot}>·</AppText> : null}
            <AppText style={[styles.standingText, { color: toneColor(p.tone === 'muted' ? 'neutral' : p.tone, colors) }]}>{p.text}</AppText>
          </View>
        ))}
      </View>
      <AppText style={styles.arrow}>›</AppText>
    </PressableScale>
  );
}

/** Position rooms as small chips that open into one meter bar per room (the bars draw the room's label, not a measurement). */
export function TodayRooms({ chips, onOpenTrades }: { chips: TodayRoomChip[]; onOpenTrades: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  if (chips.length === 0) return null;
  const weakest = chips.find((c) => c.weakest);
  const color = (c: TodayRoomChip) => (c.tone === 'muted' ? colors.textSecondary : toneColor(c.tone, colors));
  return (
    <AccentCard accent={weakest ? colors.warning : colors.accent} compact>
      <View testID="today-rooms">
        <Pressable
          accessibilityRole="button"
          accessibilityState={{ expanded: open }}
          accessibilityLabel={`Position rooms: ${chips.map((c) => `${c.position} ${c.label}`).join(', ')}. ${open ? 'Collapse' : 'Expand'}`}
          onPress={() => setOpen((v) => !v)}
          style={styles.roomsHeader}
        >
          <View style={styles.roomsText}>
            <AppText style={styles.kicker}>POSITION ROOMS</AppText>
            <View style={styles.chipWrap}>
              {chips.map((c) => (
                <View key={c.position} style={[styles.chip, { borderColor: color(c), backgroundColor: `${color(c)}1A` }]} testID={`today-room-chip-${c.position}`}>
                  <AppText style={[styles.chipText, { color: color(c) }]}>
                    {c.position}
                    {c.mark === '!' ? ' !' : c.mark === 'check' ? ' ✓' : ''}
                  </AppText>
                </View>
              ))}
            </View>
          </View>
          <AppText style={styles.expand}>{open ? 'Hide ⌃' : 'Expand ⌄'}</AppText>
        </Pressable>
        <Collapse open={open}>
          <View style={styles.bars}>
            {chips.map((c) => (
              <View key={c.position} style={styles.barRow} accessible accessibilityLabel={`${c.position} room: ${c.label}`}>
                <View style={styles.barBadge}>
                  <PositionBadge position={c.position} />
                </View>
                <View style={styles.barTrack}>
                  <View style={{ width: `${Math.round(c.fill * 100)}%`, height: '100%', backgroundColor: color(c) }} />
                </View>
                <AppText style={[styles.barLabel, { color: color(c) }]}>{c.label}</AppText>
              </View>
            ))}
            {weakest ? (
              <PressableScale accessibilityRole="link" onPress={onOpenTrades} hitSlop={LINK_HIT_SLOP} style={styles.link}>
                <AppText style={styles.linkText}>Improve {weakest.position} first: Trade Hub ideas ›</AppText>
              </PressableScale>
            ) : null}
          </View>
        </Collapse>
      </View>
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    kicker: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, color: colors.textTertiary },
    standingLine: { flexDirection: 'row', alignItems: 'center', minHeight: 44, paddingLeft: spacing.md, borderRadius: radii.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface },
    standingParts: { flex: 1, minWidth: 0, flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center' },
    standingPart: { flexDirection: 'row', alignItems: 'center' },
    standingDot: { marginHorizontal: spacing.sm, color: colors.textTertiary, fontWeight: '800' },
    standingText: { fontSize: 14, fontWeight: '800' },
    arrow: { alignSelf: 'center', paddingRight: spacing.md, fontSize: 20, color: colors.accent },
    roomsHeader: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44 },
    roomsText: { flex: 1, minWidth: 0, gap: 4 },
    chipWrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
    chip: { minHeight: 24, paddingHorizontal: 8, borderRadius: radii.pill, borderWidth: 1, justifyContent: 'center' },
    chipText: { fontSize: 12.5, fontWeight: '800' },
    expand: { fontSize: 13, fontWeight: '700', color: colors.accent },
    bars: { gap: spacing.sm, paddingTop: spacing.xs },
    barRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    barBadge: { width: 36 },
    barTrack: { flex: 1, height: 8, borderRadius: radii.pill, overflow: 'hidden', backgroundColor: colors.border },
    barLabel: { fontSize: 12.5, fontWeight: '700', minWidth: 72, textAlign: 'right' },
    link: { minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' },
    linkText: { color: colors.accent, fontWeight: '700', fontSize: 14 },
  });
}
