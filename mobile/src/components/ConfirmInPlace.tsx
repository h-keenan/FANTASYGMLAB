import React, { useCallback, useEffect, useMemo, useReducer, useState, type ReactNode } from 'react';
import { AccessibilityInfo, Pressable, StyleSheet, View, type LayoutChangeEvent, type StyleProp, type ViewStyle } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import Button from './Button';
import { useThemeMode } from '../context/ThemeModeContext';
import {
  DEFAULT_ERROR_TEXT,
  confirmAnnouncement,
  reduceConfirm,
  revertMs,
  type ConfirmMode,
} from '../lib/confirmInPlace';
import { disabledOpacity, radii, spacing, type ThemeColors } from '../theme';

export type ConfirmInPlaceProps = {
  /** 'button' = text button, 'icon' = icon-only (trash), 'row' = a full-width row action. */
  variant?: 'button' | 'icon' | 'row';
  /** Trigger text (button / row) or accessible name (icon). */
  label: string;
  /** Accessible name for the idle trigger when the visible text is shorter ("Remove" vs "Remove Team 3"). */
  ariaLabel?: string;
  /**
   * 'tap-again': the control keeps its footprint, its label becomes "Tap again to confirm", reverts
   * after 4 s. 'ask': the control is replaced, in place, by "<prompt> [Confirm] [Keep]".
   * Default: tap-again for 'button', ask for 'icon' and 'row'.
   */
  mode?: ConfirmMode;
  prompt?: string;
  confirmLabel?: string;
  keepLabel?: string;
  /** Runs on the confirming tap. Throw, reject or return false to show the error state. */
  onConfirm: () => void | boolean | Promise<void | boolean>;
  errorText?: string;
  disabled?: boolean;
  buttonVariant?: 'secondary' | 'dangerOutline' | 'ghost';
  size?: 'sm' | 'md';
  /** Custom glyph for the icon variant (default: trash). */
  icon?: ReactNode;
  /**
   * The row's own content, shown to the left of the trigger. In 'ask' mode the panel replaces the
   * WHOLE row (content and trigger) at the height the row had, so a list never jumps. React Native
   * cannot paint over siblings, which is why the row is handed in rather than covered
   * (web-next uses `overlay="parent"` for the same effect).
   */
  rowContent?: ReactNode;
  style?: StyleProp<ViewStyle>;
  testID?: string;
};

/**
 * Twin of web-next's components/ui/ConfirmInPlace.tsx. A destructive control
 * that confirms where it stands: first tap morphs it in place, the second
 * acts. State machine and copy: lib/confirmInPlace.ts.
 *
 * a11y: the polite announcement goes through AccessibilityInfo; the trigger
 * reports `expanded`; the destructive button is never first in reading order
 * (Keep comes first); there is no motion to reduce (changes are instant).
 */
