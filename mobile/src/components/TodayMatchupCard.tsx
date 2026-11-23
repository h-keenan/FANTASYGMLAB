import React, { useMemo, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import AccentCard from './AccentCard';
import AppText from './AppText';
import { SwingPlayers } from './MatchupModule';
import { Collapse } from './Presence';
import PressableScale from './PressableScale';
import { StatusRingMark } from './StatusHeader';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import type { MatchupResponse } from '../lib/api';
import { matchupSwingPlayers, swingInputsFromMatchup } from '../lib/matchupModules';
import { statusRing } from '../lib/statusHeader';
import type { TeamStatusMatchup } from '../lib/teamStatus';
import { todayMatchupRing } from '../lib/todayView';
import { LINK_HIT_SLOP, spacing, type ThemeColors } from '../theme';

/**
 * Today's matchup card (concept C): the win-chance ring, "WK 10 · VS SHIESTY", both scores and a "trailing 27.2" chip in one
 * compact card. Tapping expands the detail (the swing players, with avatars) and a link to the Matchup screen. It is the ONE
 * place Today states the score and the win chance. Web twin: components/TodayMatchupCard.tsx.
 */
export default function TodayMatchupCard({ line, matchup, onOpenMatchup, move }: { line: TeamStatusMatchup; matchup: MatchupResponse | null; onOpenMatchup: () => void; /** The single best move for this matchup (lib/todayView.ts todayMatchupMove) and what its tap opens: the lineup planner on that swap. */ move?: { text: string; onPress: () => void } | null }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [open, setOpen] = useState(false);
  const ring = todayMatchupRing(line);
  const swing = matchup?.my_team && matchup.opponent ? matchupSwingPlayers(swingInputsFromMatchup(matchup.my_team, matchup.opponent).inputs, matchup.opponent.team_name) : [];
  const status = statusRing(ring.pct, ring.pct != null ? `${ring.pct}%` : '–', ring.pct != null ? `Win chance ${ring.pct}%` : 'Win chance not modeled', ring.tone);
  const chipColor = ring.chip ? (ring.chip.tone === 'danger' ? colors.danger : colors.success) : colors.textTertiary;
  return (
    <AccentCard accent={colors.accent} compact>
      <View testID="today-matchup">
        <Pressable
          accessibilityRole="button"
          accessibilityState={{ expanded: open }}
          accessibilityLabel={[ring.kicker, ring.scoreLine, ring.chip?.label, status.label].filter(Boolean).join('. ')}
          onPress={() => setOpen((v) => !v)}
          style={styles.header}
        >
          <StatusRingMark ring={status} size={68} />
          <View style={styles.text}>
            <AppText style={styles.kicker} numberOfLines={1}>
              {ring.kicker}
            </AppText>
            {ring.scoreLine ? <AppText style={styles.score}>{ring.scoreLine}</AppText> : null}
            <View style={styles.chipRow}>
              {ring.chip ? <ToneBadge label={ring.chip.label} color={chipColor} /> : null}
              {ring.scoreCaption ? <AppText style={styles.caption}>{ring.scoreCaption}</AppText> : null}
            </View>
          </View>
          <AppText style={styles.chevron}>{open ? '⌃' : '⌄'}</AppText>
        </Pressable>
        {move ? (
          <PressableScale accessibilityRole="link" accessibilityLabel={`Best move: ${move.text}. Open the lineup`} onPress={move.onPress} style={styles.move} testID="today-matchup-move">
            <AppText style={styles.moveText} numberOfLines={2}>
              <AppText style={styles.moveKicker}>BEST MOVE </AppText>
              {move.text}
            </AppText>
            <AppText style={styles.linkText}>›</AppText>
          </PressableScale>
        ) : null}
        <Collapse open={open}>
          <View style={styles.body}>
            <SwingPlayers swing={swing} />
            <PressableScale accessibilityRole="link" onPress={onOpenMatchup} hitSlop={LINK_HIT_SLOP} style={styles.link}>
              <AppText style={styles.linkText}>Open matchup ›</AppText>
            </PressableScale>
          </View>
        </Collapse>
      </View>
    </AccentCard>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    header: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, minHeight: 76 },
    text: { flex: 1, minWidth: 0, gap: 2 },
    kicker: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, color: colors.textTertiary },
    score: { fontSize: 24, fontWeight: '800', color: colors.textPrimary },
    chipRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    caption: { fontSize: 12.5, color: colors.textTertiary },
    chevron: { fontSize: 14, color: colors.textTertiary },
    body: { gap: spacing.sm, paddingTop: spacing.xs },
    move: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, minHeight: 44 },
    moveText: { flex: 1, color: colors.accent, fontWeight: '700', fontSize: 14 },
    moveKicker: { color: colors.textTertiary, fontWeight: '800', fontSize: 12, letterSpacing: 0.8 },
    link: { minHeight: 44, justifyContent: 'center', alignSelf: 'flex-start' },
    linkText: { color: colors.accent, fontWeight: '700', fontSize: 14 },
  });
}
