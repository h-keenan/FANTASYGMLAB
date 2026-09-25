import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { ActivityIndicator, FlatList, RefreshControl, StyleSheet, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';
import AppText from '../components/AppText';
import BrandHeaderBar from '../components/BrandHeaderBar';
import { useFocusEffect } from '@react-navigation/native';
import type { NativeStackScreenProps } from '@react-navigation/native-stack';
import { useHeaderHeight } from '@react-navigation/elements';

import BrandedSpinner from '../components/BrandedSpinner';
import GridBackground from '../components/GridBackground';
import PlayerIdentityRow from '../components/PlayerIdentityRow';
import ScreenInfoNote from '../components/ScreenInfoNote';
import SectionHeading from '../components/SectionHeading';
import { api, TEAM_STANCE_OPTIONS, type LineupPlayer, type TeamStance } from '../lib/api';
import { useOrbClearance } from '../lib/orbLayout';
import { useScreenHeaderTitle } from '../lib/useScreenHeaderTitle';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, type ThemeColors } from '../theme';
import type { RootStackParamList } from '../navigation/RootNavigator';

type Props = NativeStackScreenProps<RootStackParamList, 'TeamStance'>;

interface ProtectRow {
  player: LineupPlayer;
  protected: boolean;
}

/**
 * Team Situation — a small, standalone screen (Decision Memory v1 gap):
 * declare a fixed stance (Rebuilding/Competing/Balanced) that biases
 * trade-idea rationale TEXT only, plus a "protected players" checklist that
 * reads/writes the SAME untouchable flag GM Targets already owns
 * (modules.gm_targets) rather than a second, parallel protect list.
 * Deliberately not embedded in My Team or Dashboard — those get separate
 * structural redesigns; this is reachable from More (Settings) only.
 */
