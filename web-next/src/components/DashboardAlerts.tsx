"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AlertsFeed } from "@/components/AlertsContent";
import { CompactModule } from "@/components/ui/CompactModule";
import { ErrorState } from "@/components/ErrorState";
import { useAuth } from "@/context/AuthContext";
import { api, type AlertsResponse } from "@/lib/api";
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
export function DashboardAlerts({ leagueId, leagueName }: { leagueId: string; leagueName: string }) {
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
        parts={
          data
            ? notice
              ? [{ key: "notice", text: notice }]
              : unread > 0
                ? [{ key: "unread", text: `${unread} unread`, strong: true }, items[0]?.title ? { key: "lead", text: items[0].title } : null]
                : [{ key: "quiet", text: items.length > 0 ? "All caught up" : "All quiet" }]
            : []
        }
      >
        {failed ? (
          <ErrorState bare message="Could not load Alerts." onRetry={() => {
              setFailed(false);
              load();
            }} />
        ) : data ? (
          <AlertsFeed leagueId={leagueId} leagueName={leagueName} data={data} userId={userId} />
        ) : null}
      </CompactModule>
    </div>
  );
}
