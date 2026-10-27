/**
 * Pure logic for iOS Live Activities / home-screen widget (no RN imports, so
 * node:test can run it). Orchestration + native bridge: liveActivity.ts.
 *
 * Ships DARK: EXPO_PUBLIC_LIVE_ACTIVITIES_ENABLED must be "1" AND the native
 * module must exist (it only does in a build prebuilt with
 * FANTASYDESK_LIVE_ACTIVITIES=1 — see plugins/withLiveActivities.js).
 */

export interface LiveSnapshotInput {
  available: boolean;
  should_run: boolean;
  week: number | null;
  game_state: string | null;
  me: { team_name: string; points: number | null };
  opponent: { team_name: string; points: number | null };
  margin: number | null;
  win_probability: number | null;
}

/** Must stay field-for-field in sync with FantasyDeskActivityAttributes.ContentState (Swift); a test enforces it. */
export interface LiveActivityContentState {
  myTeam: string;
  opponentTeam: string;
  myPoints: number;
  opponentPoints: number;
  winProbability: number | null;
  week: number;
}

export type LiveActivityAction = 'start' | 'update' | 'end' | 'none';

export function parseLiveActivitiesFlag(raw: string | undefined | null): boolean {
  const v = (raw ?? '').trim().toLowerCase();
  return v === '1' || v === 'true' || v === 'on';
}

/** Null when there is nothing real to show — never a fabricated 0-0. */
export function toContentState(s: LiveSnapshotInput): LiveActivityContentState | null {
  if (!s.available || s.me.points == null || s.opponent.points == null || s.week == null) return null;
  return {
    myTeam: s.me.team_name,
    opponentTeam: s.opponent.team_name,
    myPoints: s.me.points,
    opponentPoints: s.opponent.points,
    winProbability: s.win_probability,
    week: s.week,
  };
}

export function planLiveActivityAction(
  snapshot: LiveSnapshotInput | null,
  running: boolean,
  options: { enabled: boolean; isGuest: boolean },
): LiveActivityAction {
  if (!options.enabled || options.isGuest) return running ? 'end' : 'none';
  const wantRun = !!snapshot && snapshot.should_run && toContentState(snapshot) !== null;
  if (wantRun) return running ? 'update' : 'start';
  return running ? 'end' : 'none';
}

export interface WidgetAlertInput {
  title: string | null;
  matched_player: string | null;
  read: boolean;
}

export interface WidgetSnapshot {
  leagueName: string;
  alerts: { title: string; player: string | null }[];
  unreadCount: number;
  updatedAt: number;
}

/** Real alerts only; unread first, capped (small widgets fit 3). */
export function toWidgetSnapshot(
  leagueName: string,
  items: WidgetAlertInput[],
  now: number,
  max = 3,
): WidgetSnapshot {
  const usable = items.filter((i) => !!i.title && i.title.trim().length > 0);
  const unread = usable.filter((i) => !i.read);
  const ordered = [...unread, ...usable.filter((i) => i.read)];
  return {
    leagueName,
    alerts: ordered.slice(0, max).map((i) => ({ title: (i.title as string).trim(), player: i.matched_player })),
    unreadCount: unread.length,
    updatedAt: now,
  };
}
