import React, { useMemo, type ReactNode } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import PlayerAvatarSlot from './PlayerAvatarSlot';
import { PlayerTap } from './PlayerOpenContext';
import PlayerName from './PlayerName';
import PositionBadge from './PositionBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import type { PlayerRef } from '../lib/playerAnatomy';
import { spacing, type ThemeColors } from '../theme';

/**
 * The compact player card used INSIDE other modules (trade sides, bar rows). The whole card is the tap target and opens the
 * quick view by default (role button, 44pt, PressableScale feedback); `onOpen` opens something else, `nonInteractive="reason"`
 * is for a card inside a control that already acts. Twin of ui/CompactPlayerCard.tsx.
 */
export default function CompactPlayerCard({ player, detail, trailing, testID = 'compact-player-card', onOpen, nonInteractive }: { player: PlayerRef; detail?: string | null; trailing?: ReactNode; testID?: string; onOpen?: () => void; nonInteractive?: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const card = (
    <View style={styles.row} testID={testID}>
      <PlayerAvatarSlot player={player} tier="dense" nonInteractive="the whole card is the tap target" />
      <View style={styles.main}>
        <View style={styles.line}>
          <PlayerName name={player.name} style={styles.name} />
          <PositionBadge position={player.position} />
        </View>
        {detail ? <AppText style={styles.detail}>{detail}</AppText> : null}
      </View>
      {trailing ? <View style={styles.trailing}>{trailing}</View> : null}
    </View>
  );
  return (
    <PlayerTap player={player} onOpen={onOpen} nonInteractive={nonInteractive}>
      {card}
    </PlayerTap>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { minHeight: 44, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    main: { flex: 1, minWidth: 0 },
    line: { flexDirection: 'row', alignItems: 'center', gap: 6 },
    name: { fontSize: 14, fontWeight: '700', color: colors.textPrimary, flexShrink: 1 },
    detail: { fontSize: 12, color: colors.textTertiary },
    trailing: { flexShrink: 0, flexDirection: 'row', alignItems: 'center', gap: 6 },
  });
}
