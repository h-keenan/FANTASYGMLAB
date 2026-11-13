"use client";

import { useMemo } from "react";

import { Button } from "@/components/Button";
import { shareCardCacheKey } from "@/lib/shareCard/cacheKey";
import { reviewShareLines, type ReviewSection, type ReviewShareModel } from "@/lib/simReview";
import { useShareImage } from "@/lib/useShareImage";

/** Share the Season in Review card (rendered in the browser ahead of the tap, see useShareImage). */
export function SimReviewShareButton({ model, sections, gameId }: { model: ReviewShareModel; sections: readonly ReviewSection[]; gameId: string }) {
  const text = useMemo(
    () => [`${[model.headline, model.record].filter(Boolean).join(", ")}. Grade ${model.letter}.`, ...reviewShareLines(sections), "Play Fantasy Sim on FantasyDesk."].join("\n"),
    [model, sections],
  );
  const share = useShareImage({
    cacheKey: shareCardCacheKey({ review: model }),
    build: async () => {
      const { renderSeasonReviewCardBlob } = await import("@/lib/shareCard/clientRender");
      return renderSeasonReviewCardBlob(model);
    },
    filename: "fantasydesk-season-in-review.png",
    text,
    title: "Season in Review",
    itemKind: "sim_season_review",
    leagueId: gameId,
  });
  return (
    <div className="flex items-center gap-2">
      <Button variant="secondary" onClick={share.onClick} disabled={share.busy}>{share.label("Share your season")}</Button>
      {share.status ? <span role="status" className="text-xs" style={{ color: "var(--color-text-muted)" }}>{share.status}</span> : null}
    </div>
  );
}
