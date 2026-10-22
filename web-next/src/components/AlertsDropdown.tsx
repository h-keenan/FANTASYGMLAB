"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { AlertRow } from "@/components/AlertsContent";
import { EmptyState } from "@/components/EmptyState";
import { SheetHandle } from "@/components/SheetHandle";
import { useAuth } from "@/context/AuthContext";
import { markAlertReadSynced, overlayPendingAlertReads, reconcileAlertReads } from "@/lib/alertReadSync";
import { alertsReasonMessage } from "@/lib/alertsPresentation";
import { api, type AlertItem, type AlertsResponse } from "@/lib/api";
import { useSheetDragDismiss } from "@/lib/useSheetDragDismiss";

/**
 * The header bell. Tapping it opens a dropdown over the current page (a top
 * sheet on phones) instead of navigating. Nothing is fetched until it is
 * first opened; the unread badge appears once the feed has been loaded.
 * Mount it with key={leagueId} so each league gets its own feed. Read state is the durable cross-device sync (lib/alertReadSync.ts):
 * tapping a row marks it read, and closing the dropdown marks everything it
 * showed as read.
 */
export function AlertsBell({
  leagueId,
  alertsHref,
  iconProps,
  buttonStyle,
}: {
  leagueId: string;
  alertsHref: string;
  iconProps: React.SVGProps<SVGSVGElement>;
  buttonStyle?: React.CSSProperties;
}) {
  const { session } = useAuth();
  const userId = session?.user?.id ?? "";
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<AlertsResponse | null>(null);
  const [failed, setFailed] = useState(false);
  const [tapped, setTapped] = useState<ReadonlySet<string>>(() => new Set());
  const dataRef = useRef<AlertsResponse | null>(null);

  const items: AlertItem[] = useMemo(
    () =>
      data
        ? overlayPendingAlertReads(userId, leagueId, data.items).map((row) =>
            !row.read && tapped.has(row.alert_key) ? { ...row, read: true } : row,
          )
        : [],
    [data, tapped, userId, leagueId],
  );
  const unread = items.filter((item) => !item.read).length;

  const load = useCallback(() => {
    setFailed(false);
    api
      .getLeagueAlerts(leagueId)
      .then((result) => {
        dataRef.current = result;
        setData(result);
        reconcileAlertReads(userId, leagueId, result.items);
      })
      .catch(() => {
        if (!dataRef.current) setFailed(true);
      });
  }, [leagueId, userId]);

  const markRead = useCallback(
    (alert: AlertItem) => {
      if (alert.read) return;
      setTapped((prev) => new Set(prev).add(alert.alert_key));
      void markAlertReadSynced(userId, leagueId, alert.alert_key);
    },
    [userId, leagueId],
  );

  const close = useCallback(() => {
    // Viewing counts as reading: everything the dropdown showed is synced read.
    const shown = dataRef.current?.items ?? [];
    for (const row of overlayPendingAlertReads(userId, leagueId, shown)) {
      if (!row.read) markRead(row);
    }
    setOpen(false);
  }, [userId, leagueId, markRead]);

  const toggle = () => {
    if (open) {
      close();
      return;
    }
    setOpen(true);
    load();
  };

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") close();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, close]);

  const { sheetRef, sheetStyle } = useSheetDragDismiss<HTMLDivElement>({ onDismiss: close, enabled: open });
  const notice = data?.reason ? alertsReasonMessage(data.reason) : null;

  return (
    <>
      <button
        type="button"
        aria-label={unread > 0 ? `Alerts, ${unread} unread` : "Alerts"}
        aria-haspopup="dialog"
        aria-expanded={open}
        onClick={toggle}
        className="relative inline-flex items-center justify-center"
        style={buttonStyle}
      >
        <svg {...iconProps}>
          <path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9" />
          <path d="M10.3 21a1.94 1.94 0 0 0 3.4 0" />
        </svg>
        {unread > 0 ? (
          <span
            data-testid="alerts-unread-badge"
            aria-hidden="true"
            className="absolute flex items-center justify-center font-bold"
            style={{
              top: "0.1rem",
              right: "0.1rem",
              minWidth: "0.95rem",
              height: "0.95rem",
              padding: "0 0.2rem",
              borderRadius: "999px",
              background: "var(--color-accent)",
              color: "#fff",
              fontSize: "0.625rem",
            }}
          >
            {unread > 9 ? "9+" : unread}
          </span>
        ) : null}
      </button>
      {open ? (
        <div className="fixed inset-0" style={{ zIndex: 50 }}>
          <div
            data-testid="alerts-backdrop"
            className="absolute inset-0"
            style={{ background: "var(--scrim, rgba(0,0,0,0.5))" }}
            onClick={close}
          />
          <div
            ref={sheetRef}
            role="dialog"
            aria-label="Alerts"
            className="glass-surface absolute flex flex-col left-2 right-2 md:left-auto md:right-4 md:w-96"
            style={{ top: "3.5rem", maxHeight: "70vh", ...sheetStyle }}
          >
            <div className="flex items-center justify-between gap-2 px-4 pt-3 pb-2">
              <h2 style={{ font: "var(--font-card-title)", color: "var(--color-text-primary)" }}>Alerts</h2>
              <button
                type="button"
                aria-label="Close alerts"
                onClick={close}
                className="text-sm"
                style={{ color: "var(--color-text-muted)" }}
              >
                ✕
              </button>
            </div>
            <div className="flex-1 overflow-y-auto px-4" style={{ minHeight: 0 }}>
              {!data && !failed ? (
                <p className="text-sm py-4" style={{ color: "var(--color-text-muted)" }}>
                  Loading…
                </p>
              ) : failed ? (
                <p className="text-sm py-4" style={{ color: "var(--color-danger)" }}>
                  Could not load Alerts.
                </p>
              ) : notice ? (
                <p className="text-sm py-4" style={{ color: "var(--color-text-muted)" }}>
                  {notice}
                </p>
              ) : items.length === 0 ? (
                <div className="py-3">
                  <EmptyState title="All quiet" subtitle="No relevant news for your roster right now." />
                </div>
              ) : (
                items.map((alert) => <AlertRow key={alert.alert_key} alert={alert} onOpen={markRead} />)
              )}
            </div>
            <div className="px-4 py-3" style={{ borderTop: "var(--border-width-default) solid var(--color-border)" }}>
              <Link href={alertsHref} onClick={close} className="text-sm font-bold" style={{ color: "var(--color-accent)" }}>
                View all alerts →
              </Link>
            </div>
            <SheetHandle />
          </div>
        </div>
      ) : null}
    </>
  );
}