export default function ConfirmInPlace({
  variant = 'button',
  label,
  ariaLabel,
  mode,
  prompt = 'Are you sure?',
  confirmLabel,
  keepLabel = 'Keep',
  onConfirm,
  errorText = DEFAULT_ERROR_TEXT,
  disabled = false,
  buttonVariant = 'dangerOutline',
  size = 'md',
  icon,
  rowContent,
  style,
  testID,
}: ConfirmInPlaceProps) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const resolvedMode: ConfirmMode = variant === 'icon' ? 'ask' : (mode ?? (variant === 'button' ? 'tap-again' : 'ask'));
  const [phase, dispatch] = useReducer(reduceConfirm, 'idle');
  const [rowHeight, setRowHeight] = useState<number | null>(null);
  const confirmText = confirmLabel ?? label;

  // Announce each phase change once.
  useEffect(() => {
    const text = confirmAnnouncement(phase, resolvedMode, { label, prompt, confirmLabel: confirmText, keepLabel, errorText });
    if (text) AccessibilityInfo.announceForAccessibility(text);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [phase, resolvedMode]);

  // Auto-revert while armed (never mid-request or while showing an error).
  useEffect(() => {
    if (phase !== 'armed') return;
    const timer = setTimeout(() => dispatch('timeout'), revertMs(resolvedMode));
    return () => clearTimeout(timer);
  }, [phase, resolvedMode]);

  const run = useCallback(async () => {
    dispatch('confirm');
    try {
      const result = await onConfirm();
      dispatch(result === false ? 'failed' : 'succeeded');
    } catch {
      dispatch('failed');
    }
  }, [onConfirm]);

  const onTrigger = () => {
    if (phase === 'idle') dispatch('arm');
    else if (resolvedMode === 'tap-again' && phase === 'armed') void run();
  };

  const busy = phase === 'busy';
  const showPanel = (resolvedMode === 'ask' && phase !== 'idle') || phase === 'error';
  const armedTapAgain = resolvedMode === 'tap-again' && phase === 'armed';

  const trigger =
    variant === 'icon' ? (
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={label}
        accessibilityState={{ disabled: disabled || busy, expanded: showPanel }}
        disabled={disabled || busy}
        onPress={onTrigger}
        style={({ pressed }) => [styles.icon, pressed && styles.pressed, (disabled || busy) && styles.dim]}
        testID={testID ? `${testID}-trigger` : undefined}
      >
        {icon ?? <Ionicons name="trash-outline" size={18} color={colors.danger} />}
      </Pressable>
    ) : resolvedMode === 'tap-again' ? (
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={armedTapAgain ? `Tap again to confirm: ${label}` : (ariaLabel ?? label)}
        accessibilityState={{ disabled: disabled || busy, busy, expanded: armedTapAgain }}
        disabled={disabled || busy}
        onPress={onTrigger}
        style={({ pressed }) => [
          styles.tapAgain,
          size === 'sm' && styles.tapAgainSm,
          buttonVariant === 'secondary' && styles.tapAgainSecondary,
          buttonVariant === 'ghost' && styles.tapAgainGhost,
          armedTapAgain && styles.tapAgainArmed,
          variant === 'row' && styles.fill,
          pressed && styles.pressed,
          (disabled || busy) && styles.dim,
        ]}
        testID={testID ? `${testID}-trigger` : undefined}
      >
        {/* Invisible copy of the longer label holds the width, so arming never resizes the button. */}
        <AppText style={[styles.tapAgainText, styles.sizer]} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
          {label.length > 'Tap again to confirm'.length ? label : 'Tap again to confirm'}
        </AppText>
        <AppText
          style={[styles.tapAgainText, styles.tapAgainVisible, { color: buttonVariant === 'secondary' && !armedTapAgain ? colors.textPrimary : colors.danger }]}
          numberOfLines={1}
        >
          {armedTapAgain ? 'Tap again to confirm' : label}
        </AppText>
      </Pressable>
    ) : (
      <Button label={label} variant={buttonVariant === 'ghost' ? 'ghost' : buttonVariant} size={size} disabled={disabled} onPress={onTrigger} />
    );

  const panel = (
    <View style={[styles.panel, rowHeight ? { height: rowHeight } : null]} accessibilityLiveRegion={phase === 'error' ? 'assertive' : 'polite'} testID={testID ? `${testID}-panel` : undefined}>
      <AppText style={styles.panelText} numberOfLines={2} accessibilityRole="alert">
        {phase === 'error' ? errorText : prompt}
      </AppText>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={phase === 'error' ? 'Cancel' : keepLabel}
        disabled={busy}
        onPress={() => dispatch('cancel')}
        style={[styles.keep, busy && styles.dim]}
      >
        <AppText style={styles.keepText}>{phase === 'error' ? 'Cancel' : keepLabel}</AppText>
      </Pressable>
      <Button label={phase === 'error' ? 'Retry' : confirmText} variant="danger" size="sm" loading={busy} onPress={() => void run()} />
    </View>
  );

  const onLayout = (event: LayoutChangeEvent) => {
    if (!showPanel) setRowHeight(event.nativeEvent.layout.height);
  };

  if (rowContent) {
    return (
      <View style={style} testID={testID}>
        {showPanel ? (
          panel
        ) : (
          <View style={styles.row} onLayout={onLayout}>
            <View style={styles.rowContent}>{rowContent}</View>
            {trigger}
          </View>
        )}
      </View>
    );
  }

  return (
    <View style={style} testID={testID} onLayout={onLayout}>
      {showPanel ? panel : trigger}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    row: { flexDirection: 'row', alignItems: 'stretch', gap: spacing.sm },
    rowContent: { flex: 1, minWidth: 0 },
    icon: {
      minWidth: 44,
      minHeight: 44,
      alignItems: 'center',
      justifyContent: 'center',
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.danger,
    },
    tapAgain: {
      minHeight: 44,
      paddingHorizontal: spacing.lg,
      alignItems: 'center',
      justifyContent: 'center',
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.danger,
      alignSelf: 'flex-start',
    },
    tapAgainSm: { paddingHorizontal: spacing.md },
    tapAgainSecondary: { borderColor: colors.borderStrong },
    tapAgainGhost: { borderColor: 'transparent' },
    tapAgainArmed: { borderColor: colors.danger, backgroundColor: colors.dangerMuted },
    fill: { alignSelf: 'stretch' },
    tapAgainText: { fontSize: 14, fontWeight: '700' },
    sizer: { opacity: 0 },
    tapAgainVisible: { position: 'absolute', left: 0, right: 0, textAlign: 'center' },
    panel: {
      minHeight: 44,
      flexDirection: 'row',
      alignItems: 'center',
      gap: spacing.sm,
      paddingLeft: spacing.md,
      paddingRight: spacing.sm,
      borderRadius: radii.md,
      borderWidth: 1,
      borderColor: colors.danger,
      backgroundColor: colors.dangerMuted,
    },
    panelText: { flex: 1, minWidth: 0, fontSize: 13.5, fontWeight: '700', color: colors.textPrimary },
    keep: { minHeight: 44, paddingHorizontal: spacing.sm, alignItems: 'center', justifyContent: 'center' },
    keepText: { fontSize: 13.5, fontWeight: '800', color: colors.textSecondary },
    pressed: { opacity: 0.7 },
    dim: { opacity: disabledOpacity },
  });
}
