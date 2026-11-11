"use client";

import { useCallback, useEffect, useState } from "react";

import { Select } from "@/components/Input";
import { OptionRadioGroup } from "@/components/OptionRadioGroup";
import { Toggle } from "@/components/Toggle";
import {
  api,
  type NotificationLeagueMode,
  type NotificationPreferencesResponse,
  type NotificationPrefsPatch,
} from "@/lib/api";
import {
  HOUR_OPTIONS,
  LEAGUE_MODE_OPTIONS,
  activeCapPreset,
  deviceTimezone,
  digestEnabled,
  digestPatch,
  leagueMode,
} from "@/lib/notificationControls";
import { supabase } from "@/lib/supabase";

type SavedLeague = { league_id: string; league_name: string | null };

const BORDER = "var(--border-width-default) solid var(--color-border)";

function Row({ title, description, children }: { title: string; description?: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-3 p-3">
      <div className="flex flex-col gap-0.5">
        <span className="text-sm">{title}</span>
        {description ? (
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            {description}
          </span>
        ) : null}
      </div>
      {children}
    </div>
  );
}

/**
 * Notification controls beyond the per-category switches: quiet hours, how
 * often, a daily digest for non-urgent updates and per-league mute. Same
 * settings, copy and defaults as the app's More > Notifications
 * (mobile/src/components/NotificationControls.tsx). Fails soft: renders
 * nothing if the preferences cannot be read.
 */
