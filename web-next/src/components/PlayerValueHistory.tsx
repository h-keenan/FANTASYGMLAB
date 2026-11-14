"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";

import { SkeletonBlock } from "@/components/Skeleton";
import { api, type RatingHistoryResponse } from "@/lib/api";
import { formatRatingDelta, ratingHistoryCaption } from "@/lib/valueHistoryPresentation";

const RatingHistoryChart = dynamic(() => import("@/components/RatingHistoryChart").then((m) => m.RatingHistoryChart), {
  ssr: false,
  loading: () => <SkeletonBlock height={140} />,
});

/**
 * "Value history" on Player Quick View and the full profile: the player's 0-99
 * overall rating across the real stored daily snapshots (GET
 * .../rating-history). Only stored days are drawn; a short history says how
 * short it is. Renders nothing while loading fails or storage is unavailable.
 * Mirrors mobile's PlayerValueHistory. `bare` drops the section and its
 * heading, for use inside the tap-the-value popover (TapForWhy chart slot),
 * which already has its own title.
 */
export function PlayerValueHistory({ playerId, bare = false }: { playerId: string; bare?: boolean }) {
  const [history, setHistory] = useState<RatingHistoryResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getPlayerRatingHistory(playerId)
      .then((result) => {
        if (!cancelled) setHistory(result);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [playerId]);

  const caption = ratingHistoryCaption(history);
  if (!history || !caption) return null;
  return (
    <section className={bare ? "flex flex-col gap-2" : "pqv-model-row"} aria-label="Value history" data-testid="player-value-history">
      {bare ? null : <h3>Value history</h3>}
      {caption.chart ? <RatingHistoryChart points={history.points} /> : null}
      {caption.changes.length ? (
        <p className="text-sm font-bold" style={{ color: "var(--color-text-primary)" }}>
          {caption.changes.map((text, i) => (
            <span key={text}>
              {i ? " · " : ""}
              {text}
            </span>
          ))}
        </p>
      ) : null}
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {caption.text}
        {history.current_rating != null ? ` Latest rating ${history.current_rating}.` : ""}
        {!caption.changes.length && caption.chart && history.change
          ? ` ${formatRatingDelta(history.change.delta)} since the first snapshot.`
          : ""}
      </p>
    </section>
  );
}