export default function TeamStanceScreen({ route, navigation }: Props) {
  const orbClearance = useOrbClearance();
  const headerHeight = useHeaderHeight();
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { leagueId, leagueName } = route.params;

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [stance, setStance] = useState<TeamStance | ''>('');
  const [savingStance, setSavingStance] = useState(false);
  const [rows, setRows] = useState<ProtectRow[]>([]);
  const [busyPlayerId, setBusyPlayerId] = useState<string | null>(null);

  useScreenHeaderTitle(navigation, 'Team Situation', leagueName);

  const load = useCallback(async () => {
    setError(null);
    try {
      const [stanceResult, teamResult, targetsResult] = await Promise.all([
        api.getTeamStance(leagueId),
        api.getLeagueMyTeam(leagueId),
        api.getGmTargets(leagueId),
      ]);
      setStance(stanceResult.stance);
      const protectedIds = new Set(
        targetsResult.targets.filter((t) => t.untouchable).map((t) => t.player_id),
      );
      const roster = [...teamResult.starters, ...teamResult.bench];
      const seen = new Set<string>();
      const nextRows: ProtectRow[] = [];
      for (const player of roster) {
        if (seen.has(player.player_id)) continue;
        seen.add(player.player_id);
        nextRows.push({ player, protected: protectedIds.has(player.player_id) });
      }
      setRows(nextRows);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load Team Situation.');
    } finally {
      setLoading(false);
    }
  }, [leagueId]);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const onPickStance = useCallback(
    async (next: TeamStance) => {
      if (savingStance || next === stance) return;
      const previous = stance;
      setStance(next);
      setSavingStance(true);
      try {
        const result = await api.setTeamStance(leagueId, next);
        if (!result.ok) setStance(previous);
      } catch {
        setStance(previous);
      } finally {
        setSavingStance(false);
      }
    },
    [leagueId, savingStance, stance],
  );

  const onToggleProtect = useCallback(
    async (playerId: string, next: boolean) => {
      setBusyPlayerId(playerId);
      setRows((prev) => prev.map((row) => (row.player.player_id === playerId ? { ...row, protected: next } : row)));
      try {
        // Reuses GM Targets' existing untouchable flag rather than a second
        // protect list — a player must be a GM Target row before it can be
        // marked untouchable, so protecting one not already watched adds it
        // first (source_surface identifies where the target came from).
        const existing = await api.getGmTargets(leagueId);
        const isTracked = existing.targets.some((t) => t.player_id === playerId);
        if (next && !isTracked) {
          await api.addGmTarget(leagueId, playerId, 'team_stance');
        }
        if (next || isTracked) {
          const result = await api.setGmTargetUntouchable(leagueId, playerId, next);
          if (!result.ok) throw new Error(result.reason || 'not_available');
        }
      } catch {
        setRows((prev) =>
          prev.map((row) => (row.player.player_id === playerId ? { ...row, protected: !next } : row)),
        );
      } finally {
        setBusyPlayerId(null);
      }
    },
    [leagueId],
  );

  const protectedRows = useMemo(() => rows.filter((row) => row.protected), [rows]);
  const otherRows = useMemo(() => rows.filter((row) => !row.protected), [rows]);

  if (loading) {
    return <BrandedSpinner style={[styles.center, { paddingTop: headerHeight }]} />;
  }

  return (
    <View style={[styles.container, { paddingTop: headerHeight }]}>
      <GridBackground />
      <BrandHeaderBar leagueId={leagueId} leagueName={leagueName} />
      <ScreenInfoNote
        text="Tell us how you see this team right now. We'll lean trade-idea language toward that stance — this never changes player values, rankings, or scoring."
      />

      {error ? <AppText style={styles.error}>{error}</AppText> : null}

      <FlatList
        data={otherRows}
        keyExtractor={(row) => row.player.player_id}
        contentContainerStyle={[styles.listContent, { paddingBottom: orbClearance }]}
        refreshControl={<RefreshControl refreshing={false} onRefresh={load} />}
        ListHeaderComponent={
          <View>
            <SectionHeading title="Team Situation" icon="compass-outline" />
            <View style={styles.stanceRow}>
              {TEAM_STANCE_OPTIONS.map((option) => {
                const active = stance === option.value;
                return (
                  <TouchableOpacity
                    key={option.value}
                    style={[styles.stanceCard, active && styles.stanceCardActive]}
                    onPress={() => onPickStance(option.value)}
                    disabled={savingStance}
                    activeOpacity={0.8}
                  >
                    <AppText style={[styles.stanceLabel, active && styles.stanceLabelActive]}>
                      {option.label}
                    </AppText>
                    <AppText style={styles.stanceDescription}>{option.description}</AppText>
                  </TouchableOpacity>
                );
              })}
            </View>
            {savingStance ? (
              <View style={styles.savingRow}>
                <ActivityIndicator size="small" color={colors.accent} />
                <AppText style={styles.savingText}>Saving...</AppText>
              </View>
            ) : null}

            <SectionHeading title="Protected Players" icon="lock-closed-outline" />
            <AppText style={styles.protectCaption}>
              Mark players you don't want traded away. This is the same protection GM Targets' untouchable flag
              uses — toggling it here or there shows up in both places.
            </AppText>
            {protectedRows.map((row, index) => (
              <ProtectPlayerRow
                key={row.player.player_id}
                row={row}
                isFirst={index === 0}
                isLast={index === protectedRows.length - 1}
                busy={busyPlayerId === row.player.player_id}
                onToggle={onToggleProtect}
              />
            ))}
            {otherRows.length > 0 ? <SectionHeading title="Rest of Roster" icon="people-outline" /> : null}
          </View>
        }
        renderItem={({ item, index }) => (
          <ProtectPlayerRow
            row={item}
            isFirst={index === 0}
            isLast={index === otherRows.length - 1}
            busy={busyPlayerId === item.player.player_id}
            onToggle={onToggleProtect}
          />
        )}
      />
    </View>
  );
}

