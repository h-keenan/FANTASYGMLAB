import React, { useMemo } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import Input from './Input';
import { useThemeMode } from '../context/ThemeModeContext';
import { spacing, type ThemeColors } from '../theme';

/**
 * Search in a crowded control row: collapsed it is a 44pt search icon button (so the row's tabs and Filters keep their room and a
 * placeholder is never squeezed); tapped, it fills the row (the parent hides its other controls while `open`) with the field and a
 * Close button. Web twin: web-next/src/components/ui/ExpandingSearch.tsx.
 */
export default function ExpandingSearch({
  value,
  onChange,
  open,
  onOpenChange,
  label = 'Search',
  placeholder = 'Search',
}: {
  value: string;
  onChange: (next: string) => void;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  label?: string;
  placeholder?: string;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);

  if (!open) {
    return (
      <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={() => onOpenChange(true)} style={styles.icon} testID="search-open">
        <Ionicons name="search-outline" size={20} color={value ? colors.accent : colors.textSecondary} />
      </Pressable>
    );
  }
  return (
    <View style={styles.expanded}>
      <Input autoFocus style={styles.field} placeholder={placeholder} value={value} onChangeText={onChange} autoCapitalize="none" accessibilityLabel={label} />
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Close search"
        onPress={() => {
          onChange('');
          onOpenChange(false);
        }}
        style={styles.close}
      >
        <AppText style={styles.closeText}>Close</AppText>
      </Pressable>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    icon: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center', borderRadius: 12, borderWidth: 1, borderColor: colors.glassInputBorder, backgroundColor: colors.glassInput },
    expanded: { flex: 1, minWidth: 0, flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    field: { flex: 1, minWidth: 0, fontSize: 15 },
    close: { minHeight: 44, justifyContent: 'center', paddingHorizontal: spacing.sm },
    closeText: { fontSize: 14, fontWeight: '700', color: colors.accent },
  });
}
