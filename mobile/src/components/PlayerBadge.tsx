import React, { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import { Sheet } from './Sheet';
import { withAlpha } from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { BADGES, badgeLegend, badgeTitle, badgesAriaLabel, resolveBadges, type BadgeInput, type BadgeKind, type BadgeTone } from '../lib/playerBadges';
import { spacing, type ThemeColors } from '../theme';

function toneColor(tone: BadgeTone, colors: ThemeColors): string {
  switch (tone) {
    case 'success': return colors.success;
    case 'danger': return colors.danger;
    case 'warning': return colors.warning;
    case 'accent': return colors.accent;
    case 'action': return colors.accent;
    default: return colors.textTertiary;
  }
}

/**
 * ONE glyph badge (twin of web-next components/ui/PlayerBadge.tsx; docs/ui-patterns.md, "PlayerBadge"): a 20pt tinted
 * circle/capsule with a letter or symbol. The full word is the accessibility label (VoiceOver / TalkBack) and the legend
 * sheet; `showDetail` (quick view headers) adds the detail text ("Out 2 wks").
 */
export function PlayerBadge({ kind, detail, showDetail = false }: { kind: BadgeKind; detail?: string | null; showDetail?: boolean }) {
  const { colors } = useThemeMode();
  const spec = BADGES[kind];
  const color = toneColor(spec.tone, colors);
  const title = badgeTitle({ kind, detail });
  return (
    <View
      accessible
      accessibilityRole="image"
      accessibilityLabel={title}
      testID="player-badge"
      style={[styles.badge, { backgroundColor: withAlpha(color, 0.15), borderColor: withAlpha(color, 0.45) }, showDetail && detail ? styles.withDetail : null]}
    >
      <AppText style={[styles.glyph, { color }]} importantForAccessibility="no">{spec.glyph}</AppText>
      {showDetail && detail ? <AppText style={[styles.detail, { color }]} importantForAccessibility="no">{detail}</AppText> : null}
    </View>
  );
}

/** A row's badge strip: severity order, context-suppressed kinds hidden, at most `max` glyphs and "+n". `onLegend` makes it a tap target. */
export function PlayerBadges({
  badges,
  suppress,
  max,
  showDetail = false,
  onLegend,
}: {
  badges: ReadonlyArray<BadgeInput | null | undefined | false>;
  suppress?: ReadonlyArray<BadgeKind>;
  max?: number;
  showDetail?: boolean;
  onLegend?: () => void;
}) {
  const { colors } = useThemeMode();
  const r = resolveBadges(badges, { suppress, max });
  if (r.shown.length === 0) return null;
  const strip = (
    <>
      {r.shown.map((b) => (
        <PlayerBadge key={b.kind} kind={b.kind} detail={b.detail} showDetail={showDetail} />
      ))}
      {r.overflow > 0 ? <AppText style={[styles.more, { color: colors.textTertiary }]} importantForAccessibility="no">+{r.overflow}</AppText> : null}
    </>
  );
  if (onLegend) {
    return (
      <Pressable onPress={onLegend} accessibilityRole="button" accessibilityLabel={`${badgesAriaLabel(r)}. What the symbols mean`} style={styles.strip} hitSlop={{ top: 12, bottom: 12, left: 6, right: 6 }} testID="player-badges">
        {strip}
      </Pressable>
    );
  }
  return (
    <View style={styles.strip} accessible accessibilityLabel={badgesAriaLabel(r)} testID="player-badges">
      {strip}
    </View>
  );
}

/** The legend sheet: every symbol (or just `kinds`), its glyph and what it means. */
export function BadgeLegendSheet({ open, onClose, kinds }: { open: boolean; onClose: () => void; kinds?: ReadonlyArray<BadgeKind> }) {
  const { colors } = useThemeMode();
  return (
    <Sheet open={open} onClose={onClose} title="What the symbols mean">
      <View testID="badge-legend">
        {badgeLegend(kinds).map((spec) => (
          <View key={spec.kind} style={[styles.legendRow, { borderBottomColor: colors.border }]}>
            <PlayerBadge kind={spec.kind} />
            <View style={{ flex: 1, minWidth: 0 }}>
              <AppText style={{ fontSize: 14, fontWeight: '800', color: colors.textPrimary }}>{spec.label}</AppText>
              <AppText style={{ fontSize: 12, color: colors.textTertiary }}>{spec.legend}</AppText>
            </View>
          </View>
        ))}
      </View>
    </Sheet>
  );
}

/** A small "Key" button for a list header: opens the legend sheet. */
export function BadgeLegendButton({ kinds }: { kinds?: ReadonlyArray<BadgeKind> }) {
  const { colors } = useThemeMode();
  const [open, setOpen] = useState(false);
  return (
    <>
      <Pressable onPress={() => setOpen(true)} accessibilityRole="button" accessibilityLabel="What the symbols mean" style={styles.keyButton}>
        <AppText style={{ fontSize: 12, fontWeight: '800', color: colors.textTertiary }}>ⓘ Key</AppText>
      </Pressable>
      <BadgeLegendSheet open={open} onClose={() => setOpen(false)} kinds={kinds} />
    </>
  );
}

const styles = StyleSheet.create({
  badge: { minWidth: 20, height: 20, paddingHorizontal: 5, borderRadius: 999, borderWidth: StyleSheet.hairlineWidth * 2, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 4 },
  withDetail: { paddingLeft: 6, paddingRight: 8 },
  glyph: { fontSize: 12, fontWeight: '800', lineHeight: 14 },
  detail: { fontSize: 12, fontWeight: '700', lineHeight: 14 },
  more: { fontSize: 12, fontWeight: '700' },
  strip: { flexDirection: 'row', alignItems: 'center', columnGap: spacing.xs, alignSelf: 'flex-start' },
  legendRow: { flexDirection: 'row', alignItems: 'center', columnGap: spacing.md, paddingVertical: spacing.sm, borderBottomWidth: StyleSheet.hairlineWidth },
  keyButton: { minHeight: 44, minWidth: 44, alignItems: 'center', justifyContent: 'center' },
});
