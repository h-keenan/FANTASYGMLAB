import React, { useState, type ReactNode } from 'react';
import { StyleSheet, View, type StyleProp, type TextStyle, type ViewStyle } from 'react-native';

import AppText from './AppText';
import ManagerProfileModal from './ManagerProfileModal';
import PressableScale from './PressableScale';
import TeamAvatar from './TeamAvatar';
import { teamDisplayName, teamLinkInteractive, teamOpenLabel, TEAM_TAP_MIN } from '../lib/teamTap';

/**
 * THE team tap target (twin of web-next TeamNameLink.tsx; rule in lib/teamTap.ts): a league team's name, optionally with its
 * avatar, opens the shared team sheet (ManagerProfileModal, the one the trade card opens). One accessible button, 44pt
 * minimum. Renders plain when the league or roster is unknown, or when `current` says the screen is already that team's own
 * page (a tap would be a no-op).
 */
export default function TeamNameLink({
  leagueId,
  leagueName,
  rosterId,
  name,
  avatarId,
  showAvatar = false,
  avatarSize = 24,
  avatarStyle,
  vertical = false,
  alignEnd = false,
  fill = false,
  ownerName,
  current = false,
  textStyle,
  style,
  numberOfLines = 2,
  children,
}: {
  leagueId?: string | null;
  leagueName?: string;
  rosterId?: string | number | null;
  name?: string | null;
  avatarId?: string | null;
  showAvatar?: boolean;
  avatarSize?: number;
  avatarStyle?: StyleProp<ViewStyle>;
  /** Stack the avatar above the name and centre both (a scoreboard side). */
  vertical?: boolean;
  /** Sit at the trailing edge of the parent (a right-aligned column). */
  alignEnd?: boolean;
  /** Take the remaining width of a row (flex 1). */
  fill?: boolean;
  /** Manager handle shown in the sheet header. */
  ownerName?: string | null;
  current?: boolean;
  textStyle?: StyleProp<TextStyle>;
  style?: StyleProp<ViewStyle>;
  numberOfLines?: number;
  /** Replaces the default name text (the tap target stays the same). */
  children?: ReactNode;
}) {
  const [sheetOpen, setSheetOpen] = useState(false);
  const shown = teamDisplayName(name);
  const content = (
    <View style={[styles.row, vertical && styles.vertical, style]}>
      {showAvatar ? <TeamAvatar avatarId={avatarId} name={name} size={avatarSize} style={avatarStyle} /> : null}
      <View style={styles.text}>{children ?? <AppText style={textStyle} numberOfLines={numberOfLines}>{shown}</AppText>}</View>
    </View>
  );
  if (!teamLinkInteractive({ leagueId, rosterId, name }, current) || !leagueId || rosterId == null) return fill ? <View style={styles.targetFill}>{content}</View> : content;
  return (
    <>
      <PressableScale
        accessibilityRole="button"
        accessibilityLabel={teamOpenLabel(name)}
        onPress={() => setSheetOpen(true)}
        style={[styles.target, alignEnd && styles.targetEnd, fill && styles.targetFill]}
      >
        {content}
      </PressableScale>
      {sheetOpen ? (
        <ManagerProfileModal
          visible
          onClose={() => setSheetOpen(false)}
          leagueId={leagueId}
          leagueName={leagueName}
          rosterId={rosterId}
          teamName={shown}
          ownerName={ownerName}
          avatarId={avatarId}
        />
      ) : null}
    </>
  );
}

const styles = StyleSheet.create({
  target: { minHeight: TEAM_TAP_MIN, justifyContent: 'center', alignSelf: 'flex-start', maxWidth: '100%' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, flexShrink: 1 },
  targetFill: { flex: 1, alignSelf: 'stretch' },
  targetEnd: { alignSelf: 'flex-end' },
  vertical: { flexDirection: 'column', alignSelf: 'center', gap: 2 },
  text: { flexShrink: 1 },
});
