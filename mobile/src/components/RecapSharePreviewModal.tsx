import React, { useMemo, useRef, useState } from 'react';
import { Pressable, Share, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from './AppText';
import Button from './Button';
import { captureRef } from 'react-native-view-shot';
import * as Sharing from 'expo-sharing';

import type { WeeklyRecap } from '../lib/api';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors, scrim } from '../theme';
import RecapShareCard, { CARD_HEIGHT, CARD_WIDTH, type RecapRosterMap } from './RecapShareCard';
import { SheetModal, SwipeDismissCard } from './SwipeDismissSheet';
import { shareLink } from '../lib/shareLinks';

const PREVIEW_SCALE = 0.82;

interface Props {
  visible: boolean;
  onClose: () => void;
  leagueName: string;
  recap: WeeklyRecap;
  rosterMap: RecapRosterMap;
}

/** Preview + share sheet for the real branded recap PNG, plus a fallback plain-text share. */
export default function RecapSharePreviewModal({ visible, onClose, leagueName, recap, rosterMap }: Props) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const cardRef = useRef<View>(null);
  const [capturing, setCapturing] = useState(false);

  const onShareImage = async () => {
    if (!cardRef.current) return;
    setCapturing(true);
    try {
      const uri = await captureRef(cardRef, {
        format: 'png',
        quality: 1,
        result: 'tmpfile',
        width: CARD_WIDTH * 3,
        height: CARD_HEIGHT * 3,
      });
      const canShare = await Sharing.isAvailableAsync();
      if (canShare) {
        await Sharing.shareAsync(uri, { mimeType: 'image/png', dialogTitle: 'Share recap' });
      }
    } catch {
      // Fall through silently — the text-share fallback below still works.
    } finally {
      setCapturing(false);
    }
  };

  const onShareText = () => {
    const lines = [
      `${leagueName} — ${recap.headline}`,
      '',
      ...recap.stories.map((story) => `${story.title}: ${story.summary}`),
      '',
      'Recapped with FantasyDesk',
    ].filter(Boolean);
    Share.share({ message: [...lines, '', shareLink('recap')].join('\n') }).catch(() => {});
  };

  return (
    <SheetModal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <SwipeDismissCard style={styles.sheet} onDismiss={onClose}>
          <AppText style={styles.title}>Share this recap</AppText>
          <View style={styles.previewWrap}>
            <View style={styles.previewScaled}>
              <RecapShareCard ref={cardRef} leagueName={leagueName} recap={recap} rosterMap={rosterMap} />
            </View>
          </View>
          <Button label="Share image" onPress={onShareImage} loading={capturing} style={styles.primaryButton} />
          <TouchableOpacity style={styles.secondaryButton} onPress={onShareText}>
            <AppText style={styles.secondaryButtonText}>Share as text instead</AppText>
          </TouchableOpacity>
          <TouchableOpacity style={styles.closeButton} onPress={onClose}>
            <AppText style={styles.closeButtonText}>Cancel</AppText>
          </TouchableOpacity>
        </SwipeDismissCard>
      </Pressable>
    </SheetModal>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: scrim,
    alignItems: 'center',
    justifyContent: 'center',
    padding: spacing.lg,
  },
  sheet: {
    backgroundColor: colors.backgroundElevated,
    borderRadius: radii.lg,
    borderWidth: 1,
    borderColor: colors.cardBorder,
    padding: spacing.lg,
    alignItems: 'center',
    width: '100%',
    maxWidth: 400,
  },
  title: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, marginBottom: spacing.md },
  // See TradeSharePreviewModal's identical fix: a plain `transform: scale`
  // shrinks what's drawn but not the layout box, so the wrapper is sized to
  // the post-scale dimensions and clips the oversized box to fit, with the
  // scale anchored top-left instead of a hand-tuned negative-margin fudge.
  previewWrap: {
    width: CARD_WIDTH * PREVIEW_SCALE,
    height: CARD_HEIGHT * PREVIEW_SCALE,
    overflow: 'hidden',
  },
  previewScaled: {
    width: CARD_WIDTH,
    height: CARD_HEIGHT,
    transform: [{ scale: PREVIEW_SCALE }],
    transformOrigin: '0 0',
  },
  primaryButton: { width: '100%', marginTop: spacing.md },
  secondaryButton: { paddingVertical: spacing.sm, marginTop: spacing.xs },
  secondaryButtonText: { color: colors.accent, fontSize: 13, fontWeight: '600' },
  closeButton: { paddingVertical: spacing.sm },
  closeButtonText: { color: colors.textSecondary, fontSize: 13, fontWeight: '600' },
  });
}
