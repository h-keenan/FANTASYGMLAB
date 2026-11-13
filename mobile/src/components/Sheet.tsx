import React, { useEffect, useId, useMemo, useSyncExternalStore, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import AppText from './AppText';
import { SheetModal, SheetScrollView, SwipeDismissCard } from './SwipeDismissSheet';
import { useThemeMode } from '../context/ThemeModeContext';
import { sheetStack } from '../lib/sheetStack';
import { radii, scrim, spacing, type ThemeColors } from '../theme';

export type SheetProps = {
  open: boolean;
  onClose: () => void;
  /** The sheet's accessible name and visible heading. */
  title: string;
  /** One line under the title. */
  description?: string;
  children: ReactNode;
  /** Sticky footer (an Apply bar, for example). Sits above the safe area. */
  footer?: ReactNode;
  /** Same prop as web; on phones every size is a full-width bottom sheet. */
  size?: 'sm' | 'md' | 'lg';
  /** Hide the visible heading (the title still names the sheet). */
  hideTitle?: boolean;
  testID?: string;
};

/**
 * The one sheet (twin of web-next's components/ui/Sheet.tsx, same props). A
 * bottom sheet with a grab bar, swipe-down to dismiss, a scrim you can tap,
 * Android back to close, safe-area aware. It composes SheetModal /
 * SwipeDismissCard / SheetScrollView, which already own the gesture.
 *
 * Stacking rule: sheets never stack. Opening a second sheet HIDES the first
 * (React Native cannot present two Modals reliably); closing the second brings
 * it back. A hidden sheet's children are unmounted by the Modal, so keep
 * anything that must survive in the CALLER's state, not inside the sheet.
 */
export function Sheet({ open, onClose, title, description, children, footer, hideTitle = false, testID }: SheetProps) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const insets = useSafeAreaInsets();
  const id = useId();

  useSyncExternalStore(sheetStack.subscribe, sheetStack.version, sheetStack.version);
  useEffect(() => {
    if (!open) return;
    sheetStack.open(id);
    return () => sheetStack.close(id);
  }, [open, id]);

  const hidden = open && sheetStack.isHidden(id);
  if (!open) return null;

  return (
    <SheetModal visible={!hidden} transparent animationType="slide" onRequestClose={onClose} statusBarTranslucent>
      <Pressable style={styles.backdrop} onPress={onClose} accessibilityLabel={`Close ${title}`} accessibilityRole="button">
        <SwipeDismissCard style={styles.sheet} onDismiss={onClose} testID={testID}>
          <View style={styles.header} accessibilityViewIsModal>
            <View style={styles.headerText}>
              <AppText
                accessibilityRole="header"
                style={hideTitle ? styles.srOnly : styles.title}
                numberOfLines={2}
              >
                {title}
              </AppText>
              {description ? <AppText style={styles.description}>{description}</AppText> : null}
            </View>
            <Pressable onPress={onClose} hitSlop={10} style={styles.close} accessibilityRole="button" accessibilityLabel={`Close ${title}`}>
              <Ionicons name="close" size={18} color={colors.textSecondary} />
            </Pressable>
          </View>
          <SheetScrollView
            contentContainerStyle={[styles.content, !footer && { paddingBottom: spacing.xl + insets.bottom }]}
            showsVerticalScrollIndicator={false}
            keyboardShouldPersistTaps="handled"
          >
            {children}
          </SheetScrollView>
          {footer ? <View style={[styles.footer, { paddingBottom: spacing.md + insets.bottom }]}>{footer}</View> : null}
        </SwipeDismissCard>
      </Pressable>
    </SheetModal>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    backdrop: { flex: 1, backgroundColor: scrim, justifyContent: 'flex-end' },
    sheet: {
      backgroundColor: colors.surface,
      borderTopLeftRadius: radii.lg,
      borderTopRightRadius: radii.lg,
      borderWidth: 1,
      borderBottomWidth: 0,
      borderColor: colors.glassBorder,
      maxHeight: '88%',
    },
    header: { flexDirection: 'row', alignItems: 'flex-start', gap: spacing.sm, paddingHorizontal: spacing.lg, paddingBottom: spacing.xs },
    headerText: { flex: 1, minWidth: 0 },
    title: { fontSize: 19, fontWeight: '800', color: colors.textPrimary },
    description: { fontSize: 13, color: colors.textTertiary, marginTop: 2 },
    srOnly: { position: 'absolute', width: 1, height: 1, opacity: 0 },
    close: {
      width: 32,
      height: 32,
      borderRadius: radii.pill,
      alignItems: 'center',
      justifyContent: 'center',
      borderWidth: 1,
      borderColor: colors.glassBorder,
      backgroundColor: colors.glassInset,
    },
    content: { paddingHorizontal: spacing.lg, paddingTop: spacing.sm, gap: spacing.md },
    footer: {
      paddingHorizontal: spacing.lg,
      paddingTop: spacing.md,
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: colors.border,
      backgroundColor: colors.surface,
    },
  });
}
