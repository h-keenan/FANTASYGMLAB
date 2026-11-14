import React, { useEffect, useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, View } from 'react-native';

import AppText from './AppText';
import PositionBadge from './PositionBadge';
import { simToneColor } from './SimGameParts';
import { useThemeMode } from '../context/ThemeModeContext';
import { api } from '../lib/api';
import {
  simDraftBestByPosition,
  simDraftNeedPills,
  simDraftProgress,
  simDraftTeamEmblem,
} from '../lib/simDraft';
import { simFmtValue, type SimDraftState, type SimGamePlayer, type SimPos, type SimSlot } from '../lib/simGame';
import { radii, spacing, type ThemeColors } from '../theme';

function lastName(name: string): string {
  const parts = name.trim().split(/\s+/);
  return parts.length > 1 ? parts[parts.length - 1] : name;
}

/** Fixed-size team emblem: initials in a ring, accented for your own team. */
export function SimDraftEmblem({ name, you = false }: { name: string; you?: boolean }) {
  const { colors } = useThemeMode();
  const color = you ? colors.accent : colors.textSecondary;
  return (
    <View style={{ width: 24, height: 24, borderRadius: 12, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: color, backgroundColor: you ? colors.accentMuted : colors.glass }}>
      <AppText style={{ fontSize: 12, fontWeight: '800', color }}>{simDraftTeamEmblem(name)}</AppText>
    </View>
  );
}

/**
 * The expanded on-the-clock body (inside the clock CompactModule): progress bar, best available by position and
 * your roster needs as colored position pills. The status line, recent picks and mini board live elsewhere.
 */
export function SimDraftHero({
  gameId,
  draft,
  teams,
  slots,
  positions,
  tick,
  onOpen,
}: {
  gameId: string;
  draft: SimDraftState;
  teams: number;
  slots: SimSlot[];
  positions: SimPos[];
  tick: number;
  onOpen: (player: SimGamePlayer) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const progress = simDraftProgress(draft, teams);
  const needs = simDraftNeedPills(draft.your_roster, slots);
  const [best, setBest] = useState<Record<string, SimGamePlayer | null>>({});
  const pickCount = draft.picks?.length ?? 0;
  const done = draft.status === 'complete';

  useEffect(() => {
    if (done) return;
    let cancelled = false;
    Promise.all(
      positions.map((pos) =>
        Promise.resolve(api.getSimGamePlayers(gameId, `pos=${pos}&status=available&sort=adp&page=1&page_size=1`))
          .then((body) => [pos, body?.items?.[0] ?? null] as const)
          .catch(() => [pos, null] as const),
      ),
    ).then((entries) => {
      if (!cancelled) setBest(Object.fromEntries(entries));
    });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [gameId, tick, pickCount, done]);

  const strip = simDraftBestByPosition(
    positions.map((pos) => best[pos]).filter((p): p is SimGamePlayer => Boolean(p)),
    positions,
  );

  return (
    <View style={styles.wrap} testID="draft-hero">
      <View style={styles.block}>
        <View style={styles.track} accessibilityRole="progressbar" accessibilityLabel="Draft progress" accessibilityValue={{ min: 0, max: progress.total, now: progress.made }}>
          <View style={[styles.fill, { width: `${Math.round(progress.fraction * 100)}%` }]} />
        </View>
      </View>

      {!done ? (
        <View style={styles.block}>
          <AppText style={styles.kicker}>Best available</AppText>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.strip} style={styles.stripBox}>
            {strip.map(({ pos, player }) => (
              <Pressable
                key={pos}
                disabled={!player}
                onPress={() => player && onOpen(player)}
                accessibilityRole="button"
                accessibilityLabel={player ? `Best available ${pos}: ${player.name}` : `No ${pos} left`}
                style={[styles.pickChip, { minWidth: 96, opacity: player ? 1 : 0.5 }]}
              >
                <PositionBadge position={pos} />
                <View>
                  <AppText style={styles.chipName}>{player ? lastName(player.name) : '-'}</AppText>
                  <AppText style={styles.chipMeta}>ADP {simFmtValue(player?.adp)}</AppText>
                </View>
              </Pressable>
            ))}
          </ScrollView>
        </View>
      ) : null}

      <View style={styles.block}>
        <AppText style={styles.kicker}>Your needs</AppText>
        <View style={styles.needs}>
          {needs.map((n) => (
            <View key={n.pos} style={styles.need} accessibilityLabel={`${n.pos}: ${n.have} of ${n.starters} starters`}>
              <PositionBadge position={n.pos} label={`${n.pos} ${n.have}/${n.starters}`} />
              <View style={[styles.dot, { backgroundColor: simToneColor(n.tone, colors) }]} />
            </View>
          ))}
        </View>
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    wrap: { gap: spacing.md },
    block: { gap: 6 },
    between: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    strong: { fontSize: 13, fontWeight: '700', color: colors.textSecondary },
    muted: { fontSize: 12, color: colors.textTertiary },
    small: { flex: 1, fontSize: 13, color: colors.textSecondary },
    kicker: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, textTransform: 'uppercase', color: colors.textTertiary },
    track: { height: 8, borderRadius: radii.pill, backgroundColor: colors.glass, overflow: 'hidden' },
    fill: { height: '100%', borderRadius: radii.pill, backgroundColor: colors.accent },
    etaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    etaBox: { minWidth: 48, height: 40, paddingHorizontal: 8, borderRadius: radii.md, alignItems: 'center', justifyContent: 'center' },
    etaText: { fontSize: 18, fontWeight: '800', fontVariant: ['tabular-nums'] },
    stripBox: { minHeight: 44, flexGrow: 0 },
    strip: { gap: spacing.sm, alignItems: 'center' },
    pickChip: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 6,
      height: 44,
      paddingHorizontal: spacing.sm,
      borderRadius: radii.md,
      backgroundColor: colors.glass,
      borderBottomWidth: 3,
      borderBottomColor: colors.borderStrong,
    },
    chipName: { fontSize: 12, fontWeight: '700', color: colors.textPrimary },
    chipMeta: { fontSize: 12, color: colors.textTertiary },
    needs: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
    need: { flexDirection: 'row', alignItems: 'center', gap: 4 },
    dot: { width: 8, height: 8, borderRadius: 4 },
  });
}
