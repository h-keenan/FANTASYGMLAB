import React, { useMemo } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import AppText from './AppText';
import { Ionicons } from '@expo/vector-icons';

import type { RecapStory, RecapTradeAsset } from '../lib/api';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import IconCircle from './IconCircle';
import PlayerAvatar from './PlayerAvatar';
import PositionBadge from './PositionBadge';

interface Props {
  visible: boolean;
  onClose: () => void;
  story: RecapStory | null;
}

/**
 * Read-only, historical trade detail — opened by tapping a "Notable trade"
 * recap card. Deliberately not the live Trade Analyzer (which grades a
 * hypothetical proposal): this just displays the full asset lists for a
 * trade that already happened, using the untruncated `left_assets` /
 * `right_assets` modules/league_recaps.py's `_trade_story` now includes
 * (the card itself, and `players`, stay truncated to 2-per-side).
 */
export default function RecapTradeDetailModal({ visible, onClose, story }: Props) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (!story) return null;
  const leftAssets = story.left_assets ?? [];
  const rightAssets = story.right_assets ?? [];

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.backdrop} onPress={onClose}>
        <Pressable style={styles.sheet} onPress={(e) => e.stopPropagation()}>
          <View style={styles.headerRow}>
            <AppText style={styles.title} numberOfLines={1}>
              {story.title || 'Trade detail'}
            </AppText>
            <Pressable onPress={onClose} hitSlop={8}>
              <Ionicons name="close" size={20} color={colors.textSecondary} />
            </Pressable>
          </View>
          {story.summary ? <AppText style={styles.summary}>{story.summary}</AppText> : null}
          <ScrollView style={styles.body} contentContainerStyle={styles.bodyContent}>
            <TeamAssetColumn teamName={story.primary_team} assets={leftAssets} />
            <View style={styles.divider}>
              <Ionicons name="swap-horizontal" size={16} color={colors.textTertiary} />
            </View>
            <TeamAssetColumn teamName={story.secondary_team} assets={rightAssets} />
            {story.editorial_label ? (
              <AppText style={styles.editorial}>{story.editorial_label}</AppText>
            ) : null}
            {(story.value_lenses ?? []).map((lens, index) => (
              <View key={`${lens.lens}-${index}`} style={styles.lensRow}>
                <AppText style={styles.lensLabel}>{lens.label}</AppText>
                <AppText style={styles.lensNote}>{lens.note}</AppText>
              </View>
            ))}
          </ScrollView>
        </Pressable>
      </Pressable>
    </Modal>
  );
}

function TeamAssetColumn({ teamName, assets }: { teamName: string; assets: RecapTradeAsset[] }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.column}>
      <AppText style={styles.columnTeam} numberOfLines={1}>
        {teamName || 'Unknown team'}
      </AppText>
      {assets.length === 0 ? (
        <AppText style={styles.emptyNote}>No assets recorded</AppText>
      ) : (
        assets.map((asset, index) => <AssetRow key={`${asset.name}-${index}`} asset={asset} />)
      )}
    </View>
  );
}

function AssetRow({ asset }: { asset: RecapTradeAsset }) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  if (asset.kind === 'pick') {
    return (
      <View style={styles.assetRow}>
        <IconCircle name="albums-outline" color={colors.accent} size={32} iconSize={16} />
        <AppText style={styles.assetName} numberOfLines={1}>
          {asset.label || asset.name}
        </AppText>
      </View>
    );
  }
  return (
    <View style={styles.assetRow}>
      <PlayerAvatar playerId={asset.player_id} size={32} />
      <View style={styles.assetInfo}>
        <AppText style={styles.assetName} numberOfLines={1}>
          {asset.name}
        </AppText>
        <View style={styles.assetMetaRow}>
          <PositionBadge position={asset.position} />
          {asset.team ? <AppText style={styles.assetMeta}>{asset.team}</AppText> : null}
        </View>
      </View>
    </View>
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
    width: '100%',
    maxWidth: 420,
    maxHeight: '80%',
  },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: spacing.xs,
  },
  title: { fontSize: 16, fontWeight: '700', color: colors.textPrimary, flex: 1, marginRight: spacing.sm },
  summary: { fontSize: 13, color: colors.textSecondary, lineHeight: 18, marginBottom: spacing.md },
  body: { flexGrow: 0 },
  bodyContent: { paddingBottom: spacing.sm },
  column: { marginBottom: spacing.md },
  columnTeam: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.accent,
    letterSpacing: 0.4,
    marginBottom: spacing.sm,
    textTransform: 'uppercase',
  },
  divider: { alignItems: 'center', marginVertical: spacing.xs },
  emptyNote: { fontSize: 13, color: colors.textTertiary },
  assetRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.sm,
    paddingVertical: spacing.xs,
  },
  assetInfo: { flex: 1 },
  assetName: { fontSize: 14, fontWeight: '600', color: colors.textPrimary },
  assetMetaRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginTop: 2 },
  assetMeta: { fontSize: 11, color: colors.textSecondary },
  editorial: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.textSecondary,
    marginTop: spacing.sm,
  },
  lensRow: { marginTop: spacing.xs },
  lensLabel: { fontSize: 12, fontWeight: '700', color: colors.textPrimary },
  lensNote: { fontSize: 11, color: colors.textTertiary, marginTop: 1 },
  });
}
