import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { StyleSheet, TouchableOpacity, View } from 'react-native';

import AnimatedCard from './AnimatedCard';
import AppText from './AppText';
import SectionHeading from './SectionHeading';
import Toggle from './Toggle';
import { useThemeMode } from '../context/ThemeModeContext';
import { api, type NotificationLeagueMode, type NotificationPreferencesResponse, type NotificationPrefsPatch } from '../lib/api';
import {
  LEAGUE_MODE_OPTIONS,
  activeCapPreset,
  deviceTimezone,
  digestEnabled,
  digestPatch,
  hourLabel,
  leagueMode,
} from '../lib/notificationControls';
import { radii, spacing, type ThemeColors } from '../theme';

interface Props {
  savedLeagues: Array<{ league_id: string; league_name: string | null }>;
}

/**
 * Notification controls beyond the per-category switches: quiet hours, how
 * often, a daily digest for non-urgent updates and per-league mute. Same
 * settings, copy and defaults as the web Account page
 * (web-next/src/components/NotificationControls.tsx). Fails soft: renders
 * nothing if the preferences cannot be read.
 */
export default function NotificationControls({ savedLeagues }: Props) {
  const { colors } = useThemeMode();
  const styles = useMemo(() => createStyles(colors), [colors]);
  const [data, setData] = useState<NotificationPreferencesResponse | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getNotificationPreferences()
      .then((result) => {
        if (!cancelled && result.ok) setData(result);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const save = useCallback(
    async (
      patch: NotificationPrefsPatch,
      optimistic: (current: NotificationPreferencesResponse) => NotificationPreferencesResponse,
    ) => {
      if (!data) return;
      const previous = data;
      setData(optimistic(previous));
      setSaving(true);
      setError(null);
      try {
        const result = await api.updateNotificationPreferences(patch);
        if (result.ok) {
          setData(result);
        } else {
          setData(previous);
          setError('Could not save that change. Please try again.');
        }
      } catch {
        setData(previous);
        setError('Could not save that change. Please try again.');
      } finally {
        setSaving(false);
      }
    },
    [data],
  );

  if (!data) return null;
  const { prefs } = data;
  const capKey = activeCapPreset(prefs, data.cap_presets, data.default_weekly_cap);
  const withPrefs = (next: Partial<typeof prefs>) => (current: NotificationPreferencesResponse) => ({
    ...current,
    prefs: { ...current.prefs, ...next },
  });
  const tz = deviceTimezone();
  const withTz = tz ? { timezone: tz } : {};

  const stepHour = (value: number, delta: number) => (value + delta + 24) % 24;

  const Stepper = ({
    label,
    value,
    onChange,
  }: {
    label: string;
    value: number;
    onChange: (next: number) => void;
  }) => (
    <View style={styles.stepper}>
      <AppText style={styles.rowLabel}>{label}</AppText>
      <View style={styles.stepperControls}>
        <TouchableOpacity
          accessibilityRole="button"
          accessibilityLabel={`${label}, earlier`}
          disabled={saving}
          onPress={() => onChange(stepHour(value, -1))}
          style={styles.stepButton}
        >
          <AppText style={styles.stepGlyph}>{'−'}</AppText>
        </TouchableOpacity>
        <AppText style={styles.stepValue}>{hourLabel(value)}</AppText>
        <TouchableOpacity
          accessibilityRole="button"
          accessibilityLabel={`${label}, later`}
          disabled={saving}
          onPress={() => onChange(stepHour(value, 1))}
          style={styles.stepButton}
        >
          <AppText style={styles.stepGlyph}>+</AppText>
        </TouchableOpacity>
      </View>
    </View>
  );

  const digestOn = digestEnabled(prefs);

  return (
    <View>
      <SectionHeading title="Quiet hours" topGap={16} />
      <AnimatedCard style={styles.card}>
        <View style={[styles.row, prefs.quiet_hours_enabled && styles.divider]}>
          <View style={styles.rowText}>
            <AppText style={styles.rowLabel}>Pause notifications</AppText>
            <AppText style={styles.rowDescription}>Held, not lost: anything still relevant arrives after quiet hours end</AppText>
          </View>
          <Toggle
            value={prefs.quiet_hours_enabled}
            disabled={saving}
            label="Pause notifications during quiet hours"
            onValueChange={(next) => save({ quiet_hours_enabled: next }, withPrefs({ quiet_hours_enabled: next }))}
          />
        </View>
        {prefs.quiet_hours_enabled ? (
          <>
            <View style={styles.divider}>
              <Stepper
                label="From"
                value={prefs.quiet_start}
                onChange={(next) => {
                  if (next === prefs.quiet_end) return;
                  void save({ quiet_start: next, quiet_end: prefs.quiet_end, ...withTz }, withPrefs({ quiet_start: next }));
                }}
              />
            </View>
            <View style={styles.divider}>
              <Stepper
                label="To"
                value={prefs.quiet_end}
                onChange={(next) => {
                  if (next === prefs.quiet_start) return;
                  void save({ quiet_start: prefs.quiet_start, quiet_end: next, ...withTz }, withPrefs({ quiet_end: next }));
                }}
              />
            </View>
            <View style={styles.row}>
              <View style={styles.rowText}>
                <AppText style={styles.rowLabel}>Let urgent alerts through</AppText>
                <AppText style={styles.rowDescription}>Injuries, lineup locks and the trade deadline can still arrive</AppText>
              </View>
              <Toggle
                value={prefs.critical_breaks_quiet}
                disabled={saving}
                label="Let urgent alerts through quiet hours"
                onValueChange={(next) => save({ critical_breaks_quiet: next }, withPrefs({ critical_breaks_quiet: next }))}
              />
            </View>
          </>
        ) : null}
      </AnimatedCard>

      <SectionHeading title="How often" topGap={16} />
      <View style={styles.chipRow}>
        {data.cap_presets.map((preset) => {
          const active = capKey === preset.key;
          return (
            <TouchableOpacity
              key={preset.key}
              accessibilityRole="button"
              accessibilityState={{ selected: active }}
              disabled={saving}
              style={[styles.chip, active && styles.chipActive]}
              onPress={() => {
                if (!active) void save({ weekly_cap: preset.cap }, withPrefs({ weekly_cap: preset.cap }));
              }}
            >
              <AppText style={[styles.chipLabel, active && styles.chipLabelActive]}>{preset.label}</AppText>
              <AppText style={styles.chipDescription}>{`Up to ${preset.cap} a week`}</AppText>
            </TouchableOpacity>
          );
        })}
      </View>
      <AppText style={styles.caption}>One slot a week is always kept for urgent alerts.</AppText>

      <SectionHeading title="Daily digest" topGap={16} />
      <AnimatedCard style={styles.card}>
        <View style={[styles.row, digestOn && styles.divider]}>
          <View style={styles.rowText}>
            <AppText style={styles.rowLabel}>Batch non-urgent updates</AppText>
            <AppText style={styles.rowDescription}>
              Top moves, watch items, recaps and roundups arrive together once a day
            </AppText>
          </View>
          <Toggle
            value={digestOn}
            disabled={saving}
            label="Batch non-urgent updates into a daily digest"
            onValueChange={(next) =>
              save(digestPatch(next), (current) => ({
                ...current,
                prefs: { ...current.prefs, category_modes: digestPatch(next).category_modes ?? {} },
              }))
            }
          />
        </View>
        {digestOn ? (
          <Stepper
            label="Deliver around"
            value={prefs.digest_hour}
            onChange={(next) => void save({ digest_hour: next, ...withTz }, withPrefs({ digest_hour: next }))}
          />
        ) : null}
      </AnimatedCard>

      {savedLeagues.length > 1 ? (
        <>
          <SectionHeading title="Per league" topGap={16} />
          {savedLeagues.map((league) => {
            const mode = leagueMode(prefs, league.league_id);
            return (
              <View key={league.league_id} style={styles.leagueBlock}>
                <AppText style={styles.rowLabel}>{league.league_name || league.league_id}</AppText>
                <View style={styles.chipRow}>
                  {LEAGUE_MODE_OPTIONS.map((option) => {
                    const active = mode === option.value;
                    return (
                      <TouchableOpacity
                        key={option.value}
                        accessibilityRole="button"
                        accessibilityState={{ selected: active }}
                        accessibilityLabel={`${league.league_name || league.league_id}: ${option.label}`}
                        disabled={saving}
                        style={[styles.chip, active && styles.chipActive]}
                        onPress={() => {
                          if (active) return;
                          const value: NotificationLeagueMode = option.value;
                          void save({ league_overrides: { [league.league_id]: value } }, (current) => {
                            const overrides = { ...current.prefs.league_overrides };
                            if (value === 'all') delete overrides[league.league_id];
                            else overrides[league.league_id] = value;
                            return { ...current, prefs: { ...current.prefs, league_overrides: overrides } };
                          });
                        }}
                      >
                        <AppText style={[styles.chipLabel, active && styles.chipLabelActive]}>{option.label}</AppText>
                      </TouchableOpacity>
                    );
                  })}
                </View>
              </View>
            );
          })}
          <AppText style={styles.caption}>
            Urgent only keeps injuries, lineup locks and the trade deadline. Muted silences the league completely.
          </AppText>
        </>
      ) : null}

      {error ? <AppText style={styles.error}>{error}</AppText> : null}
    </View>
  );
}

function createStyles(colors: ThemeColors) {
  return StyleSheet.create({
    card: { padding: spacing.md, paddingVertical: 0 },
    row: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      paddingVertical: spacing.md,
      gap: spacing.md,
    },
    divider: { borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.border },
    rowText: { flex: 1, flexShrink: 1 },
    rowLabel: { fontSize: 16.5, color: colors.textPrimary },
    rowDescription: { fontSize: 13.5, color: colors.textSecondary, marginTop: 2 },
    stepper: {
      flexDirection: 'row',
      justifyContent: 'space-between',
      alignItems: 'center',
      paddingVertical: spacing.sm,
    },
    stepperControls: { flexDirection: 'row', alignItems: 'center', gap: spacing.sm },
    stepButton: {
      width: 44,
      height: 44,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.glassBorder,
      backgroundColor: colors.glassInset,
      alignItems: 'center',
      justifyContent: 'center',
    },
    stepGlyph: { fontSize: 20, color: colors.textPrimary },
    stepValue: { minWidth: 64, textAlign: 'center', fontSize: 16.5, fontWeight: '700', color: colors.textPrimary },
    chipRow: { flexDirection: 'row', gap: spacing.sm, marginTop: spacing.sm },
    chip: {
      flex: 1,
      minHeight: 44,
      borderRadius: radii.md,
      borderWidth: StyleSheet.hairlineWidth * 1.5,
      borderColor: colors.glassBorder,
      backgroundColor: colors.glassInset,
      paddingVertical: spacing.sm,
      paddingHorizontal: spacing.sm,
      justifyContent: 'center',
    },
    chipActive: { borderColor: colors.accent, backgroundColor: colors.accentMuted },
    chipLabel: { fontSize: 15.5, fontWeight: '700', color: colors.textPrimary },
    chipLabelActive: { color: colors.accent },
    chipDescription: { fontSize: 13.5, color: colors.textSecondary },
    caption: { fontSize: 13.5, color: colors.textSecondary, marginTop: spacing.sm },
    leagueBlock: { marginBottom: spacing.sm },
    error: { fontSize: 13.5, color: colors.danger, marginTop: spacing.sm },
  });
}