export function NotificationControls() {
  const [data, setData] = useState<NotificationPreferencesResponse | null>(null);
  const [leagues, setLeagues] = useState<SavedLeague[]>([]);
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
    Promise.resolve(supabase.from("saved_leagues").select("league_id, league_name").order("is_default", { ascending: false }))
      .then(({ data: rows }) => {
        if (!cancelled && rows) setLeagues(rows as SavedLeague[]);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  const save = useCallback(
    async (patch: NotificationPrefsPatch, optimistic: (current: NotificationPreferencesResponse) => NotificationPreferencesResponse) => {
      if (!data) return;
      const previous = data;
      setData(optimistic(previous));
      setSaving(true);
      setError(null);
      try {
        const result = await api.updateNotificationPreferences(patch);
        if (result.ok) setData(result);
        else {
          setData(previous);
          setError("Could not save that change. Please try again.");
        }
      } catch {
        setData(previous);
        setError("Could not save that change. Please try again.");
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

  return (
    <div className="flex flex-col gap-4" aria-busy={saving}>
      <div className="flex flex-col gap-2">
        <span className="text-sm font-semibold">Quiet hours</span>
        <div className="flex flex-col" style={{ border: BORDER }}>
          <Row title="Pause notifications" description="Held, not lost: anything still relevant arrives after quiet hours end">
            <Toggle
              checked={prefs.quiet_hours_enabled}
              stateLabel={prefs.quiet_hours_enabled ? "On" : "Off"}
              disabled={saving}
              onChange={(next) => save({ quiet_hours_enabled: next }, withPrefs({ quiet_hours_enabled: next }))}
            />
          </Row>
          {prefs.quiet_hours_enabled ? (
            <>
              <div className="flex flex-wrap items-center gap-3 p-3" style={{ borderTop: BORDER }}>
                <label className="flex items-center gap-2 text-sm">
                  From
                  <Select
                    aria-label="Quiet hours start"
                    value={prefs.quiet_start}
                    disabled={saving}
                    onChange={(event) => {
                      const quiet_start = Number(event.target.value);
                      if (quiet_start === prefs.quiet_end) return;
                      const timezone = deviceTimezone();
                      save({ quiet_start, quiet_end: prefs.quiet_end, ...(timezone ? { timezone } : {}) }, withPrefs({ quiet_start }));
                    }}
                  >
                    {HOUR_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </label>
                <label className="flex items-center gap-2 text-sm">
                  To
                  <Select
                    aria-label="Quiet hours end"
                    value={prefs.quiet_end}
                    disabled={saving}
                    onChange={(event) => {
                      const quiet_end = Number(event.target.value);
                      if (quiet_end === prefs.quiet_start) return;
                      const timezone = deviceTimezone();
                      save({ quiet_start: prefs.quiet_start, quiet_end, ...(timezone ? { timezone } : {}) }, withPrefs({ quiet_end }));
                    }}
                  >
                    {HOUR_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </label>
                <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                  Your local time
                </span>
              </div>
              <div style={{ borderTop: BORDER }}>
                <Row title="Let urgent alerts through" description="Injuries, lineup locks and the trade deadline can still arrive">
                  <Toggle
                    checked={prefs.critical_breaks_quiet}
                    stateLabel={prefs.critical_breaks_quiet ? "On" : "Off"}
                    disabled={saving}
                    onChange={(next) => save({ critical_breaks_quiet: next }, withPrefs({ critical_breaks_quiet: next }))}
                  />
                </Row>
              </div>
            </>
          ) : null}
        </div>
      </div>

      <OptionRadioGroup
        id="notification-cap-label"
        label="How often"
        options={data.cap_presets.map((preset) => ({
          value: preset.key,
          label: preset.label,
          description: `Up to ${preset.cap} a week. One slot is always kept for urgent alerts.`,
        }))}
        value={capKey ?? ""}
        onChange={(key) => {
          const preset = data.cap_presets.find((item) => item.key === key);
          if (preset) save({ weekly_cap: preset.cap }, withPrefs({ weekly_cap: preset.cap }));
        }}
      />

      <div className="flex flex-col gap-2">
        <span className="text-sm font-semibold">Daily digest</span>
        <div className="flex flex-col" style={{ border: BORDER }}>
          <Row title="Batch non-urgent updates" description="Top moves, watch items, recaps and roundups arrive together once a day">
            <Toggle
              checked={digestEnabled(prefs)}
              stateLabel={digestEnabled(prefs) ? "On" : "Off"}
              disabled={saving}
              onChange={(next) =>
                save(digestPatch(next), (current) => ({
                  ...current,
                  prefs: { ...current.prefs, category_modes: digestPatch(next).category_modes ?? {} },
                }))
              }
            />
          </Row>
          {digestEnabled(prefs) ? (
            <div className="flex items-center gap-3 p-3" style={{ borderTop: BORDER }}>
              <label className="flex items-center gap-2 text-sm">
                Deliver around
                <Select
                  aria-label="Digest time"
                  value={prefs.digest_hour}
                  disabled={saving}
                  onChange={(event) => {
                    const digest_hour = Number(event.target.value);
                    const timezone = deviceTimezone();
                    save({ digest_hour, ...(timezone ? { timezone } : {}) }, withPrefs({ digest_hour }));
                  }}
                >
                  {HOUR_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </Select>
              </label>
            </div>
          ) : null}
        </div>
      </div>

      {leagues.length > 1 ? (
        <div className="flex flex-col gap-2">
          <span className="text-sm font-semibold">Per league</span>
          <div className="flex flex-col" style={{ border: BORDER }}>
            {leagues.map((league, index) => (
              <div key={league.league_id} style={{ borderTop: index === 0 ? "none" : BORDER }}>
                <Row title={league.league_name || league.league_id}>
                  <Select
                    aria-label={`Notifications for ${league.league_name || league.league_id}`}
                    value={leagueMode(prefs, league.league_id)}
                    disabled={saving}
                    onChange={(event) => {
                      const mode = event.target.value as NotificationLeagueMode;
                      save({ league_overrides: { [league.league_id]: mode } }, (current) => {
                        const overrides = { ...current.prefs.league_overrides };
                        if (mode === "all") delete overrides[league.league_id];
                        else overrides[league.league_id] = mode;
                        return { ...current, prefs: { ...current.prefs, league_overrides: overrides } };
                      });
                    }}
                  >
                    {LEAGUE_MODE_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </Row>
              </div>
            ))}
          </div>
          <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
            Urgent only keeps injuries, lineup locks and the trade deadline. Muted silences the league completely.
          </span>
        </div>
      ) : null}

      {error ? (
        <p role="alert" className="text-xs" style={{ color: "var(--color-danger)" }}>
          {error}
        </p>
      ) : null}
    </div>
  );
}
