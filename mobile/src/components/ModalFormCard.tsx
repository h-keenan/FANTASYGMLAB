import React, { useMemo } from 'react';
import { StyleSheet, View } from 'react-native';

import AppText from './AppText';
import Button from './Button';
import { SheetModal, SwipeDismissCard } from './SwipeDismissSheet';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, scrim, spacing, type ThemeColors } from '../theme';

/**
 * The one centered form dialog (rename a league, add a league, create an
 * account): scrim backdrop, a swipe-down-to-dismiss card, and the shared
 * title / hint / Cancel + confirm rows. Replaces the per-screen
 * rename and guestUpgrade style copies in Home and More.
 */
export default function ModalFormCard({
  visible,
  onClose,
  handleOnly = false,
  children,
}: {
  visible: boolean;
  onClose: () => void;
  /** Only the grab bar may drag (for cards with scrolling content). */
  handleOnly?: boolean;
  children: React.ReactNode;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <SheetModal visible={visible} animationType="fade" transparent onRequestClose={onClose}>
      <View style={styles.backdrop}>
        <SwipeDismissCard style={styles.card} onDismiss={onClose} handleOnly={handleOnly}>
          {children}
        </SwipeDismissCard>
      </View>
    </SheetModal>
  );
}

export function ModalFormTitle({ children }: { children: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return <AppText style={styles.title}>{children}</AppText>;
}

export function ModalFormHint({ children }: { children: string }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return <AppText style={styles.hint}>{children}</AppText>;
}

/** Cancel (ghost) + confirm (primary, spinner while `loading`) row. */
export function ModalFormActions({
  onCancel,
  cancelLabel = 'Cancel',
  cancelDisabled = false,
  confirmLabel,
  onConfirm,
  confirmDisabled = false,
  confirmLoading = false,
}: {
  onCancel: () => void;
  cancelLabel?: string;
  cancelDisabled?: boolean;
  confirmLabel: string;
  onConfirm: () => void;
  confirmDisabled?: boolean;
  confirmLoading?: boolean;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.actions}>
      <Button label={cancelLabel} variant="ghost" onPress={onCancel} disabled={cancelDisabled} />
      <Button label={confirmLabel} onPress={onConfirm} disabled={confirmDisabled} loading={confirmLoading} />
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    backdrop: { flex: 1, backgroundColor: scrim, justifyContent: 'center', padding: spacing.xl },
    card: {
      backgroundColor: colors.backgroundElevated,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      padding: spacing.lg,
    },
    title: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: 4 },
    hint: { fontSize: 12, color: colors.textSecondary, marginBottom: spacing.md, lineHeight: 16 },
    actions: {
      flexDirection: 'row',
      justifyContent: 'flex-end',
      gap: spacing.sm,
      marginTop: spacing.md,
    },
  });
}
