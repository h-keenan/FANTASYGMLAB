import React, { forwardRef, useCallback, useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import AppText from './AppText';

import CircularProgressRing from './CircularProgressRing';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';
import ShareCardChrome, { CARD_HEIGHT, CARD_WIDTH } from './ShareCardChrome';
import { compareRowWinner, type CompareRow } from '../lib/playerCompare';
import { percentileColor } from '../lib/percentile';
import { colors, spacing } from '../theme';

// Same safety net as TradeShareCard/PlayerShareCard's AVATAR_READY_TIMEOUT_MS
// — not the fix, just a floor so a hung headshot request on either side
// can't leave the share button stuck forever. See PlayerAvatar's
// onLoadSettle doc comment for the real fix this waits on.
const AVATAR_READY_TIMEOUT_MS = 4000;

/** Just enough of a head-to-head side for the export card — the real
 * identity fields PlayerIdentityRow/IdentityHeader already render on
 * PlayerCompareScreen, never a second fetch. */
export interface CompareShareCardSide {
  playerId: string;
  name: string;
  position?: string | null;
  team?: string | null;
  tier?: string | null;
  overallRating: number | null;
}

function IdentityColumn({
  side,
  trackKey,
  onAvatarSettle,
}: {
  side: CompareShareCardSide;
  trackKey: string;
  onAvatarSettle: (key: string) => void;
}) {
  const ringColor = side.overallRating !== null ? percentileColor(side.overallRating, colors) : colors.accent;
  return (
    <View style={styles.identityColumn}>
      <PlayerAvatar
        playerId={side.playerId}
        size={64}
        tier={side.tier}
        onLoadSettle={() => onAvatarSettle(trackKey)}
      />
      {side.overallRating !== null ? (
        <CircularProgressRing
          percent={side.overallRating}
          size={48}
          strokeWidth={5}
          valueLabel={String(side.overallRating)}
          valueFontScale={0.34}
          color={ringColor}
          label="OVR"
        />
      ) : null}
      <AppText style={styles.identityName} numberOfLines={2}>
        {side.name}
      </AppText>
      <View style={styles.identityMetaRow}>
        <PositionBadge position={side.position} />
        {side.team ? (
          <AppText style={styles.identityMeta} numberOfLines={1}>
            {side.team}
          </AppText>
        ) : null}
      </View>
    </View>
  );
}

/** One head-to-head row on the export card — same compareRowWinner
 * win-highlight logic PlayerCompareScreen's own CompareRowView uses
 * on-screen, never a second tie/lower-is-better computation. */
function ValueRowView({ row }: { row: CompareRow }) {
  const winner = compareRowWinner(row);
  const display = (value: number | null) => (value === null ? '—' : row.format ? row.format(value) : String(value));
  return (
    <View style={styles.row}>
      <AppText style={[styles.rowValue, winner === 'a' && styles.rowValueWin]} numberOfLines={1}>
        {display(row.a)}
      </AppText>
      <AppText style={styles.rowLabel} numberOfLines={1}>
        {row.label}
      </AppText>
      <AppText style={[styles.rowValue, winner === 'b' && styles.rowValueWin]} numberOfLines={1}>
        {display(row.b)}
      </AppText>
    </View>
  );
}

/**
 * The literal graphic captured + shared for "Share this comparison" on
 * PlayerCompareScreen — both players' portrait/OVR/name/position/team side
 * by side (mirroring IdentityHeader's on-screen layout) plus the core
 * "Value & Rank" row (Value Score, Overall Rank, Position Rank, Age) that
 * screen already builds via buildValueRows. The fuller "Model Breakdown"
 * section (Market/Opportunity/Scarcity/Role/Age Lens/Confidence) is left
 * off this card on purpose — PlayerShareCard's single-player card only ever
 * surfaces one headline attribute row, not every tab's data, and six more
 * head-to-head rows would cram a shareable image well past that card's
 * level of restraint. `rows` is passed in by the screen (buildValueRows'
 * real output) rather than recomputed here.
 *
 * Shares ShareCardChrome with PlayerShareCard (header/QR/footer) so every
 * exported share graphic reads as one family. `onReadyChange` mirrors
 * TradeShareCard's multi-avatar readiness tracking — true only once BOTH
 * headshots have settled (loaded, failed, or had no id), or the timeout
 * floor fires.
 */
const CompareShareCard = forwardRef<
  View,
  {
    sideA: CompareShareCardSide;
    sideB: CompareShareCardSide;
    rows: CompareRow[];
    onReadyChange?: (ready: boolean) => void;
  }
>(({ sideA, sideB, rows, onReadyChange }, ref) => {
  const trackedSignature = `${sideA.playerId}|${sideB.playerId}`;

  const [settledKeys, setSettledKeys] = useState<Set<string>>(new Set());
  const handleAvatarSettle = useCallback((key: string) => {
    setSettledKeys((prev) => (prev.has(key) ? prev : new Set(prev).add(key)));
  }, []);
  const allSettled = settledKeys.has('a') && settledKeys.has('b');

  const [forceReady, setForceReady] = useState(false);
  useEffect(() => {
    setSettledKeys(new Set());
    setForceReady(false);
    const timer = setTimeout(() => setForceReady(true), AVATAR_READY_TIMEOUT_MS);
    return () => clearTimeout(timer);
  }, [trackedSignature]);

  const ready = allSettled || forceReady;
  useEffect(() => {
    onReadyChange?.(ready);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  return (
    <ShareCardChrome
      ref={ref}
      headerRight={<AppText style={styles.headToHead}>HEAD-TO-HEAD</AppText>}
      qrSubtitle="Real player grades, model breakdowns, and a dynasty engine built for GMs."
    >
      <View style={styles.identityRow}>
        <IdentityColumn side={sideA} trackKey="a" onAvatarSettle={handleAvatarSettle} />
        <AppText style={styles.vsLabel}>VS</AppText>
        <IdentityColumn side={sideB} trackKey="b" onAvatarSettle={handleAvatarSettle} />
      </View>

      <View style={styles.hairline} />

      <AppText style={styles.rowsLabel}>Value & Rank</AppText>
      <View style={styles.rowsGroup}>
        {rows.map((row) => (
          <ValueRowView key={row.label} row={row} />
        ))}
      </View>
    </ShareCardChrome>
  );
});
CompareShareCard.displayName = 'CompareShareCard';

export default CompareShareCard;
export { CARD_WIDTH, CARD_HEIGHT };

const styles = StyleSheet.create({
  headToHead: { fontSize: 11, fontWeight: '800', color: colors.textTertiary, letterSpacing: 0.6 },
  hairline: { height: StyleSheet.hairlineWidth, backgroundColor: colors.border, marginVertical: spacing.sm },
  identityRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    marginTop: spacing.md,
  },
  identityColumn: { flex: 1, alignItems: 'center', gap: spacing.xs },
  identityName: { fontSize: 14, fontWeight: '700', color: colors.textPrimary, textAlign: 'center', marginTop: 2 },
  identityMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs },
  identityMeta: { fontSize: 11, color: colors.textSecondary },
  vsLabel: { fontSize: 12, fontWeight: '800', color: colors.textTertiary, marginTop: spacing.xl },
  rowsLabel: {
    fontSize: 11,
    fontWeight: '700',
    color: colors.textTertiary,
    letterSpacing: 0.5,
    textTransform: 'uppercase',
    marginBottom: spacing.xs,
  },
  rowsGroup: { gap: 2 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingVertical: spacing.xs + 2,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.border,
  },
  rowLabel: {
    flex: 1.1,
    fontSize: 10.5,
    fontWeight: '700',
    color: colors.textSecondary,
    textAlign: 'center',
    textTransform: 'uppercase',
    letterSpacing: 0.3,
  },
  rowValue: { flex: 1, fontSize: 16, fontWeight: '700', color: colors.textPrimary, textAlign: 'center' },
  rowValueWin: { color: colors.successBright, fontWeight: '800' },
});
