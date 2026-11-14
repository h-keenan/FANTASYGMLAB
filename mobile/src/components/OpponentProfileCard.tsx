import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import Button from './Button';
import PositionBadge from './PositionBadge';
import SectionHeading from './SectionHeading';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  firstsFlowText,
  hasProfileContent,
  offerCaption,
  ordinal,
  picksText,
  rankText,
  type OpponentProfileResponse,
  type OpponentTradeTarget,
} from '../lib/opponentProfile';
import { spacing, type ThemeColors } from '../theme';
import PlayerName from './PlayerName';

/** Opponent profile card (League Rankings manager profile): strongest/weakest
 * room, starter strength vs. bench depth, surplus and needs, pick capital,
 * team direction, and a trade angle with an "Offer this" button that opens the
 * Trade Analyzer prefilled (same quick-add the player sheets use). Mirrors
 * web-next/src/components/OpponentProfileCard.tsx; renders nothing for fields
 * the server could not compute. */
export default function OpponentProfileCard({
  profile,
  onOffer,
}: {
  profile: OpponentProfileResponse | null | undefined;
  onOffer: (target: OpponentTradeTarget) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!profile || !hasProfileContent(profile)) return null;
  const { direction, rooms = [], strongest, weakest, starter_bench: depth, picks, trade_tendency: tendency, trade_angle: angle } = profile;
  const flow = picks ? firstsFlowText(picks) : null;
  const picksLine = picks ? picksText(picks) : '';
  const directionMeta = [
    direction?.rank && direction.league_size ? `${ordinal(direction.rank)} of ${direction.league_size} in power` : '',
    direction?.record ? `Record ${direction.record}` : '',
  ]
    .filter(Boolean)
    .join(' · ');

  return (
    <View testID="opponent-profile">
      <SectionHeading title="Roster profile" />
      <AccentCard accent={colors.accent} compact style={styles.card}>
        {direction?.label ? (
          <View style={styles.row}>
            <AppText style={styles.label}>Direction</AppText>
            <View style={styles.inline}>
              <ToneBadge label={direction.label} color={colors.accent} />
              {tendency ? <ToneBadge label={`${tendency.label} in trades`} color={colors.premium} /> : null}
            </View>
            {directionMeta ? <AppText style={styles.muted}>{directionMeta}</AppText> : null}
          </View>
        ) : null}
        {strongest || weakest ? (
          <View style={styles.row}>
            <AppText style={styles.label}>Rooms</AppText>
            {strongest ? <AppText style={styles.value}>Strongest: {rankText(strongest)}</AppText> : null}
            {weakest ? <AppText style={styles.value}>Weakest: {rankText(weakest)}</AppText> : null}
          </View>
        ) : null}
        {rooms.length > 0 ? (
          <View style={styles.rooms} accessibilityLabel="League rank by position">
            {rooms.map((room) => (
              <View key={room.position} style={styles.room}>
                <PositionBadge position={room.position} />
                <AppText style={styles.roomRank}>{ordinal(room.rank)}</AppText>
                {room.tag ? (
                  <ToneBadge
                    label={room.tag === 'surplus' ? 'Surplus' : 'Need'}
                    color={room.tag === 'surplus' ? colors.success : colors.danger}
                    size="xs"
                  />
                ) : null}
              </View>
            ))}
          </View>
        ) : null}
        {depth ? (
          <View style={styles.row}>
            <AppText style={styles.label}>Starters vs. bench</AppText>
            <AppText style={styles.value}>
              {depth.label}: starters {ordinal(depth.starter_rank)}, bench {ordinal(depth.bench_rank)} of {depth.of}
            </AppText>
            <AppText style={styles.muted}>{depth.note}</AppText>
          </View>
        ) : null}
        {picks && (picksLine || flow) ? (
          <View style={styles.row}>
            <AppText style={styles.label}>Future picks</AppText>
            {picksLine ? <AppText style={styles.value}>{picksLine}</AppText> : null}
            {flow ? <AppText style={styles.muted}>{flow}</AppText> : null}
          </View>
        ) : null}
      </AccentCard>
      {angle ? (
        <AccentCard accent={colors.success} compact style={styles.card}>
          <View style={styles.row}>
            <AppText style={styles.label}>Trade angle</AppText>
            <AppText style={styles.value}>{angle.text}</AppText>
          </View>
          {angle.target ? (
            <>
              <View style={styles.inline}>
                <PositionBadge position={angle.target.position} />
                <View style={{ flex: 1, minWidth: 0, flexDirection: 'row', flexWrap: 'wrap', alignItems: 'baseline', columnGap: 6 }}>
                  <PlayerName name={angle.target.name} style={[styles.value, styles.targetName]} />
                  {angle.target.team ? <AppText style={[styles.value, styles.targetName]}>{angle.target.team}</AppText> : null}
                </View>
              </View>
              <AppText style={styles.muted}>{offerCaption(angle.target)}</AppText>
              <View style={styles.cta}>
                <Button label="Offer this" size="sm" onPress={() => onOffer(angle.target as OpponentTradeTarget)} />
              </View>
            </>
          ) : null}
        </AccentCard>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: { marginBottom: spacing.sm, gap: spacing.sm },
    row: { gap: 2 },
    inline: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: spacing.sm },
    label: { fontSize: 12.5, fontWeight: '800', textTransform: 'uppercase', color: colors.textSecondary },
    value: { fontSize: 15.5, fontWeight: '600', color: colors.textPrimary },
    muted: { fontSize: 13.5, color: colors.textSecondary },
    rooms: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.md },
    room: { flexDirection: 'row', alignItems: 'center', gap: 6 },
    roomRank: { fontSize: 13.5, fontWeight: '700', color: colors.textPrimary },
    targetName: { flex: 1 },
    cta: { alignSelf: 'flex-start' },
  });
}