function ProtectPlayerRow({
  row,
  isFirst,
  isLast,
  busy,
  onToggle,
}: {
  row: ProtectRow;
  isFirst: boolean;
  isLast: boolean;
  busy: boolean;
  onToggle: (playerId: string, next: boolean) => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const { player, protected: isProtected } = row;

  return (
    <View
      style={[
        styles.row,
        isFirst && styles.rowFirst,
        isLast && styles.rowLast,
        !isLast && styles.rowDivider,
      ]}
    >
      <View style={styles.identity}>
        <PlayerIdentityRow
          playerId={player.player_id}
          name={player.name}
          position={player.position}
          team={player.team}
          tier={player.tier}
          showDivider={false}
        />
      </View>
      <TouchableOpacity
        style={[styles.iconButton, isProtected && styles.iconButtonActive]}
        onPress={() => onToggle(player.player_id, !isProtected)}
        disabled={busy}
        hitSlop={8}
        accessibilityLabel={isProtected ? 'Remove protected flag' : 'Mark protected'}
      >
        {busy ? (
          <ActivityIndicator size="small" color={colors.textSecondary} />
        ) : (
          <Ionicons
            name={isProtected ? 'lock-closed' : 'lock-open-outline'}
            size={15}
            color={isProtected ? colors.premium : colors.textSecondary}
          />
        )}
      </TouchableOpacity>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    container: { flex: 1, backgroundColor: colors.background, paddingTop: spacing.md },
    center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.background },
    listContent: { paddingHorizontal: spacing.lg, paddingBottom: spacing.xl },
    error: { color: colors.danger, textAlign: 'center', marginHorizontal: spacing.lg, marginBottom: spacing.sm },
    stanceRow: { flexDirection: 'row', gap: spacing.sm, marginBottom: spacing.md },
    stanceCard: {
      flex: 1,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.cardBorder,
      backgroundColor: colors.surface,
      paddingVertical: spacing.md,
      paddingHorizontal: spacing.sm,
    },
    stanceCardActive: { borderColor: colors.accent, backgroundColor: colors.accentMuted },
    stanceLabel: { fontSize: 14, fontWeight: '700', color: colors.textPrimary, marginBottom: 2 },
    // accentOnTint: sits on stanceCardActive's own accentMuted fill, where
    // plain accent falls under AA on light mode (color-system audit,
    // 2026-09-25).
    stanceLabelActive: { color: colors.accentOnTint },
    stanceDescription: { fontSize: 12, color: colors.textSecondary },
    savingRow: { flexDirection: 'row', alignItems: 'center', gap: spacing.xs, marginBottom: spacing.md },
    savingText: { fontSize: 12, color: colors.textSecondary },
    protectCaption: { fontSize: 12, color: colors.textSecondary, marginBottom: spacing.sm },
    row: {
      flexDirection: 'row',
      alignItems: 'center',
      backgroundColor: colors.surface,
      paddingHorizontal: spacing.md,
      borderLeftWidth: StyleSheet.hairlineWidth * 1.5,
      borderRightWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.cardBorder,
    },
    rowFirst: {
      borderTopWidth: StyleSheet.hairlineWidth * 1.5,
      borderTopLeftRadius: radii.md,
      borderTopRightRadius: radii.md,
    },
    rowLast: {
      borderBottomWidth: StyleSheet.hairlineWidth * 1.5,
      borderBottomLeftRadius: radii.md,
      borderBottomRightRadius: radii.md,
      marginBottom: spacing.md,
    },
    rowDivider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    identity: { flex: 1 },
    iconButton: {
      width: 30,
      height: 30,
      borderRadius: radii.pill,
      borderWidth: 1,
      borderColor: colors.cardBorder,
      alignItems: 'center',
      justifyContent: 'center',
    },
    iconButtonActive: { borderColor: colors.premium, backgroundColor: colors.premiumMuted },
  });
}
