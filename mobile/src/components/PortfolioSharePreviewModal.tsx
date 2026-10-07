import React, { useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, Share, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from './AppText';
import { captureRef } from 'react-native-view-shot';
import * as Sharing from 'expo-sharing';
import { Ionicons } from '@expo/vector-icons';

import type { PortfolioLeague } from '../lib/api';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import PortfolioShareCard, { CARD_HEIGHT, CARD_WIDTH, portfolioHeadlineStat } from './PortfolioShareCard';

const PREVIEW_SCALE = 0.82;

interface Props {
  visible: boolean;
  onClose: () => void;
  leagues: PortfolioLeague[];
}

/** Preview + share sheet for the real branded Portfolio PNG, plus a fallback plain-text share. */
export default function PortfolioSharePreviewModal({ visible, onClose, leagues }: Props) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const cardRef = useRef<View>(null);
  const [capturing, setCapturing] = useState(false);
  // Same root cause as TradeSharePreviewModal's identical comment:
  // captureRef doesn't wait for in-flight <Image> loads, so onShareImage
  // waits on PortfolioShareCard's reported readiness below before snapping.
  const imagesReadyRef = useRef(false);

  const waitForImagesReady = async (timeoutMs = 4000) => {
    const start = Date.now();
    while (!imagesReadyRef.current && Date.now() - start < timeoutMs) {
      // eslint-disable-next-line no-await-in-loop
      await new Promise((resolve) => setTimeout(resolve, 50));
    }
  };

  const onShareImage = async () => {
    if (!cardRef.current) return;
    setCapturing(true);
    try {
      await waitForImagesReady();
      // Yield two animation frames so the native layer flushes the paint
      // before the native snapshot runs — see TradeSharePreviewModal's
      // identical comment for why this isn't a guessed fixed wait.
      await new Promise<void>((resolve) => requestAnimationFrame(() => requestAnimationFrame(() => resolve())));
      const uri = await captureRef(cardRef, {
        format: 'png',
        quality: 1,
        result: 'tmpfile',
        width: CARD_WIDTH * 3,
        height: CARD_HEIGHT * 3,
      });
      const canShare = await Sharing.isAvailableAsync();
      if (canShare) {
        await Sharing.shareAsync(uri, { mimeType: 'image/png', dialogTitle: 'Share portfolio' });
      }
    } catch {
      // Fall through silently — the text-share fallback below still works.
    } finally {
      setCapturing(false);
    }
  };

  const onShareText = () => {
    const headline = portfolioHeadlineStat(leagues);
    const lines = [
      `My FantasyGM Lab Portfolio — ${headline}`,
      '',
      ...leagues.map((league) => {
        const record = league.wins == null && league.losses == null ? '' : ` (${league.wins ?? 0}-${league.losses ?? 0})`;
        const rank = league.power_rank != null ? ` — ${league.power_rank_tied ? 'T-' : '#'}${league.power_rank}` : '';
        return `${league.league_name}${record}${rank}`;
      }),
      '',
      'Tracked with FantasyGM Lab',
    ].filter(Boolean);
    Share.share({ message: lines.join('\n') }).catch(() => {});
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <AppText style={styles.title}>Share your portfolio</AppText>
          <View style={styles.previewWrap}>
            <View style={styles.previewScaled}>
              <PortfolioShareCard
                ref={cardRef}
                leagues={leagues}
                onReadyChange={(ready) => {
                  imagesReadyRef.current = ready;
                }}
              />
            </View>
          </View>
          <TouchableOpacity style={styles.primaryButton} onPress={onShareImage} disabled={capturing}>
            {capturing ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <>
                <Ionicons name="image-outline" size={16} color="#fff" />
                <AppText style={styles.primaryButtonText}>Share image</AppText>
              </>
            )}
          </TouchableOpacity>
          <TouchableOpacity style={styles.secondaryButton} onPress={onShareText}>
            <AppText style={styles.secondaryButtonText}>Share as text instead</AppText>
          </TouchableOpacity>
          <TouchableOpacity style={styles.closeButton} onPress={onClose}>
            <AppText style={styles.closeButtonText}>Cancel</AppText>
          </TouchableOpacity>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
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
  primaryButton: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: spacing.xs,
    backgroundColor: colors.accent,
    borderRadius: radii.md,
    paddingVertical: spacing.md,
    width: '100%',
    marginTop: spacing.md,
  },
  primaryButtonText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  secondaryButton: { paddingVertical: spacing.sm, marginTop: spacing.xs },
  secondaryButtonText: { color: colors.accent, fontSize: 13, fontWeight: '600' },
  closeButton: { paddingVertical: spacing.sm },
  closeButtonText: { color: colors.textSecondary, fontSize: 13, fontWeight: '600' },
  });
}
