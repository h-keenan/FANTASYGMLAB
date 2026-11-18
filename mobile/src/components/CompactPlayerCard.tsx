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
export default function CompactPlayerCard({ player, detail, trailing, testID = 'compact-player-card', onOpen, nonInteractive, shortName = false, stacked = false }: { player: PlayerRef; detail?: ReactNode; trailing?: ReactNode; testID?: string; onOpen?: () => void; nonInteractive?: string; /** Trade cards: always "J. Surname" (PlayerName `short`). */ shortName?: boolean; /** Two-column sides (the trade scale): name on line one, position badge left and trailing chips right-aligned on line two. */ stacked?: boolean }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const card = stacked ? (
    <View style={styles.stack} testID={testID}>
      <View style={styles.identityStacked}>
        <PlayerAvatarSlot player={player} tier="dense" nonInteractive="the whole card is the tap target" />
        <View style={styles.main}>
          <PlayerName name={player.name} short={shortName} style={styles.name} />
          {detail ? <AppText style={styles.detail}>{detail}</AppText> : null}
        </View>
      </View>
      <View style={styles.stackFoot}>
        <PositionBadge position={player.position} />
        {trailing ? <View style={styles.trailing}>{trailing}</View> : null}
      </View>
    </View>
  ) : (
    <View style={styles.row} testID={testID}>
      <View style={styles.identity}>
        <PlayerAvatarSlot player={player} tier="dense" nonInteractive="the whole card is the tap target" />
        <View style={styles.main}>
          <View style={styles.line}>
            <PlayerName name={player.name} short={shortName} style={styles.name} />
            <View style={styles.badge}><PositionBadge position={player.position} /></View>
          </View>
          {detail ? <AppText style={styles.detail}>{detail}</AppText> : null}
        </View>
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
    // Narrow widths: the identity block keeps a 160pt floor and the trailing chips wrap to a second line, never squeezing the name.
    row: { minHeight: 44, flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', columnGap: spacing.sm, rowGap: 2 },
    identity: { flex: 1, flexBasis: 160, minWidth: 0, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    badge: { flexShrink: 0 },
    stack: { gap: 2, paddingVertical: 2 },
    identityStacked: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minWidth: 0 },
    stackFoot: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    main: { flex: 1, minWidth: 0 },
    line: { flexDirection: 'row', alignItems: 'center', gap: 6 },
    name: { fontSize: 14, fontWeight: '700', color: colors.textPrimary, flexShrink: 1 },
    detail: { fontSize: 12, color: colors.textTertiary },
    trailing: { flexShrink: 0, marginLeft: 'auto', flexDirection: 'row', alignItems: 'center', gap: 6 },
  });
}
