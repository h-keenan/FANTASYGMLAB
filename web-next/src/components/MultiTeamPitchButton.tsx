"use client";

import { useMemo, useState } from "react";

import { Button } from "@/components/Button";
import { trackUse } from "@/lib/analytics";
import { buildShareModel, buildShareText, type MultiTeamTradeResponse } from "@/lib/multiTeamTrade";
import { isPrivacyMode } from "@/lib/privacy";
import { shareCardCacheKey } from "@/lib/shareCard/cacheKey";
import { isCompletedShare } from "@/lib/shareImage";
import { useShareImage } from "@/lib/useShareImage";

/**
 * The pitch-style share for a multi-team deal (a persuasion framed picture, see
 * lib/shareCard/multiTradeCard.tsx): one button that renders the card and opens
 * the share sheet. Used by the Analyzer's results and by each 3-team idea in
 * Trade Hub, so both share exactly the same card.
 */
export function PitchShareButton({
  response,
  leagueId,
  leagueName,
  label = "Share the pitch",
  itemKind = "multi_team",
}: {
  response: Pick<MultiTeamTradeResponse, "teams" | "flows">;
  leagueId: string;
  leagueName: string;
  label?: string;
  /** Analytics item kind for the completed share. */
  itemKind?: string;
}) {
  const model = useMemo(() => buildShareModel(response), [response]);
  const text = useMemo(() => buildShareText(model, leagueName), [model, leagueName]);
  const [copied, setCopied] = useState(false);
  const share = useShareImage({
    cacheKey: shareCardCacheKey({ multi: model, leagueName, privacy: isPrivacyMode() }),
    build: async () => {
      const { renderMultiTradeCardBlob } = await import("@/lib/shareCard/clientRender");
      return renderMultiTradeCardBlob(model, leagueName);
    },
    filename: "fantasydesk-multi-team-trade.png",
    text,
    title: `${model.teams.length}-team trade`,
    itemKind: "multi_team_trade",
    leagueId,
    onOutcome: (outcome) => {
      if (isCompletedShare(outcome)) trackUse("trade_analyzer", "shared", { leagueId, props: { item_kind: itemKind } });
      if (outcome === "copied" || outcome === "copied-image" || outcome === "saved-image") {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      }
    },
  });
  return (
    <div className="flex items-center gap-2">
      <Button size="sm" onClick={share.onClick} disabled={share.busy}>
        {copied ? "Copied!" : share.label(label)}
      </Button>
      {share.status ? (
        <span role="status" className="text-xs" style={{ color: "var(--color-text-muted)" }}>
          {share.status}
        </span>
      ) : null}
    </div>
  );
}
