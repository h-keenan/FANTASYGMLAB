"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AlertsFeed } from "@/components/AlertsContent";
import { CompactModule } from "@/components/ui/CompactModule";
import { ErrorState } from "@/components/ErrorState";
import { PlayerAvatarSlot } from "@/components/ui/PlayerAvatarSlot";
import { WatchListCard } from "@/components/WatchListCard";
import { useAuth } from "@/context/AuthContext";
import { api, type AlertsResponse, type BriefingItem } from "@/lib/api";
import { todayAlertsSummary } from "@/lib/todayView";
import { overlayPendingAlertReads } from "@/lib/alertReadSync";
import { alertsReasonMessage } from "@/lib/alertsPresentation";

/** The URL fragment that targets this section (`/dashboard/<id>#alerts`; the retired /alerts route and the header bell link here). */
export const ALERTS_SECTION_HASH = "alerts";

/**
 * The Alerts section of Today (2026-11-16 nav consolidation: Alerts is no longer its own page). A compact, tap-to-expand
 * module with the unread count as a badge; opening it shows the same roster-news feed the Alerts page used to. It opens
 * itself and scrolls into view when the URL carries `#alerts` (the old route redirects there, and so does the header
 * bell's "View all alerts"). Re-reads the feed when the tab becomes visible again, so a read made on the phone shows here.
 */
export function DashboardAlerts({ leagueId, leagueName, watchItems = [] }: { leagueId: string; leagueName: string; /** The Dashboard's watchlist items: folded into this section (one place for "things to keep an eye on"). */ watchItems?: BriefingItem[] }) {
  const { session } = useAuth();
  const userId = session?.user?.id ?? "";
  const [data, setData] = useState<AlertsResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [targeted, setTargeted] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const hasData = useRef(false);

  const load = useCallback(() => {
    api
      .getLeagueAlerts(leagueId)
      .then((result) => {
        hasData.current = true;
        setFailed(false);
        setData(result);
      })
      .catch(() => {
        // A failed background refresh keeps the feed already on screen.
        if (!hasData.current) setFailed(true);
      });
  }, [leagueId]);

  useEffect(() => {
    load();
    const onVisibility = () => {
      if (document.visibilityState === "visible") load();
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [load]);

  // `#alerts` opens the section and brings it into view (on load and when the hash changes on this page).
  useEffect(() => {
    const check = () => {
      if (window.location.hash !== `#${ALERTS_SECTION_HASH}`) return;
      setTargeted(true);
      ref.current?.scrollIntoView({ block: "start", behavior: "smooth" });
    };
    check();
    window.addEventListener("hashchange", check);
    return () => window.removeEventListener("hashchange", check);
  }, []);

  const notice = data?.reason ? alertsReasonMessage(data.reason) : null;
  const items = data && !notice ? overlayPendingAlertReads(userId, leagueId, data.items) : [];
  const unread = items.filter((item) => !item.read).length;
  // The collapsed row: avatars of the players behind the newest alerts / watch items, then the newest headline and how many more.
  const summary = todayAlertsSummary([
    ...items.map((item) => ({ playerId: item.matched_player_id, name: item.matched_player, position: item.matched_player_position, team: item.matched_player_team, tier: item.matched_player_tier, title: item.title ?? "" })),
    ...watchItems.map((item) => ({ playerId: item.route_player_id || null, name: item.route_player_name || null, position: item.route_player_position || null, team: item.route_player_team || null, tier: item.route_player_tier || null, title: item.headline })),
  ]);
  const total = items.length + watchItems.length;

  const title = (
    <span className="inline-flex items-center gap-2">
      Alerts
      {unread > 0 ? (
        <span
          data-testid="dashboard-alerts-count"
          className="inline-flex items-center justify-center font-bold"
          style={{
            minWidth: "1.125rem",
            height: "1.125rem",
            padding: "0 0.3rem",
            borderRadius: "var(--radius-pill)",
            background: "var(--color-accent)",
            color: "var(--color-on-accent)",
            fontSize: "0.6875rem",
          }}
        >
          {unread > 99 ? "99+" : unread}
        </span>
      ) : null}
    </span>
  );

  return (
    <div id={ALERTS_SECTION_HASH} ref={ref} style={{ scrollMarginTop: "calc(var(--shell-header-height, 3.5rem) + 0.5rem)" }}>
      <CompactModule
        // Not remembered: a section that opens itself on `#alerts` and otherwise starts collapsed should not fight a stored state.
        id="today.alerts"
        persist={false}
        key={targeted ? "targeted" : "idle"}
        defaultOpen={targeted}
        title={title}
        label="Alerts"
        testId="dashboard-alerts"
        tone={unread > 0 ? "warning" : "muted"}
        loading={!data && !failed}
        preview={
          summary.avatars.length > 0 ? (
            <span className="flex items-center gap-1" data-testid="dashboard-alerts-avatars">
              {summary.avatars.map((a) => (
                <PlayerAvatarSlot key={a.playerId} player={{ id: a.playerId, name: a.name ?? "this player", position: a.position, team: a.team, tier: a.tier }} tier="row" />
              ))}
            </span>
          ) : undefined
        }
        parts={
          data
            ? notice
              ? [{ key: "notice", text: notice }]
              : total > 0
                ? [
                    unread > 0 ? { key: "unread", text: `${unread} new`, strong: true } : null,
                    summary.lead ? { key: "lead", text: summary.lead } : null,
                    summary.more > 0 ? { key: "more", text: `+${summary.more} more`, tone: "muted" as const } : null,
                  ]
                : [{ key: "quiet", text: "All quiet" }]
            : []
        }
      >
        {failed ? (
          <ErrorState bare message="Could not load Alerts." onRetry={() => {
              setFailed(false);
              load();
            }} />
        ) : data ? (
          <>
            {watchItems.length > 0 ? <WatchListCard items={watchItems} leagueId={leagueId} leagueName={leagueName} /> : null}
            <AlertsFeed leagueId={leagueId} leagueName={leagueName} data={data} userId={userId} />
          </>
        ) : null}
      </CompactModule>
    </div>
  );
}
