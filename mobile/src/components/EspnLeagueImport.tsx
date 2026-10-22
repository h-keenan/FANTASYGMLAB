import React, { useMemo, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, TextInput, TouchableOpacity, View } from 'react-native';
import { Ionicons } from '@expo/vector-icons';

import AppText from './AppText';
import SegmentedTabBar from './SegmentedTabBar';
import { ApiError, api, type EspnLeaguePreviewResponse } from '../lib/api';
import { ESPN_SAVE_FAILURE_COPY, espnSeasonOptions } from '../lib/leaguePlatform';
import { useThemeMode } from '../context/ThemeModeContext';
import { radii, spacing, typography, type ThemeColors } from '../theme';

/**
 * ESPN half of Home's "Add a league" sheet (same sheet, platform chosen at
 * the top) — mirrors web-next's EspnImportForm. Public ESPN leagues only:
 * enter the league ID and season, see what loaded and which features work
 * for ESPN leagues today, pick your own team, save. ESPN exposes no
 * username lookup for public leagues, so the team pick is how "my roster"
 * is known later. Private leagues would need the user's espn_s2/SWID
 * cookies stored on our server, so this never asks for them.
 */
export default function EspnLeagueImport({
  onSaved,
  onCapReached,
  onCancel,
}: {
  onSaved: (leagueId: string, leagueName: string) => void;
  onCapReached: (cap: number) => void;
  onCancel: () => void;
}) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const seasons = useMemo(() => espnSeasonOptions(), []);
  const [leagueId, setLeagueId] = useState('');
  const [season, setSeason] = useState(String(seasons[0]));
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [preview, setPreview] = useState<EspnLeaguePreviewResponse | null>(null);
  const [rosterId, setRosterId] = useState('');

  const findLeague = async () => {
    const clean = leagueId.trim();
    if (!/^\d{1,12}$/.test(clean)) {
      setMessage("Enter your ESPN league ID. It's the number after leagueId= in your ESPN league's web address.");
      return;
    }
    setBusy(true);
    setMessage(null);
    setPreview(null);
    setRosterId('');
    try {
      const result = await api.previewEspnLeague(clean, Number(season));
      if (!result.league) {
        setMessage(result.message || "That ESPN league couldn't be loaded.");
        return;
      }
      setPreview(result);
      if (!result.ok) setMessage(result.message);
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : 'Could not reach the FantasyDesk API.');
    } finally {
      setBusy(false);
    }
  };

  const save = async () => {
    if (!preview?.league || !rosterId) return;
    const { league_key: key, name } = preview.league;
    setBusy(true);
    setMessage(null);
    try {
      const result = await api.saveLeague({ leagueId: key, leagueName: name, rosterId, makeDefault: true });
      if (result.ok) {
        onSaved(key, name);
        return;
      }
      if (result.reason === 'at_cap') {
        onCapReached(result.cap);
        return;
      }
      setMessage(ESPN_SAVE_FAILURE_COPY[result.reason] ?? 'Could not save that league right now. Please try again in a moment.');
    } catch (error) {
      setMessage(error instanceof ApiError ? error.message : 'Could not reach the FantasyDesk API.');
    } finally {
      setBusy(false);
    }
  };

  if (preview?.league) {
    const diagnostics = preview.diagnostics;
    const available = (preview.features ?? []).filter((item) => item.status === 'available');
    const unavailable = (preview.features ?? []).filter((item) => item.status !== 'available');
    return (
      <View>
        <AppText style={styles.leagueName}>{preview.league.name}</AppText>
        <AppText style={styles.meta}>
          ESPN · {preview.league.season} season · {preview.league.team_count} teams
        </AppText>
        {diagnostics ? (
          <AppText style={styles.hint}>
            {diagnostics.canonical_matched_count} of {diagnostics.total_espn_players_seen} rostered players matched
            FantasyDesk's player list ({Math.round(diagnostics.matched_rate * 100)}%). Team defenses (D/ST) and players
            we don't track yet aren't valued.
          </AppText>
        ) : null}
        {preview.ok ? (
          <>
            <AppText style={styles.kicker}>Which team is yours?</AppText>
            <ScrollView style={styles.teamList} keyboardShouldPersistTaps="handled">
              {(preview.teams ?? []).map((team) => {
                const selected = team.roster_id === rosterId;
                return (
                  <TouchableOpacity
                    key={team.roster_id}
                    style={styles.teamRow}
                    onPress={() => setRosterId(team.roster_id)}
                    accessibilityRole="radio"
                    accessibilityState={{ checked: selected }}
                  >
                    <View style={styles.teamText}>
                      <AppText style={styles.teamName} numberOfLines={1}>
                        {team.team_name}
                      </AppText>
                      <AppText style={styles.meta}>{team.owner_name}</AppText>
                    </View>
                    <Ionicons
                      name={selected ? 'checkmark-circle' : 'ellipse-outline'}
                      size={20}
                      color={selected ? colors.accent : colors.textTertiary}
                    />
                  </TouchableOpacity>
                );
              })}
            </ScrollView>
          </>
        ) : null}
        <View style={styles.featureCard}>
          <AppText style={styles.featureText}>
            <AppText style={styles.featureStrong}>Works for ESPN leagues: </AppText>
            {available.map((item) => item.feature).join(', ')}.
          </AppText>
          <AppText style={styles.featureText}>
            <AppText style={styles.featureStrong}>Not available for ESPN leagues yet: </AppText>
            {unavailable.map((item) => item.feature).join(', ')}.
          </AppText>
        </View>
        {message ? <AppText style={styles.error}>{message}</AppText> : null}
        <View style={styles.actions}>
          <TouchableOpacity
            style={styles.cancelButton}
            disabled={busy}
            onPress={() => {
              setPreview(null);
              setMessage(null);
              setRosterId('');
            }}
          >
            <AppText style={styles.cancelText}>Back</AppText>
          </TouchableOpacity>
          {preview.ok ? (
            <TouchableOpacity
              style={[styles.primaryButton, !rosterId && styles.primaryButtonDisabled]}
              disabled={busy || !rosterId}
              onPress={() => void save()}
            >
              {busy ? <ActivityIndicator size="small" color={colors.onAccent} /> : <AppText style={styles.primaryText}>Add league</AppText>}
            </TouchableOpacity>
          ) : null}
        </View>
      </View>
    );
  }

  return (
    <View>
      <AppText style={styles.hint}>
        FantasyDesk can read public ESPN leagues. Your league ID is the number after leagueId= in your ESPN league's web
        address. Private ESPN leagues aren't supported yet; your league manager can make the league viewable to the
        public in ESPN's league settings.
      </AppText>
      <TextInput
        style={styles.input}
        value={leagueId}
        onChangeText={setLeagueId}
        placeholder="ESPN league ID"
        placeholderTextColor={colors.textTertiary}
        keyboardType="number-pad"
        autoCorrect={false}
        editable={!busy}
        onSubmitEditing={() => void findLeague()}
        maxLength={12}
      />
      <AppText style={styles.kicker}>Season</AppText>
      <SegmentedTabBar<string>
        options={seasons.map((option) => ({ key: String(option), label: String(option) }))}
        active={season}
        onChange={setSeason}
      />
      {message ? <AppText style={styles.error}>{message}</AppText> : null}
      <View style={styles.actions}>
        <TouchableOpacity style={styles.cancelButton} onPress={onCancel} disabled={busy}>
          <AppText style={styles.cancelText}>Cancel</AppText>
        </TouchableOpacity>
        <TouchableOpacity style={styles.primaryButton} onPress={() => void findLeague()} disabled={busy}>
          {busy ? <ActivityIndicator size="small" color={colors.onAccent} /> : <AppText style={styles.primaryText}>Find league</AppText>}
        </TouchableOpacity>
      </View>
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    hint: { fontSize: 12, color: colors.textSecondary, marginBottom: spacing.md, lineHeight: 16 },
    input: {
      borderWidth: 1,
      borderColor: colors.cardBorder,
      borderRadius: radii.sm,
      paddingHorizontal: spacing.md,
      paddingVertical: 10,
      fontSize: 15,
      backgroundColor: colors.surface,
      color: colors.textPrimary,
      marginBottom: spacing.md,
    },
    kicker: {
      ...typography.kicker,
      color: colors.textTertiary,
      textTransform: 'uppercase',
      marginBottom: spacing.xs,
      marginTop: spacing.sm,
    },
    leagueName: { fontSize: 16, fontWeight: '700', color: colors.textPrimary },
    meta: { fontSize: 12, color: colors.textSecondary, marginTop: 2, marginBottom: spacing.xs },
    teamList: { maxHeight: 220 },
    teamRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingVertical: spacing.sm,
      borderBottomWidth: StyleSheet.hairlineWidth,
      borderBottomColor: colors.border,
    },
    teamText: { flex: 1, marginRight: spacing.sm },
    teamName: { fontSize: 15, fontWeight: '600', color: colors.textPrimary },
    featureCard: {
      marginTop: spacing.md,
      padding: spacing.md,
      gap: spacing.xs,
      borderRadius: radii.sm,
      borderWidth: StyleSheet.hairlineWidth,
      borderColor: colors.border,
      backgroundColor: colors.surface,
    },
    featureText: { fontSize: 12, color: colors.textSecondary, lineHeight: 17 },
    featureStrong: { fontSize: 12, fontWeight: '700', color: colors.textPrimary },
    error: { fontSize: 12, color: colors.danger, marginTop: spacing.sm, lineHeight: 16 },
    actions: { flexDirection: 'row', justifyContent: 'flex-end', gap: spacing.sm, marginTop: spacing.md },
    cancelButton: { paddingHorizontal: spacing.md, paddingVertical: 10 },
    cancelText: { fontSize: 14, fontWeight: '600', color: colors.textSecondary },
    primaryButton: {
      backgroundColor: colors.accent,
      paddingHorizontal: spacing.lg,
      paddingVertical: 10,
      borderRadius: radii.sm,
      minWidth: 64,
      alignItems: 'center',
    },
    primaryButtonDisabled: { opacity: 0.5 },
    primaryText: { fontSize: 14, fontWeight: '700', color: colors.onAccent },
  });
}
