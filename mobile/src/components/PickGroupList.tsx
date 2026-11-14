import React, { useMemo, useState } from 'react';
import { StyleSheet, View } from 'react-native';
import PressableScale from './PressableScale';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import SegmentedTabBar from './SegmentedTabBar';
import ToneBadge from './ToneBadge';
import { useThemeMode } from '../context/ThemeModeContext';
import { groupPicksForList, roundGroupDefaultOpen, type GroupablePick } from '../lib/pickGroups';
import { radii, spacing, type ThemeColors } from '../theme';

/**
 * The one grouped draft-pick list: year tabs on top, then a collapsible group
 * per round with a count; long groups start collapsed. Draft Center, Trade
 * Finder and Trade Analyzer all use it and supply only the row via
 * `renderPick`, so each keeps its own selection behavior. Web twin:
 * web-next/src/components/PickGroupList.tsx.
 */
export default function PickGroupList<T extends GroupablePick>({
  picks,
  renderPick,
  selectedIds,
  emptyMessage = 'No picks to show.',
}: {
  picks: T[];
  /** Render one pick row. `isLast` lets the row drop its trailing divider. */
  renderPick: (pick: T, isLast: boolean) => React.ReactNode;
  /** Picks currently selected: counted on the round header and force that round open. */
  selectedIds?: ReadonlySet<string>;
  emptyMessage?: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const seasons = useMemo(() => groupPicksForList(picks), [picks]);
  const [season, setSeason] = useState('');
  const [toggled, setToggled] = useState<Record<string, boolean>>({});
  const active = seasons.find((group) => group.label === season) ?? seasons[0];

  if (!active) return <AppText style={styles.empty}>{emptyMessage}</AppText>;

  return (
    <View style={styles.root}>
      {seasons.length > 1 ? (
        <SegmentedTabBar<string>
          scrollable
          options={seasons.map((group) => ({ key: group.label, label: `${group.label} (${group.count})` }))}
          active={active.label}
          onChange={setSeason}
        />
      ) : null}
      {active.rounds.map((group, index) => {
        const key = `${active.label}:${group.round}`;
        const open = toggled[key] ?? roundGroupDefaultOpen(group, index === 0, selectedIds);
        const selectedCount = selectedIds ? group.picks.filter((pick) => selectedIds.has(pick.pick_id)).length : 0;
        return (
          <View key={key} style={styles.group}>
            <PressableScale
              style={styles.header}
              onPress={() => setToggled((prev) => ({ ...prev, [key]: !open }))}
              accessibilityRole="button"
              accessibilityState={{ expanded: open }}
              accessibilityLabel={`${group.label}, ${group.picks.length} picks`}
            >
              <AppText style={styles.headerTitle}>{group.label}</AppText>
              <ToneBadge label={`${group.picks.length} ${group.picks.length === 1 ? 'pick' : 'picks'}`} color={colors.accent} />
              {selectedCount > 0 ? <ToneBadge label={`${selectedCount} selected`} color={colors.success} /> : null}
              <Ionicons
                name={open ? 'chevron-up' : 'chevron-down'}
                size={16}
                color={colors.textSecondary}
                style={styles.chevron}
              />
            </PressableScale>
            {open ? (
              <View style={styles.body}>
                {group.picks.map((pick, i) => (
                  <React.Fragment key={pick.pick_id}>{renderPick(pick, i === group.picks.length - 1)}</React.Fragment>
                ))}
              </View>
            ) : null}
          </View>
        );
      })}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    root: { gap: spacing.sm },
    empty: { textAlign: 'center', color: colors.textSecondary, marginVertical: spacing.md },
    group: {
      backgroundColor: colors.glass,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.glassBorder,
      overflow: 'hidden',
    },
    header: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingHorizontal: spacing.md, paddingVertical: spacing.sm },
    headerTitle: { fontSize: 15.5, fontWeight: '700', color: colors.textPrimary },
    chevron: { marginLeft: 'auto' },
    body: { borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, paddingHorizontal: spacing.md },
  });
}
