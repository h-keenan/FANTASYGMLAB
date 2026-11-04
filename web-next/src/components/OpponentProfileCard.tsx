"use client";

import { ButtonLink } from "@/components/Button";
import { AccentCard } from "@/components/AccentCard";
import { PositionBadge } from "@/components/PositionBadge";
import { SectionHeading } from "@/components/SectionHeading";
import { ToneBadge } from "@/components/ToneBadge";
import { offerBuilderHref } from "@/lib/tradeOffer";
import {
  firstsFlowText,
  hasProfileContent,
  offerCaption,
  ordinal,
  picksText,
  rankText,
  type OpponentProfileResponse,
} from "@/lib/opponentProfile";

const LABEL_STYLE = { color: "var(--color-text-muted)", letterSpacing: "var(--letter-spacing-badge)" } as const;

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-xs uppercase font-extrabold" style={LABEL_STYLE}>
        {label}
      </span>
      {children}
    </div>
  );
}

/** Opponent profile card (League Rankings manager sheet): strongest/weakest
 * room, starter strength vs. bench depth, surplus and needs, pick capital,
 * team direction, and a trade angle with an "Offer this" button that opens the
 * Trade Analyzer prefilled through the same playerId quick-add the player
 * sheets use. Renders nothing for fields the server could not compute. */
export function OpponentProfileCard({
  profile,
  leagueId,
  leagueName,
}: {
  profile: OpponentProfileResponse | null;
  leagueId: string;
  leagueName: string;
}) {
  if (!hasProfileContent(profile) || !profile) return null;
  const { direction, rooms = [], strongest, weakest, starter_bench: depth, picks, trade_tendency: tendency, trade_angle: angle } = profile;
  const flow = picks ? firstsFlowText(picks) : null;
  const picksLine = picks ? picksText(picks) : "";

  return (
    <div className="flex flex-col gap-3" data-testid="opponent-profile">
      <SectionHeading>Roster profile</SectionHeading>
      <AccentCard accent="var(--color-accent)" compact as="div">
        <div className="flex flex-col gap-3">
        {direction?.label ? (
          <Row label="Direction">
            <div className="flex items-center gap-2 flex-wrap">
              <ToneBadge label={direction.label} color="var(--color-accent)" />
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                {[direction.rank && direction.league_size ? `${ordinal(direction.rank)} of ${direction.league_size} in power` : "", direction.record ? `Record ${direction.record}` : ""]
                  .filter(Boolean)
                  .join(" · ")}
              </span>
              {tendency ? (
                <ToneBadge label={`${tendency.label} in trades`} color="var(--color-premium)" />
              ) : null}
            </div>
          </Row>
        ) : null}
        {strongest || weakest ? (
          <Row label="Rooms">
            {strongest ? (
              <span className="text-sm font-semibold">Strongest: {rankText(strongest)}</span>
            ) : null}
            {weakest ? <span className="text-sm font-semibold">Weakest: {rankText(weakest)}</span> : null}
          </Row>
        ) : null}
        {rooms.length > 0 ? (
          <div className="flex flex-wrap gap-2" aria-label="League rank by position">
            {rooms.map((room) => (
              <span key={room.position} className="flex items-center gap-1.5 text-xs">
                <PositionBadge position={room.position} />
                <span className="font-bold">{ordinal(room.rank)}</span>
                {room.tag ? (
                  <ToneBadge
                    label={room.tag === "surplus" ? "Surplus" : "Need"}
                    color={room.tag === "surplus" ? "var(--color-success)" : "var(--color-danger)"}
                    size="xs"
                  />
                ) : null}
              </span>
            ))}
          </div>
        ) : null}
        {depth ? (
          <Row label="Starters vs. bench">
            <span className="text-sm font-semibold">
              {depth.label}: starters {ordinal(depth.starter_rank)}, bench {ordinal(depth.bench_rank)} of {depth.of}
            </span>
            <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
              {depth.note}
            </span>
          </Row>
        ) : null}
        {picks && (picksLine || flow) ? (
          <Row label="Future picks">
            {picksLine ? <span className="text-sm font-semibold">{picksLine}</span> : null}
            {flow ? (
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                {flow}
              </span>
            ) : null}
          </Row>
        ) : null}
        </div>
      </AccentCard>
      {angle ? (
        <AccentCard accent="var(--color-success)" compact as="div">
          <div className="flex flex-col gap-3">
          <Row label="Trade angle">
            <span className="text-sm font-semibold">{angle.text}</span>
          </Row>
          {angle.target ? (
            <>
              <div className="flex items-center gap-2 min-w-0">
                <PositionBadge position={angle.target.position} />
                <span className="text-sm font-bold break-words">{angle.target.name}</span>
                {angle.target.team ? (
                  <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                    {angle.target.team}
                  </span>
                ) : null}
              </div>
              <span className="text-xs" style={{ color: "var(--color-text-muted)" }}>
                {offerCaption(angle.target)}
              </span>
              <ButtonLink href={offerBuilderHref(leagueId, leagueName, angle.target.player_id)} variant="primary" size="sm">
                Offer this
              </ButtonLink>
            </>
          ) : null}
          </div>
        </AccentCard>
      ) : null}
    </div>
  );
}
