import React, { useMemo } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, View } from 'react-native';
import AppText from './AppText';
import { Ionicons } from '@expo/vector-icons';

import type { RecapStory, RecapTradeAsset } from '../lib/api';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import CompactPlayerModule from './CompactPlayerModule';
import IconCircle from './IconCircle';
import TeamAvatar from './TeamAvatar';

interface Props {
  visible: boolean;
  onClose: () => void;
  story: RecapStory | null;
  /** Sleeper avatar ids for the trade's two sides, already resolved by the
   * caller (RecapScreen's own `rosterMap`/`avatarFor`) — this modal takes
   * plain ids rather than importing that screen's roster-lookup machinery,
   * to avoid a screen <-> component circular import. */
  primaryAvatarId?: string;
  secondaryAvatarId?: string;
}

/**
 * Read-only, historical trade detail — opened by tapping a "Notable trade"
 * recap card. Deliberately not the live Trade Analyzer (which grades a
 * hypothetical proposal): this just displays the full asset lists for a
 * trade that already happened, using the untruncated `left_assets` /
 * `right_assets` modules/league_recaps.py's `_trade_story` now includes
 * (the card itself, and `players`, stay truncated to 2-per-side).
 */
export default function RecapTradeDetailModal({ visible, onClose, story, primaryAvatarId, secondaryAvatarId }: Props) {
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
            <TeamAssetColumn teamName={story.primary_team} avatarId={primaryAvatarId} assets={leftAssets} />
            <View style={styles.divider}>
              <Ionicons name="swap-horizontal" size={16} color={colors.textTertiary} />
            </View>
            <TeamAssetColumn teamName={story.secondary_team} avatarId={secondaryAvatarId} assets={rightAssets} />
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

function TeamAssetColumn({
  teamName,
  avatarId,
  assets,
}: {
  teamName: string;
  avatarId?: string;
  assets: RecapTradeAsset[];
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  return (
    <View style={styles.column}>
      <View style={styles.columnHeaderRow}>
        <TeamAvatar avatarId={avatarId} size={18} />
        <AppText style={styles.columnTeam} numberOfLines={1}>
          {teamName || 'Unknown team'}
        </AppText>
      </View>
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
    // Draft picks stay a distinct, non-player shape (Magna Carta §30: "do
    // not make picks pretend to be players") — no CompactPlayerModule here.
    return (
      <View style={styles.assetRow}>
        <IconCircle name="albums-outline" color={colors.accent} size={32} iconSize={16} />
        <AppText style={styles.assetName} numberOfLines={1}>
          {asset.label || asset.name}
        </AppText>
      </View>
    );
  }
  // Player identity portion reuses the shared compact module instead of
  // hand-rolling the same avatar/name/position-badge shape locally — this
  // modal is read-only history, so no onPress/PlayerDetail navigation is
  // wired (would require plumbing `navigation` through RecapScreen and the
  // modal's props, out of scope for this pass).
  return (
    <CompactPlayerModule
      playerId={asset.player_id}
      name={asset.name}
      position={asset.position}
      team={asset.team}
      style={styles.assetRow}
    />
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
  columnHeaderRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: spacing.xs,
    marginBottom: spacing.sm,
  },
  columnTeam: {
    fontSize: 12,
    fontWeight: '700',
    color: colors.accent,
    letterSpacing: 0.4,
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
  assetName: { fontSize: 14, fontWeight: '600', color: colors.textPrimary },
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
