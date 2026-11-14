import React, { useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { FlatList, Keyboard, Pressable, StyleSheet, useWindowDimensions, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';
import { useReducedMotion } from 'react-native-reanimated';

import AppText from './AppText';
import Button from './Button';
import DraftPickAssetRow from './DraftPickAssetRow';
import Input from './Input';
import PlayerIdentityRow from './PlayerIdentityRow';
import SegmentedTabBar from './SegmentedTabBar';
import { SheetModal, SwipeDismissCard } from './SwipeDismissSheet';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  SHEET_CONDITIONS,
  activeFilterCount,
  applyLabel,
  filterSheetItems,
  filterSummary,
  filtersEmpty,
  groupSheetItems,
  initialSheetState,
  positionsFor,
  selectedItems,
  sheetReducer,
  summarizeItems,
  type SheetFilters,
  type SheetItem,
} from '../lib/tradeSheetPicker';
import { radii, scrim, spacing, type ThemeColors } from '../theme';

/**
 * The shared trade piece picker (mirrors web-next's TradePickerSheet). Tapping
 * a side of a trade opens this bottom sheet with that side's players and
 * picks: Players | Picks control, search, one Filters button (position +
 * condition chips, committed with Apply), the selection as removable chips,
 * 56pt rows you tap to toggle, and a sticky "Add N to trade" button. The
 * player card opens from the info button, never from the row. Used by the
 * Trade Analyzer, the multi-team builder and the Fantasy Sim trade builder;
 * logic lives in lib/tradeSheetPicker.ts (byte-identical twin of web).
 *
 * Mount it while it is open: it starts from `initialSelected` and hands the
 * whole selection back through `onApply`. Closing any other way discards.
 * iOS cannot present two native modals at once, so with `hideOnInfo` the info
 * button hides this sheet while the player card is up and `onInfo` gets a
 * `restore` callback to bring it back (selection state lives outside the modal,
 * so it survives).
 */
export default function TradePickerSheet<T = unknown>({
  title,
  subtitle,
  tone,
  items,
  initialSelected,
  max,
  onApply,
  onClose,
  onInfo,
  onSearch,
  playersOnly = false,
  hideOnInfo = false,
  mode = 'multi',
  initialFilters,
  renderPlayerRow,
  hidden: hiddenExternal = false,
  flexFilter = false,
  valueLabel,
}: {
  title: string;
  subtitle?: string;
  tone: 'danger' | 'success' | 'neutral';
  items: SheetItem<T>[];
  initialSelected: string[];
  max?: number;
  onApply: (keys: string[]) => void;
  onClose: () => void;
  onInfo?: (item: SheetItem<T>, restore: () => void) => void;
  onSearch?: (query: string) => void;
  /** Hide the Picks tab (Quick Compare is players only). */
  playersOnly?: boolean;
  /** Hide this sheet while the info target presents (needed when it opens a sibling native modal). */
  hideOnInfo?: boolean;
  /** 'single' is a pick-one flow (Player Compare): tapping a row chooses it and closes, no chips or footer. */
  mode?: 'multi' | 'single';
  /** Filters already in effect when the sheet opens (e.g. the same position as the player being compared). */
  initialFilters?: SheetFilters;
  /** Render player rows with the caller's own row (Fantasy Sim: the shared PlayerListRow, tap the body for the quick view, a checkbox as its action). Picks keep the built-in row and the info button is not drawn. */
  renderPlayerRow?: (item: SheetItem<T>, control: { on: boolean; blocked: boolean; toggle: () => void }) => React.ReactNode;
  /** Hide this sheet (selection and scroll are kept by the caller's state) while a player card is up: iOS cannot present two native modals. */
  hidden?: boolean;
  /** Offer a FLEX chip (RB / WR / TE) in the position filter. */
  flexFilter?: boolean;
  /** Caption under each row's value number. Fantasy Sim passes "Trade value" so the number is never bare. */
  valueLabel?: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  // The sheet is sized from the real window and the top safe area, never from a percentage of a container that a keyboard or a
  // re-presented Modal can leave shifted: it always sits on the bottom edge and its top never goes under the status bar.
  const { height: windowHeight } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const sheetHeight = Math.min(Math.round(windowHeight * 0.9), windowHeight - insets.top - 8);
  // A keyboard left open by the search box must not outlive the sheet (or its hidden state): it shoved the Modal's layout up.
  const closeKeyboard = () => Keyboard.dismiss();
  const reduceMotion = useReducedMotion();
  const [state, dispatch] = useReducer(sheetReducer, undefined, () => {
    const kinds = initialSelected.map((key) => items.find((i) => i.key === key)?.kind);
    return initialSheetState(initialSelected, kinds.length > 0 && kinds.every((k) => k === 'pick') ? 'picks' : 'players', initialFilters);
  });
  const [hidden, setHidden] = useState(false);
  const filtersOpen = state.draft !== null;
  const single = mode === 'single';

  const visibleItems = useMemo(() => (playersOnly ? items.filter((i) => i.kind === 'player') : items), [items, playersOnly]);
  const hasPicks = !playersOnly && visibleItems.some((i) => i.kind === 'pick');
  const positions = useMemo(() => positionsFor(visibleItems, flexFilter), [visibleItems, flexFilter]);
  const rows = useMemo(
    () => filterSheetItems(visibleItems, { tab: state.tab, query: state.query, filters: state.filters }),
    [visibleItems, state.tab, state.query, state.filters],
  );
  const chosen = useMemo(() => selectedItems(visibleItems, state.selected), [visibleItems, state.selected]);
  const summary = summarizeItems(chosen);
  const playerCount = visibleItems.filter((i) => i.kind === 'player').length;
  const pickCount = visibleItems.length - playerCount;
  const atMax = max != null && state.selected.length >= max;
  const filterCount = activeFilterCount(state.filters);
  const toneColor = tone === 'danger' ? colors.danger : tone === 'success' ? colors.successBright : colors.accent;

  // Section headers for picks (by season); players are one flat list.
  const listData = useMemo(() => {
    if (state.tab !== 'picks') return rows.map((item) => ({ type: 'item' as const, item }));
    return groupSheetItems(rows).flatMap((group) => [
      ...(group.label ? [{ type: 'header' as const, label: group.label }] : []),
      ...group.items.map((item) => ({ type: 'item' as const, item })),
    ]);
  }, [rows, state.tab]);

  // Selection survives the info round-trip because it lives in this component, not in the modal tree.
  const infoRestore = useRef(() => setHidden(false));
  useEffect(() => {
    infoRestore.current = () => setHidden(false);
  }, []);

  return (
    <SheetModal visible={!hidden && !hiddenExternal} transparent animationType={reduceMotion ? 'none' : 'slide'} onRequestClose={() => (filtersOpen ? dispatch({ type: 'closeFilters' }) : onClose())}>
      <Pressable style={styles.backdrop} onPress={() => { closeKeyboard(); onClose(); }} accessibilityLabel={`Close ${title}`}>
        <SwipeDismissCard style={[styles.sheet, { height: sheetHeight }]} onDismiss={() => { closeKeyboard(); onClose(); }} handleOnly testID="trade-picker">
          <View style={styles.header}>
            <View style={[styles.dot, { backgroundColor: toneColor }]} />
            <View style={styles.headerText}>
              <AppText style={styles.title} numberOfLines={1} accessibilityRole="header">
                {title}
              </AppText>
              {subtitle ? (
                <AppText style={styles.subtitle} numberOfLines={1}>
                  {subtitle}
                </AppText>
              ) : null}
            </View>
            <Pressable onPress={onClose} style={styles.close} accessibilityRole="button" accessibilityLabel={`Close ${title}`}>
              <Ionicons name="close" size={20} color={colors.textSecondary} />
            </Pressable>
          </View>

          {!single && chosen.length > 0 ? (
            <View style={styles.chips} accessibilityLabel="Selected">
              {chosen.map((item) => (
                <Pressable key={item.key} style={styles.chip} onPress={() => dispatch({ type: 'remove', key: item.key })} accessibilityRole="button" accessibilityLabel={`Remove ${item.label}`}>
                  <AppText style={styles.chipText} numberOfLines={1}>
                    {item.label}
                  </AppText>
                  <Ionicons name="close" size={14} color={colors.textTertiary} />
                </Pressable>
              ))}
            </View>
          ) : null}

          <View style={styles.controls}>
            {hasPicks ? (
              <SegmentedTabBar<'players' | 'picks'>
                options={[
                  { key: 'players', label: `Players ${playerCount}` },
                  { key: 'picks', label: `Picks ${pickCount}` },
                ]}
                active={state.tab}
                onChange={(tab) => dispatch({ type: 'tab', tab })}
              />
            ) : null}
            <View style={styles.searchRow}>
              <Input
                style={styles.search}
                placeholder={state.tab === 'picks' ? 'Search picks' : 'Search players'}
                accessibilityLabel={state.tab === 'picks' ? 'Search picks' : 'Search players'}
                value={state.query}
                onChangeText={(query) => {
                  dispatch({ type: 'query', query });
                  onSearch?.(query);
                }}
                autoCapitalize="none"
                autoCorrect={false}
                returnKeyType="search"
              />
              {state.tab === 'players' ? (
                <Pressable
                  style={[styles.filterButton, filtersOpen && styles.filterButtonOpen]}
                  onPress={() => dispatch({ type: filtersOpen ? 'closeFilters' : 'openFilters' })}
                  accessibilityRole="button"
                  accessibilityState={{ expanded: filtersOpen }}
                  accessibilityLabel={`Filters${filterCount ? ` (${filterCount})` : ''}`}
                >
                  <AppText style={[styles.filterButtonText, filtersOpen && { color: colors.accent }]}>Filters{filterCount ? ` (${filterCount})` : ''}</AppText>
                </Pressable>
              ) : null}
            </View>
            {state.tab === 'players' && !filtersEmpty(state.filters) ? (
              <View style={styles.activeFilters}>
                <AppText style={styles.activeFiltersText} numberOfLines={1}>
                  {filterSummary(state.filters)}
                </AppText>
                <Pressable
                  onPress={() => {
                    dispatch({ type: 'openFilters' });
                    dispatch({ type: 'clearDraft' });
                    dispatch({ type: 'applyFilters' });
                  }}
                  accessibilityRole="button"
                  accessibilityLabel="Clear filters"
                  style={styles.clearLink}
                >
                  <AppText style={[styles.activeFiltersText, { color: colors.accent, fontWeight: '800' }]}>Clear</AppText>
                </Pressable>
              </View>
            ) : null}
          </View>

          {filtersOpen && state.draft ? (
            <View style={styles.filterPanel} accessibilityLabel="Filters">
              <View style={styles.filterScroll}>
                <FilterGroup title="Position" styles={styles}>
                  {positions.map((position) => (
                    <FilterChip key={position} label={position} on={state.draft!.positions.includes(position)} onPress={() => dispatch({ type: 'draftPosition', position })} styles={styles} colors={colors} />
                  ))}
                </FilterGroup>
                <FilterGroup title="Condition" styles={styles}>
                  {SHEET_CONDITIONS.map((condition) => (
                    <FilterChip key={condition.value} label={condition.label} on={state.draft!.conditions.includes(condition.value)} onPress={() => dispatch({ type: 'draftCondition', condition: condition.value })} styles={styles} colors={colors} />
                  ))}
                </FilterGroup>
              </View>
              <View style={styles.footer}>
                <Button label="Clear" variant="secondary" onPress={() => dispatch({ type: 'clearDraft' })} />
                <Button label="Apply" onPress={() => dispatch({ type: 'applyFilters' })} style={styles.footerButton} />
              </View>
            </View>
          ) : (
            <>
              <FlatList
                style={styles.list}
                data={listData}
                keyExtractor={(entry) => (entry.type === 'header' ? `h:${entry.label}` : entry.item.key)}
                keyboardShouldPersistTaps="handled"
                initialNumToRender={14}
                ListEmptyComponent={
                  <AppText style={styles.empty}>{state.query || !filtersEmpty(state.filters) ? `No matching ${state.tab}.` : `No ${state.tab} available.`}</AppText>
                }
                renderItem={({ item: entry }) => {
                  if (entry.type === 'header') {
                    return <AppText style={styles.groupLabel}>{entry.label}</AppText>;
                  }
                  const item = entry.item;
                  const on = state.selected.includes(item.key);
                  const blocked = !on && atMax;
                  const value = item.value != null ? String(Math.round(item.value)) : '—';
                  if (renderPlayerRow && item.kind === 'player') {
                    return <View style={[styles.row, on && styles.rowOn]}>{renderPlayerRow(item, { on, blocked, toggle: () => dispatch({ type: 'toggle', key: item.key, max }) })}</View>;
                  }
                  return (
                    <View style={[styles.row, on && styles.rowOn]}>
                      <Pressable
                        style={[styles.rowMain, blocked && { opacity: 0.45 }]}
                        disabled={blocked}
                        onPress={() => (single ? onApply([item.key]) : dispatch({ type: 'toggle', key: item.key, max }))}
                        accessibilityRole="button"
                        accessibilityState={{ selected: on, disabled: blocked }}
                        accessibilityLabel={single ? `Choose ${item.label}` : `${on ? 'Remove' : 'Add'} ${item.label}`}
                      >
                        <View style={styles.rowIdentity}>
                          {item.kind === 'player' ? (
                            <PlayerIdentityRow
                              playerId={item.photoId ?? item.id}
                              name={item.label}
                              position={item.position}
                              team={item.team}
                              tier={item.tier}
                              trailingValue={value}
                              trailingCaption={valueLabel}
                              showDivider={false}
                            />
                          ) : (
                            <DraftPickAssetRow pickId={item.id} round={item.round} label={item.label} projectedRange={item.detail} trailingValue={value} trailingCaption={valueLabel} showDivider={false} />
                          )}
                        </View>
                        {single ? null : (
                          <View style={[styles.check, on && { backgroundColor: colors.accent, borderColor: colors.accent }]}>{on ? <Ionicons name="checkmark" size={14} color={colors.onAccent} /> : null}</View>
                        )}
                      </Pressable>
                      {onInfo && item.kind === 'player' ? (
                        <Pressable
                          style={styles.info}
                          accessibilityRole="button"
                          accessibilityLabel={`${item.label} player card`}
                          onPress={() => {
                            if (hideOnInfo) setHidden(true);
                            onInfo(item, infoRestore.current);
                          }}
                        >
                          <Ionicons name="information-circle-outline" size={22} color={colors.textTertiary} />
                        </Pressable>
                      ) : null}
                    </View>
                  );
                }}
              />
              {single ? null : (
              <View style={styles.footer}>
                <AppText style={styles.footerCount}>
                  {summary.count} selected
                  {summary.total > 0 ? ` · ${Math.round(summary.total).toLocaleString()}` : ''}
                  {atMax ? ' · max' : ''}
                </AppText>
                <Button label={applyLabel(state.selected, initialSelected)} onPress={() => onApply(state.selected)} style={styles.footerButton} />
              </View>
              )}
            </>
          )}
        </SwipeDismissCard>
      </Pressable>
    </SheetModal>
  );
}

function FilterGroup({ title, children, styles }: { title: string; children: React.ReactNode; styles: ReturnType<typeof createStyles> }) {
  return (
    <View style={styles.filterGroup}>
      <AppText style={styles.filterTitle}>{title.toUpperCase()}</AppText>
      <View style={styles.filterChips}>{children}</View>
    </View>
  );
}

function FilterChip({ label, on, onPress, styles, colors }: { label: string; on: boolean; onPress: () => void; styles: ReturnType<typeof createStyles>; colors: ThemeColors }) {
  return (
    <Pressable
      onPress={onPress}
      accessibilityRole="button"
      accessibilityState={{ selected: on }}
      accessibilityLabel={label}
      style={[styles.filterChip, on && { backgroundColor: colors.accentMuted, borderColor: colors.accent }]}
    >
      <AppText style={[styles.filterChipText, on && { color: colors.textPrimary }]}>{label}</AppText>
    </Pressable>
  );
}

/**
 * The compact per-side summary shown on the trade page once the sheet is
 * closed: label, count and total value, the picked assets as removable chips,
 * and one big tap target (the whole header) that opens the sheet.
 */
export function TradeSideSummary({
  label,
  tone,
  items,
  onOpen,
  onRemove,
  hint,
  testID,
}: {
  label: string;
  tone: 'danger' | 'success';
  items: SheetItem[];
  onOpen: () => void;
  onRemove: (key: string) => void;
  hint?: string;
  testID?: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const summary = summarizeItems(items);
  const parts = [summary.players ? `${summary.players} player${summary.players === 1 ? '' : 's'}` : '', summary.picks ? `${summary.picks} pick${summary.picks === 1 ? '' : 's'}` : ''].filter(Boolean).join(', ');
  return (
    <View style={styles.side} testID={testID}>
      <Pressable
        style={styles.sideOpen}
        onPress={onOpen}
        accessibilityRole="button"
        accessibilityLabel={items.length ? `${label}: ${parts}. Edit` : `${label}: add players or picks`}
      >
        <View style={styles.sideText}>
          <View style={styles.sideLabelRow}>
            <View style={[styles.sideDot, { backgroundColor: tone === 'danger' ? colors.danger : colors.successBright }]} />
            <AppText style={styles.sideLabel}>{label}</AppText>
          </View>
          {items.length ? (
            <AppText style={styles.sideCount}>
              {parts}
              {summary.total > 0 ? <AppText style={styles.sideTotal}> · {Math.round(summary.total).toLocaleString()}</AppText> : null}
            </AppText>
          ) : (
            <AppText style={styles.sideHint}>{hint ?? 'Add players or picks'}</AppText>
          )}
        </View>
        <AppText style={[styles.sideAdd, { color: colors.accent }]}>{items.length ? 'Edit' : '+ Add'}</AppText>
      </Pressable>
      {items.length ? (
        <View style={styles.sideChips}>
          {items.map((item) => (
            <Pressable key={item.key} style={styles.chip} onPress={() => onRemove(item.key)} accessibilityRole="button" accessibilityLabel={`Remove ${item.label}`}>
              <AppText style={styles.chipText} numberOfLines={1}>
                {item.label}
              </AppText>
              <Ionicons name="close" size={14} color={colors.textTertiary} />
            </Pressable>
          ))}
        </View>
      ) : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    backdrop: { ...StyleSheet.absoluteFillObject, backgroundColor: scrim, justifyContent: 'flex-end' },
    sheet: {
      backgroundColor: colors.surface,
      borderTopLeftRadius: radii.lg,
      borderTopRightRadius: radii.lg,
      borderWidth: 1,
      borderColor: colors.border,
      overflow: 'hidden',
    },
    header: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm, paddingHorizontal: spacing.lg, paddingBottom: spacing.sm },
    dot: { width: 8, height: 8, borderRadius: 4 },
    headerText: { flex: 1, minWidth: 0 },
    title: { fontSize: 19, fontWeight: '800', color: colors.textPrimary },
    subtitle: { fontSize: 13, color: colors.textTertiary },
    close: { width: 44, height: 44, borderRadius: radii.pill, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: colors.glassBorder, backgroundColor: colors.glassInset },
    chips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, paddingHorizontal: spacing.lg, paddingBottom: spacing.xs, maxHeight: 112, overflow: 'hidden' },
    sideChips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.xs, paddingBottom: spacing.xs },
    chip: {
      flexDirection: 'row',
      alignItems: 'center',
      gap: 6,
      maxWidth: '100%',
      minHeight: 36,
      paddingHorizontal: spacing.md,
      borderRadius: radii.pill,
      backgroundColor: colors.accentMuted,
      borderWidth: 1,
      borderColor: colors.accent,
    },
    chipText: { flexShrink: 1, fontSize: 13, fontWeight: '700', color: colors.textPrimary },
    controls: { paddingHorizontal: spacing.lg, paddingBottom: spacing.sm, gap: spacing.sm },
    searchRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    search: { flex: 1 },
    filterButton: { minHeight: 44, paddingHorizontal: spacing.md, borderRadius: radii.input, borderWidth: 1, borderColor: colors.borderStrong, alignItems: 'center', justifyContent: 'center' },
    filterButtonOpen: { borderColor: colors.accent },
    filterButtonText: { fontSize: 14, fontWeight: '800', color: colors.textPrimary },
    activeFilters: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    activeFiltersText: { flexShrink: 1, fontSize: 13, color: colors.textSecondary },
    clearLink: { minHeight: 44, justifyContent: 'center' },
    list: { flex: 1, paddingHorizontal: spacing.lg },
    groupLabel: { paddingTop: spacing.sm, paddingBottom: spacing.xs, fontSize: 12, fontWeight: '800', letterSpacing: 0.8, color: colors.textTertiary, textTransform: 'uppercase' },
    empty: { paddingVertical: spacing.xl, textAlign: 'center', color: colors.textTertiary },
    row: { flexDirection: 'row', alignItems: 'stretch', borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    rowOn: { backgroundColor: colors.accentMuted },
    rowMain: { flex: 1, minWidth: 0, minHeight: 56, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    rowIdentity: { flex: 1, minWidth: 0 },
    check: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: colors.borderStrong, alignItems: 'center', justifyContent: 'center' },
    info: { width: 44, alignItems: 'center', justifyContent: 'center' },
    filterPanel: { flex: 1 },
    filterScroll: { flex: 1, gap: spacing.lg, paddingHorizontal: spacing.lg, paddingTop: spacing.sm },
    filterGroup: { gap: spacing.sm },
    filterTitle: { fontSize: 12, fontWeight: '800', letterSpacing: 0.8, color: colors.textTertiary },
    filterChips: { flexDirection: 'row', flexWrap: 'wrap', gap: spacing.sm },
    filterChip: { minHeight: 44, minWidth: 56, paddingHorizontal: spacing.lg, borderRadius: radii.pill, borderWidth: 1, borderColor: colors.borderStrong, alignItems: 'center', justifyContent: 'center' },
    filterChipText: { fontSize: 14, fontWeight: '800', color: colors.textSecondary },
    footer: { flexDirection: 'row', alignItems: 'center', gap: spacing.md, paddingHorizontal: spacing.lg, paddingTop: spacing.sm, paddingBottom: spacing.xl, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.border, backgroundColor: colors.surface },
    footerCount: { fontSize: 13, color: colors.textSecondary },
    footerButton: { flex: 1 },
    side: { minWidth: 0, backgroundColor: colors.glass, borderRadius: radii.md, borderWidth: 1, borderColor: colors.glassBorder, padding: spacing.sm, gap: spacing.xs },
    sideOpen: { minHeight: 56, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: spacing.sm },
    sideText: { flex: 1, minWidth: 0, gap: 2 },
    sideLabelRow: { flexDirection: 'row', alignItems: 'center', gap: 6 },
    sideDot: { width: 7, height: 7, borderRadius: 3.5 },
    sideLabel: { fontSize: 12.5, fontWeight: '800', letterSpacing: 0.8, color: colors.textTertiary, textTransform: 'uppercase' },
    sideCount: { fontSize: 15, fontWeight: '800', color: colors.textPrimary },
    sideTotal: { fontSize: 13, fontWeight: '400', color: colors.textTertiary },
    sideHint: { fontSize: 14, color: colors.textSecondary },
    sideAdd: { fontSize: 14, fontWeight: '800' },
  });
}
