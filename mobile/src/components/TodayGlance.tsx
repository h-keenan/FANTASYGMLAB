import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import PickAvatar from './PickAvatar';
import PlayerAvatar from './PlayerAvatar';
import PlayerName from './PlayerName';
import PositionBadge from './PositionBadge';
import { Collapse } from './Presence';
import PressableScale from './PressableScale';
import { useThemeMode } from '../context/ThemeModeContext';
import { playerHeadshotId, playerInitials } from '../lib/playerAnatomy';
import type { TodayRoomChip, TodayTile, TodayTradeAsset, TodayTradeIdea } from '../lib/todayView';
import { tradeIdeaGainText } from '../lib/tradeIdeaSummary';
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
 * The compact tile row under "Do this now": Standing, Playoffs, Trades (model: lib/todayView.ts todayTiles). One tile per
 * fact; each opens the screen that owns the detail. Web twin: components/TodayGlance.tsx.
 */
export function TodayTiles({ tiles, onOpen }: { tiles: TodayTile[]; onOpen: (key: TodayTile['key']) => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (tiles.length === 0) return null;
  return (
    <View style={styles.tiles} testID="today-tiles">
      {tiles.map((tile) => (
        <PressableScale
          key={tile.key}
          accessibilityRole="button"
          accessibilityLabel={`${tile.label.toLowerCase()}: ${tile.value} ${tile.sub}. Open`}
          onPress={() => onOpen(tile.key)}
          style={styles.tile}
          testID={`today-tile-${tile.key}`}
        >
          <AppText style={styles.kicker}>{tile.label}</AppText>
          <AppText style={[styles.tileValue, { color: toneColor(tile.tone === 'muted' ? 'neutral' : tile.tone, colors) }]}>{tile.value}</AppText>
          <AppText style={styles.tileSub}>{tile.sub}</AppText>
        </PressableScale>
      ))}
    </View>
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

function TradeSide({ label, assets }: { label: string; assets: TodayTradeAsset[] }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (assets.length === 0) return null;
  return (
    <View style={styles.sideRow}>
      <AppText style={[styles.kicker, styles.sideLabel]}>{label.toUpperCase()}</AppText>
      {assets.slice(0, 2).map((a) => (
        <View key={a.id ?? a.name} style={styles.asset}>
          {a.isPick ? (
            <PickAvatar label={a.name} size={24} />
          ) : (
            <PlayerAvatar playerId={playerHeadshotId({ id: a.id, name: a.name })} tier={a.tier ?? undefined} size={24} fallbackLabel={playerInitials(a.name)} />
          )}
          {a.isPick ? <AppText style={styles.assetName}>{a.name}</AppText> : <PlayerName name={a.name} style={styles.assetName} />}
          {a.position ? <PositionBadge position={a.position} /> : null}
        </View>
      ))}
      {assets.length > 2 ? <AppText style={styles.tileSub}>+{assets.length - 2}</AppText> : null}
    </View>
  );
}

/** The trade idea as one card (concept B): kicker, "Get a QB from Team Iron", who goes and who comes, the value gain. The whole card opens it in Trade Hub. */
export function TodayTradeIdeaCard({ idea, deadline, onOpen }: { idea: TodayTradeIdea; deadline?: string | null; onOpen: () => void }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const gain = idea.gain != null && idea.gain !== 0 ? tradeIdeaGainText(idea.gain) : null;
  return (
    <AccentCard accent={colors.accent} compact onPress={onOpen}>
      <View testID="today-trade-idea" accessible accessibilityRole="button" accessibilityLabel={`Trade idea: ${idea.title}. Open in Trade Hub`} style={styles.tradeBody}>
        <View style={styles.tradeHead}>
          <AppText style={[styles.kicker, { color: colors.accent }]}>{`TRADE IDEA${deadline ? ` · DEADLINE ${deadline.toUpperCase()}` : ''}`}</AppText>
          {gain ? <AppText style={[styles.gain, { color: (idea.gain ?? 0) > 0 ? colors.success : colors.danger }]}>{gain} value</AppText> : null}
        </View>
        <AppText style={styles.tradeTitle}>{idea.title}</AppText>
        <TradeSide label="Send" assets={idea.send} />
        <TradeSide label="Get" assets={idea.receive} />
      </View>
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    kicker: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, color: colors.textTertiary },
    tiles: { flexDirection: 'row', gap: spacing.sm },
    tile: { flex: 1, minWidth: 0, minHeight: 76, alignItems: 'center', justifyContent: 'center', gap: 2, borderRadius: radii.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surface, paddingHorizontal: spacing.xs },
    tileValue: { fontSize: 24, fontWeight: '800' },
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
    tradeBody: { gap: 4 },
    tradeHead: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    gain: { fontSize: 12.5, fontWeight: '800' },
    tradeTitle: { fontSize: 16, fontWeight: '800', color: colors.textPrimary },
    sideRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: spacing.sm },
    sideLabel: { width: 36 },
    asset: { flexDirection: 'row', alignItems: 'center', gap: 6, flexShrink: 1 },
    assetName: { fontSize: 14, fontWeight: '700', color: colors.textPrimary },
  });
}
