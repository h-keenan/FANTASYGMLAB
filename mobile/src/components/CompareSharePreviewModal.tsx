import React, { useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Modal, Pressable, Share, StyleSheet, TouchableOpacity, View } from 'react-native';
import AppText from './AppText';
import { captureRef } from 'react-native-view-shot';
import * as Sharing from 'expo-sharing';
import { Ionicons } from '@expo/vector-icons';

import { useThemeMode } from '../context/ThemeModeContext';
import type { CompareRow } from '../lib/playerCompare';
import { radii, spacing, type ThemeColors } from '../theme';
import CompareShareCard, { CARD_HEIGHT, CARD_WIDTH, type CompareShareCardSide } from './CompareShareCard';

const PREVIEW_SCALE = 0.82;

interface Props {
  visible: boolean;
  onClose: () => void;
  sideA: CompareShareCardSide;
  sideB: CompareShareCardSide;
  rows: CompareRow[];
}

/** Preview + share sheet for the real branded head-to-head PNG, plus a
 * fallback plain-text share — same structure as PlayerSharePreviewModal/
 * TradeSharePreviewModal, just captured off CompareShareCard instead. See
 * those components' comments for why the capture waits on image-settle +
 * two animation frames before snapshotting. */
export default function CompareSharePreviewModal({ visible, onClose, sideA, sideB, rows }: Props) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const cardRef = useRef<View>(null);
  const [capturing, setCapturing] = useState(false);
  // See TradeShareCard/TradeSharePreviewModal's identical imagesReadyRef
  // comment: captureRef does not wait for in-flight <Image> loads, so both
  // headshots' readiness is tracked here and awaited before capture.
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
      // Same two-animation-frame yield TradeSharePreviewModal uses — gives
      // the native layer time to actually paint the settled images before
      // the native snapshot runs.
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
        await Sharing.shareAsync(uri, { mimeType: 'image/png', dialogTitle: `Share ${sideA.name} vs ${sideB.name}` });
      }
    } catch {
      // Fall through silently — the text-share fallback below still works.
    } finally {
      setCapturing(false);
    }
  };

  const onShareText = () => {
    const display = (row: CompareRow, value: number | null) =>
      value === null ? '—' : row.format ? row.format(value) : String(value);
    const rowLines = rows
      .filter((row) => row.a !== null || row.b !== null)
      .map((row) => `${row.label}: ${display(row, row.a)} vs ${display(row, row.b)}`);
    const lines = [`${sideA.name} vs ${sideB.name}`, ...rowLines, '', 'Compared with FantasyGM Lab'].filter(Boolean);
    Share.share({ message: lines.join('\n') }).catch(() => {});
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <AppText style={styles.title}>Share this comparison</AppText>
          <View style={styles.previewWrap}>
            <View style={styles.previewScaled}>
              <CompareShareCard
                ref={cardRef}
                sideA={sideA}
                sideB={sideB}
                rows={rows}
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
  // Same post-scale-clip trick PlayerSharePreviewModal/TradeSharePreviewModal
  // use: the card renders at its real CARD_WIDTH/CARD_HEIGHT (so
  // react-native-view-shot captures it full-resolution via cardRef), then
  // gets visually shrunk to fit the modal via a corner-anchored transform,
  // with the wrapper sized to the post-scale dimensions to clip the
  // oversized layout box down to exactly that size.
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
