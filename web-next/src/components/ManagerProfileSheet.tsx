"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { api, type ManagerTendenciesDetailResponse } from "@/lib/api";
import { TENDENCY_SIGNALS } from "@/lib/managerTendencies";
import { SheetHandle } from "@/components/SheetHandle";

/** Manager profile sheet (League Rankings): every readable signal with its
 * evidence line. Loaded only when opened. Reuses the quick-view sheet shell. */
export function ManagerProfileSheet({
  leagueId,
  rosterId,
  teamName,
  onClose,
}: {
  leagueId: string;
  rosterId: string | number;
  teamName: string;
  onClose: () => void;
}) {
  const [data, setData] = useState<ManagerTendenciesDetailResponse | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    api
      .getManagerTendencyDetail(leagueId, rosterId)
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch(() => {
        if (!cancelled) setFailed(true);
      });
    return () => {
      cancelled = true;
    };
  }, [leagueId, rosterId]);

  useEffect(() => {
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [onClose]);

  const signals = data?.manager?.signals ?? {};
  const rows = TENDENCY_SIGNALS.filter(([key]) => signals[key]?.status === "ok");

  return (
    <div
      className="pqv-backdrop"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div className="pqv-modal" role="dialog" aria-modal="true" aria-labelledby="mgr-profile-name">
        <SheetHandle />
        <button type="button" className="pqv-close" aria-label="Close manager profile" onClick={onClose}>
          ×
        </button>
        <div className="pqv-scroll">
          <div className="flex flex-col gap-0.5 pr-10">
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              How this manager trades
            </span>
            <h2 id="mgr-profile-name" className="text-lg font-extrabold">
              {teamName}
            </h2>
          </div>
          {failed ? (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              Couldn&apos;t load this profile.
            </p>
          ) : !data ? (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              Loading…
            </p>
          ) : !data.is_premium ? (
            <div className="flex flex-col gap-2">
              <p className="text-sm font-bold">{data.upsell?.title ?? "Manager Tendencies"}</p>
              <Link href="/premium" className="text-sm font-bold self-start" style={{ color: "var(--color-premium)" }}>
                Upgrade →
              </Link>
            </div>
          ) : rows.length === 0 ? (
            <p className="text-sm" style={{ color: "var(--color-text-muted)" }}>
              Not enough trade history yet.
            </p>
          ) : (
            <ul className="flex flex-col gap-3">
              {rows.map(([key, title]) => (
                <li key={key} className="flex flex-col gap-0.5">
                  <span
                    className="text-xs uppercase font-bold"
                    style={{ color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" }}
                  >
                    {title}
                  </span>
                  <span className="text-sm">{signals[key].summary}</span>
                  <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                    {signals[key].sample_size} trade{signals[key].sample_size === 1 ? "" : "s"} analyzed
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
