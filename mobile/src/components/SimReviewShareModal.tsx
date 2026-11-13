import React, { useMemo, useRef, useState } from 'react';
import { Pressable, Share, StyleSheet, TouchableOpacity, View } from 'react-native';
import { captureRef } from 'react-native-view-shot';
import * as Sharing from 'expo-sharing';

import AppText from './AppText';
import Button from './Button';
import { CARD_WIDTH } from './ShareCardChrome';
import SimReviewShareCard, { SIM_REVIEW_CARD_HEIGHT } from './SimReviewShareCard';
import { SheetModal, SwipeDismissCard } from './SwipeDismissSheet';
import { useThemeMode } from '../context/ThemeModeContext';
import { shareLink } from '../lib/shareLinks';
import { reviewShareLines, type ReviewSection, type ReviewShareModel } from '../lib/simReview';
import { radii, scrim, spacing, type ThemeColors } from '../theme';

const PREVIEW_SCALE = 0.82;

/** Preview + share sheet for the Season in Review PNG, with a plain-text fallback. */
export default function SimReviewShareModal({
  visible,
  onClose,
  model,
  sections,
}: {
  visible: boolean;
  onClose: () => void;
  model: ReviewShareModel;
  sections: readonly ReviewSection[];
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const cardRef = useRef<View>(null);
  const [capturing, setCapturing] = useState(false);

  const onShareImage = async () => {
    if (!cardRef.current) return;
    setCapturing(true);
    try {
      const uri = await captureRef(cardRef, { format: 'png', quality: 1, result: 'tmpfile', width: CARD_WIDTH * 3, height: SIM_REVIEW_CARD_HEIGHT * 3 });
      if (await Sharing.isAvailableAsync()) await Sharing.shareAsync(uri, { mimeType: 'image/png', dialogTitle: 'Share your season' });
    } catch {
      // The text share below still works.
    } finally {
      setCapturing(false);
    }
  };

  const onShareText = () => {
    const lines = [`${[model.headline, model.record].filter(Boolean).join(", ")}. Grade ${model.letter}.`, ...reviewShareLines(sections), '', 'Play Fantasy Sim on FantasyDesk.', shareLink('recap')];
    Share.share({ message: lines.join('\n') }).catch(() => {});
  };

  return (
    <SheetModal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <SwipeDismissCard style={styles.sheet} onDismiss={onClose}>
          <AppText style={styles.title}>Share your season</AppText>
          <View style={styles.previewWrap}>
            <View style={styles.previewScaled}>
              <SimReviewShareCard ref={cardRef} model={model} />
            </View>
          </View>
          <Button label="Share image" onPress={onShareImage} loading={capturing} style={styles.primary} />
          <TouchableOpacity style={styles.secondary} onPress={onShareText}>
            <AppText style={styles.secondaryText}>Share as text instead</AppText>
          </TouchableOpacity>
          <TouchableOpacity style={styles.secondary} onPress={onClose}>
            <AppText style={styles.closeText}>Cancel</AppText>
          </TouchableOpacity>
        </SwipeDismissCard>
      </Pressable>
    </SheetModal>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    backdrop: { flex: 1, backgroundColor: scrim, alignItems: 'center', justifyContent: 'center', padding: spacing.lg },
    sheet: { backgroundColor: colors.backgroundElevated, borderRadius: radii.lg, borderWidth: 1, borderColor: colors.cardBorder, padding: spacing.lg, alignItems: 'center', width: '100%', maxWidth: 400 },
    title: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.md },
    previewWrap: { width: CARD_WIDTH * PREVIEW_SCALE, height: SIM_REVIEW_CARD_HEIGHT * PREVIEW_SCALE, overflow: 'hidden' },
    previewScaled: { width: CARD_WIDTH, height: SIM_REVIEW_CARD_HEIGHT, transform: [{ scale: PREVIEW_SCALE }], transformOrigin: '0 0' },
    primary: { width: '100%', marginTop: spacing.md },
    secondary: { paddingVertical: spacing.sm, marginTop: spacing.xs },
    secondaryText: { color: colors.accent, fontSize: 13, fontWeight: '600' },
    closeText: { color: colors.textSecondary, fontSize: 13, fontWeight: '600' },
  });
}
