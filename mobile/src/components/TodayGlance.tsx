import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import PickAvatar from './PickAvatar';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import { Collapse } from './Presence';
import PressableScale from './PressableScale';
import { useThemeMode } from '../context/ThemeModeContext';
import { playerHeadshotId, playerInitials } from '../lib/playerAnatomy';
import { tradeGainLabel, type TodayRoomChip, type TodayTile, type TodayTradeAsset, type TodayTradeIdea } from '../lib/todayView';
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
 * The one snapshot strip under "Do this now": Standing, Playoffs, Team rank (model: lib/todayView.ts todayTiles). It is a
 * single control: the whole strip opens My Team, which hosts the rank bars, position rooms and tiles. Web twin:
 * components/TodayGlance.tsx.
 */
export function TodaySnapshotStrip({ tiles, onOpen }: { tiles: TodayTile[]; onOpen: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (tiles.length === 0) return null;
  return (
    <PressableScale accessibilityRole="button" accessibilityLabel={`${tiles.map((t) => `${t.label.toLowerCase()} ${t.value} ${t.sub}`).join(', ')}. Open My Team`} onPress={onOpen} style={styles.tiles} testID="today-tiles">
      {tiles.map((tile, i) => (
        <View key={tile.key} style={[styles.tile, i > 0 ? styles.tileDivider : null]} testID={`today-tile-${tile.key}`}>
          <AppText style={styles.kicker}>{tile.label}</AppText>
          <AppText style={[styles.tileValue, { color: toneColor(tile.tone === 'muted' ? 'neutral' : tile.tone, colors) }]}>{tile.value}</AppText>
          <AppText style={styles.tileSub}>{tile.sub}</AppText>
        </View>
      ))}
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

/**
 * The best trade as ONE compact row: avatars of who you send, an arrow, who you get, and the gain in green. A trade that
 * costs value never reaches this row (lib/todayView.ts bestTradeIdea); no negative or red figure is ever drawn. The row
 * opens it in Trade Hub. Web twin: TodayTradeRow in components/TodayGlance.tsx.
 */
export function TodayTradeRow({ idea, deadline, onOpen, info }: { idea: TodayTradeIdea; deadline?: string | null; onOpen: () => void; info?: React.ReactNode }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const gain = tradeGainLabel(idea);
  const faces = (assets: TodayTradeAsset[]) =>
    assets.slice(0, 2).map((a) =>
      a.isPick ? <PickAvatar key={a.name} label={a.name} size={28} /> : <PlayerAvatar key={a.id ?? a.name} playerId={playerHeadshotId({ id: a.id, name: a.name })} tier={a.tier ?? undefined} size={28} fallbackLabel={playerInitials(a.name)} />,
    );
  const names = (assets: TodayTradeAsset[]) => assets.map((a) => a.name).join(' + ');
  return (
    <AccentCard accent={colors.accent} compact>
      <View style={styles.tradeHead}>
        <AppText style={[styles.kicker, { color: colors.accent }]}>{`BEST TRADE${deadline ? ` · DEADLINE ${deadline.toUpperCase()}` : ''}`}</AppText>
        {info}
      </View>
      <PressableScale testID="today-trade-idea" accessibilityRole="button" accessibilityLabel={`Best trade: ${idea.title}${gain ? `, ${gain} value` : ''}. Open in Trade Hub`} onPress={onOpen} style={styles.tradeRow}>
        <View style={styles.faces}>
          {faces(idea.send)}
          <AppText style={styles.tileSub}>→</AppText>
          {faces(idea.receive)}
        </View>
        <View style={styles.tradeText}>
          <AppText style={styles.tradeTitle}>{idea.title}</AppText>
          <AppText style={styles.tileSub}>{[idea.send.length > 0 ? names(idea.send) : null, idea.receive.length > 0 ? names(idea.receive) : null].filter(Boolean).join(' → ')}</AppText>
        </View>
        {gain ? (
          <AppText style={[styles.gain, { color: colors.success }]} testID="today-trade-gain">
            {gain}
          </AppText>
        ) : null}
      </PressableScale>
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    kicker: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, color: colors.textTertiary },
    tiles: { flexDirection: 'row', alignItems: 'stretch', minHeight: 60, borderRadius: radii.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface },
    tile: { flex: 1, minWidth: 0, alignItems: 'center', justifyContent: 'center', paddingVertical: spacing.xs, paddingHorizontal: spacing.xs },
    tileDivider: { borderLeftWidth: StyleSheet.hairlineWidth, borderLeftColor: colors.border },
    arrow: { alignSelf: 'center', paddingRight: spacing.md, fontSize: 20, color: colors.accent },
    tileValue: { fontSize: 20, fontWeight: '800' },
    tileSub: { fontSize: 12.5, color: colors.textTertiary },
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
    tradeHead: { flexDirection: 'row', alignItems: 'center' },
    tradeRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44 },
    faces: { flexDirection: 'row', alignItems: 'center', gap: 4 },
    tradeText: { flex: 1, minWidth: 0 },
    gain: { fontSize: 14, fontWeight: '800' },
    tradeTitle: { fontSize: 14.5, fontWeight: '700', color: colors.textPrimary },
  });
}
