"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { AlertsFeed } from "@/components/AlertsContent";
import { ButtonLink } from "@/components/Button";
import { ExpandRow, ExpandRowGroup } from "@/components/ui/ExpandRow";
import { SectionHeading } from "@/components/SectionHeading";
import { ErrorState } from "@/components/ErrorState";
import { PlayerAvatarSlot } from "@/components/ui/PlayerAvatarSlot";
import { WatchListCard } from "@/components/WatchListCard";
import { useAuth } from "@/context/AuthContext";
import { api, type AlertsResponse, type BriefingItem } from "@/lib/api";
import { markAlertReadSynced } from "@/lib/alertReadSync";
import { todayAlertRows } from "@/lib/todayView";
import { overlayPendingAlertReads } from "@/lib/alertReadSync";
import { alertsReasonMessage } from "@/lib/alertsPresentation";

/** The URL fragment that targets this section (`/dashboard/<id>#alerts`; the retired /alerts route and the header bell link here). */
export const ALERTS_SECTION_HASH = "alerts";

/**
 * The Alerts section of Today: news about YOUR rostered players only, as action rows (avatar, one line, ONE button: Swap /
 * Lineup for a starter, Read for a bench player). League-wide headlines never appear here. "All alerts" opens the full
 * roster-news feed (and the watchlist); `#alerts` (the retired Alerts route, the header bell) opens it and scrolls here.
 * Re-reads the feed when the tab becomes visible again, so a read made on the phone shows here. Mobile twin:
 * components/AlertsSection.tsx.
 */
export function DashboardAlerts({ leagueId, leagueName, watchItems = [] }: { leagueId: string; leagueName: string; /** The Dashboard's watchlist items: folded into this section (one place for "things to keep an eye on"). */ watchItems?: BriefingItem[] }) {
  const { session } = useAuth();
  const userId = session?.user?.id ?? "";
  const [data, setData] = useState<AlertsResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [showAll, setShowAll] = useState(false);
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
      setShowAll(true);
      ref.current?.scrollIntoView({ block: "start", behavior: "smooth" });
    };
    check();
    window.addEventListener("hashchange", check);
    return () => window.removeEventListener("hashchange", check);
  }, []);

  const notice = data?.reason ? alertsReasonMessage(data.reason) : null;
  const items = data && !notice ? overlayPendingAlertReads(userId, leagueId, data.items) : [];
  // Only news tied to a player on this roster; the rest of the feed is not Today's business.
  const rostered = items.filter((item) => item.matched_player_id && item.roster_relationship);
  const unread = rostered.filter((item) => !item.read).length;
  const { rows, total } = todayAlertRows(rostered);
  const feed = data ? { ...data, items: rostered } : null;
  const hasMore = total > rows.length || watchItems.length > 0;
  const planHref = `/matchup/${encodeURIComponent(leagueId)}?${new URLSearchParams({ name: leagueName, plan: "all" }).toString()}`;
  const read = (key: string) => void markAlertReadSynced(userId, leagueId, key);

  if (failed) {
    return (
      <div id={ALERTS_SECTION_HASH} ref={ref}>
        <ErrorState bare message="Could not load Alerts." onRetry={() => { setFailed(false); load(); }} />
      </div>
    );
  }
  if (!data || notice || (rows.length === 0 && !hasMore)) return <div id={ALERTS_SECTION_HASH} ref={ref} />;

  const title = (
    <span className="inline-flex items-center gap-2">
      Alerts
      {unread > 0 ? (
        <span
          data-testid="dashboard-alerts-count"
          className="inline-flex items-center justify-center font-bold"
          style={{ minWidth: "1.125rem", height: "1.125rem", padding: "0 0.3rem", borderRadius: "var(--radius-pill)", background: "var(--color-accent)", color: "var(--color-on-accent)", fontSize: "0.6875rem" }}
        >
          {unread > 99 ? "99+" : unread}
        </span>
      ) : null}
    </span>
  );

  return (
    <div id={ALERTS_SECTION_HASH} ref={ref} className="flex flex-col gap-2" style={{ scrollMarginTop: "calc(var(--shell-header-height, 3.5rem) + 0.5rem)" }} data-testid="dashboard-alerts">
      <SectionHeading id="today-alerts-heading">{title}</SectionHeading>
      {rows.length > 0 ? (
        <ExpandRowGroup accent={rows.some((r) => r.tone === "danger") ? "var(--color-danger)" : "var(--color-accent)"} testId="alert-rows">
          {rows.map((r) => (
            <ExpandRow
              key={r.key}
              testId="alert-row"
              label={`${r.player.name}: ${r.reason}`}
              leading={<PlayerAvatarSlot player={{ id: r.player.id, name: r.player.name, position: r.player.position, team: r.player.team, tier: r.player.tier }} tier="row" nonInteractive="the row is the tap target" />}
              title={<span className="line-clamp-2">{r.reason}</span>}
              caption={r.unread ? "New" : undefined}
              action={
                r.target === "matchup" ? (
                  <ButtonLink href={planHref} variant="primary" size="sm" aria-label={`${r.button}: ${r.reason}`} onClick={() => read(r.alertKey)} data-testid="alert-primary">
                    {r.button}
                  </ButtonLink>
                ) : (
                  <ButtonLink href={r.link ?? "#"} variant="primary" size="sm" target="_blank" rel="noopener noreferrer" aria-label={`${r.button}: ${r.reason}`} onClick={() => read(r.alertKey)} data-testid="alert-primary">
                    {r.button}
                  </ButtonLink>
                )
              }
            />
          ))}
        </ExpandRowGroup>
      ) : null}
      {hasMore ? (
        <button type="button" onClick={() => setShowAll((v) => !v)} aria-expanded={showAll} className="tap-link self-start text-sm font-bold" style={{ minHeight: "var(--touch-target-min)", color: "var(--color-accent)" }} data-testid="alerts-see-all">
          {showAll ? "Hide alerts" : `All alerts (${total + watchItems.length})`}
        </button>
      ) : null}
      {showAll && feed ? (
        <>
          {watchItems.length > 0 ? <WatchListCard items={watchItems} leagueId={leagueId} leagueName={leagueName} /> : null}
          <AlertsFeed leagueId={leagueId} leagueName={leagueName} data={feed} userId={userId} />
        </>
      ) : null}
    </div>
  );
}
