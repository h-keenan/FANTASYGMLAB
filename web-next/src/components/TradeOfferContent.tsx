"use client";

import { useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";

import { AccentCard } from "@/components/AccentCard";
import { ButtonLink } from "@/components/Button";
import { EmptyState } from "@/components/EmptyState";
import { LoadingScreen } from "@/components/LoadingScreen";
import { PageTitle } from "@/components/PageTitle";
import { PremiumUpsellCard } from "@/components/PremiumUpsellCard";
import { ExchangeSide } from "@/components/TradeAssetExchange";
import { ToneBadge } from "@/components/ToneBadge";
import { api, type TradeTargetOffer, type TradeTargetResponse } from "@/lib/api";
import { trackFeatureUse } from "@/lib/analytics";
import { offerAnalyzerHref } from "@/lib/tradeOffer";

const ACCEPT_COLOR: Record<TradeTargetOffer["acceptance"]["label"], string> = {
  Likely: "var(--color-success)",
  Possible: "var(--color-warning)",
  "Long shot": "var(--color-danger)",
};

function formatValue(n: number): string {
  return Math.round(n).toLocaleString("en-US");
}

/**
 * "Build an offer": the user picked a player on ANOTHER team and the engine
 * (GET .../trade-target, modules/trade_target_offers.py) built 2-3 packages:
 * what to send, what the other side should add back, how likely they are to
 * say yes and why. Each card opens in the Trade Analyzer to tweak and share.
 * Pro, gated the same way as Trade Finder. Mobile twin: TradeOfferScreen.tsx.
 */
export function TradeOfferContent({
  leagueId,
  leagueName,
  playerId,
  lens,
}: {
  leagueId: string;
  leagueName: string;
  playerId: string;
  lens: string;
}) {
  const router = useRouter();
  const [result, setResult] = useState<TradeTargetResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    setResult(null);
    setError(null);
    if (!playerId) {
      setError("Pick a player on another team to build an offer for.");
      return;
    }
    trackFeatureUse("trade_offer_built", { leagueId, dedupe: false });
    api
      // "auto": the server resolves your team posture (Team Situation first).
      .getTradeTargetOffers(leagueId, playerId, "auto", lens)
      .then(setResult)
      .catch((err) => setError(err instanceof Error ? err.message : "Could not build an offer."));
  }, [leagueId, playerId, lens]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- fetch on mount / when the target changes
    load();
  }, [load]);

  if (error) {
    return (
      <main className="flex-1 flex flex-col gap-4 px-4 py-8 max-w-3xl w-full mx-auto">
        <EmptyState title="Could not build an offer." subtitle={error} actionLabel="Try again" onAction={load} />
      </main>
    );
  }
  if (!result) return <LoadingScreen status="Building your offers…" />;

  if (result.status === "locked") {
    return (
      <PremiumUpsellCard
        kicker="Build an offer"
        leagueName={leagueName}
        upsell={result.upsell}
        fallbackTitle="Build an offer for any player"
        fallbackBody="Pick a player on another team and Pro builds the offer for you. Upgrade to Pro to unlock it."
      />
    );
  }

  const target = result.target;
  return (
    <main className="flex-1 flex flex-col gap-6 px-4 py-8 max-w-3xl w-full mx-auto">
      <header className="flex flex-col gap-1">
        <PageTitle page="Build an Offer" leagueName={leagueName} />
        {result.offers.length > 0 ? (
          <p className="text-sm" style={{ color: "var(--color-text-muted)" }} data-testid="offer-headline">
            {result.headline || (target ? `Offers for ${target.label}` : "")}
          </p>
        ) : null}
      </header>

      {result.status === "error" ? (
        <EmptyState title="The search hit a problem." subtitle={result.headline} actionLabel="Try again" onAction={load} />
      ) : result.offers.length === 0 ? (
        <EmptyState
          title="No offer to show"
          subtitle={result.headline}
          actionLabel={result.status === "not_rostered" ? "Go to Waivers" : undefined}
          onAction={
            result.status === "not_rostered"
              ? () => router.push(`/waivers/${encodeURIComponent(leagueId)}?name=${encodeURIComponent(leagueName)}`)
              : undefined
          }
        />
      ) : (
        <div className="flex flex-col gap-4">
          {result.offers.map((offer) => (
            <OfferCard key={offer.rank} offer={offer} leagueId={leagueId} leagueName={leagueName} />
          ))}
        </div>
      )}
    </main>
  );
}

export function OfferCard({ offer, leagueId, leagueName }: { offer: TradeTargetOffer; leagueId: string; leagueName: string }) {
  return (
    <AccentCard accent="var(--color-accent)" data-testid="offer-card">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-bold">
          Offer {offer.rank}: {offer.title}
        </span>
        <ToneBadge
          label={`${offer.acceptance.label} to accept`}
          color={ACCEPT_COLOR[offer.acceptance.label]}
          title={offer.acceptance.reason}
        />
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)] gap-3 items-start">
        <ExchangeSide
          label="You send"
          dotColor="var(--color-danger)"
          assets={offer.package.send}
          total={{ text: formatValue(offer.send_value), color: "var(--color-text-secondary)" }}
        />
        <ExchangeSide
          label="You get"
          dotColor="var(--color-success)"
          assets={offer.package.receive}
          total={{ text: formatValue(offer.receive_value), color: "var(--color-text-secondary)" }}
        />
      </div>
      <ul className="flex flex-col gap-1 list-disc pl-5 text-sm" style={{ color: "var(--color-text-secondary)" }}>
        {offer.why.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      <p className="text-xs" style={{ color: "var(--color-text-muted)" }}>
        {offer.acceptance.reason}
      </p>
      <ButtonLink
        href={offerAnalyzerHref(leagueId, leagueName, offer)}
        variant="primary"
        fullWidth
        onClick={() => trackFeatureUse("trade_offer_opened_in_analyzer", { leagueId, dedupe: false })}
      >
        Open in Trade Analyzer
      </ButtonLink>
    </AccentCard>
  );
}
